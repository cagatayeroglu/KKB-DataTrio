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


def test_a_place_free_query_prefers_the_national_series_over_regional_variants(snapshot):
    """X4: unqualified "konut fiyat endeksi" should read as Türkiye, not a 4-way ask."""
    output = result(snapshot, "konut fiyat endeksi")
    top = [c.series.record.series_id for c in output.candidates]
    assert top[0] == "EVDS:TP.KFE.TR"
    # The regional variants stay available, but below the national one.
    assert {"EVDS:TP.KFE.TR10", "EVDS:TP.KFE.TR31", "EVDS:TP.KFE.TR51"} <= set(top)
    assert top.index("EVDS:TP.KFE.TR") < min(
        top.index(sid) for sid in ("EVDS:TP.KFE.TR10", "EVDS:TP.KFE.TR31", "EVDS:TP.KFE.TR51")
    )


def test_asking_for_regional_series_generically_demotes_the_national_one(snapshot):
    """ "bölgesel konut fiyat endeksi" wants the provincial variants, not Türkiye."""
    output = result(snapshot, "güncel bölgesel konut fiyat endeksi serileri")
    top = [c.series.record.series_id for c in output.candidates]
    regional = {"EVDS:TP.KFE.TR10", "EVDS:TP.KFE.TR31", "EVDS:TP.KFE.TR51"}
    assert top[0] in regional
    assert top.index("EVDS:TP.KFE.TR") > max(top.index(sid) for sid in regional)


def test_naming_a_city_promotes_its_regional_series_above_the_national_one(snapshot):
    for city, series_id in (
        ("İstanbul", "EVDS:TP.KFE.TR10"),
        ("İzmir", "EVDS:TP.KFE.TR31"),
        ("Ankara", "EVDS:TP.KFE.TR51"),
    ):
        output = result(snapshot, f"{city} konut fiyat endeksi")
        assert output.candidates[0].series.record.series_id == series_id


BDDK_TOTAL = "BDDK:selector:v1:fa6e3c79bc8c9ead8680507965533a20366829cdf7aab8aa754224beb82b0f66"
BDDK_TP = "BDDK:selector:v1:388f6263c2bd73dafb71579bf74f6756be7d74976a400b5d00798d506d521eb0"
BDDK_YP = "BDDK:selector:v1:fb2bf2c7a47d0399251e6e46f55f09c7e7d8c85612f44096f66470744774d4d2"


@pytest.mark.parametrize(
    ("query", "series_id"),
    [
        # DEC-165: the aggregate is the default over its TP/YP columns when no currency is named.
        ("konut kredisi bakiyesi", BDDK_TOTAL),
        # E1 (2026-09-19): the inflected Turkish noun still carries the balance intent.
        ("2021-2025 konut kredisi bakiyesini aylık getir", BDDK_TOTAL),
        # A named currency picks the column instead.
        ("döviz cinsi konut kredisi bakiyesi", BDDK_YP),
        ("TP konut kredisi bakiyesi", BDDK_TP),
        # National over regions when no place is named; the regions share the concept.
        ("konut fiyat endeksi", "EVDS:TP.KFE.TR"),
        # One candidate is its own default.
        ("İstanbul konut fiyat endeksi", "EVDS:TP.KFE.TR10"),
        # The newest base is the default when none is named; the old base stays reachable.
        ("TÜFE genel endeks", "EVDS:TP.TUKFIY2025.GENEL"),
        ("eski baz yıllı genel TÜFE serisi", "EVDS:TP.GENENDEKS.T1"),
    ],
)
def test_reviewed_defaults_make_the_first_candidate_unambiguous(snapshot, query, series_id):
    output = result(snapshot, query)
    assert output.candidates[0].series.record.series_id == series_id
    assert output.top_candidate == "unambiguous"
    assert output.clarification_required  # The flag is unchanged; the signal sits beside it.


@pytest.mark.parametrize(
    "query",
    [
        "bölgesel konut fiyat endeksi serileri",  # which province: the regions tie
        "ihtiyaç kredisi faizini göster",  # KMH dahil / hariç: the two scopes tie
        "konut",  # balances, rates, prices and a CPI division: no shared concept
        "konut kredisi",  # balance or rate: the question does not say
    ],
)
def test_ties_on_an_axis_the_question_did_not_name_stay_ambiguous(snapshot, query):
    output = result(snapshot, query)
    assert len(output.candidates) > 1 and output.top_candidate == "ambiguous"


def test_no_candidates_means_no_top_candidate(snapshot):
    output = result(snapshot, "zzzx unfamiliar wording")
    assert output.status == "NO_MATCH" and output.top_candidate == "none"


def test_inflected_intent_words_are_read_as_their_stem(snapshot):
    """ "faizini"/"bakiyesini" carry the same intent as "faiz"/"bakiye" (E1 finding)."""
    rates = result(snapshot, "ihtiyaç kredisi faizini göster")
    assert all(c.series.record.stock_flow.value == "rate" for c in rates.candidates[:3])
    balance = result(snapshot, "konut kredisi bakiyesini getir")
    assert balance.candidates[0].series.record.series_id == BDDK_TOTAL
    assert balance.candidates[0].series.record.stock_flow.value == "stock"


def test_a_title_denomination_is_not_a_component(snapshot):
    """EVDS "(TL, Akım, %)" titles are denominations; only TP/YP labels are columns."""
    output = result(snapshot, "ihtiyaç kredisi faizi")
    first = output.candidates[0].series.record
    assert first.series_id in {"EVDS:TP.KTF10", "EVDS:TP.KTF101"}
    output = result(snapshot, "konut kredisi bakiyesi")
    order = [c.series.record.series_id for c in output.candidates]
    assert order.index(BDDK_TOTAL) < order.index(BDDK_TP) and order.index(BDDK_TOTAL) < order.index(
        BDDK_YP
    )
