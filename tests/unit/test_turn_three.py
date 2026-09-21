"""The three-turn operator rehearsal must compute, verify and publish every turn."""

import json
from datetime import date

import pytest
from test_co_movement import TOTAL_ID, arguments
from test_co_movement import lake as lake
from test_evds_load import FakeSource
from test_turn_two import CPI_ID, cpi_values, transform

from kkb_agent import live_check
from kkb_agent.ingest.evds_load import ingest_series
from kkb_agent.ingest.evds_request import EvdsWindow
from kkb_agent.llm import scripted


@pytest.fixture(autouse=True)
def _legacy_writer_rehearsals(monkeypatch):
    """Keep these scripted negative/repair rehearsals on the writer fallback."""
    monkeypatch.setattr("kkb_agent.agent.loop.deterministic_draft", lambda result: None)


def proposal(question, steps):
    return json.dumps({"question": question, "steps": steps})


def step(tool, arguments, step_id="step", depends_on=()):
    return {
        "tool": tool,
        "arguments": arguments,
        "step_id": step_id,
        "depends_on": list(depends_on),
    }


def prepared(lake):
    for code, source in [
        ("TP.TUKFIY2025.GENEL", FakeSource(mutate=cpi_values)),
        ("TP.KFE.TR", FakeSource()),
    ]:
        ingest_series(
            lake, code, EvdsWindow(start=date(2021, 1, 1), end=date(2021, 6, 30)), retrieve=source
        )
    lake.connection.close()


def first_two(second_draft="Tablo hazırlandı."):
    return [
        proposal(
            live_check.TURN_ONE_QUESTION,
            [step("change_detection", arguments().model_dump(mode="json"))],
        ),
        "Tablo hazırlandı.",
        proposal(
            live_check.TURN_TWO_QUESTION,
            [step("table_transform", transform().model_dump(mode="json"))],
        ),
        second_draft,
    ]


@pytest.mark.parametrize(
    "case", ["complete", "inherited_condition", "only_added", "nominal", "wrong_direction"]
)
def test_three_turn_acceptance_requires_requested_real_comparison(lake, tmp_path, case):
    """A plan naming the nominal column still produces the required real comparison.

    The tool resolves a column to its deflated counterpart when the table carries
    one, so `nominal` and `complete` reach the same published comparison. What
    still fails acceptance is adding the column without comparing it, or comparing
    it in the wrong direction.
    """
    requested_real = case in {"complete", "inherited_condition", "nominal"}
    prepared(lake)
    third = [
        step(
            "table_transform",
            {
                "operation": "add_series",
                "source": live_check.TURN_TWO_NAME,
                "series_id": "EVDS:TP.KFE.TR",
            },
            "add",
        )
    ]
    if case != "only_added":
        comparison = {
            "operation": "table_co_movement",
            "input_step": "add",
            "driver_column": "EVDS:TP.KFE.TR",
            "target_column": TOTAL_ID
            if case == "nominal"
            else f"{TOTAL_ID} real, 2021-06 prices ({CPI_ID})",
            "driver_direction": "up",
            "target_direction": "up" if case == "wrong_direction" else "non_increasing",
        }
        if case != "inherited_condition":
            comparison.update(
                when_column="EVDS:TP.KTF12 monthly average (by_end)", when_direction="down"
            )
        third.append(step("change_detection", comparison, "compare", ("add",)))
    provider = scripted(
        *first_two(), proposal(live_check.TURN_THREE_QUESTION, third), "Tablo hazırlandı."
    )
    report = live_check.run_prepared_check(provider, lake.root, tmp_path / "work", turns=3)
    assert report["passed"] is requested_real, json.dumps(report, ensure_ascii=False)
    assert len(report["turns"]) == 3
    final = report["turns"][-1]
    assert final["relationship_checked"] is requested_real
    assert final["published"] == [
        live_check.TURN_ONE_NAME,
        live_check.TURN_TWO_NAME,
        live_check.TURN_THREE_NAME,
    ]
    if requested_real:
        assert list(final["result"]["counts"].values())[-6:] == [5, 0, 4, 4, 4, 4]
        if case == "inherited_condition":
            assert final["result"]["transformations"][-1] == "table_co_movement"
        assert final["tables"][0]["rows"] == 6
        assert final["result"]["transformations"] == [
            "align_weekly_to_monthly",
            "deflate",
            "add_series",
            "table_co_movement",
        ]


def test_an_invented_figure_is_withheld_and_the_verified_table_is_still_published(lake, tmp_path):
    # The table is what the tools computed. A sentence the gate withheld used to cost the
    # turn its table, and with it everything the next question builds on.
    prepared(lake)
    provider = scripted(*first_two("Tablo hazırlandı. Kredi bakiyesi 987654321 milyon TL oldu."))
    report = live_check.run_prepared_check(provider, lake.root, tmp_path / "work", turns=2)
    final = report["turns"][-1]
    assert final["answer"]["status"] == "qualified"
    assert "987654321" not in final["answer"]["text"]
    assert final["passed"] is True  # the reader has verified prose and the verified table


