"""DEC-175: `lakehouse` reads catalogue series by identity; the tool writes the SELECT.

Live K1 (2026-09-19) spent 5,800 reasoning tokens and 853 s on a two-step plan, almost all of
it on how a free SELECT becomes a table: which columns, how the value column is labelled,
whether an alias is a projection. Named identities also let the discovery rule see what a
read names, and let a reviewed series the store lacks be fetched before it is read.
"""

from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError
from test_catalog_continuation import CATALOG, proposal, seed_prepared
from test_co_movement import TOTAL_ID
from test_co_movement import lake as lake  # noqa: F401 - the pool fixture builds on it
from test_official_acquisition import HOUSE_PRICES, TODAY, FakeSource
from test_same_plan_tables import registry_for
from test_turn_two import CPI_ID
from test_turn_two import pool as pool  # noqa: F401

from kkb_agent.agent import AnalyticalPlan, ExecutionContext, ToolStatus, validate_plan
from kkb_agent.agent.discovery import needs_series_discovery
from kkb_agent.api.prepared import PreparedRunner, open_lakehouse
from kkb_agent.catalog.inspection import PreparedSeriesInspector
from kkb_agent.catalog.mappings import load_reviewed_snapshot
from kkb_agent.core import ResultStatus, declared_series_identities
from kkb_agent.ingest.acquisition import AcquiringInspector, OfficialSources, TurnAcquirer
from kkb_agent.llm import scripted
from kkb_agent.tools import make_lakehouse_tool
from kkb_agent.tools.change_detection import ChangeDetectionArguments
from kkb_agent.tools.lakehouse import LakehouseRequest, SeriesRead

CONTEXT = ExecutionContext(question="seriyi getir")


@pytest.fixture
def seed_pool(tmp_path):
    """The prepared seed, which does not hold the house price index."""
    root = tmp_path / "prepared"
    seed_prepared(root)
    return root


def read(*series, **window):
    return {
        "step_id": "fetch",
        "tool": "lakehouse",
        "arguments": {"series": list(series), **window},
    }


def run(tool, arguments):
    return tool.run(tool.parse(arguments), CONTEXT)


def test_a_typed_read_returns_what_the_direct_select_returns(pool):  # noqa: F811
    lake_, _ = pool
    tool = make_lakehouse_tool(lake_.connection, lineage=lake_.lineage)
    typed = run(tool, {"series": [CPI_ID], "start": "2021-02-01", "end": "2021-05-31"})
    assert typed.status is ToolStatus.SUCCESS, typed.warnings
    result = typed.output.result
    assert result.status is ResultStatus.COMPUTED and len(result.values) == 4
    assert {value.label for value in result.values} == {CPI_ID}
    written = run(
        tool,
        {
            "sql": "SELECT o.series_id, o.period_start, o.period_end, o.value "
            f"FROM silver_observations o WHERE o.series_id = '{CPI_ID}' "
            "AND o.period_end BETWEEN DATE '2021-02-01' AND DATE '2021-05-31' "
            "ORDER BY o.period_end"
        },
    )
    assert [(v.period, v.value, v.unit, v.scale) for v in result.values] == [
        (v.period, v.value, v.unit, v.scale) for v in written.output.result.values
    ]


def test_several_series_become_one_table_labelled_by_identity(pool):  # noqa: F811
    lake_, _ = pool
    tool = make_lakehouse_tool(lake_.connection, lineage=lake_.lineage)
    both = run(tool, {"series": [TOTAL_ID, CPI_ID], "start": "2021-01-01", "end": "2021-06-30"})
    assert both.status is ToolStatus.SUCCESS, both.warnings
    labels = [value.label for value in both.output.result.values]
    assert labels.count(TOTAL_ID) == labels.count(CPI_ID) == 6


@pytest.mark.parametrize(
    "arguments",
    [
        {"series": [CPI_ID], "sql": "SELECT 1"},  # one way or the other, never both
        {"series": []},
        {"series": [CPI_ID, CPI_ID]},
        {"series": ["x' OR '1'='1"]},  # an identity cannot carry a quote
        {"series": [CPI_ID], "start": "2022-01-01", "end": "2021-01-01"},
    ],
)
def test_malformed_reads_are_refused_before_any_query(pool, arguments):  # noqa: F811
    lake_, _ = pool
    tool = make_lakehouse_tool(lake_.connection)
    with pytest.raises((ValidationError, ValueError)):
        tool.parse(arguments)


