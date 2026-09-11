"""Granger precedence between two series (M6-11, DEC-120).

A Granger test asks one narrow question: does the past of one series improve a
linear prediction of the other beyond that series' own past? A yes is
**predictive precedence**. It is not a mechanism, and under DEC-120 this module
never words it as one: every result carries the limitations, and the M6-01
contract refuses a causality result that omits them.

Three things decide whether a Granger p-value means anything here.

**Calendar.** A row at period t in an order-p regression needs the p periods
immediately before t. Rows are keyed on the declared calendar through the same
positions M6-24 gave the lag search, so a missing period removes the rows that
would need it. Compressing the gap would present a value two months old as one
month old, and the test would never notice.

**Search.** Each order from 1 to the requested maximum is tested separately, in
both directions. The smallest of those p-values was found by looking, and the
result says how many were looked at.

**Stationarity.** The F-test assumes stationary series and rejects far too
often on trending levels. Nothing here tests stationarity. A strong trend is
flagged and period-over-period changes are named as the check, as the
association module does, without silently differencing.
"""

from __future__ import annotations

import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from math import isfinite
from typing import Final

from kkb_agent.analytics.association import (
    BASE_LIMITATIONS,
    DEFAULT_INPUTS,
    DEFAULT_MAX_LAG,
    DEFAULT_MINIMUM_PAIRS,
    LAG_CAP,
    TREND_LIMIT,
    _calendar_positions,
    _prepare,
    _refuse,
    _trend,
)
from kkb_agent.core import (
    DIMENSIONLESS,
    AnalyticalResult,
    Period,
    ResultEvidence,
    ResultKind,
    ResultStatus,
    ResultValue,
    SampleCounts,
    Scale,
)
from kkb_agent.lakehouse.records import Observation
from kkb_agent.lakehouse.semantics import SeriesSemantics

METHOD: Final = "granger_ssr_f"

#: Rows an order-p test needs for each coefficient it estimates (2p + 1).
#: Three is a floor, not a comfort. PROPOSED: no benchmark has measured it.
ROWS_PER_COEFFICIENT: Final = 3

#: An unrestricted fit whose residual sum of squares is this small a fraction
#: of the restricted one is exact to rounding, and its F is not a statistic.
EXACT_FIT: Final = 1e-12

#: DEC-120 names small samples, common drivers and structural breaks; they are
#: attached to every Granger result on top of the association limitations.
GRANGER_LIMITATIONS: Final = (
    "Granger precedence is predictive only: one series' past improved a linear forecast "
    "of the other's, which is not evidence that it moves it",
    "Common drivers such as inflation or the policy rate can produce precedence in either "
    "direction, or in both",
    "Structural breaks inside the window were not tested, and a break can create or hide "
    "precedence",
    "The F-test's p-value is approximate in samples this small, and a few years of monthly "
    "data support only short lag orders",
)


@dataclass(frozen=True, slots=True)
class _Test:
    """One order in one direction, with the rows it rested on."""

    order: int
    rows: int
    f_value: float
    p_value: float
    df_denom: int


def _rows(positions: Sequence[int], order: int) -> list[tuple[int, list[int]]]:
    """Each usable row with the list indices of its `order` predecessors.

    A row exists only when every one of the previous `order` declared periods
    was published by both series — the M6-24 rule, applied to a regression.
    """
    at = {position: index for index, position in enumerate(positions)}
    rows: list[tuple[int, list[int]]] = []
    for index, position in enumerate(positions):
        history = [at[position - step] for step in range(1, order + 1) if position - step in at]
        if len(history) == order:
            rows.append((index, history))
    return rows


def _rows_needed(order: int, minimum_rows: int) -> int:
    return max(minimum_rows, ROWS_PER_COEFFICIENT * (2 * order + 1))


