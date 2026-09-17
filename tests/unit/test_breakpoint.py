"""Breakpoints: a regime change is found, and a quiet series does not get one."""

from dataclasses import replace
from datetime import date

import pytest
from test_turn_two import CPI_SEMANTICS

from kkb_agent.analytics.breakpoint import (
    DEFAULT_MINIMUM_SEGMENT,
    detect_breakpoints,
)
from kkb_agent.core import CumulativeKind, ResultStatus, Scale, StockFlow
from kkb_agent.lakehouse.records import Observation

SEMANTICS = replace(
    CPI_SEMANTICS,
    unit="TRY",
    scale=Scale.MILLION,
    observation=StockFlow.STOCK,
    cumulative=CumulativeKind.NONE,
    base_year=None,
)


def months(count, start=date(2021, 1, 31)):
    found = [start]
    while len(found) < count:
        previous = found[-1]
        year, month = divmod(previous.year * 12 + previous.month, 12)
        following = date(year, month + 1, 1)
        after = date(following.year + (following.month == 12), following.month % 12 + 1, 1)
        found.append(date.fromordinal(after.toordinal() - 1))
    return found


def series(values, start=date(2021, 1, 31)):
    return [
        Observation(date(end.year, end.month, 1), end, value)
        for end, value in zip(months(len(values), start), values, strict=True)
    ]


def levels(steps):
    """A level series built from the monthly changes it should show."""
    total = 1000.0
    found = [total]
    for step in steps:
        total += step
        found.append(total)
    return found


def test_a_regime_change_is_found_with_its_shift_and_the_months_behind_it():
    # 14 months growing by ~4, then 14 growing by ~20.
    slow = [4.0, 3.5, 4.5, 4.0, 3.8, 4.2, 4.1, 3.9, 4.0, 4.3, 3.7, 4.0, 4.1, 3.9]
    fast = [20.0, 19.5, 20.5, 20.0, 19.8, 20.2, 20.1, 19.9, 20.0, 20.3, 19.7, 20.0, 20.1, 19.9]
    result = detect_breakpoints(series(levels(slow + fast)), SEMANTICS, series_id="TEST:credit")
    assert result.status is ResultStatus.COMPUTED
    count = next(v for v in result.values if v.label.endswith("breakpoints found"))
    assert count.value == 1.0
    (shift,) = [v for v in result.values if "average change shift" in v.label]
    assert shift.value == pytest.approx(16.0, abs=0.5)  # ~20 a month instead of ~4
    assert (shift.unit, shift.scale) == ("TRY", Scale.MILLION)
    # Dated to the first month of the new regime: 2021-01 is the base level, the 14 slow
    # changes run to 2022-03, so the first fast month is 2022-04.
    assert shift.period.end == date(2022, 4, 30)
    recorded = result.parameters["breakpoints"][0]
    assert recorded["observations_before"] == 14 and recorded["observations_after"] == 14
    assert recorded["mean_change_before"] < recorded["mean_change_after"]
    assert result.samples.used == 28
    assert any("establishes no cause" in note for note in result.warnings)
    assert any("proposed defaults" in note for note in result.limitations)


def test_a_steady_series_reports_zero_rather_than_a_fabricated_break():
    steady = [4.0, 3.6, 4.4, 4.1, 3.9, 4.2, 3.8, 4.0, 4.3, 3.7, 4.1, 3.9] * 3
    result = detect_breakpoints(series(levels(steady)), SEMANTICS, series_id="TEST:credit")
    assert result.status is ResultStatus.COMPUTED
    count = next(v for v in result.values if v.label.endswith("breakpoints found"))
    assert count.value == 0.0 and len(result.values) == 1
    assert result.parameters["breakpoints"] == []


def test_two_regime_changes_are_reported_in_order():
    first = [4.0, 3.8, 4.2, 4.1, 3.9, 4.0, 4.3, 3.7]
    second = [20.0, 19.8, 20.2, 20.1, 19.9, 20.0, 20.3, 19.7]
    third = [2.0, 1.8, 2.2, 2.1, 1.9, 2.0, 2.3, 1.7]
    result = detect_breakpoints(
        series(levels(first + second + third)), SEMANTICS, series_id="TEST:credit"
    )
    shifts = [v for v in result.values if "average change shift" in v.label]
    assert len(shifts) == 2
    assert [v.period.end for v in shifts] == sorted(v.period.end for v in shifts)
    assert shifts[0].value > 0 and shifts[1].value < 0  # up, then down