def test_the_statement_is_the_canonical_direct_column_select():
    statement = SeriesRead(series=["EVDS:TP.KTF12"], start=date(2024, 1, 1)).statement()
    assert statement == (
        "SELECT o.series_id, o.period_start, o.period_end, o.value FROM silver_observations o "
        "WHERE o.series_id IN ('EVDS:TP.KTF12') AND o.period_end >= DATE '2024-01-01' "
        "ORDER BY o.series_id, o.period_end"
    )


def test_a_series_the_catalogue_refuses_is_named_with_its_reason(pool):  # noqa: F811
    lake_, _ = pool
    inspector = PreparedSeriesInspector(load_reviewed_snapshot(CATALOG.read_bytes()))
    tool = make_lakehouse_tool(lake_.connection, inspector=inspector)
    refused = run(tool, {"series": [CPI_ID, "EVDS:TP.KFE.TR10", "EVDS:NOT.A.SERIES"]})
    assert refused.status is ToolStatus.FAILURE and refused.error_category == "series_unknown"
    (reason,) = refused.warnings
    assert "EVDS:TP.KFE.TR10: unresolved_catalog" in reason
    assert "EVDS:NOT.A.SERIES: unknown_identity" in reason and CPI_ID not in reason


def test_a_reviewed_series_the_store_lacks_is_fetched_before_it_is_read(seed_pool):
    """As SQL this read could only ever return no rows: nothing named the series to fetch."""
    source = FakeSource()
    with open_lakehouse(seed_pool) as opened:
        inspector = AcquiringInspector(
            PreparedSeriesInspector(load_reviewed_snapshot(CATALOG.read_bytes())),
            TurnAcquirer(opened, TODAY, sources=OfficialSources(evds=source)),
        )
        tool = make_lakehouse_tool(opened.connection, inspector=inspector)
        fetched = run(tool, {"series": [HOUSE_PRICES], "start": "2021-01-01", "end": "2021-06-30"})
        assert fetched.status is ToolStatus.SUCCESS, fetched.warnings
        assert len(source.requests) == 1
        assert len(fetched.output.result.values) == 6


def test_the_discovery_rule_sees_what_a_typed_read_names(pool):  # noqa: F811
    registry = registry_for(pool)

    def needs(step, proven):
        plan = AnalyticalPlan.model_validate({"question": "q", "steps": [step]})
        return needs_series_discovery(
            validate_plan(plan, registry, budget=SimpleNamespace(max_steps=12)), proven
        )

    assert needs(read(CPI_ID), frozenset()) is True
    assert needs(read(CPI_ID), frozenset({CPI_ID})) is False
    assert needs(read(CPI_ID, TOTAL_ID), frozenset({CPI_ID})) is True
    # SQL can name anything, so it never qualifies, proven or not.
    written = {"step_id": "fetch", "tool": "lakehouse", "arguments": {"sql": "SELECT 1"}}
    assert needs(written, frozenset({CPI_ID})) is True


def test_identities_inside_a_union_or_a_list_are_declared():
    request = LakehouseRequest.model_validate({"series": ["EVDS:TP.KTF12", "EVDS:TP.KFE.TR"]})
    assert declared_series_identities(request) == {"EVDS:TP.KTF12", "EVDS:TP.KFE.TR"}
    assert declared_series_identities(LakehouseRequest.model_validate({"sql": "SELECT 1"})) is None
    # An optional identity used to go uncounted: only the outer annotation was read.
    paired = ChangeDetectionArguments.model_validate(
        {
            "operation": "co_movement",
            "series_id": "EVDS:TP.KTF12",
            "driver_series_id": "EVDS:TP.KFE.TR",
            "start": "2021-01-01",
            "end": "2021-12-31",
        }
    )
    assert declared_series_identities(paired) == {"EVDS:TP.KTF12", "EVDS:TP.KFE.TR"}


def test_a_served_turn_reads_a_series_outside_the_pool_by_identity(seed_pool, tmp_path):
    source = FakeSource()
    runner = PreparedRunner(
        scripted(
            proposal(
                {
                    "step_id": "d",
                    "tool": "catalog_search",
                    "arguments": {"query": "konut fiyat endeksi"},
                }
            ),
            proposal(read(HOUSE_PRICES, start="2021-04-01", end="2021-06-30")),
            "Tabloda Nisan-Haziran 2021 konut fiyat endeksi yer alıyor.",
        ),
        seed_pool,
        tmp_path / "runtime",
        catalog_bytes=CATALOG.read_bytes(),
        official=OfficialSources(evds=source),
        clock=lambda: TODAY,
    )
    answer = runner(uuid4().hex, uuid4().hex, "Nisan-Haziran 2021 konut fiyat endeksini getir.")
    assert answer.status.value == "accepted", answer
    assert len(source.requests) == 1
    assert answer.result is not None and len(answer.result.cells) == 3
