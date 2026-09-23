"""Live 2026-09-23 (A3): two correct things an analyst writes, reported as unverified.

The answer's four-part commentary had bold headings, "**1) Kredi tarafı daralıyor.**",
and "1", "2", "3", "4" were listed to the reader as figures no tool had returned. And
"Mart 2026'da hem stok faiz 34,27'den 39,69'a fırladı" was reported as misdated: 34,27
is February's close, which is exactly where a March move starts from. The rest pins
that a figure no tool returned, or one given the wrong month, is still reported.
"""

from __future__ import annotations

from datetime import date

import pytest

from kkb_agent.agent.claim_qualifiers import is_movement_origin
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

RATES = {1: 33.59, 2: 34.27, 3: 39.69, 4: 39.73, 5: 39.43, 6: 40.12}
MONTH_ENDS = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30}


def rate(month: int) -> ResultValue:
    end = date(2026, month, MONTH_ENDS[month])
    return ResultValue(
        label="EVDS:TP.BKR.TRY.17",
        value=RATES[month],
        unit="percent",
        scale=Scale.ONE,
        measure=StockFlow.RATE,
        period=Period(start=end.replace(day=1), end=end, frequency=Frequency.MONTHLY),
    )


def table() -> dict[str, AnalyticalResult]:
    return {
        "a10": AnalyticalResult(
            result_id="a10",
            kind=ResultKind.SERIES,
            status=ResultStatus.COMPUTED,
            tool="table_transform",
            values=[rate(month) for month in RATES],
            coverage=Period(
                start=date(2026, 1, 1), end=date(2026, 6, 30), frequency=Frequency.MONTHLY
            ),
            evidence=ResultEvidence(input_refs=["a3"]),
        )
    }


@pytest.mark.parametrize(
    "line",
    [
        "**1) Kredi tarafı daralıyor, faiz yükseliyor.** Bakiye geriledi.",
        "### 2. Pazar canlı",
        "- 3) Faiz sıçraması",
        "> **4.** Yılın ikinci yarısı",
        "__1)__ Kısa not",
    ],
)
def test_a_marker_behind_markdown_is_not_a_figure(line):
    assert extract_numbers(line) == []


@pytest.mark.parametrize(
    "text, expected",
    [
        # A figure with a unit is an amount wherever it sits.
        ("**3) milyon TL** kadar", [3.0]),
        # A decimal is not a marker.
        ("- 1.5 puan arttı", [1.5]),
        # Mid-line is prose, not a list.
        ("toplam **12)** adet", [12.0]),
    ],
)
def test_figures_that_only_look_like_markers_are_still_read(text, expected):
    assert [number.value for number in extract_numbers(text)] == expected


def test_the_live_commentary_binds_every_figure():
    answer = (
        "**1) Kredi tarafı daralıyor, faiz yükseliyor.** Stok faiz oranı Ocak'tan "
        "Haziran'a 33,59'dan 40,12'ye çıktı.\n\n"
        "**3) Faiz sıçraması ile satış zirvesi aynı aya denk geliyor.** Mart 2026'da hem "
        "stok faiz 34,27'den 39,69'a fırladı hem de satışlar arttı."
    )
    reported, _ = _figures(answer, table(), None)
    assert reported == []


@pytest.mark.parametrize(
    "sentence, figure",
    [
        # February's rate given as March's own level.
        ("Mart 2026'da stok faiz 34,27 oldu.", "34,27"),
        # A move said to start two months after the figure's own month.
        ("Nisan 2026'da stok faiz 34,27'den 39,73'e çıktı.", "34,27"),
        # A figure no tool returned.
        ("Mart 2026'da stok faiz 35,00'ten 39,69'a çıktı.", "35,00"),
    ],
)
def test_a_misdated_or_unknown_start_is_still_reported(sentence, figure):
    reported, _ = _figures(sentence, table(), None)
    assert [item.split(" ")[0] for item in reported] == [figure]


@pytest.mark.parametrize(
    "text, origin",
    [
        ("34,27'den 39,69'a", True),
        ("%33,59'dan %40,12'ye", True),
        ("52.044'ten 43.062 milyon TL'ye", True),
        ("34,27’den 39,69’a", True),
        # Ablative with no arrival figure: "since", not a movement.
        ("34,27'den fazla", False),
        ("34,27 oldu", False),
    ],
)
def test_what_counts_as_the_start_of_a_movement(text, origin):
    [first, *_] = extract_numbers(text)
    assert is_movement_origin(text, first.start, first.start + len(first.text)) is origin
