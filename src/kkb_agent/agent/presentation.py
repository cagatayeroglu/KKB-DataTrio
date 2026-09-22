"""M8-20: display text, never a replacement for a trusted ResultValue.

Six significant digits leave margin inside the existing 5e-4 relative gate.
Integer-valued floats retain every integer digit. Fixed notation is bounded
by the finite float range and avoids exponents the answer parser cannot read.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Mapping
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
    Frequency,
    Period,
    ResultKind,
    ResultStatus,
    ResultValue,
    Scale,
    StockFlow,
)
from kkb_agent.lakehouse.periods import expected_periods
from kkb_agent.lakehouse.semantics import SemanticsError

_SCALES = {Scale.ONE: "", Scale.THOUSAND: "bin", Scale.MILLION: "milyon", Scale.BILLION: "milyar"}
#: Month names as a Turkish reader writes them; the answer gate reads them back.
_MONTH_NAMES = "Ocak Şubat Mart Nisan Mayıs Haziran Temmuz Ağustos Eylül Ekim Kasım Aralık".split()


def period_label(period: Period) -> str | None:
    """How a reader names one monthly or yearly period: "Ocak 2025", "2025"; else None.

    The writer was shown only "2025-01-01..2025-01-31" and wrote that into Turkish prose
    ("2025-01-01..2025-01-31 döneminde", N48, live DeepSeek 2026-09-22). A week or a day is
    not named by its month, so only a period of that frequency covering one calendar month,
    or one calendar year, gets a label.
    """
    start, end = period.start, period.end
    if (
        period.frequency is Frequency.MONTHLY
        and start.day == 1
        and (start.year, start.month) == (end.year, end.month)
    ):
        return f"{_MONTH_NAMES[start.month - 1]} {start.year}"
    if (
        period.frequency is Frequency.ANNUAL
        and start.year == end.year
        and (start.month, start.day, end.month, end.day) == (1, 1, 12, 31)
    ):
        return str(start.year)
    return None


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
    #: A mass on its own, not only under a price: a series quoted in grams had the
    #: "TRY/g" spelling and none for "g". (Taken from PR #316.)
    **dict(_QUANTITY_WORDS),
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
    calendars = {
        (v.period.frequency, v.period.weekly_anchor)
        for v in result.values
        if v.label in labels and v.period is not None
    }
    if len(calendars) == 1:
        frequency, anchor = next(iter(calendars))
        try:
            expected = expected_periods(frequency, periods[0][1], periods[-1][1], anchor=anchor)
            if len(expected) <= 2048:
                periods = sorted(set(periods) | set(expected))
        except SemanticsError:
            pass  # Irregular or unsupported calendars cannot invent periods.
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
            heading = comparison_heading(result)
            return "\n".join(
                ["Aylık yön karşılaştırması hesaplandı.", *([heading] if heading else []), *values]
            )
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
            periods = result.evidence.transformations[-1].parameters.get("joint_periods")
            if not isinstance(periods, list) or not all(isinstance(p, str) for p in periods):
                return None
            matched = [
                v
                for v in result.values
                if table_count_display_label(result, v)
                == TABLE_COUNT_LABELS["eligible transitions matching both directions"]
            ]
            if len(matched) != 1 or matched[0].value != len(periods):
                return None
            try:
                dates = [date.fromisoformat(str(p)).isoformat() for p in periods]
            except ValueError:
                return None
            period_text = (
                "Koşulu sağlayan dönemler: " + ", ".join(dates) + "."
                if dates
                else "Koşulu sağlayan dönem yok."
            )
            heading = comparison_heading(result)
            return "\n".join(
                [
                    "Tablodaki aylık yönler karşılaştırıldı.",
                    *([heading] if heading else []),
                    *values,
                    period_text,
                ]
            )
    return None


_DIRECTIONS = {
    "up": "yükseldiği",
    "down": "düştüğü",
    "non_increasing": "yükselmediği",
    "non_decreasing": "düşmediği",
    "unchanged": "değişmediği",
}


def _column_name(result: AnalyticalResult, label: str) -> str | None:
    """A column as a person would call it, or None when that cannot be said without a digit.

    A sentence of the answer passes the gate like any other, and a digit in it is a figure
    to bind: an ID such as "EVDS:TP.KTF12" or a base year in a name would cost the line.
    """
    names = result.parameters.get("series_names")
    name = None
    if isinstance(names, dict):
        held = [
            identity for identity in names if label == identity or label.startswith(identity + " ")
        ]
        if held:
            name = str(names[max(held, key=len)])
            if " real, " in label:
                name += " (reel)"
    return _without_figures(name or label)


def _without_figures(name: str) -> str | None:
    """`name` with every part that carries a digit dropped; None when nothing is left.

    A digit here is a figure the gate must bind, and a reviewed name carries one whenever
    the series is an index: "Konut fiyat endeksi, Türkiye geneli (2023=100), TCMB, aylık".
    Refusing the whole name for it cost the reader the entire line that says which series a
    count is about -- live 2026-09-22, the jury's third question counted months of "birinci
    seri" and "ikinci seri" and never named either. The base year is dropped; what the
    series is survives.

    Dropping a whole comma-separated part for one digit was too coarse. A CPI component is
    "Tüketici Fiyat Endeksi (2025=100): 01. Gıda Ve Alkolsüz İçecekler" and an equity index
    "BIST 100 kapanış (XU100)": there the digit sits inside the only part there is, so the
    entire heading disappeared for all thirteen CPI components and for every BIST series.
    The word carrying the digit goes; the words around it stay.
    """
    without_base = re.sub(r"\s*\([^()]*\d[^()]*\)", "", name)
    kept: list[str] = []
    for part in without_base.split(","):
        words = [word for word in part.split() if not any(c.isdigit() for c in word)]
        trimmed = " ".join(words).strip(" .:-")
        if trimmed:
            kept.append(trimmed)
    return ", ".join(kept) or None


def comparison_heading(result: AnalyticalResult) -> str | None:
    """Which series the counts below are about, and in which direction, in one line.

    A table comparison states the pair in its last transformation and a co-movement in its
    own parameters. Both need this line: without it the counts are about a "birinci seri"
    the answer never names, which is how the jury's first question came back (live
    2026-09-22).
    """
    asked: Mapping[str, object] | None = None
    if result.evidence is not None and result.evidence.transformations:
        recorded = result.evidence.transformations[-1].parameters
        asked = recorded if "driver_column" in recorded else None
    if asked is None:
        pair = result.parameters.get("direction_comparison")
        asked = pair if isinstance(pair, dict) else None
    if asked is None:
        return None
    parts: list[str] = []
    for position, column, direction in (
        ("Birinci seri", asked.get("driver_column"), asked.get("driver_direction")),
        ("İkinci seri", asked.get("target_column"), asked.get("target_direction")),
        ("Ön koşul", asked.get("when_column"), asked.get("when_direction")),
    ):
        if column is None and position == "Ön koşul":
            continue
        name = _column_name(result, column) if isinstance(column, str) else None
        moved = _DIRECTIONS.get(direction) if isinstance(direction, str) else None
        if name is None or moved is None:
            return None
        parts.append(f"{position}: {name}, {moved} aylar sayıldı.")
    return " ".join(parts)


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
