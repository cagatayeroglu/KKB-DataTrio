"""Source-bound BIST index-close semantics; a generic JSON field stays unknown."""

import json
from datetime import UTC, date, datetime

import pytest

from kkb_agent.core import Scale, StockFlow
from kkb_agent.ingest.bist_index_semantics import bist_index_close_metrics
from kkb_agent.ingest.fetched import fetched_source
from kkb_agent.ingest.json_table import load_records
from kkb_agent.tools._document_column import ColumnRefused
from kkb_agent.tools._document_table import read_daily_table, table_result, table_snapshot
from kkb_agent.tools._document_value import grids


def source_case(code: str = "XTUMY"):
    host = "https://www.borsaistanbul.com"
    page = f"{host}/endeks/{code.lower()}"
    endpoint = f"{host}/graphic.php?veriTuru=endeks-graphic&indexCode={code}"
    payload = json.dumps(
        {
            "data": [
                {"indexName": code, "clval": value, "hisTs": day}
                for day, value in (("2026-01-30", 1000.0), ("2026-02-27", 1050.0))
            ]
        }
    ).encode()
    return page, endpoint, payload, load_records(payload)


@pytest.mark.parametrize("code", ["XTUMY", "XU100"])
def test_reviewed_close_mapping_is_typed_and_bound_to_existing_proof(code):
    page, endpoint, payload, records = source_case(code)
    mapping = bist_index_close_metrics(page, endpoint, records)
    assert mapping["clval"].unit == "index_points"
    assert mapping["clval"].scale is Scale.ONE
    assert mapping["clval"].measure is StockFlow.INDEX
    table = read_daily_table(
        grids(records, None),
        "hisTs",
        ["clval"],
        rule="last",
        as_of=date(2026, 3, 1),
        reviewed_metrics=mapping,
    )
    column = table.columns[0]
    assert (column.unit, column.scale, column.measure) == (
        "index_points",
        Scale.ONE,
        StockFlow.INDEX,
    )
    assert column.unit_source == f"reviewed Borsa Istanbul {code} index-close mapping"
    source = fetched_source(endpoint, payload, retrieved_at=datetime(2026, 3, 1, tzinfo=UTC))
    result = table_result(table, source, source_node="source-node")
    assert result.evidence is not None
    assert result.evidence.sources == [source]
    assert result.evidence.input_refs == ["source-node"]
    assert result.evidence.transformations[0].parameters["columns"][0]["unit_source"] == (
        column.unit_source
    )
    assert '"unit_source":"reviewed Borsa Istanbul' in table_snapshot(
        table, source, "application/json"
    )
    assert not result.unresolved_semantics
    with pytest.raises(ColumnRefused, match="NO_USABLE_COLUMN"):
        read_daily_table(
            grids(records, None),
            "hisTs",
            ["clval"],
            rule="last",
            as_of=date(2026, 3, 1),
            reviewed_metrics=mapping,
            declared_units={"clval": ("TRY", Scale.ONE)},
        )


@pytest.mark.parametrize(
    ("page", "endpoint_change", "code_change"),
    [
        ("https://example.test/endeks/xtumy", None, None),
        ("https://www.borsaistanbul.com/endeks/other", None, None),
        ("http://www.borsaistanbul.com/endeks/xtumy", None, None),
        (None, "https://other.test/graphic.php?veriTuru=endeks-graphic&indexCode=XTUMY", None),
        (None, "https://www.borsaistanbul.com/graphic.php?indexCode=XTUMY", None),
        (None, None, "XU100"),
    ],
)
def test_clval_name_or_spoofed_source_cannot_create_index_metadata(
    page, endpoint_change, code_change
):
    original_page, endpoint, _, records = source_case()
    if code_change is not None:
        changed = json.dumps(
            {
                "data": [
                    {"indexName": code_change, "clval": n, "hisTs": day}
                    for n, day in ((1, "2026-01-30"), (2, "2026-02-27"))
                ]
            }
        ).encode()
        records = load_records(changed)
    assert (
        bist_index_close_metrics(page or original_page, endpoint_change or endpoint, records) == {}
    )


def test_generic_clval_column_stays_unknown():
    _, _, _, records = source_case()
    table = read_daily_table(
        grids(records, None),
        "hisTs",
        ["clval"],
        rule="last",
        as_of=date(2026, 3, 1),
        reviewed_metrics={},
    )
    column = table.columns[0]
    assert column.unit is None and column.scale is Scale.UNKNOWN
    assert column.measure is StockFlow.UNKNOWN
