"""Live 2026-09-23 (A1 on f25a160): nine correct figures reported as unverified.

Every one of the answer's 18 cells matched the official bulletin. Its commentary was
reported as unbound in three ways: "satır 3", which says where in the bulletin the row
is; "−%5,76", "−%1,30", "−%17,26" and "−%2,5", whose sign stands before the percent
sign; and the December and June levels, held both by the table and by a comparison
that labels them "<series> at <date>" - one observation under two labels. The last
tests pin that a figure no tool returned is still reported.
"""

from __future__ import annotations

from datetime import date

import pytest

from kkb_agent.agent.trust_answer import _figures
from kkb_agent.agent.verifier import extract_numbers
from kkb_agent.core import (
    AnalyticalResult,
    Frequency,
    Period,
    ResultEvidence,
    ResultKind,
    ResultStatus,
    ResultValue,
    Scale,
    StockFlow,
)

SERIES = "BDDK:selector:v1:tasit"
LEVELS = {
    date(2025, 12, 31): 52044.0,
    date(2026, 1, 31): 49046.0,
    date(2026, 2, 28): 47218.0,
    date(2026, 3, 31): 46606.0,
    date(2026, 4, 30): 45282.0,
    date(2026, 5, 31): 44145.0,
    date(2026, 6, 30): 43062.0,
}


def month(end: date) -> Period:
    return Period(start=end.replace(day=1), end=end, frequency=Frequency.MONTHLY)


def value(label: str, amount: float, period: Period, unit: str = "TRY") -> ResultValue:
    return ResultValue(
        label=label,
        value=amount,
        unit=unit,
        scale=Scale.MILLION if unit == "TRY" else Scale.ONE,
        measure=StockFlow.STOCK,
        period=period,
    )


def result(name: str, tool: str, kind: ResultKind, values: list[ResultValue]) -> AnalyticalResult:
    return AnalyticalResult(
        result_id=name,
        kind=kind,
        status=ResultStatus.COMPUTED,
        tool=tool,
        values=values,
        coverage=Period(
            start=date(2025, 12, 1), end=date(2026, 6, 30), frequency=Frequency.MONTHLY
        ),
        evidence=ResultEvidence(input_refs=["lake"]),
    )


def results() -> dict[str, AnalyticalResult]:
    ends = sorted(LEVELS)
    changes, percents = [], []
    for before, after in zip(ends, ends[1:], strict=False):
        moved = LEVELS[after] - LEVELS[before]
        changes.append(value(f"{SERIES} change (lag 1)", moved, month(after)))
        percents.append(
            value(
                f"{SERIES} % change (lag 1)",
                moved / LEVELS[before] * 100,
                month(after),
                unit="percent",
            )
        )
    span = Period(start=date(2025, 12, 1), end=date(2026, 6, 30), frequency=Frequency.MONTHLY)
    first, last = ends[0], ends[-1]
    return {
        "a3": result(
            "a3",
            "lakehouse",
            ResultKind.SERIES,
            [value(SERIES, LEVELS[end], month(end)) for end in ends],
        ),
        "a8": result(
            "a8",
            "table_transform",
            ResultKind.SERIES,
            [value(SERIES, LEVELS[end], month(end)) for end in ends[1:]] + changes + percents,
        ),
        "a10": result(
            "a10",
            "change_detection",
            ResultKind.COMPARISON,
            [
                value(f"{SERIES} at {first.isoformat()}", LEVELS[first], month(first)),
                value(f"{SERIES} at {last.isoformat()}", LEVELS[last], month(last)),
                value(f"{SERIES} absolute change", LEVELS[last] - LEVELS[first], span),
                value(
                    f"{SERIES} relative change",
                    (LEVELS[last] - LEVELS[first]) / LEVELS[first] * 100,
                    span,
                    unit="percent",
                ),
            ],
        ),
    }


LIVE = (
    'Kaynak: BDDK Aylık Bülten, "Tüketici Kredileri" tablosu, satır 3: *Tüketici Kredileri '
    "- Taşıt*, sektör toplamı.\n\n"
    "Ocak 2026 değişimi için Aralık 2025 (52.044 milyon TL) okundu.\n\n"
    "- Bakiye altı ayın her birinde geriledi; dönem boyunca toplam **−8.982 milyon TL "
    "(−%17,26)** (Aralık 2025: 52.044 → Haziran 2026: 43.062).\n"
    "- En sert düşüş Ocak 2026'da (−2.998 milyon TL, −%5,76); en ılımlı ay Mart 2026 "
    "(−612 milyon TL, −%1,30).\n"
)


def test_the_live_commentary_binds_every_figure():
    reported, _ = _figures(LIVE, results(), None)
    assert reported == []


@pytest.mark.parametrize(
    "text, expected",
    [
        ("(−%5,76)", [-5.76]),
        ("-%17,26", [-17.26]),
        ("%−1,30", [-1.3]),
        ("%5,76", [5.76]),
        # A minus glued to a figure before it is a range, not a sign.
        ("5−%3", [5.0, 3.0]),
    ],
)
def test_a_sign_before_the_percent_sign_is_the_figure_sign(text, expected):
    assert [number.value for number in extract_numbers(text)] == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("tablo 4, satır 3: taşıt", []),
        ("(a1, s. 2)", []),
        ("Ek 3: Hafif ticari", []),
        ("3. satırda", []),
        ("Sayfa 10 ve Tablo 1", []),
        # Amounts and counts are still read.
        ("ek 3 ay sürdü", [3.0]),
        ("satır 3 milyon TL", [3.0]),
        ("3 satır eklendi", [3.0]),
    ],
)
def test_a_place_in_a_source_is_not_a_figure(text, expected):
    assert [number.value for number in extract_numbers(text)] == expected


@pytest.mark.parametrize(
    "sentence, figure",
    [
        ("En sert düşüş Ocak 2026'da (−%6,10).", "6,10"),
        ("En sert düşüş Ocak 2026'da (−%5,90).", "5,90"),
        ("Aralık 2025: 52.100 milyon TL.", "52.100"),
    ],
)
def test_a_wrong_figure_is_still_reported(sentence, figure):
    reported, _ = _figures(sentence, results(), None)
    assert [item.split(" ")[0] for item in reported] == [figure]


@pytest.mark.parametrize(
    "text",
    [
        "geçiş sayısı 5.\nEksik gözlem sayısı 0.",
        "geçiş sayısı 5. Tablo aşağıda.",
        "sayısı 5. Ek bilgi",
    ],
)
def test_a_count_ending_a_sentence_is_still_read(text):
    assert extract_numbers(text)[0].value == 5.0