@pytest.mark.parametrize(
    ("semantics", "status", "needle"),
    [
        (
            # Only a flow series may accumulate; that is the contract's own rule.
            replace(
                SEMANTICS,
                observation=StockFlow.FLOW,
                cumulative=CumulativeKind.YEARLY_RESET,
            ),
            ResultStatus.ABSTAINED,
            "accumulates",
        ),
        (replace(SEMANTICS, scale=Scale.UNKNOWN), ResultStatus.ABSTAINED, "unresolved"),
    ],
)
def test_a_series_whose_meaning_blocks_the_question_is_refused(semantics, status, needle):
    result = detect_breakpoints(series(levels([4.0] * 30)), semantics, series_id="TEST:credit")
    assert result.status is status and needle in result.reason
    assert not result.values


def test_a_short_window_and_a_constant_series_say_which_one_they_are():
    short = detect_breakpoints(series(levels([4.0] * 6)), SEMANTICS, series_id="TEST:credit")
    assert short.status is ResultStatus.INSUFFICIENT
    assert short.samples.minimum_required == 2 * DEFAULT_MINIMUM_SEGMENT

    constant = detect_breakpoints(series(levels([4.0] * 30)), SEMANTICS, series_id="TEST:credit")
    assert constant.status is ResultStatus.UNDEFINED
    assert "no spread" in constant.reason


def test_a_gap_is_not_bridged_into_an_invented_change():
    values = levels([4.0, 3.8, 4.2, 4.1] * 8)
    observations = series(values)
    observations[10] = replace(observations[10], value=None)
    result = detect_breakpoints(observations, SEMANTICS, series_id="TEST:credit")
    assert result.samples.missing == 1
    assert result.samples.used == len(observations) - 3  # the gap ends two pairs
    assert any("gap ends a pair" in note for note in result.warnings)


def test_the_planner_can_ask_for_a_breakpoint_through_the_tool(tmp_path):
    """The operation exists in the schema and runs end to end over stored series."""
    from datetime import UTC, datetime

    from kkb_agent.agent import ExecutionContext, ToolStatus
    from kkb_agent.core import Aggregation, Frequency, SourceRef
    from kkb_agent.lakehouse import open_lakehouse
    from kkb_agent.tools import ChangeDetectionArguments, make_change_detection_tool

    slow = [4.0, 3.5, 4.5, 4.0, 3.8, 4.2, 4.1, 3.9, 4.0, 4.3, 3.7, 4.0, 4.1, 3.9]
    fast = [20.0, 19.5, 20.5, 20.0, 19.8, 20.2, 20.1, 19.9, 20.0, 20.3, 19.7, 20.0, 20.1, 19.9]
    observations = series(levels(slow + fast))
    stored = replace(SEMANTICS, aggregation=Aggregation.LAST, frequency=Frequency.MONTHLY)

    with open_lakehouse(tmp_path / "lake") as lake:
        artifact = lake.record_artifact(
            b"synthetic",
            source=SourceRef(source_id="x", source_type="fixture", locator="opaque:x"),
            media_type="text/plain",
            recorded_at=datetime(2026, 9, 18, tzinfo=UTC),
        )
        lake.register_series(
            "TEST:credit",
            title="Synthetic credit",
            semantics=stored,
            artifact_id=artifact.artifact_id,
        )
        lake.append_observations("TEST:credit", observations)
        tool = make_change_detection_tool(lake.connection, lineage=lake.lineage)
        arguments = ChangeDetectionArguments.model_validate(
            {
                "operation": "breakpoint",
                "series_id": "TEST:credit",
                "start": "2021-01-31",
                "end": "2023-05-31",
            }
        )
        outcome = tool.run(arguments, ExecutionContext(question="Kırılma var mı?"))

    assert outcome.status is ToolStatus.SUCCESS
    assert outcome.output.status is ResultStatus.COMPUTED
    assert outcome.output.kind.value == "change_point"
    assert (
        next(v.value for v in outcome.output.values if v.label.endswith("breakpoints found")) == 1.0
    )
    assert "breakpoint" in tool.description
    # The threshold stays a harness constant: the planner cannot pass one.
    assert (
        "threshold"
        not in ChangeDetectionArguments.model_json_schema()["$defs"]["SeriesChangeArguments"][
            "properties"
        ]
    )
