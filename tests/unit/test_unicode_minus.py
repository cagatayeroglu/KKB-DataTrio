"""QA-20: the typographic minus (U+2212) is a sign, and nothing else changes.

Live 2026-09-23 the jury's A1 answer wrote its five monthly differences with U+2212.
Each was read as a positive number, found in no tool result, and reported to the
reader as unverified although the table held exactly those negative values. The
first two tests are Codex's own, verbatim; the rest pin what must not move.
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

MINUS = "−"


def test_unicode_mathematical_minus_keeps_the_sign():
    [written] = extract_numbers(MINUS + "1.828 milyon TL")
    assert written.value == -1828, (written.text, written.value)


def test_ascii_minus_control():
    [written] = extract_numbers("-1.828 milyon TL")
    assert written.value == -1828


@pytest.mark.parametrize(
    "text, expected",
    [
        (f"({MINUS}612)", [-612.0]),
        (f"Ocak ayı {MINUS}5,76 %", [-5.76]),
        (f"fark {MINUS}512,259 milyar TL", [-512259.0]),
        ("+1.828", [1828.0]),
        ("1 828", [1828.0]),
    ],
)
def test_signs_and_grouping_read_as_written(text, expected):
    assert [number.value for number in extract_numbers(text)] == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        (f"2021{MINUS}2025 dönemi", [2021.0, 2025.0]),
        (f"202101{MINUS}202512", [202101.0, 202512.0]),
        ("2021-2025 dönemi", [2021.0, 2025.0]),
        ("TP.KTF12", []),
    ],
)
def test_a_minus_between_two_figures_is_a_range_not_a_sign(text, expected):
    assert [number.value for number in extract_numbers(text)] == expected


def month(end: date, value: float) -> ResultValue:
    return ResultValue(
        label="tasit fark",
        value=value,
        unit="TRY",
        scale=Scale.MILLION,
        measure=StockFlow.FLOW,
        period=Period(start=end.replace(day=1), end=end, frequency=Frequency.MONTHLY),
    )


def differences() -> dict[str, AnalyticalResult]:
    values = [
        month(date(2026, 2, 28), -1828.0),
        month(date(2026, 3, 31), -612.0),
        month(date(2026, 4, 30), -1324.0),
        month(date(2026, 5, 31), -1137.0),
        month(date(2026, 6, 30), -1083.0),
    ]
    return {
        "a4": AnalyticalResult(
            result_id="a4",
            kind=ResultKind.SERIES,
            status=ResultStatus.COMPUTED,
            tool="table_transform",
            values=values,
            coverage=Period(
                start=date(2026, 2, 1), end=date(2026, 6, 30), frequency=Frequency.MONTHLY
            ),
            evidence=ResultEvidence(input_refs=["a3"]),
        )
    }


def test_the_live_answer_binds_every_negative_difference():
    """The sentences the live answer wrote, against the table it wrote them from."""
    answer = (
        f"Şubat 2026'da fark {MINUS}1.828 milyon TL, Mart 2026'da {MINUS}612 milyon TL, "
        f"Nisan 2026'da {MINUS}1.324 milyon TL, Mayıs 2026'da {MINUS}1.137 milyon TL ve "
        f"Haziran 2026'da {MINUS}1.083 milyon TL oldu."
    )
    reported, _ = _figures(answer, differences(), None)
    assert reported == []


def test_a_wrong_negative_figure_is_still_reported():
    """The gate is not switched off: a figure no tool returned is still named."""
    reported, _ = _figures(f"Şubat 2026'da fark {MINUS}1.900 milyon TL oldu.", differences(), None)
    assert [item.split(" ")[0] for item in reported] == [f"{MINUS}1.900"]


def test_a_positive_figure_does_not_bind_to_a_negative_value():
    """The sign is part of the figure now: +1828 is not the table's −1828."""
    reported, _ = _figures("Şubat 2026'da fark +1.828 milyon TL oldu.", differences(), None)
    assert reported and reported[0].startswith("+1.828")