def _f_test(
    target: Sequence[float],
    other: Sequence[float],
    rows: Sequence[tuple[int, list[int]]],
    order: int,
) -> _Test | None:
    """Whether `other`'s past improves on `target`'s own; None when F is undefined."""
    # Imported here so the association and lag paths, and every tool listing,
    # do not pay statsmodels' import time for a test they never run.
    from statsmodels.regression.linear_model import OLS
    from statsmodels.tools.sm_exceptions import SingularMatrixWarning

    endog = [target[index] for index, _ in rows]
    own = [[1.0, *(target[earlier] for earlier in history)] for _, history in rows]
    joint = [
        [*base, *(other[earlier] for earlier in history)]
        for base, (_, history) in zip(own, rows, strict=True)
    ]
    with warnings.catch_warnings():
        # A rank-deficient design is detected below from the degrees of
        # freedom and reported in the result; the library's console warning
        # would only repeat it where nobody reads it.
        warnings.simplefilter("ignore", SingularMatrixWarning)
        restricted = OLS(endog, own).fit()
        unrestricted = OLS(endog, joint).fit()
    df_denom = int(unrestricted.df_resid)
    if int(restricted.df_resid) - df_denom != order or df_denom < 1:
        # A lag column was redundant, so the p restrictions were not all testable.
        return None
    ssr_restricted, ssr_unrestricted = float(restricted.ssr), float(unrestricted.ssr)
    if ssr_restricted <= 0 or ssr_unrestricted <= ssr_restricted * EXACT_FIT:
        return None
    f_value, p_value, _ = unrestricted.compare_f_test(restricted)
    f_value, p_value = float(f_value), float(p_value)
    if not (isfinite(f_value) and isfinite(p_value)):
        return None
    return _Test(order, len(rows), f_value, p_value, df_denom)


def granger_precedence(
    left: Sequence[Observation],
    left_semantics: SeriesSemantics,
    right: Sequence[Observation],
    right_semantics: SeriesSemantics,
    *,
    left_id: str,
    right_id: str,
    max_order: int = DEFAULT_MAX_LAG,
    start: date | None = None,
    end: date | None = None,
    minimum_rows: int = DEFAULT_MINIMUM_PAIRS,
    result_id: str | None = None,
    input_refs: Sequence[str] = DEFAULT_INPUTS,
    lineage_node: str | None = None,
) -> AnalyticalResult:
    """Granger F-tests at every order from 1 to `max_order`, in both directions.

    "`left` precedes `right` at order p" means: adding the previous p declared
    periods of `left` to a constant and the previous p of `right` reduced the
    error of predicting `right` by more than chance would, at the reported
    p-value. The other direction swaps the roles. Neither is a mechanism.
    """
    identifier = result_id or f"granger:{left_id}:{right_id}"

    def refuse(
        status: ResultStatus, reason: str, samples: SampleCounts, unresolved: Sequence[str] = ()
    ) -> AnalyticalResult:
        return _refuse(
            identifier, ResultKind.CAUSALITY, status, reason, samples, unresolved, method=METHOD
        )

    if not 1 <= max_order <= LAG_CAP:
        return refuse(
            ResultStatus.ABSTAINED,
            f"A Granger order of {max_order} is outside the permitted 1..{LAG_CAP}; the test "
            "needs at least one past period, and every extra order is another chance to find "
            "something by searching",
            SampleCounts(used=0),
        )
    prepared = _prepare(left, left_semantics, right, right_semantics, start, end)
    if isinstance(prepared, str):
        return refuse(
            ResultStatus.ABSTAINED,
            prepared,
            SampleCounts(used=0),
            left_semantics.unresolved + right_semantics.unresolved,
        )
    periods, xs, ys, dropped = prepared
    positions = _calendar_positions(periods, left_semantics)
    if isinstance(positions, str):
        return refuse(ResultStatus.ABSTAINED, positions, SampleCounts(used=0))
    counts = SampleCounts(used=len(xs), missing=dropped, minimum_required=minimum_rows)

    rows_by_order = {order: _rows(positions, order) for order in range(1, max_order + 1)}
    eligible = [
        order
        for order, rows in rows_by_order.items()
        if len(rows) >= _rows_needed(order, minimum_rows)
    ]
    if not eligible:
        return refuse(
            ResultStatus.INSUFFICIENT,
            f"No Granger order in 1..{max_order} had enough calendar-valid rows: order p "
            f"needs {ROWS_PER_COEFFICIENT} rows per coefficient (2p + 1) and never fewer "
            f"than {minimum_rows}; {len(xs)} period(s) aligned",
            counts,
        )
    if len(set(xs)) < 2 or len(set(ys)) < 2:
        return refuse(
            ResultStatus.UNDEFINED,
            "One of the series does not vary over these periods, so neither can improve a "
            "prediction of the other; the test is undefined rather than negative",
            counts,
        )

    directions = (
        ("forward", left_id, right_id, ys, xs),
        ("backward", right_id, left_id, xs, ys),
    )
    found: dict[str, list[_Test]] = {}
    degenerate = 0
    for name, _, _, target, other in directions:
        found[name] = []
        for order in eligible:
            test = _f_test(target, other, rows_by_order[order], order)
            if test is None:
                degenerate += 1
            else:
                found[name].append(test)

    coverage = Period(start=periods[0], end=periods[-1])
    values: list[ResultValue] = []
    for name, cause, effect, _, _ in directions:
        for test in found[name]:
            prefix = f"{cause} precedes {effect}, Granger order {test.order}"
            values.extend(
                ResultValue(
                    label=label,
                    value=value,
                    unit=DIMENSIONLESS,
                    scale=Scale.ONE,
                    period=coverage,
                    samples=SampleCounts(used=test.rows),
                )
                for label, value in (
                    (f"{prefix}: p-value", test.p_value),
                    (f"{prefix}: F({test.order}, {test.df_denom})", test.f_value),
                )
            )
    tests_run = sum(len(tests) for tests in found.values())
    if not tests_run:
        return refuse(
            ResultStatus.UNDEFINED,
            "Every regression was exact or had a redundant lag column, which leaves no F "
            "statistic to report",
            counts,
        )

    return AnalyticalResult(
        result_id=identifier,
        kind=ResultKind.CAUSALITY,
        status=ResultStatus.COMPUTED,
        tool="analytics",
        method=METHOD,
        values=values,
        coverage=coverage,
        parameters={
            "left": left_id,
            "right": right_id,
            "method": (
                "Granger F-test on residual sums of squares: a constant and p own lags, "
                "against the same plus p lags of the other series"
            ),
            "directions": {
                "forward": f"{left_id} precedes {right_id}",
                "backward": f"{right_id} precedes {left_id}",
            },
            "max_order": max_order,
            "orders_tested": {name: [test.order for test in found[name]] for name in found},
            "tests_run": tests_run,
            "lag_unit": (
                f"declared {left_semantics.frequency.value} periods; a row needs its period and "
                "the p before it published by both series, so no row reaches across a gap"
            ),
            "minimum_rows": minimum_rows,
            "rows_per_coefficient": ROWS_PER_COEFFICIENT,
            "row_floor_status": "PROPOSED; no benchmark has measured it",
        },
        samples=counts,
        evidence=ResultEvidence(input_refs=list(input_refs), lineage_node=lineage_node),
        warnings=_warnings(
            xs, ys, max_order, eligible, tests_run, degenerate, dropped, minimum_rows
        ),
        limitations=[*BASE_LIMITATIONS, *GRANGER_LIMITATIONS],
    )


