"""What the store declares about a column whose values are running totals.

The organizer's brief warns that some BDDK figures accumulate from their first publication
and some within each year, and that a calculation which ignores it is wrong. The store
records which series do (`silver_series.cumulative`), the analysis tools that read a
stored series refuse them, and `to_flow` converts them. But a table cell carries no
cumulative kind, so every table operation took a year-to-date column for each month's own
amount: a served turn summed twelve running totals into "2021 toplam net kârı 7.800 milyon
TL" where the year earned 1.200, and the answer gate accepted it, because every figure in
the sentence was one the harness had computed (audit of 2026-09-21).

A lakehouse read labels each column by its `series_id`, so the declaration is one lookup
away. A column `to_flow` produced is labelled differently and is no stored series, so it
is never refused here; neither is a document column, about which nothing is declared.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:  # pragma: no cover
    from duckdb import DuckDBPyConnection

#: The declarations under which a value is a running total rather than the period's amount.
ACCUMULATING: Final = ("yearly_reset", "since_inception")

_WORDS: Final = {
    "yearly_reset": "a year-to-date running total that starts again every January",
    "since_inception": "a running total since the series began",
}


def declared_accumulation(connection: DuckDBPyConnection, label: str) -> str | None:
    """The accumulating kind the store declares for this column's series, if it declares one."""
    row = connection.execute(
        "SELECT cumulative FROM silver_series WHERE series_id = ?", [label]
    ).fetchone()
    return row[0] if row is not None and row[0] in ACCUMULATING else None


def running_total_refusal(label: str, kind: str, operation: str) -> str:
    """Why `operation` is refused on this column, and what to plan instead."""
    return (
        f"Column {label!r} is declared {kind}: each value is {_WORDS[kind]}, so {operation} of "
        "it measures accumulation, not the amount of each period. Convert it with "
        "table_transform to_flow first (source = this table, column = this label, the read "
        "step in depends_on), then apply this operation to the flow column it adds"
    )


def running_total_limitation(label: str, kind: str) -> str:
    """Said with a read of such a series, so nobody quotes a running total as a month."""
    return (
        f"{label} is declared {kind}: each value is {_WORDS[kind]}, not the amount of that "
        "period alone; table_transform to_flow gives the amount of each period"
    )
