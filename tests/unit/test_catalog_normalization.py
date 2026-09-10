"""Deterministic search-text preparation, with no retrieval or live sources."""

import unicodedata

import pytest

from kkb_agent.catalog import (
    CatalogRecord,
    normalize_index_text,
    normalize_query_text,
    normalize_search_text,
)


@pytest.mark.parametrize(
    ("original", "expected"),
    [
        ("I ı İ i", "i i i i"),
        ("İSTANBUL IĞDIR ışıK", "istanbul igdir isik"),
        ("Şş Ğğ Üü Öö Çç", "ss gg uu oo cc"),
        ("ŞUBELER VE NÜFUSA GÖRE DAĞILIM", "subeler ve nufusa gore dagilim"),
        ("FinTürk Üç Aylık", "finturk uc aylik"),
        ("HAFTALIK(ÇARŞAMBA)", "haftalik carsamba"),
        ("Konut Kredisi, (TL, Akım, %)", "konut kredisi tl akim %"),
        ("KonUt   Kredisi (TL, Akım, %)", "konut kredisi tl akim %"),
        ("  KREDİ\t\n\r  oranı\u00a0 ", "kredi orani"),
        ("Konut,,,;;___kredisi!!!", "konut kredisi"),
        ("“Sentetik” [Konut] {Kredisi}: Örnek…", "sentetik konut kredisi ornek"),
        ("i\u0307", "i"),
        ("I\u0307STANBUL", "istanbul"),
        ("Âdet Ê É î û", "adet e e i u"),
        ("", ""),
        (" \t\n\u2003", ""),
        (".,;()", ""),
        ("İ", "i"),
    ],
)
def test_declared_search_representation(original: str, expected: str) -> None:
    assert normalize_search_text(original) == expected


@pytest.mark.parametrize("text", ["İstanbul", "IĞDIR", "Şubeler", "Üç aylık", "ÇÖĞ şü", "café"])
def test_unicode_canonical_forms_agree(text: str) -> None:
    assert normalize_search_text(unicodedata.normalize("NFC", text)) == normalize_search_text(
        unicodedata.normalize("NFD", text)
    )


@pytest.mark.parametrize(
    "text",
    [
        "İSTANBUL Şubeleri",
        "Konut,,, Kredisi (%)",
        "2003=100; 46,750 / 1.234,56",
        "(-2,5%) / +3.0",
        "2021-01 – 2026-06",
        "I\u0307\u0301 ı",
        "中文 عَرَبِيّ Ελληνικά ₺ €",
        "... ;\n",
        "",
        "konut kredisi",
    ],
)
def test_idempotent(text: str) -> None:
    normalized = normalize_search_text(text)
    assert normalize_search_text(normalized) == normalized


def test_non_latin_text_and_meaningful_symbols_are_not_ascii_dropped() -> None:
    text = "中文 عَرَبِيّ ₺ € % / + −"
    assert normalize_search_text(text) == text


@pytest.mark.parametrize(
    "text",
    ["46,750", "1.234,56", "1,234.56", "-2,5%", "+3.0", "2003=100", "1/2", "2026-01"],
)
def test_numeric_separators_signs_and_units_are_preserved(text: str) -> None:
    assert normalize_search_text(text) == text


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("konut kredisi", "mortgage"),
        ("akım", "stok"),
        ("Bin TL", "Milyon TL"),
        ("Konut (Arşiv)", "Konut"),
        ("HAFTALIK(CUMA)", "HAFTALIK(ÇARŞAMBA)"),
        ("arttı", "artmadı"),
        ("1,5", "15"),
        ("-5", "5"),
        ("%5", "5"),
        ("2003=100", "2025=100"),
    ],
)
def test_normalization_does_not_invent_equivalence(left: str, right: str) -> None:
    assert normalize_search_text(left) != normalize_search_text(right)


@pytest.mark.parametrize("value", [None, 0, True, b"text", ["kredi"], {"title": "kredi"}])
def test_non_strings_are_rejected(value: object) -> None:
    with pytest.raises(TypeError, match="must be a string"):
        normalize_search_text(value)


def test_index_and_query_entry_points_are_the_single_shared_function() -> None:
    # Fails if either entry point gains an independent implementation, even if
    # the current example strings happen to agree.
    assert normalize_index_text is normalize_query_text is normalize_search_text
    assert normalize_index_text("SENTETİK Konut Kredisi, (TL, Akım, %)") == normalize_query_text(
        "sentetik konut kredisi (tl, akım, %)"
    )


@pytest.mark.parametrize(
    ("provider", "code", "title"),
    [
        ("EVDS", "TP.SYNTH.M1303.A", "Sentetik Konut Kredisi, (TL, Akım, %)"),
        ("BDDK", "synthetic-selector:FinTürk/2026-6/İl-01", "Sentetik Seçilmiş Krediler (Bin TL)"),
    ],
)
def test_search_preparation_leaves_catalog_identity_and_metadata_untouched(
    provider: str, code: str, title: str
) -> None:
    record = CatalogRecord(
        series_id="catalog:" + code,
        provider=provider,
        source_series_id=code,
        title=title,
        labels=("Özgün Birim: Bin TL",),
        source={"source_id": "s1", "source_type": "fixture", "locator": "memory://synthetic"},
    )
    before = record.model_dump_json()
    indexed = normalize_index_text(record.title)
    assert indexed == normalize_query_text(title)
    assert record.model_dump_json() == before
    assert record.source_series_id == code
    assert record.title == title


def test_matching_search_text_does_not_collapse_different_series_ids() -> None:
    candidates = [
        ("TP.SYNTH.M1303.A", normalize_index_text("Sentetik Konut Kredisi, (TL, Stok, %)")),
        ("TP.SYNTH.M1303.B", normalize_index_text("SENTETİK Konut Kredisi (TL, Stok, %)")),
    ]
    query = normalize_query_text("sentetik konut kredisi (tl, stok, %)")
    assert [series_id for series_id, text in candidates if text == query] == [
        "TP.SYNTH.M1303.A",
        "TP.SYNTH.M1303.B",
    ]