def comparison(step_id, target, when=None, direction="non_increasing"):
    arguments = {
        "operation": "table_co_movement",
        "input_step": "add",
        "driver_column": "EVDS:TP.KTF12 monthly average (by_end)",
        "target_column": target,
        "driver_direction": "down",
        "target_direction": direction,
    }
    if when is not None:
        arguments.update(when_column=when[0], when_direction=when[1])
    return step("change_detection", arguments, step_id, ("add",))


ADD_KFE = step(
    "table_transform",
    {"operation": "add_series", "source": live_check.TURN_TWO_NAME, "series_id": "EVDS:TP.KFE.TR"},
    "add",
)
REAL = f"{TOTAL_ID} real, 2021-06 prices ({CPI_ID})"


def test_live_parallel_comparisons_both_reach_the_writer_without_a_second_plan(lake, tmp_path):
    """M11-07 live Turn 3: two unconsumed comparisons published only the last one and the
    first was dropped unseen. The plan was then refused for it, at the price of another
    planner call; now it runs, the last result is the table, and the writer is shown both."""
    prepared(lake)
    parallel = [
        ADD_KFE,
        comparison("kfe", "EVDS:TP.KFE.TR", when=(REAL, "non_increasing"), direction="up"),
        comparison("real", REAL),
    ]
    provider = scripted(
        *first_two(),
        proposal(live_check.TURN_THREE_QUESTION, parallel),
        "Tablo hazırlandı.",
    )
    report = live_check.run_prepared_check(provider, lake.root, tmp_path / "work", turns=3)
    final = report["turns"][-1]
    assert final["published"][-1] == live_check.TURN_THREE_NAME
    assert final["result"]["transformations"][-1] == "table_co_movement"
    planner_messages = " ".join(m.content for m in provider.seen[-2])
    assert "rejected" not in planner_messages
    writer_context = " ".join(m.content for m in provider.seen[-1])
    assert "condition column " + REAL + " direction non_increasing" in writer_context
    assert f"{live_check.TURN_THREE_NAME}_ek_" in writer_context


def test_live_absence_prose_cannot_pass_turn_three(lake, tmp_path, monkeypatch):
    # The optional wording contract; the served gate binds figures and leaves wording be.
    monkeypatch.setattr("kkb_agent.agent.verifier.WORDING_RULES", True)
    prepared(lake)
    third = [ADD_KFE, comparison("compare", REAL, when=("EVDS:TP.KFE.TR", "up"))]
    provider = scripted(
        *first_two(),
        proposal(live_check.TURN_THREE_QUESTION, third),
        "Konut fiyat endeksi sütunu için sonuçlarda değer bulunmuyor. Bu durumda birlikte "
        "hareket hesaplanamıyor.",
    )
    report = live_check.run_prepared_check(provider, lake.root, tmp_path / "work", turns=3)
    final = report["turns"][-1]
    assert report["passed"] is False and final["passed"] is False
    assert final["answer"]["status"] != "accepted"
    assert live_check.TURN_THREE_NAME not in final["published"]


def real_may_draft(reference):
    from test_turn_two import REAL

    from kkb_agent.agent.presentation import display_value
    from kkb_agent.core import ResultValue, Scale

    shown = display_value(ResultValue(label="real", value=REAL[4], unit="TRY", scale=Scale.MILLION))
    return (
        "Tablo korunarak bakiye enflasyondan arındırıldı. 2021-05 döneminde enflasyondan "
        f"arındırılmış bakiye {reference} fiyatlarıyla {shown}."
    )


@pytest.mark.parametrize(
    ("reference", "accepted"),
    [("2021-06", True), ("Haziran 2021", True)],
)
def test_recorded_price_reference_in_a_figure_sentence(lake, tmp_path, reference, accepted):
    """End to end, the recorded reference month may be written beside a real figure.

    The fixture's value and reference share 2021, so the cross-year live failure
    (2023-12 value, 2025-12 prices) is proven in test_price_reference_period.py.
    """
    prepared(lake)
    provider = scripted(*first_two(real_may_draft(reference)))
    report = live_check.run_prepared_check(provider, lake.root, tmp_path / "work", turns=2)
    final = report["turns"][-1]
    assert (final["answer"]["status"] == "accepted") is accepted, final["answer"]
    assert (live_check.TURN_TWO_NAME in final["published"]) is accepted


def test_turn_three_heading_and_duplicated_counts_do_not_block_publication(lake, tmp_path):
    """M11-07 live repeat 2: headings and Turn 1 duplicate counts withheld Turn 3."""
    prepared(lake)
    third = [ADD_KFE, comparison("compare", REAL, when=("EVDS:TP.KFE.TR", "up"))]
    provider = scripted(
        *first_two(),
        proposal(live_check.TURN_THREE_QUESTION, third),
        "Değerlendirme: bu birlikte hareket kredinin artmamasını tek başına açıklamaz.",
    )
    report = live_check.run_prepared_check(provider, lake.root, tmp_path / "work", turns=3)
    final = report["turns"][-1]
    assert report["passed"] is True and final["answer"]["status"] == "accepted", final["answer"]
    writer_context = " ".join(m.content for m in provider.seen[-1])
    assert "display AMBIGUOUS" in writer_context