def _warnings(
    xs: Sequence[float],
    ys: Sequence[float],
    max_order: int,
    eligible: Sequence[int],
    tests_run: int,
    degenerate: int,
    dropped: int,
    minimum_rows: int,
) -> list[str]:
    """What a reader has to know before quoting a p-value."""
    notes = [
        "A small p-value at order p means the other series' previous p periods improved the "
        "prediction beyond the series' own past: predictive precedence, not a mechanism",
        f"{tests_run} Granger test(s) were run across orders and both directions; the smallest "
        "p-value was found by searching, so it is not a pre-specified test",
    ]
    untested = [order for order in range(1, max_order + 1) if order not in eligible]
    if untested:
        notes.append(
            f"Order(s) {', '.join(map(str, untested))} were not tested: an order-p regression "
            f"estimates 2p + 1 coefficients and needs {ROWS_PER_COEFFICIENT} calendar-valid rows "
            f"for each, and never fewer than {minimum_rows}"
        )
    if degenerate:
        notes.append(
            f"{degenerate} test(s) were skipped because the regression was exact or a lag "
            "column was redundant, which leaves no F statistic"
        )
    if any(score is not None and abs(score) > TREND_LIMIT for score in (_trend(xs), _trend(ys))):
        notes.append(
            "At least one series trends strongly over this window; the Granger F-test assumes "
            "stationary series and rejects far too often on trending levels, so compare "
            "period-over-period changes before reading precedence"
        )
    if dropped:
        notes.append(
            f"{dropped} period(s) were dropped because one series had no published value; "
            "no regression row reaches across a gap"
        )
    return notes
