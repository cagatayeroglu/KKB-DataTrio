"""M8-20: display text, never a replacement for a trusted ResultValue.

Six significant digits leave margin inside the existing 5e-4 relative gate.
Integer-valued floats retain every integer digit. Fixed notation is bounded
by the finite float range and avoids exponents the answer parser cannot read.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from kkb_agent.agent.claim_qualifiers import (
    COMOVEMENT_COUNT_LABELS,
    TABLE_COUNT_LABELS,
    UNITS,
    comovement_count_display_label,
    table_count_display_label,
)
from kkb_agent.core import (
    DIMENSIONLESS,
    AnalyticalResult,
    ResultKind,
    ResultStatus,
    ResultValue,
    Scale,
    StockFlow,
)

_SCALES = {Scale.ONE: "", Scale.THOUSAND: "bin", Scale.MILLION: "milyon", Scale.BILLION: "milyar"}
#: What a price is quoted per, in the words a Turkish reader uses (DEC-177).
_QUANTITY_WORDS = {"g": "gr", "kg": "kg", "oz": "ons", "t": "ton", "piece": "adet"}
_CURRENCY_WORDS = {"try": "TL", "usd": "USD", "eur": "EUR"}
_UNITS = {
    **{unit: unit.upper() for unit in UNITS.values() if len(unit) == 3},
    "try": "TL",
    "percent": "yüzde",
    "percentage_points": "yüzde puan",
    "basis_points": "baz puan",
    "index_points": "endeks puan",
    "index": "endeks",
    #: A count is a number of things and the label says what they are, so no unit
    #: word is added. Without an entry here every cell of a "kişi" or "adet" series
    #: read "gösterilemiyor" and the writer could not quote one (finding DN-6.4).
    "count": "",
    #: A price per quantity: "TRY/g" reads as "TL/gr".
    **{
        f"{currency}/{quantity}": f"{currency_word}/{quantity_word}"
        for currency, currency_word in _CURRENCY_WORDS.items()
        for quantity, quantity_word in _QUANTITY_WORDS.items()
    },
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

    The vocabulary is the gate's currency/rate vocabulary, the explicit
    dimensionless unit and the typed index-level unit used by prepared series.
    Unsupported free-text units remain canonical metadata, but receive no
    numerical display rather than a guessed label.
    """
    if value.semantics_are_unresolved:
        return None
    folded = (value.unit or "").lower().replace("\u0307", "").replace("ı", "i")
    if folded == "index" and (value.measure is not StockFlow.INDEX or value.scale is not Scale.ONE):
        return None
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


@dataclass(frozen=True, slots=True)
class EndpointObservation:
    """A bounded comparison of two typed cells, not an all-window trend."""

    label: str
    first: ResultValue
    last: ResultValue
    direction: Literal["rose", "fell", "unchanged"]


def endpoint_observations(result: AnalyticalResult) -> tuple[EndpointObservation, ...]:
    """Project only first/last comparable values already in a verified result.

    A gate rechecks the result's execution proof before trusting this projection.
    No interpolation, period aggregation or model arithmetic is involved.
    """
    if result.status is not ResultStatus.COMPUTED or period_table(result) is None:
        return ()
    by_label: dict[str, list[ResultValue]] = {}
    for value in result.values:
        if value.period is not None and value.unit != DIMENSIONLESS:
            by_label.setdefault(value.label, []).append(value)
    observations = []
    for label, values in by_label.items():
        if len(values) < 2 or any(value.semantics_are_unresolved for value in values):
            continue
        ordered = sorted(values, key=lambda value: (value.period.end, value.period.start))  # type: ignore[union-attr]
        first, last = ordered[0], ordered[-1]
        if any(
            value.unit != first.unit or value.scale != first.scale or value.measure != first.measure
            for value in ordered
        ):
            continue
        direction: Literal["rose", "fell", "unchanged"] = (
            "rose"
            if last.value > first.value
            else "fell"
            if last.value < first.value
            else "unchanged"
        )
        observations.append(EndpointObservation(label, first, last, direction))
        if len(observations) == 3:
            break
    return tuple(observations)


def deterministic_draft(result: AnalyticalResult) -> str | None:
    """Present only four known table-producing contracts without a writer call.

    This is a draft, not an acceptance decision. The ordinary verifier, execution
    proof and publication gate still run. Unknown shapes go to the model writer.
    """
    if (
        result.status is not ResultStatus.COMPUTED
        or result.unresolved_semantics
        or period_table(result) is None
        or any(display_value(value) is None for value in result.values)
    ):
        return None

    if result.tool == "table_transform" and result.evidence and result.evidence.transformations:
        transform = result.evidence.transformations[-1]
        if sum(value.label == transform.output_ref for value in result.values) < 2:
            return None
        if result.method == "deflate-v1" and transform.operation == "deflate":
            reference = transform.parameters.get("reference_period")
            if not isinstance(reference, str):
                return None
            try:
                month = date.fromisoformat(reference).strftime("%Y-%m")
            except ValueError:
                return None
            if f"real, {month} prices" not in transform.output_ref:
                return None
            return (
                f"Tabloya enflasyondan arındırılmış sütun eklendi. Fiyat referans dönemi: {month}."
            )
        if result.method == "add-monthly-series-v1" and transform.operation == "add_series":
            return "Tabloya aylık seri sütunu eklendi."

    if result.kind is not ResultKind.COMPARISON:
        return None
    if result.tool == "analytics" and result.method == "monthly-direction-v1":
        if any(
            value.unit == DIMENSIONLESS and comovement_count_display_label(result, value) is None
            for value in result.values
        ):
            return None
        values = _controlled_counts(result, comovement_count_display_label, COMOVEMENT_COUNT_LABELS)
        if values is not None:
            return "Aylık yön karşılaştırması hesaplandı.\n" + "\n".join(values)
    if (
        result.tool == "change_detection"
        and result.method == "table-direction-comparison-v1"
        and result.evidence
        and result.evidence.transformations
        and result.evidence.transformations[-1].operation == "table_co_movement"
    ):
        if any(
            value.unit == DIMENSIONLESS
            and table_count_display_label(result, value) is None
            and comovement_count_display_label(result, value) is None
            # The counts of a comparison an earlier turn made travel with the table it
            # left. They are that table's content, not this answer's figures. Refusing to
            # word the new comparison because of them sent the third reference turn to the
            # model writer, which spent its whole 16,384 tokens thinking and wrote nothing
            # (live 2026-09-21).
            and not value.label.startswith(EARLIER_COMPARISON)
            for value in result.values
        ):
            return None
        values = _controlled_counts(result, table_count_display_label, TABLE_COUNT_LABELS)
        if values is not None:
            return "Tablodaki aylık yönler karşılaştırıldı.\n" + "\n".join(values)
    return None


#: How a table comparison labels its counts; `table_count_display_label` words the latest.
EARLIER_COMPARISON = "table comparison "


def _controlled_counts(
    result: AnalyticalResult,
    labeler: Callable[[AnalyticalResult, ResultValue], str | None],
    expected: dict[str, str],
) -> list[str] | None:
    """Use the verifier's exact controlled phrases, never positional counts."""
    found: dict[str, ResultValue] = {}
    for value in result.values:
        phrase = labeler(result, value)
        if phrase is None:
            continue
        if (
            phrase in found
            or value.unit != DIMENSIONLESS
            or value.scale is not Scale.ONE
            or value.value < 0
            or not value.value.is_integer()
        ):
            return None
        found[phrase] = value
    if set(found) != set(expected.values()):
        return None
    return [f"{phrase} {format_number(found[phrase].value)}." for phrase in expected.values()]
