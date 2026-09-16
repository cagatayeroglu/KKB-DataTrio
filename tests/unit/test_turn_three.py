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


@pytest.mark.parametrize("case", ["complete", "only_added", "nominal", "wrong_direction"])
def test_three_turn_acceptance_requires_requested_real_comparison(lake, tmp_path, case):
    """A plan naming the nominal column still produces the required real comparison.

    The tool resolves a column to its deflated counterpart when the table carries
    one, so `nominal` and `complete` reach the same published comparison. What
    still fails acceptance is adding the column without comparing it, or comparing
    it in the wrong direction.
    """
    requested_real = case in {"complete", "nominal"}
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
        third.append(
            step(
                "change_detection",
                {
                    "operation": "table_co_movement",
                    "input_step": "add",
                    "driver_column": "EVDS:TP.KFE.TR",
                    "target_column": TOTAL_ID
                    if case == "nominal"
                    else f"{TOTAL_ID} real, 2021-06 prices ({CPI_ID})",
                    "driver_direction": "up",
                    "target_direction": "up" if case == "wrong_direction" else "non_increasing",
                    "when_column": "EVDS:TP.KTF12 monthly average (by_end)",
                    "when_direction": "down",
                },
                "compare",
                ("add",),
            )
        )
    provider = scripted(
        *first_two(), proposal(live_check.TURN_THREE_QUESTION, third), "Tablo hazırlandı."
    )
    report = live_check.run_prepared_check(provider, lake.root, tmp_path / "work", turns=3)
    assert report["passed"] is requested_real, report
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
        assert final["tables"][0]["rows"] == 6
        assert final["result"]["transformations"] == [
            "align_weekly_to_monthly",
            "deflate",
            "add_series",
            "table_co_movement",
        ]


def test_final_qualified_answer_without_publication_is_not_a_passing_rehearsal(lake, tmp_path):
    prepared(lake)
    provider = scripted(*first_two("Tablo hazırlandı. Kredi bakiyesi 987654321 milyon TL oldu."))
    report = live_check.run_prepared_check(provider, lake.root, tmp_path / "work", turns=2)
    assert report["passed"] is False
    final = report["turns"][-1]
    assert final["answer"]["status"] == "qualified"
    assert final["published"] == [live_check.TURN_ONE_NAME]
    assert final["passed"] is False


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


def test_live_parallel_comparisons_are_repaired_into_one_published_condition(lake, tmp_path):
    """M11-07 live Turn 3: two unconsumed comparisons published only the last one."""
    prepared(lake)
    parallel = [
        ADD_KFE,
        comparison("kfe", "EVDS:TP.KFE.TR", when=(REAL, "non_increasing"), direction="up"),
        comparison("real", REAL),
    ]
    combined = [ADD_KFE, comparison("compare", REAL, when=("EVDS:TP.KFE.TR", "up"))]
    provider = scripted(
        *first_two(),
        proposal(live_check.TURN_THREE_QUESTION, parallel),
        proposal(live_check.TURN_THREE_QUESTION, combined),
        "Tablo hazırlandı.",
    )
    report = live_check.run_prepared_check(provider, lake.root, tmp_path / "work", turns=3)
    final = report["turns"][-1]
    assert report["passed"] is True and final["relationship_checked"] is True, report
    assert final["published"][-1] == live_check.TURN_THREE_NAME
    assert final["result"]["transformations"][-1] == "table_co_movement"
    planner_feedback = " ".join(m.content for m in provider.seen[-2])
    assert "final calculation steps" in planner_feedback
    writer_context = " ".join(m.content for m in provider.seen[-1])
    assert "condition column EVDS:TP.KFE.TR direction up" in writer_context
    presence = next(
        line for line in writer_context.splitlines() if "have a value in every period" in line
    )
    assert "EVDS:TP.KFE.TR" in presence or "Konut" in presence


def test_live_absence_prose_cannot_pass_turn_three(lake, tmp_path):
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
