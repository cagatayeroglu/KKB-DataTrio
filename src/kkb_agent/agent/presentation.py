"""M8-20: display text, never a replacement for a trusted ResultValue.

Six significant digits leave margin inside the existing 5e-4 relative gate.
Integer-valued floats retain every integer digit. Fixed notation is bounded
by the finite float range and avoids exponents the answer parser cannot read.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from kkb_agent.agent.claim_qualifiers import UNITS
from kkb_agent.core import DIMENSIONLESS, AnalyticalResult, ResultStatus, ResultValue, Scale

_SCALES = {Scale.ONE: "", Scale.THOUSAND: "bin", Scale.MILLION: "milyon", Scale.BILLION: "milyar"}
_UNITS = {
    **{unit: unit.upper() for unit in UNITS.values() if len(unit) == 3},
    "try": "TL",
    "percent": "yüzde",
    "percentage_points": "yüzde puan",
    "basis_points": "baz puan",
    "index_points": "endeks puan",
    DIMENSIONLESS: DIMENSIONLESS,
}


def format_number(value: float) -> str:
    """Return one deterministic Turkish number, readable by the existing gate.

    A lone separator followed by three digits means grouping to parse_written.
    Thus 1.234 is displayed as 1,2340, not the thousandfold-ambiguous 1,234.
    The extra zero is intentional; the verifier's locale policy is unchanged.
    """
    if not math.isfinite(value):
        raise ValueError("Only finite analytical values have display numbers")
    if value == 0:
        return "0"
    fixed = (
        format(value, ".0f") if value.is_integer() else format(Decimal(format(value, ".6g")), "f")
    )
    integer, _, fraction = fixed.partition(".")
    fraction = fraction.rstrip("0")
    sign = "-" if integer.startswith("-") else ""
    digits = integer.lstrip("-")
    groups = [digits[max(0, end - 3) : end] for end in range(len(digits), 0, -3)]
    grouped = ".".join(reversed(groups))
    if len(fraction) == 3 and "." not in grouped:
        fraction += "0"
    return sign + grouped + ("," + fraction if fraction else "")


def display_value(value: ResultValue) -> str | None:
    """Quote only supported, resolved metadata; never infer a unit or rescale.

    The vocabulary is the gate's existing currency/rate vocabulary plus its
    explicit dimensionless unit. Unsupported free-text units remain canonical
    metadata, but receive no numerical display rather than a guessed label.
    """
    if value.semantics_are_unresolved:
        return None
    folded = (value.unit or "").lower().replace("\u0307", "").replace("ı", "i")
    unit = _UNITS.get(UNITS.get(folded, folded))
    scale = _SCALES.get(value.scale)
    if unit is None or scale is None:
        return None
    number = format_number(value.value)
    return " ".join(part for part in (number, scale, unit) if part)


@dataclass(frozen=True, slots=True)
class PeriodTable:
    """Every per-period value of one result, laid out by code (M6-14).

    Cells are the same display phrases the writer receives, taken from the
    result itself; no model touches them, so the table needs no number-by-number
    prose verification. An empty cell means the result holds no value for that
    period; `UNAVAILABLE` means the value's unit/scale cannot be displayed.
    """

    columns: tuple[str, ...]
    rows: tuple[tuple[str, tuple[str, ...]], ...]

    def markdown(self) -> str:
        header = "| Dönem | " + " | ".join(self.columns) + " |"
        rule = "|---|" + "---:|" * len(self.columns)
        body = [f"| {period} | " + " | ".join(cells) + " |" for period, cells in self.rows]
        return "\n".join([header, rule, *body])


def period_table(result: AnalyticalResult) -> PeriodTable | None:
    """Series-like values (two or more periods per label) of a computed result.

    Summary values without a period, dimensionless counts and single-period
    values stay in the prose. A label with two values for the same period makes
    the layout ambiguous, so no table is produced rather than picking one.
    """
    if result.status is not ResultStatus.COMPUTED:
        return None
    series: dict[str, dict[tuple[date, date], str]] = {}
    for value in result.values:
        if value.period is None or value.unit == DIMENSIONLESS:
            continue
        cells = series.setdefault(value.label, {})
        key = (value.period.start, value.period.end)
        if key in cells:
            return None
        cells[key] = display_value(value) or "UNAVAILABLE"
    labels = [label for label, cells in series.items() if len(cells) >= 2]
    if not labels:
        return None
    names = result.parameters.get("series_names")
    titles = []
    for label in labels:
        title = label
        if isinstance(names, dict):
            for series_id, name in names.items():
                if isinstance(name, str):
                    title = title.replace(series_id, name)
        titles.append(title)
    periods = sorted({key for label in labels for key in series[label]})
    return PeriodTable(
        tuple(titles),
        tuple(
            (
                f"{start.isoformat()}..{end.isoformat()}",
                tuple(series[label].get((start, end), "") for label in labels),
            )
            for start, end in periods
        ),
    )
