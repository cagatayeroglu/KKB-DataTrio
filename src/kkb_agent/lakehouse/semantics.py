"""What a silver series must declare before it may hold a value.

The rule this module enforces: a number whose unit, scale, reporting calendar,
measurement kind or accumulation behaviour is unrecorded cannot enter silver.
Rejecting it is the point. An unusable number that is stored looks exactly like
a usable one at the moment it is read, and by then the caller has already
charted it.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

from kkb_agent.core import Aggregation, CumulativeKind, Frequency, Scale, StockFlow, WeeklyAnchor

#: Semantics a series must resolve before promotion. Aggregation is deliberately
#: absent: it may stay UNKNOWN until someone actually combines periods.
REQUIRED_SEMANTICS = ("unit", "scale", "frequency", "observation", "cumulative")

#: Units this project understands. Extend with a decision, not in passing.
KNOWN_UNITS = frozenset({"TRY", "USD", "EUR", "XAU", "percent", "index", "count", "ratio"})
#: DEC-177: a quoted price is money per quantity ("TRY/g", "USD/oz"). It is a unit of its own:
#: never summed with money, never deflated as an amount, only compared with the same unit.
PRICE_CURRENCIES = frozenset({"TRY", "USD", "EUR"})
PRICE_QUANTITIES = frozenset({"g", "kg", "oz", "t", "piece"})


def known_unit(unit: str) -> bool:
    """A unit of the closed set, or a price of one of its currencies per a listed quantity."""
    if unit in KNOWN_UNITS:
        return True
    money, slash, quantity = unit.partition("/")
    return bool(slash) and money in PRICE_CURRENCIES and quantity in PRICE_QUANTITIES


_MONTHS_PER_PERIOD = {
    Frequency.MONTHLY: 1,
    Frequency.QUARTERLY: 3,
    Frequency.SEMIANNUAL: 6,
    Frequency.ANNUAL: 12,
}


class SemanticsError(ValueError):
    """A series cannot be promoted to silver as declared."""


class UnresolvedSemantics(SemanticsError):
    """One or more required semantics are unknown. Names them; resolves nothing."""

    def __init__(self, missing: tuple[str, ...]):
        self.missing = missing
        super().__init__("Unresolved semantics: " + ", ".join(missing))


class PeriodMismatch(SemanticsError):
    """An observation's period does not match the series' declared calendar."""


@dataclass(frozen=True, slots=True)
class SeriesSemantics:
    """A complete, self-consistent description of what a series' numbers mean.

    Construction validates internal consistency only. Whether the declaration is
    *true* of the source is a separate question that only the source's own
    metadata can answer; this type cannot and does not check that.
    """

    unit: str
    scale: Scale
    frequency: Frequency
    observation: StockFlow
    cumulative: CumulativeKind
    aggregation: Aggregation = Aggregation.UNKNOWN
    anchor: WeeklyAnchor | None = None
    base_year: int | None = None

    def __post_init__(self) -> None:
        if not known_unit(self.unit):
            raise SemanticsError(f"Unrecognized unit: {self.unit!r}")
        if self.observation is StockFlow.STOCK and self.aggregation is Aggregation.SUM:
            raise SemanticsError("A stock cannot be summed across periods")
        if self.unit == "percent" and self.observation not in (StockFlow.RATE, StockFlow.UNKNOWN):
            raise SemanticsError("Percent values require rate semantics")
        if self.observation is StockFlow.RATE and self.unit not in ("percent", "ratio"):
            raise SemanticsError("A rate requires a percent or ratio unit")
        if self.observation is StockFlow.INDEX and self.unit != "index":
            raise SemanticsError("An index requires an index unit")
        if self.unit == "index" and self.observation not in (StockFlow.INDEX, StockFlow.UNKNOWN):
            raise SemanticsError("Index units require index semantics")
        if self.frequency is Frequency.WEEKLY and self.anchor is None:
            raise SemanticsError("A weekly series must name the weekday its period ends on")
        if self.frequency is not Frequency.WEEKLY and self.anchor is not None:
            raise SemanticsError("Only a weekly series carries a weekday anchor")
        if self.observation is StockFlow.INDEX and self.base_year is None:
            raise SemanticsError("An index must record its base year")
        if self.base_year is not None and not 1900 <= self.base_year <= 2100:
            raise SemanticsError(f"Implausible base year: {self.base_year}")
        if (
            self.observation in (StockFlow.RATE, StockFlow.INDEX)
            and self.aggregation is Aggregation.SUM
        ):
            raise SemanticsError(
                f"A {self.observation.value} series cannot be summed across periods"
            )
        accumulates = self.cumulative in (
            CumulativeKind.SINCE_INCEPTION,
            CumulativeKind.YEARLY_RESET,
        )
        # UNKNOWN is not a claim that the series accumulates, so it is allowed
        # here and refused later by require_resolved().
        if accumulates and self.observation is not StockFlow.FLOW:
            raise SemanticsError("Only a flow series can accumulate")

    @property
    def unresolved(self) -> tuple[str, ...]:
        """Required semantics still unknown, in declaration order."""
        return tuple(
            name
            for name in REQUIRED_SEMANTICS
            if getattr(getattr(self, name), "value", None) == "unknown"
        )

    def require_resolved(self) -> None:
        if self.unresolved:
            raise UnresolvedSemantics(self.unresolved)


def period_bounds(
    frequency: Frequency, end: date, *, anchor: WeeklyAnchor | None = None
) -> tuple[date, date]:
    """Inclusive [start, end] the given period-end implies under `frequency`.

    Takes the period *end* because that is what both sources publish: BDDK dates
    a weekly observation to its Friday and a monthly one to its month, and EVDS
    dates a weekly observation to its anchor weekday.
    """
    if frequency in (Frequency.DAILY, Frequency.BUSINESS_DAY):
        return end, end
    if frequency is Frequency.WEEKLY:
        if anchor is None:
            raise SemanticsError("A weekly period needs its anchor weekday")
        if end.weekday() != anchor.weekday:
            raise PeriodMismatch(
                f"Weekly period ends on {end.isoformat()}, which is not a {anchor.value}"
            )
        return date.fromordinal(end.toordinal() - 6), end
    months = _MONTHS_PER_PERIOD.get(frequency)
    if months is None:
        raise SemanticsError(f"No period arithmetic is defined for {frequency.value}")
    if end.day != calendar.monthrange(end.year, end.month)[1]:
        raise PeriodMismatch(
            f"{frequency.value} period must end on the last day of a month, got {end.isoformat()}"
        )
    if end.month % months:
        raise PeriodMismatch(f"{frequency.value} period cannot end in month {end.month}")
    start_month = end.month - months + 1
    return date(end.year, start_month, 1), end


def check_period(semantics: SeriesSemantics, start: date, end: date) -> None:
    """Reject an observation whose period contradicts the declared calendar.

    A weekly-Friday observation dated to a Thursday is the failure this catches:
    it aligns plausibly against a monthly series and is wrong by a day forever.
    """
    if end < start:
        raise PeriodMismatch(
            f"Period ends before it starts: {start.isoformat()}..{end.isoformat()}"
        )
    expected_start, expected_end = period_bounds(semantics.frequency, end, anchor=semantics.anchor)
    if (start, end) != (expected_start, expected_end):
        raise PeriodMismatch(
            f"{semantics.frequency.value} period ending {end.isoformat()} spans "
            f"{expected_start.isoformat()}..{expected_end.isoformat()}, "
            f"not {start.isoformat()}..{end.isoformat()}"
        )
