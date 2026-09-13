"""M12-13/14 regressions for gold tables and the lineage graph.

The end-to-end case is the reference scenario's own shape: a monthly BDDK stock
beside a weekly EVDS rate reduced onto the same spine, with every resulting cell
traceable back to the bytes it came from.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from kkb_agent.core import (
    Aggregation,
    CumulativeKind,
    Frequency,
    Scale,
    SourceRef,
    StockFlow,
    WeeklyAnchor,
)
from kkb_agent.lakehouse import (
    EdgeKind,
    GoldError,
    LineageError,
    NodeKind,
    Observation,
    SeriesSemantics,
    WeekAssignment,
    build_gold,
    missing_provenance,
    node_id,
    open_lakehouse,
    period_bounds,
    persist_gold,
    to_monthly,
)

NOW = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)
MONTHLY = Frequency.MONTHLY
FRIDAY = WeeklyAnchor.FRIDAY
JAN, FEB, MAR = date(2023, 1, 31), date(2023, 2, 28), date(2023, 3, 31)

# BDDK monthly housing-credit stock, real published values (million TRY).
KONUT_STOCK = {JAN: 362695.0, FEB: 367891.0, MAR: 391782.0}
# Weekly Friday rate observations, real cadence from the EVDS inspection.
WEEKLY_RATE = [
    (date(2023, 1, 6), 46.750),
    (date(2023, 1, 13), 48.088),
    (date(2023, 1, 20), 49.588),
    (date(2023, 1, 27), 50.933),
    (date(2023, 2, 3), 51.696),
    (date(2023, 2, 10), 50.007),
    (date(2023, 2, 17), 49.209),
    (date(2023, 2, 24), 49.190),
    (date(2023, 3, 3), 50.078),
    (date(2023, 3, 10), 50.316),
    (date(2023, 3, 17), 52.958),
    (date(2023, 3, 24), 53.358),
    (date(2023, 3, 31), 52.175),
]

STOCK_SEMANTICS = SeriesSemantics(
    unit="TRY",
    scale=Scale.MILLION,
    frequency=MONTHLY,
    observation=StockFlow.STOCK,
    cumulative=CumulativeKind.NONE,
    aggregation=Aggregation.LAST,
)


@pytest.fixture
def house(tmp_path):
    with open_lakehouse(tmp_path / "lake") as lake:
        yield lake


def source(name):
    return SourceRef(source_id=name, source_type="http-json", locator=f"opaque:{name}")


def seed_source(lake, name, payload):
    """Record bytes in bronze and give them a lineage node."""
    artifact = lake.record_artifact(
        payload, source=source(name), media_type="application/json", recorded_at=NOW
    )
    node = lake.lineage.record(
        NodeKind.SOURCE_FILE,
        name,
        attributes={"artifact_id": artifact.artifact_id, "byte_count": str(artifact.byte_count)},
    )
    return artifact, node


def monthly_observations(values):
    return [Observation(date(end.year, end.month, 1), end, value) for end, value in values.items()]


def weekly_observations():
    out = []
    for end, value in WEEKLY_RATE:
        start, _ = period_bounds(Frequency.WEEKLY, end, anchor=FRIDAY)
        out.append(Observation(start, end, value))
    return out


class TestLineageIsContentAddressed:
    def test_the_same_derivation_lands_on_one_node(self, house):
        _, first = seed_source(house, "bddk", b"payload")
        second = house.lineage.record(
            NodeKind.SOURCE_FILE,
            "bddk",
            attributes=house.lineage.node(first).attributes,
        )
        assert second == first
        assert house.connection.execute("SELECT count(*) FROM lineage_nodes").fetchone()[0] == 1

    def test_different_inputs_give_different_ids(self):
        base = node_id(NodeKind.COLUMN, "rate", {"table_id": "t"}, ["a"])
        assert base != node_id(NodeKind.COLUMN, "rate", {"table_id": "t"}, ["b"])
        assert base != node_id(NodeKind.COLUMN, "rate", {"table_id": "u"}, ["a"])
        assert base != node_id(NodeKind.METRIC, "rate", {"table_id": "t"}, ["a"])

    def test_id_does_not_depend_on_ordering(self):
        assert node_id(NodeKind.COLUMN, "c", {"a": "1", "b": "2"}, ["x", "y"]) == node_id(
            NodeKind.COLUMN, "c", {"b": "2", "a": "1"}, ["y", "x"]
        )

    def test_an_edge_to_a_missing_node_is_refused(self, house):
        # An edge that leads nowhere looks like provenance and is worse than none.
        with pytest.raises(LineageError, match="does not exist"):
            house.lineage.record(NodeKind.SERIES, "s", upstream=[("0" * 64, EdgeKind.DERIVES_FROM)])

    def test_a_node_needs_a_label(self, house):
        with pytest.raises(LineageError, match="needs a label"):
            house.lineage.record(NodeKind.SERIES, "   ")


class TestTracing:
    def test_a_chain_resolves_to_its_source(self, house):
        _, origin = seed_source(house, "bddk", b"payload")
        series = house.lineage.record(
            NodeKind.SERIES, "konut", upstream=[(origin, EdgeKind.DERIVES_FROM)]
        )
        transform = house.lineage.record(
            NodeKind.TRANSFORM, "align", upstream=[(series, EdgeKind.AGGREGATES)]
        )
        claim = house.lineage.record(
            NodeKind.CLAIM, "konut rose in March", upstream=[(transform, EdgeKind.CITES)]
        )
        trace = [node.node_id for node in house.lineage.trace(claim)]
        assert trace == [transform, series, origin]
        assert [node.label for node in house.lineage.sources_of(claim)] == ["bddk"]

    def test_a_node_with_no_ancestors_has_no_provenance(self, house):
        orphan = house.lineage.record(NodeKind.METRIC, "invented")
        assert not house.lineage.has_provenance(orphan)
        assert missing_provenance(house.lineage, [orphan]) == [orphan]

    def test_tracing_an_unknown_node_is_refused(self, house):
        with pytest.raises(LineageError, match="No lineage node"):
            house.lineage.trace("0" * 64)

    def test_a_diamond_reports_each_ancestor_once(self, house):
        _, origin = seed_source(house, "bddk", b"payload")
        left = house.lineage.record(
            NodeKind.SERIES, "left", upstream=[(origin, EdgeKind.DERIVES_FROM)]
        )
        right = house.lineage.record(
            NodeKind.SERIES, "right", upstream=[(origin, EdgeKind.DERIVES_FROM)]
        )
        merged = house.lineage.record(
            NodeKind.COLUMN,
            "merged",
            upstream=[(left, EdgeKind.DERIVES_FROM), (right, EdgeKind.DERIVES_FROM)],
        )
        trace = house.lineage.trace(merged)
        assert len(trace) == 3
        assert sum(node.node_id == origin for node in trace) == 1


class TestGoldPlacesSeriesOnOneSpine:
    def build(self, house, columns=None, **kwargs):
        _, origin = seed_source(house, "bddk", b"payload")
        series = house.lineage.record(
            NodeKind.SERIES, "konut", upstream=[(origin, EdgeKind.DERIVES_FROM)]
        )
        defaults = dict(
            frequency=MONTHLY,
            first_end=JAN,
            last_end=MAR,
            lineage=house.lineage,
            upstream={"konut": [(series, EdgeKind.DERIVES_FROM)]},
        )
        defaults.update(kwargs)
        return build_gold(
            "housing",
            columns if columns is not None else {"konut": monthly_observations(KONUT_STOCK)},
            **defaults,
        )

    def test_values_land_on_their_periods(self, house):
        table = self.build(house)
        assert table.row(MAR)["konut"] == pytest.approx(391782.0)
        assert [end for _, end in table.periods] == [JAN, FEB, MAR]

    def test_a_period_the_source_never_published_is_null_not_filled(self, house):
        thinned = {end: value for end, value in KONUT_STOCK.items() if end != FEB}
        table = self.build(house, {"konut": monthly_observations(thinned)})
        assert table.row(FEB)["konut"] is None
        assert table.columns["konut"].observed == 2
        assert table.columns["konut"].expected == 3
        assert table.incomplete_columns() == ["konut"]

    def test_an_explicitly_missing_value_is_also_null(self, house):
        blanked = {**KONUT_STOCK, FEB: None}
        table = self.build(house, {"konut": monthly_observations(blanked)})
        assert table.row(FEB)["konut"] is None
        assert table.columns["konut"].observed == 2

    def test_an_observation_off_the_spine_is_refused(self, house):
        stray = monthly_observations(KONUT_STOCK) + [
            Observation(date(2023, 4, 1), date(2023, 4, 30), 1.0)
        ]
        with pytest.raises(GoldError, match="off the table's spine"):
            self.build(house, {"konut": stray})

    def test_a_column_without_upstream_lineage_is_refused(self, house):
        with pytest.raises(GoldError, match="untraceable"):
            self.build(house, upstream={})

    def test_a_table_needs_a_column(self, house):
        with pytest.raises(GoldError, match="at least one column"):
            self.build(house, {})

    def test_duplicate_periods_are_refused(self, house):
        doubled = monthly_observations(KONUT_STOCK) + monthly_observations({MAR: 1.0})
        with pytest.raises(GoldError, match="duplicate periods"):
            self.build(house, {"konut": doubled})

    def test_the_column_node_records_its_coverage(self, house):
        table = self.build(house)
        attributes = house.lineage.node(table.columns["konut"].node_id).attributes
        assert attributes["observed"] == "3"
        assert attributes["expected"] == "3"
        assert attributes["first_period"] == JAN.isoformat()


class TestTheReferenceScenarioSlice:
    """A monthly stock and a weekly rate, on one spine, fully traceable."""

    def assemble(self, house):
        stock_artifact, stock_source = seed_source(house, "bddk-aylik-4", b'{"konut":362695}')
        rate_artifact, rate_source = seed_source(house, "evds-tp-ktf12", b'{"rate":"46,750"}')

        house.register_series(
            "bddk:konut",
            title="Tüketici Kredileri - Konut",
            semantics=STOCK_SEMANTICS,
            artifact_id=stock_artifact.artifact_id,
        )
        stock_series = house.lineage.record(
            NodeKind.SERIES, "bddk:konut", upstream=[(stock_source, EdgeKind.DERIVES_FROM)]
        )
        rate_series = house.lineage.record(
            NodeKind.SERIES, "evds:TP.KTF12", upstream=[(rate_source, EdgeKind.DERIVES_FROM)]
        )

        alignment = to_monthly(
            weekly_observations(),
            requested_start=date(JAN.year, JAN.month, 1),
            requested_end=MAR,
            frequency=Frequency.WEEKLY,
            aggregation=Aggregation.AVERAGE,
            anchor=FRIDAY,
            assignment=WeekAssignment.BY_END,
        )
        # The reduction is a node in its own right, carrying the parameters that
        # make it reproducible.
        rate_transform = house.lineage.record(
            NodeKind.TRANSFORM,
            "align_weekly_to_monthly",
            attributes=alignment.method,
            upstream=[(rate_series, EdgeKind.AGGREGATES)],
        )

        table = build_gold(
            "housing_credit_vs_rate",
            {"konut_stok": monthly_observations(KONUT_STOCK), "konut_faiz": alignment.observations},
            frequency=MONTHLY,
            first_end=JAN,
            last_end=MAR,
            lineage=house.lineage,
            upstream={
                "konut_stok": [(stock_series, EdgeKind.DERIVES_FROM)],
                "konut_faiz": [(rate_transform, EdgeKind.DERIVES_FROM)],
            },
        )
        return table, alignment

    def test_both_series_share_the_spine(self, house):
        table, _ = self.assemble(house)
        march = table.row(MAR)
        assert march["konut_stok"] == pytest.approx(391782.0)
        assert march["konut_faiz"] == pytest.approx(258.885 / 5)
        assert table.incomplete_columns() == []

    def test_every_column_traces_back_to_bytes(self, house):
        table, _ = self.assemble(house)
        assert missing_provenance(house.lineage, [c.node_id for c in table.columns.values()]) == []
        for column in table.columns.values():
            sources = house.lineage.sources_of(column.node_id)
            assert len(sources) == 1
            assert sources[0].attributes["artifact_id"]

    def test_the_rate_column_carries_its_reduction_method(self, house):
        table, alignment = self.assemble(house)
        trace = house.lineage.trace(table.columns["konut_faiz"].node_id)
        transform = next(node for node in trace if node.kind is NodeKind.TRANSFORM)
        assert transform.attributes == alignment.method
        assert transform.attributes["aggregation"] == "average"

    def test_the_stock_column_has_no_reduction(self, house):
        table, _ = self.assemble(house)
        trace = house.lineage.trace(table.columns["konut_stok"].node_id)
        assert not any(node.kind is NodeKind.TRANSFORM for node in trace)

    def test_a_persisted_cell_carries_its_lineage_id(self, house):
        table, _ = self.assemble(house)
        assert persist_gold(house.connection, table) == 6
        value, node = house.connection.execute(
            "SELECT value, column_node_id FROM gold_cells"
            " WHERE table_id = ? AND column_name = ? AND period_end = ?",
            ["housing_credit_vs_rate", "konut_stok", MAR],
        ).fetchone()
        assert value == pytest.approx(391782.0)
        assert house.lineage.has_provenance(str(node))

    def test_the_artifact_behind_a_cell_is_still_readable(self, house):
        table, _ = self.assemble(house)
        sources = house.lineage.sources_of(table.columns["konut_stok"].node_id)
        payload = house.read_artifact(sources[0].attributes["artifact_id"])
        assert payload == b'{"konut":362695}'
