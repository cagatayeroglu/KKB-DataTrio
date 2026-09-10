"""M5-10/11/12: the workspace holding actual values, not just definitions.

The definition DAG already knew what the analysis *is*. These tests are about
what it now holds: real typed results, addressed by content, refused when
stale, and recomputed rather than rebound.

`TestTheOrganizerScenario` is the requirement in its original form — build a
table, change the date range, add a column — carried out against real values
with a real tool, and it is the case the rest of this file exists to support.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import duckdb
import pytest

from kkb_agent.agent import (
    ArtifactKind,
    ExecutionContext,
    ToolRegistry,
    Workspace,
    WorkspaceError,
)
from kkb_agent.core import (
    Aggregation,
    AnalyticalResult,
    CumulativeKind,
    Frequency,
    Period,
    ResultEvidence,
    ResultKind,
    ResultStatus,
    ResultValue,
    SampleCounts,
    Scale,
    SourceRef,
    StockFlow,
)
from kkb_agent.lakehouse import Observation, SeriesSemantics, open_lakehouse
from kkb_agent.tools import LakehouseArguments, make_lakehouse_tool

NOW = datetime(2026, 9, 9, tzinfo=UTC)
MONTHLY = SeriesSemantics(
    unit="TRY",
    scale=Scale.MILLION,
    frequency=Frequency.MONTHLY,
    observation=StockFlow.STOCK,
    cumulative=CumulativeKind.NONE,
    aggregation=Aggregation.LAST,
)
PUBLISHED = {date(2026, 4, 30): 767314.0, date(2026, 5, 31): 782918.0, date(2026, 6, 30): 801438.0}

SOURCE = ArtifactKind.SOURCE
COLUMN = ArtifactKind.COLUMN
TABLE = ArtifactKind.TABLE
VALUE = ArtifactKind.VALUE


def a_result(value: float = 801438.0, **overrides) -> AnalyticalResult:
    fields = {
        "result_id": f"r-{value}",
        "kind": ResultKind.LEVEL,
        "status": ResultStatus.COMPUTED,
        "tool": "lakehouse",
        "values": [
            ResultValue(
                label="bddk:konut",
                value=value,
                unit="TRY",
                scale=Scale.MILLION,
                measure=StockFlow.STOCK,
                period=Period(
                    start=date(2026, 6, 1), end=date(2026, 6, 30), frequency=Frequency.MONTHLY
                ),
            )
        ],
        "samples": SampleCounts(used=3),
        "evidence": ResultEvidence(input_refs=["silver_observations"]),
    }
    fields.update(overrides)
    return AnalyticalResult(**fields)


@pytest.fixture
def workspace():
    with duckdb.connect() as connection:
        yield Workspace.open(connection)


@pytest.fixture
def house(tmp_path):
    with open_lakehouse(tmp_path / "lake") as lake:
        artifact = lake.record_artifact(
            b'{"konut": 801438}',
            source=SourceRef(source_id="bddk", source_type="http-json", locator="opaque:t4"),
            media_type="application/json",
            recorded_at=NOW,
        )
        lake.register_series(
            "bddk:konut",
            title="Tüketici Kredileri - Konut",
            semantics=MONTHLY,
            artifact_id=artifact.artifact_id,
        )
        lake.append_observations(
            "bddk:konut",
            [Observation(date(end.year, end.month, 1), end, v) for end, v in PUBLISHED.items()],
        )
        yield lake


class TestValuesAreStoredByContent:
    def test_a_result_round_trips(self, workspace):
        digest = workspace.store_result(a_result())
        assert workspace.read_result(digest) == a_result()

    def test_the_same_result_stored_twice_is_one_row(self, workspace):
        first = workspace.store_result(a_result())
        second = workspace.store_result(a_result())

        assert first == second
        rows = workspace.connection.execute("SELECT count(*) FROM workspace_results").fetchone()
        assert rows[0] == 1

    def test_a_different_result_cannot_overwrite_an_earlier_one(self, workspace):
        old = workspace.store_result(a_result(801438.0))
        new = workspace.store_result(a_result(850000.0))

        assert old != new
        # What the analysis said before the change is still answerable.
        assert workspace.read_result(old).values[0].value == pytest.approx(801438.0)

    def test_a_mutated_row_is_refused_rather_than_served(self, workspace):
        # The digest check is the only thing between an edited row and an
        # answer that cites it as evidence.
        digest = workspace.store_result(a_result())
        tampered = a_result(999999.0).model_dump_json()
        workspace.connection.execute(
            "UPDATE workspace_results SET payload = ? WHERE result_digest = ?", [tampered, digest]
        )

        with pytest.raises(WorkspaceError, match="no longer matches its content address"):
            workspace.read_result(digest)

    def test_an_unknown_digest_is_refused(self, workspace):
        with pytest.raises(WorkspaceError, match="No stored result"):
            workspace.read_result("0" * 64)


class TestRecordingAndReading:
    def test_record_binds_a_name_to_a_real_value(self, workspace):
        workspace.record("konut", VALUE, a_result())

        assert workspace.value_of("konut").values[0].value == pytest.approx(801438.0)
        assert workspace.resolve("konut").value_ref is not None

    def test_a_definition_without_a_value_says_so(self, workspace):
        workspace.define("range", SOURCE, parameters={"from": "2021-01"})
        with pytest.raises(WorkspaceError, match="holds no value"):
            workspace.value_of("range")

    def test_the_lineage_node_is_carried_across_from_the_evidence(self, workspace):
        workspace.record(
            "konut",
            VALUE,
            a_result(
                evidence=ResultEvidence(input_refs=["silver_observations"], lineage_node="n1")
            ),
        )
        assert workspace.resolve("konut").lineage_node == "n1"

    def test_values_returns_every_current_value(self, workspace):
        workspace.record("konut", VALUE, a_result(801438.0))
        workspace.record("faiz", VALUE, a_result(46.75))
        workspace.define("range", SOURCE, parameters={"from": "2021-01"})

        assert set(workspace.values()) == {"konut", "faiz"}


class TestAStaleReadIsRefused:
    def build(self, workspace):
        workspace.define("range", SOURCE, parameters={"from": "2021-01", "to": "2025-12"})
        workspace.record("konut", VALUE, a_result(), inputs=["range"])

    def test_reading_a_stale_value_is_refused(self, workspace):
        # Returning it and hoping the caller checks is_stale is how a
        # superseded number reaches an answer.
        self.build(workspace)
        workspace.define("range", SOURCE, parameters={"from": "2021-01", "to": "2026-06"})

        with pytest.raises(WorkspaceError, match="is stale"):
            workspace.value_of("konut")

    def test_resolving_a_stale_definition_is_refused_too(self, workspace):
        self.build(workspace)
        workspace.define("range", SOURCE, parameters={"from": "2021-01", "to": "2026-06"})

        with pytest.raises(WorkspaceError, match="is stale"):
            workspace.resolve("konut")

    def test_inspection_is_still_possible_when_asked_for_explicitly(self, workspace):
        self.build(workspace)
        workspace.define("range", SOURCE, parameters={"from": "2021-01", "to": "2026-06"})

        assert workspace.resolve("konut", allow_stale=True).parameters == {}
        assert workspace.value_of("konut", allow_stale=True).values[0].value == pytest.approx(
            801438.0
        )

    def test_a_stale_value_is_left_out_of_values(self, workspace):
        self.build(workspace)
        workspace.define("range", SOURCE, parameters={"from": "2021-01", "to": "2026-06"})
        assert workspace.values() == {}


class TestRefreshRecomputes:
    def build(self, workspace):
        workspace.define("range", SOURCE, parameters={"from": "2021-01", "to": "2025-12"})
        workspace.record("konut", VALUE, a_result(), inputs=["range"])
        workspace.define("range", SOURCE, parameters={"from": "2021-01", "to": "2026-06"})

    def test_refreshing_a_valued_name_without_recomputing_is_refused(self, workspace):
        # Rebinding alone would clear the stale flag and leave the old number
        # in place: a figure that looks current and describes a selection
        # nobody made any more.
        self.build(workspace)
        with pytest.raises(WorkspaceError, match="Supply a recomputer"):
            workspace.refresh("konut")

    def test_a_recomputer_produces_a_new_value_and_clears_the_flag(self, workspace):
        self.build(workspace)

        workspace.refresh("konut", lambda artifact, inputs: a_result(850000.0))

        assert not workspace.is_stale("konut")
        assert workspace.value_of("konut").values[0].value == pytest.approx(850000.0)

    def test_the_superseded_value_remains_readable(self, workspace):
        self.build(workspace)
        old_digest = workspace.resolve("konut", allow_stale=True).value_ref

        workspace.refresh("konut", lambda artifact, inputs: a_result(850000.0))

        assert workspace.read_result(old_digest).values[0].value == pytest.approx(801438.0)

    def test_the_recomputer_receives_the_artifact_and_its_current_inputs(self, workspace):
        workspace.record("base", VALUE, a_result(100.0))
        workspace.record("derived", VALUE, a_result(200.0), inputs=["base"])
        workspace.record("base", VALUE, a_result(150.0))
        seen: dict[str, object] = {}

        def recompute(artifact, inputs):
            seen["name"] = artifact.name
            seen["inputs"] = {k: v.values[0].value for k, v in inputs.items()}
            return a_result(inputs["base"].values[0].value * 2)

        workspace.refresh("derived", recompute)

        assert seen["name"] == "derived"
        assert seen["inputs"] == {"base": pytest.approx(150.0)}
        assert workspace.value_of("derived").values[0].value == pytest.approx(300.0)

    def test_a_definition_without_a_value_still_refreshes_by_rebinding(self, workspace):
        workspace.define("range", SOURCE, parameters={"from": "2021-01", "to": "2025-12"})
        workspace.define("tablo", TABLE, inputs=["range"])
        workspace.define("range", SOURCE, parameters={"from": "2021-01", "to": "2026-06"})

        workspace.refresh("tablo")

        assert not workspace.is_stale("tablo")

    def test_refreshing_before_its_inputs_is_still_refused(self, workspace):
        workspace.define("range", SOURCE, parameters={"to": "2025-12"})
        workspace.record("konut", VALUE, a_result(), inputs=["range"])
        workspace.define("tablo", TABLE, inputs=["konut"])
        workspace.define("range", SOURCE, parameters={"to": "2026-06"})

        with pytest.raises(WorkspaceError, match="after its stale inputs: konut"):
            workspace.refresh("tablo")


class TestTheOrganizerScenario:
    """Build a table, change the range, add a column — with real values."""

    def compute(self, house, sql: str) -> AnalyticalResult:
        registry = ToolRegistry()
        registry.register(make_lakehouse_tool(house.connection, lineage=house.lineage))
        outcome = registry.get("lakehouse").run(
            LakehouseArguments(sql=sql, purpose="konut"), ExecutionContext(question="q")
        )
        return outcome.output.result

    def series_sql(self, since: str) -> str:
        return (
            "SELECT o.series_id, o.period_start, o.period_end, o.value, s.unit, s.scale,"
            " s.frequency, s.anchor, s.observation"
            " FROM silver_observations o JOIN silver_series s ON s.series_id = o.series_id"
            f" WHERE o.period_end >= DATE '{since}' ORDER BY o.period_end"
        )

    def test_three_turns_preserve_and_invalidate_correctly(self, house):
        space = Workspace.open(house.connection)

        # Turn one: the table exists and holds a real value.
        space.define("range", SOURCE, parameters={"from": "2026-05-01"})
        space.record(
            "konut_stok",
            COLUMN,
            self.compute(house, self.series_sql("2026-05-31")),
            parameters={"series": "bddk:konut"},
            inputs=["range"],
        )
        space.define("tablo", TABLE, inputs=["konut_stok"])
        assert space.value_of("konut_stok").samples.used == 2

        # Turn two: widen the range. The table must not be readable as if
        # nothing happened, and the column must not be refreshable without
        # actually recomputing it.
        space.define("range", SOURCE, parameters={"from": "2026-04-01"})
        assert space.stale() == {"konut_stok", "tablo"}
        with pytest.raises(WorkspaceError, match="is stale"):
            space.value_of("konut_stok")
        with pytest.raises(WorkspaceError, match="Supply a recomputer"):
            space.refresh("konut_stok")

        for name in space.refresh_order():
            if name == "konut_stok":
                space.refresh(name, lambda a, i: self.compute(house, self.series_sql("2026-04-30")))
            else:
                space.refresh(name)
        assert space.stale() == set()
        assert space.value_of("konut_stok").samples.used == 3

        # Turn three: add a column without disturbing the table's identity.
        before = space.resolve("konut_stok").artifact_id
        space.record(
            "konut_faiz",
            COLUMN,
            self.compute(house, self.series_sql("2026-04-30")),
            parameters={"series": "evds:TP.KTF12"},
            inputs=["range"],
        )
        space.define("tablo", TABLE, inputs=["konut_stok", "konut_faiz"])

        assert space.resolve("konut_stok").artifact_id == before
        assert space.stale() == set()
        assert set(space.values()) == {"konut_stok", "konut_faiz"}

    def test_what_the_table_said_before_the_change_is_still_answerable(self, house):
        space = Workspace.open(house.connection)
        space.define("range", SOURCE, parameters={"from": "2026-05-01"})
        space.record(
            "konut_stok",
            COLUMN,
            self.compute(house, self.series_sql("2026-05-31")),
            inputs=["range"],
        )
        first = space.resolve("konut_stok").value_ref

        space.define("range", SOURCE, parameters={"from": "2026-04-01"})
        space.refresh("konut_stok", lambda a, i: self.compute(house, self.series_sql("2026-04-30")))

        assert space.read_result(first).samples.used == 2
        assert len(space.history("konut_stok")) == 2
