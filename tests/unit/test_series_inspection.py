"""Prepared metadata must match reviewed declarations before numerical promotion."""

import hashlib
import json
from datetime import date

import pytest
from pydantic import ValidationError
from test_catalog_continuation import CATALOG, NOW, TOTAL, seed_prepared

from kkb_agent import live_check
from kkb_agent.agent import ArtifactKind, ExecutionContext, ToolStatus, Workspace
from kkb_agent.catalog.inspection import InspectionRefused, PreparedSeriesInspector
from kkb_agent.catalog.mappings import ReviewedSnapshot, load_reviewed_snapshot
from kkb_agent.catalog.records import CatalogRecord, CatalogStatus
from kkb_agent.core import (
    Frequency,
    ResultStatus,
    SourceRef,
)
from kkb_agent.lakehouse import Observation, SeriesSemantics, open_lakehouse
from kkb_agent.lakehouse.result_evidence import execution_proof
from kkb_agent.llm import scripted
from kkb_agent.tools import (
    make_anomaly_tool,
    make_causality_tool,
    make_change_detection_tool,
    make_lakehouse_tool,
    make_table_transform_tool,
)
from kkb_agent.tools.change_detection import SeriesUnknown, read_series

CPI = "EVDS:TP.TUKFIY2025.GENEL"
RATE = "EVDS:TP.KTF12"
CONTEXT = ExecutionContext(question="offline inspection")
SQL = (
    "SELECT o.series_id,o.period_start,o.period_end,o.value,"
    "s.unit,s.scale,s.frequency,s.observation "
    "FROM silver_observations o JOIN silver_series s ON o.series_id=s.series_id "
    f"WHERE o.series_id='{TOTAL}' ORDER BY o.period_end"
)


@pytest.fixture
def snapshot():
    return load_reviewed_snapshot(CATALOG.read_bytes())


@pytest.fixture
def inspector(snapshot):
    return PreparedSeriesInspector(snapshot)


@pytest.fixture
def house(tmp_path, snapshot):
    root = tmp_path / "lake"
    seed_prepared(root)
    with open_lakehouse(root) as lake:
        for sid in (CPI, RATE):
            record = next(s.record for s in snapshot.series if s.record.series_id == sid)
            semantics = SeriesSemantics(
                unit=record.unit,
                scale=record.scale,
                frequency=record.frequency,
                observation=record.stock_flow,
                cumulative=record.cumulative,
                aggregation=record.aggregation.default,
                anchor=record.weekly_anchor,
                base_year=record.base_year,
            )
            artifact = lake.record_artifact(
                ("synthetic:" + sid).encode(),
                source=SourceRef(source_id="test", source_type="fixture", locator="opaque:fixture"),
                media_type="text/plain",
                recorded_at=NOW,
            )
            lake.register_series(
                sid, title="Synthetic", semantics=semantics, artifact_id=artifact.artifact_id
            )
            observations = (
                [Observation(date(2026, 3, 28), date(2026, 4, 3), 10.0)]
                if semantics.frequency is Frequency.WEEKLY
                else [
                    Observation(date(2026, m, 1), date(2026, m, end), value)
                    for m, end, value in [(4, 30, 100.0), (5, 31, 110.0), (6, 30, 120.0)]
                ]
            )
            lake.append_observations(sid, observations)
        yield lake


