"""A selected derived quantity is scored as provided, with its own producer proof."""

import json
from dataclasses import replace

import pytest
from test_anomaly import RATE, STEADY_THEN_JUMP, STOCK, series  # noqa: F401
from test_anomaly import house as house

from kkb_agent.agent import ExecutionContext, Session, ToolRegistry, Workspace
from kkb_agent.agent.verifier import result_faults
from kkb_agent.analytics import detect_anomalies
from kkb_agent.core import CumulativeKind, ResultStatus
from kkb_agent.lakehouse import Observation
from kkb_agent.lakehouse.result_evidence import execution_proof
from kkb_agent.llm import scripted
from kkb_agent.tools import (
    AnomalyArguments,
    make_anomaly_tool,
    make_lakehouse_tool,
    make_table_transform_tool,
)


def test_log_ratios_and_simple_percentage_changes_are_not_equivalent():
    # Both datasets have exactly the same 12 transitions and no exclusions.
    # MAD is affine-invariant, not invariant to a log transform.
    changes = [-70, -60, -50, -40, -30, -20, -10, 0, 10, 20, 30, 300]
    levels = [100.0]
    for change in changes:
        levels.append(levels[-1] * (1 + change / 100))
    raw = detect_anomalies(series(*levels), STOCK, series_id="level")
    derived = detect_anomalies(series(*changes), RATE, series_id="percent", basis="values")
    assert raw.status is derived.status is ResultStatus.COMPUTED
    assert raw.samples.used == derived.samples.used == 12
    assert raw.parameters["median_scored_change"] != derived.parameters["median_scored_change"]
    assert raw.values[0].value == 0 and derived.values[0].value == 1
    assert derived.values[1].unit == "percent" and derived.values[1].value == 300


def test_real_read_change_anomaly_chain_consumes_the_derived_quantity_and_proves_it(house):
    workspace = Workspace.open(house.connection, "derived-anomaly")
    registry = ToolRegistry()
    for tool in (
        make_lakehouse_tool(house.connection, lineage=house.lineage),
        make_table_transform_tool(house.connection, workspace, lineage=house.lineage),
        make_anomaly_tool(house.connection, workspace=workspace, lineage=house.lineage),
    ):
        registry.register(tool)
    label = "bddk:konut % change (lag 1)"
    steps = [
        {"step_id": "read", "tool": "lakehouse", "arguments": {"series": ["bddk:konut"]}},
        {
            "step_id": "change",
            "tool": "table_transform",
            "depends_on": ["read"],
            "arguments": {
                "operation": "change",
                "source": "read",
                "column": "bddk:konut",
                "kind": "percent",
            },
        },
        {
            "step_id": "check",
            "tool": "anomaly",
            "depends_on": ["change"],
            "arguments": {"source": "change", "column": label},
        },
    ]
    provider = scripted(
        json.dumps({"question": "Yüzde değişimlerde anomali ara", "steps": steps}),
        "Sonuç hesaplandı.",
    )
    answer = Session(provider, registry, deterministic_presentation=False).answer(
        "Yüzde değişimlerde anomali ara", house.connection, workspace=workspace, remember="out"
    )
    result = answer.results[-1]
    assert result.status is ResultStatus.COMPUTED, result.reason
    assert result.parameters["examined"] == "supplied column values"
    assert not result_faults({"out": result}, house.connection)
    assert execution_proof(result, house.connection)
    table = answer.results[-2]
    values = [v for v in table.values if v.label == label]
    expected = detect_anomalies(
        [Observation(v.period.start, v.period.end, v.value) for v in values],
        RATE,
        series_id=label,
        basis="values",
    )
    assert [(v.period, v.value, v.unit) for v in result.values] == [
        (v.period, v.value, v.unit) for v in expected.values
    ]
    assert result.samples.used == len(STEADY_THEN_JUMP) - 1  # no second differencing
    assert workspace.value_of("out") == result
    forged = table.model_copy(update={"values": table.values[:-1]})
    rejected = registry.get("anomaly").run(
        AnomalyArguments(source="fake", column=label),
        ExecutionContext("", outputs={"fake": forged}),
    )
    assert rejected.error_category == "table_reference"


def test_values_basis_does_not_invent_missing_values_or_cumulative_meaning():
    observations = series(*[float(i % 4) for i in range(13)], None)
    result = detect_anomalies(observations, RATE, series_id="derived", basis="values")
    assert result.samples.used == 13 and result.samples.missing == 1
    unresolved = replace(STOCK, cumulative=CumulativeKind.UNKNOWN)
    assert (
        detect_anomalies(observations, unresolved, series_id="unknown", basis="values").status
        is ResultStatus.ABSTAINED
    )


@pytest.mark.parametrize(
    "arguments",
    [
        {"series_id": "raw", "source": "table", "column": "change"},
        {"source": "table"},
        {"column": "change"},
        {},
    ],
)
def test_no_silent_raw_series_substitution(arguments):
    with pytest.raises(ValueError):
        AnomalyArguments.model_validate(arguments)
