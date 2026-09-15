"""M13-15 reviewed-intent ordering regressions; offline catalog only."""

from pathlib import Path

import pytest

from kkb_agent.catalog.mappings import load_reviewed_snapshot
from kkb_agent.catalog.search import CatalogSearchArguments, search_catalog

ROOT = Path(__file__).parents[2]


@pytest.fixture(scope="module")
def snapshot():
    return load_reviewed_snapshot((ROOT / "docs/catalog/prepared_v3.json").read_bytes())


def result(snapshot, query, *, include_archived=False):
    return search_catalog(
        snapshot,
        CatalogSearchArguments(query=query, include_archived=include_archived),
    )


@pytest.mark.parametrize(
    ("query", "series_id", "status"),
    [
        ("average interest rate on outstanding housing loans", "EVDS:TP.BKR.TRY.18", "PARTIAL"),
        ("bireysel ihtiyaç kredisi faiz oranı, KMH hariç", "EVDS:TP.KTF10", "MATCH"),
        (
            "döviz cinsi konut kredisi bakiyesi",
            "BDDK:selector:v1:fb2bf2c7a47d0399251e6e46f55f09c7e7d8c85612f44096f66470744774d4d2",
            "MATCH",
        ),
        ("eski baz yıllı genel TÜFE serisi", "EVDS:TP.GENENDEKS.T1", "MATCH"),
    ],
)
def test_known_qualifiers_refine_order_without_promoting_status(snapshot, query, series_id, status):
    output = result(snapshot, query)
    assert output.candidates[0].series.record.series_id == series_id
    assert output.status == status and output.clarification_required


def test_explicit_archive_intent_is_opt_in_and_neutral_queries_keep_archives_last(snapshot):
    blocked = result(snapshot, "arşivde tutulan eski konut kayıtları")
    assert not any(c.series.record.status.value == "archived" for c in blocked.candidates)
    explicit = result(snapshot, "arşivde tutulan eski konut kayıtları", include_archived=True)
    flags = [c.series.record.status.value == "archived" for c in explicit.candidates]
    assert flags[:2] == [True, True]
    neutral = result(snapshot, "konut", include_archived=True)
    neutral_flags = [c.series.record.status.value == "archived" for c in neutral.candidates]
    assert neutral_flags == sorted(neutral_flags)


def test_unspecified_reviewed_scope_remains_ambiguous(snapshot):
    output = result(snapshot, "ihtiyaç kredisi faizini göster")
    assert {c.series.record.series_id for c in output.candidates} >= {
        "EVDS:TP.KTF10",
        "EVDS:TP.KTF101",
    }
    assert output.clarification_required


def test_analysis_year_is_not_inferred_to_be_an_index_base_year(snapshot):
    output = result(snapshot, "2021 TÜFE")
    assert output.candidates[0].series.record.series_id == "EVDS:TP.TUKFIY2025.GENEL"


def test_n18_stays_partial_when_lexical_generation_does_not_surface_balance(snapshot):
    output = result(snapshot, "Turkish lira housing loan balance at banks")
    assert output.status == "PARTIAL" and output.clarification_required
    assert not any(c.series.record.provider == "BDDK" for c in output.candidates)