def revised(snapshot, sid=TOTAL, **changes):
    """Explicit test-only reviewed snapshot revision, never mutate a production artifact."""
    data = snapshot.model_dump(mode="json")
    selected = next(s for s in data["series"] if s["record"]["series_id"] == sid)
    selected["record"].update(changes)
    selected["record"] = CatalogRecord.model_validate(selected["record"]).model_dump(mode="json")
    raw = {k: v for k, v in data.items() if k != "content_sha256"}
    data["content_sha256"] = hashlib.sha256(
        json.dumps(
            raw,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()
    return ReviewedSnapshot.model_validate(data)


class MetadataOnly:
    def __init__(self, connection):
        self.connection = connection
        self.queries = []

    def execute(self, sql, parameters):
        assert "silver_observations" not in sql
        assert sql.startswith("SELECT ")
        self.queries.append((sql, parameters))
        return self.connection.execute(sql, parameters)


def test_consistency_receipt_is_read_only_and_not_calculation_permission(house, inspector):
    connection = MetadataOnly(house.connection)
    result = inspector.inspect(connection, TOTAL)
    assert result.status == "consistent" and result.calculation_authorized is False
    assert result.catalog_status is CatalogStatus.UNKNOWN
    assert result.declared_coverage.start is result.declared_coverage.end is None
    assert result.record_sha256 and result.prepared_metadata_sha256 and result.source_artifact_id
    assert len(connection.queries) == 1 and connection.queries[0][1] == [TOTAL]
    proof = result.evidence()
    assert "prepared_series_inspection_v1" in proof
    assert "opaque:fixture" not in proof and "Synthetic" not in proof
    assert "observations" not in proof
    assert inspector.inspect(connection, TOTAL).evidence() == proof


def test_unknown_identity_does_not_consult_the_database(inspector):
    class NoRead:
        def execute(self, *args):
            pytest.fail("Unknown catalog identity must not access data")

    result = inspector.inspect(NoRead(), "invented:id")
    assert result.status == "unknown_identity"
    with pytest.raises(InspectionRefused, match="unknown_identity"):
        result.evidence()


def test_catalog_presence_is_not_prepared_availability(house, inspector):
    result = inspector.inspect(house.connection, "EVDS:TP.GENENDEKS.T1")
    assert result.status == "not_prepared" and result.source_artifact_id is None


@pytest.mark.parametrize(
    "sid,field,value",
    [
        (TOTAL, "unit", "USD"),
        (TOTAL, "scale", "thousand"),
        (TOTAL, "frequency", "daily"),
        (TOTAL, "observation", "flow"),
        (CPI, "base_year", 2003),
        (RATE, "anchor", "thursday"),
    ],
)
def test_valid_but_different_prepared_declarations_are_refused(house, inspector, sid, field, value):
    # Column names come only from this fixed test table, never runtime/model text.
    house.connection.execute(f"UPDATE silver_series SET {field}=? WHERE series_id=?", [value, sid])
    result = inspector.inspect(MetadataOnly(house.connection), sid)
    assert result.status == "metadata_mismatch", result
    assert field in result.mismatch_fields
    with pytest.raises(SeriesUnknown, match="metadata_mismatch"):
        read_series(MetadataOnly(house.connection), sid, inspector=inspector)


@pytest.mark.parametrize(
    "field,value",
    [
        ("unit", "not_a_unit"),
        ("scale", "unknown"),
        ("frequency", "unknown"),
        ("observation", "unknown"),
        ("cumulative", "unknown"),
        ("cumulative", "yearly_reset"),
        ("aggregation", "not_a_method"),
    ],
)
def test_invalid_prepared_semantics_are_not_repaired_from_catalog(house, inspector, field, value):
    house.connection.execute(
        f"UPDATE silver_series SET {field}=? WHERE series_id=?", [value, TOTAL]
    )
    result = inspector.inspect(MetadataOnly(house.connection), TOTAL)
    assert result.status == "invalid_prepared_metadata"
    with pytest.raises(SeriesUnknown):
        read_series(MetadataOnly(house.connection), TOTAL, inspector=inspector)


@pytest.mark.parametrize(
    "field,value,reported",
    [
        ("unit", None, "unit"),
        ("scale", "unknown", "scale"),
        ("frequency", "unknown", "frequency"),
        ("stock_flow", "unknown", "observation"),
        ("cumulative", "unknown", "cumulative"),
    ],
)
def test_unresolved_catalog_is_not_filled_from_prepared_values(
    house, snapshot, field, value, reported
):
    inspected = PreparedSeriesInspector(revised(snapshot, **{field: value}))
    result = inspected.inspect(house.connection, TOTAL)
    assert result.status == "unresolved_catalog" and reported in result.unknown_fields
    assert result.source_artifact_id is None


def test_unresolved_index_base_remains_unresolved(house, snapshot):
    inspected = PreparedSeriesInspector(revised(snapshot, CPI, base_year=None))
    result = inspected.inspect(house.connection, CPI)
    assert result.status == "unresolved_catalog" and result.unknown_fields == ("base_year",)


def test_archive_policy_is_operator_owned_and_does_not_infer_current_status(house, snapshot):
    archived = revised(snapshot, status="archived")
    assert PreparedSeriesInspector(archived).inspect(house.connection, TOTAL).status == "archived"
    allowed = PreparedSeriesInspector(archived, allow_archived=True).inspect(
        house.connection, TOTAL
    )
    assert allowed.status == "consistent" and allowed.catalog_status is CatalogStatus.ARCHIVED
    with pytest.raises(TypeError):
        PreparedSeriesInspector(snapshot, allow_archived=1)


def test_snapshot_and_output_mutation_cannot_change_subsequent_checks(house, snapshot):
    inspected = PreparedSeriesInspector(snapshot)
    before = inspected.inspect(house.connection, TOTAL).evidence()
    next(s for s in snapshot.series if s.record.series_id == TOTAL).record.unit = "USD"
    output = inspected.inspect(house.connection, TOTAL)
    output.declared_coverage.start = date(1900, 1, 1)
    assert inspected.inspect(house.connection, TOTAL).evidence() == before


def test_previous_success_is_not_a_stale_cache(house, inspector):
    assert inspector.inspect(house.connection, TOTAL).status == "consistent"
    house.connection.execute("UPDATE silver_series SET unit='EUR' WHERE series_id=?", [TOTAL])
    assert inspector.inspect(house.connection, TOTAL).status == "metadata_mismatch"


def test_unknown_optional_aggregation_is_explicit_not_inferred(house, inspector):
    result = inspector.inspect(house.connection, TOTAL)
    assert result.status == "consistent" and "aggregation" in result.optional_unknown_fields
    assert result.calculation_authorized is False


@pytest.mark.parametrize(
    "declared",
    [
        {"default": "last"},
        {"default": "unknown", "average": False},
    ],
)
def test_applicable_aggregation_declarations_are_enforced(house, snapshot, declared):
    inspected = PreparedSeriesInspector(revised(snapshot, aggregation=declared))
    house.connection.execute(
        "UPDATE silver_series SET aggregation='average' WHERE series_id=?", [TOTAL]
    )
    result = inspected.inspect(house.connection, TOTAL)
    assert result.status == "metadata_mismatch" and result.mismatch_fields == ("aggregation",)


def test_valid_cumulative_flow_mismatch_is_refused(house, snapshot):
    inspected = PreparedSeriesInspector(revised(snapshot, stock_flow="flow", cumulative="none"))
    house.connection.execute(
        "UPDATE silver_series SET observation='flow', cumulative='yearly_reset' WHERE series_id=?",
        [TOTAL],
    )
    result = inspected.inspect(house.connection, TOTAL)
    assert result.status == "metadata_mismatch" and result.mismatch_fields == ("cumulative",)


@pytest.mark.parametrize("sid", ["", "x" * 201, "x\ny", 123])
def test_malformed_identity_is_refused_without_echo(inspector, sid):
    with pytest.raises(InspectionRefused, match="invalid_identity") as caught:
        inspector.inspect(None, sid)
    assert str(caught.value) == "Series inspection refused: invalid_identity"


def invoke(tool, **arguments):
    return tool.run(tool.parse(arguments), CONTEXT)


@pytest.mark.parametrize("kind", ["compare", "co_movement", "anomaly", "association"])
def test_registered_series_producers_cannot_skip_inspection(house, inspector, kind):
    house.connection.execute("UPDATE silver_series SET unit='USD' WHERE series_id=?", [TOTAL])
    if kind in ("compare", "co_movement"):
        tool = make_change_detection_tool(house.connection, inspector=inspector)
        args = {"operation": kind, "series_id": TOTAL, "start": "2026-04-30", "end": "2026-06-30"}
        if kind == "co_movement":
            args["driver_series_id"] = RATE
    elif kind == "anomaly":
        tool = make_anomaly_tool(house.connection, inspector=inspector)
        args = {"series_id": TOTAL}
    else:
        tool = make_causality_tool(house.connection, inspector=inspector)
        args = {"operation": "association", "left_series_id": CPI, "right_series_id": TOTAL}
    result = invoke(tool, **args)
    assert result.status is ToolStatus.FAILURE and result.output is None
    assert "metadata_mismatch" in " ".join(result.warnings)
    with pytest.raises(ValidationError):
        tool.arguments.model_validate({**args, "skip_inspection": True})


@pytest.mark.parametrize("kind", ["deflate", "add_series"])
def test_table_transform_inspects_new_series_before_calculating(house, inspector, kind):
    source = invoke(
        make_lakehouse_tool(house.connection, lineage=house.lineage, inspector=inspector), sql=SQL
    ).output.result
    assert source.status is ResultStatus.COMPUTED and execution_proof(source, house.connection)
    workspace = Workspace.open(house.connection)
    workspace.record("base", ArtifactKind.VALUE, source)
    original = workspace.value_of("base").model_dump_json()
    house.connection.execute("UPDATE silver_series SET base_year=2003 WHERE series_id=?", [CPI])
    tool = make_table_transform_tool(house.connection, workspace, inspector=inspector)
    args = {"operation": kind, "source": "base"}
    if kind == "deflate":
        args.update(column=TOTAL, index_series_id=CPI, reference_period="2026-06-30")
    else:
        args["series_id"] = CPI
    result = invoke(tool, **args)
    assert result.status is ToolStatus.FAILURE and "metadata_mismatch" in result.warnings[0]
    assert workspace.value_of("base").model_dump_json() == original


def test_sql_cannot_promote_mismatched_direct_rows_to_measurements(house, inspector):
    tool = make_lakehouse_tool(house.connection, lineage=house.lineage, inspector=inspector)
    house.connection.execute("UPDATE silver_series SET scale='thousand' WHERE series_id=?", [TOTAL])
    result = invoke(tool, sql=SQL)
    assert result.status is ToolStatus.SUCCESS  # inspection rows, no financial answer
    assert result.output.result.status is ResultStatus.ABSTAINED
    assert not result.output.result.values and not result.output.result.evidence
    assert result.evidence is None and "metadata_mismatch" in result.output.result.reason


def test_consistent_read_and_sql_bind_the_receipt_into_execution_evidence(house, inspector):
    read = read_series(house.connection, TOTAL, inspector=inspector)
    receipt = json.loads(json.loads(read.snapshot)["catalog_inspection"])
    assert receipt["kind"] == "prepared_series_inspection_v1"
    produced = invoke(
        make_lakehouse_tool(house.connection, lineage=house.lineage, inspector=inspector), sql=SQL
    ).output.result
    assert execution_proof(produced, house.connection)
    traces = house.connection.execute("SELECT attributes FROM lineage_nodes").fetchall()
    assert any("prepared_series_inspection_v1" in str(row) for row in traces)


def test_prepared_runtime_injects_inspection_even_without_a_discovery_step(tmp_path):
    root = tmp_path / "prepared"
    seed_prepared(root)
    with open_lakehouse(root) as lake:
        lake.connection.execute("UPDATE silver_series SET unit='USD' WHERE series_id=?", [TOTAL])
    plan = json.dumps(
        {
            "question": "change",
            "steps": [
                {
                    "step_id": "a",
                    "tool": "change_detection",
                    "arguments": {
                        "operation": "compare",
                        "series_id": TOTAL,
                        "start": "2026-04-30",
                        "end": "2026-06-30",
                    },
                }
            ],
        }
    )
    provider = scripted(plan)
    report = live_check.run_prepared_check(
        provider, root, tmp_path / "work", catalog_bytes=CATALOG.read_bytes()
    )
    assert not report["passed"] and report["published"] == []
    assert len(provider.seen) == 1 and report["tools"][0]["status"] == "failure"
