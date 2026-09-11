"""M8 regressions for the verifier and the query's lineage record.

The chain these close: a query runs, the run is recorded, and no number reaches
the user without a stored cell behind it.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from kkb_agent.agent import (
    ExecutionContext,
    NumberBinding,
    ToolRegistry,
    ToolStatus,
    extract_numbers,
    parse_written,
    verify,
)
from kkb_agent.core import (
    Aggregation,
    CumulativeKind,
    Frequency,
    Scale,
    SourceRef,
    StockFlow,
)
from kkb_agent.lakehouse import (
    EdgeKind,
    NodeKind,
    Observation,
    SeriesSemantics,
    build_gold,
    open_lakehouse,
    persist_gold,
)
from kkb_agent.tools import LakehouseArguments, make_lakehouse_tool

NOW = datetime(2026, 9, 9, tzinfo=UTC)
SEMANTICS = SeriesSemantics(
    unit="TRY",
    scale=Scale.MILLION,
    frequency=Frequency.MONTHLY,
    observation=StockFlow.STOCK,
    cumulative=CumulativeKind.NONE,
    aggregation=Aggregation.LAST,
)
PUBLISHED = {
    date(2026, 4, 30): 767314.0,
    date(2026, 5, 31): 782918.0,
    date(2026, 6, 30): 801438.0,
}


@pytest.fixture
def house(tmp_path):
    with open_lakehouse(tmp_path / "lake") as lake:
        artifact = lake.record_artifact(
            b'{"konut": 801438}',
            source=SourceRef(source_id="bddk", source_type="http-json", locator="opaque:t4"),
            media_type="application/json",
            recorded_at=NOW,
        )
        origin = lake.lineage.record(
            NodeKind.SOURCE_FILE, "bddk", attributes={"artifact_id": artifact.artifact_id}
        )
        series = lake.lineage.record(
            NodeKind.SERIES, "bddk:konut", upstream=[(origin, EdgeKind.DERIVES_FROM)]
        )
        lake.register_series(
            "bddk:konut", title="Konut", semantics=SEMANTICS, artifact_id=artifact.artifact_id
        )
        observations = [
            Observation(date(end.year, end.month, 1), end, value)
            for end, value in PUBLISHED.items()
        ]
        lake.append_observations("bddk:konut", observations)
        table = build_gold(
            "konut",
            {"konut_stok": observations},
            frequency=Frequency.MONTHLY,
            first_end=date(2026, 4, 30),
            last_end=date(2026, 6, 30),
            lineage=lake.lineage,
            upstream={"konut_stok": [(series, EdgeKind.DERIVES_FROM)]},
        )
        persist_gold(lake.connection, table)
        yield lake


class TestReadingNumbersAsWritten:
    @pytest.mark.parametrize(
        ("written", "expected"),
        [
            ("801.438", 801438.0),  # Turkish thousands
            ("801,438", 801438.0),  # English thousands, same quantity
            ("46,75", 46.75),  # Turkish decimal
            ("46.75", 46.75),  # English decimal
            ("1.234.567", 1234567.0),
            ("1,234,567.89", 1234567.89),
            ("1.234.567,89", 1234567.89),
            ("0,5", 0.5),
            ("-12,5", -12.5),
            ("42", 42.0),
            ("801438", 801438.0),  # unformatted, longer than one group
            ("2021", 2021.0),
        ],
    )
    def test_both_conventions_parse(self, written, expected):
        assert parse_written(written) == pytest.approx(expected)

    def test_a_thousandfold_misreading_would_change_the_value(self):
        # The failure this guards against: 801.438 read as a decimal is 801.438,
        # not 801,438 — the same mistake the EVDS response format invites.
        assert parse_written("801.438") == 801438.0
        assert parse_written("801.4") == 801.4

    def test_malformed_grouping_is_refused_rather_than_guessed(self):
        assert parse_written("1.23.456") is None
        assert parse_written("12.34,567") is None

    def test_identifiers_are_not_read_as_quantities(self):
        assert extract_numbers("Seri TP.KTF12 kullanıldı") == []

    def test_a_long_unformatted_number_is_still_found(self):
        # Without the plain alternative this matched nothing, and a number the
        # verifier never sees is a number it never checks.
        assert [item.value for item in extract_numbers("Stok 801438 milyon TL")] == [801438.0]

    def test_numbers_are_found_in_order_with_their_text(self):
        found = extract_numbers("Haziran'da 801.438 milyon TL, faiz %46,75")
        assert [item.text for item in found] == ["801.438", "46,75"]
        assert [item.value for item in found] == [801438.0, 46.75]


class TestEveryNumberNeedsACell:
    def test_a_supported_answer_is_accepted(self, house):
        verdict = verify("Haziran 2026'da konut kredisi stoğu 801.438 milyon TL.", house.connection)
        assert verdict.accepted
        # The year is bound as a year; the figure is bound to its cell.
        bindings = {item.number.value: item.binding for item in verdict.numbers}
        assert bindings == {2026.0: NumberBinding.YEAR, 801438.0: NumberBinding.CELL}
        cell = next(item for item in verdict.numbers if item.binding is NumberBinding.CELL)
        assert cell.source == "konut.konut_stok"

    def test_an_invented_number_rejects_the_answer(self, house):
        verdict = verify("Konut kredisi stoğu 999.999 milyon TL.", house.connection)
        assert not verdict.accepted
        assert [item.text for item in verdict.unbound] == ["999.999"]
        assert "does not match any stored value" in verdict.rejected[0]

    def test_one_bad_number_rejects_an_otherwise_correct_answer(self, house):
        verdict = verify(
            "Mayıs 782.918, Haziran 801.438, Temmuz 850.000 milyon TL.", house.connection
        )
        assert not verdict.accepted
        assert [item.text for item in verdict.unbound] == ["850.000"]

    def test_presentation_rounding_is_tolerated(self, house):
        # 801438.0 written as 801.438,0 is the same figure.
        assert verify("Stok 801.438,0 milyon TL.", house.connection).accepted

    def test_a_scale_slip_is_not_tolerated(self, house):
        # "801,44 milyar" is 801.44, which no cell holds. The stored figure is
        # 801438 million; writing it as billions without converting is exactly
        # the scale error the silver layer exists to prevent.
        assert not verify("Stok 801,44 milyar TL.", house.connection).accepted

    def test_a_year_does_not_need_a_cell(self, house):
        verdict = verify("2021-2025 arasında stok 801.438'e ulaştı.", house.connection)
        assert verdict.accepted
        assert [item.binding for item in verdict.numbers[:2]] == [
            NumberBinding.YEAR,
            NumberBinding.YEAR,
        ]

    def test_year_recognition_can_be_switched_off(self, house):
        assert not verify("2021 yılında.", house.connection, accept_years=False).accepted

    def test_a_caller_justified_number_is_accepted_as_context(self, house):
        verdict = verify("60 aylık dönem incelendi.", house.connection, allowed=[60])
        assert verdict.accepted
        assert verdict.numbers[0].binding is NumberBinding.CONTEXT

    def test_a_silver_observation_also_counts(self, house):
        verdict = verify("Nisan değeri 767.314.", house.connection)
        assert verdict.accepted
        assert verdict.numbers[-1].binding in {NumberBinding.CELL, NumberBinding.OBSERVATION}

    def test_an_answer_with_no_numbers_is_accepted(self, house):
        verdict = verify("Veri bu soruyu desteklemiyor.", house.connection)
        assert verdict.accepted and verdict.numbers == ()


class TestTheVerdictCarriesItsEvidenceAndItsLimits:
    def test_a_bound_number_names_the_lineage_node_behind_it(self, house):
        verdict = verify("Stok 801.438.", house.connection)
        nodes = verdict.lineage_nodes()
        assert len(nodes) == 1
        # And that node really does reach the bytes.
        assert house.lineage.has_provenance(nodes[0])

    def test_the_verdict_states_what_it_did_not_check(self, house):
        verdict = verify("Stok 801.438.", house.connection)
        joined = " ".join(verdict.limitations)
        assert "second-path recomputation" in joined
        assert "external cross-check" in joined


class TestSourceBackedQueriesReceiveLineage:
    sql = (
        "SELECT o.series_id, o.period_start, o.period_end, o.value, s.unit, s.scale"
        " FROM silver_observations o JOIN silver_series s ON s.series_id = o.series_id"
        " ORDER BY o.period_end"
    )

    def registry(self, house, lineage=True):
        registry = ToolRegistry()
        registry.register(
            make_lakehouse_tool(house.connection, lineage=house.lineage if lineage else None)
        )
        return registry

    def run(self, house, sql, lineage=True):
        spec = self.registry(house, lineage).get("lakehouse")
        return spec.run(LakehouseArguments(sql=sql, purpose="test"), ExecutionContext(question="q"))

    def test_a_successful_query_produces_a_transform_node(self, house):
        result = self.run(house, self.sql)
        assert result.status is ToolStatus.SUCCESS
        assert result.evidence is not None
        node = house.lineage.node(result.evidence)
        assert node.kind is NodeKind.TRANSFORM
        assert node.label == "lakehouse_query"

    def test_the_node_records_the_statement_and_what_it_read(self, house):
        node = house.lineage.node(self.run(house, self.sql).evidence)
        assert node.attributes["tables"] == "silver_observations, silver_series"
        assert len(node.attributes["sql_sha256"]) == 64
        assert node.attributes["rows"] == "3"
        assert (
            node.attributes["columns"] == "series_id, period_start, period_end, value, unit, scale"
        )

    def test_the_record_is_honest_about_its_granularity(self, house):
        node = house.lineage.node(self.run(house, self.sql).evidence)
        assert "table-level" in node.attributes["provenance"]

    def test_the_same_query_records_one_node(self, house):
        first = self.run(house, self.sql).evidence
        second = self.run(house, self.sql).evidence
        assert first == second

    def test_a_different_query_records_a_different_node(self, house):
        first = self.run(house, self.sql).evidence
        second = self.run(house, self.sql + " LIMIT 1").evidence
        assert first != second

    def test_a_rejected_query_records_nothing(self, house):
        before = house.connection.execute("SELECT count(*) FROM lineage_nodes").fetchone()[0]
        result = self.run(house, "SELECT * FROM lineage_nodes")
        assert result.status is ToolStatus.FAILURE
        assert result.evidence is None
        after = house.connection.execute("SELECT count(*) FROM lineage_nodes").fetchone()[0]
        assert after == before

    def test_lineage_is_optional(self, house):
        assert self.run(house, self.sql, lineage=False).evidence is None


class TestTheChainEndToEnd:
    def test_a_query_answers_and_the_answer_verifies_back_to_bytes(self, house):
        registry = ToolRegistry()
        registry.register(make_lakehouse_tool(house.connection, lineage=house.lineage))

        result = registry.get("lakehouse").run(
            LakehouseArguments(
                sql="SELECT max(value) FROM gold_cells", purpose="latest housing credit"
            ),
            ExecutionContext(question="Haziran'da konut kredisi stoğu neydi?"),
        )
        assert result.status is ToolStatus.SUCCESS
        value = result.output.table.rows[0][0]

        answer = f"Haziran 2026'da konut kredisi stoğu {value:,.0f} milyon TL.".replace(",", ".")
        verdict = verify(answer, house.connection)

        assert verdict.accepted
        node = verdict.lineage_nodes()[0]
        sources = house.lineage.sources_of(node)
        payload = house.read_artifact(sources[0].attributes["artifact_id"])
        assert payload == b'{"konut": 801438}'
