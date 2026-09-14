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
    assert report["passed"] is (case == "complete"), report
    assert len(report["turns"]) == 3
    final = report["turns"][-1]
    assert final["relationship_checked"] is (case == "complete")
    assert final["published"] == [
        live_check.TURN_ONE_NAME,
        live_check.TURN_TWO_NAME,
        live_check.TURN_THREE_NAME,
    ]
    if case == "complete":
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
