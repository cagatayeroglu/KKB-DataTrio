"""Gold: several series on one spine, every cell traceable (M12-13).

A gold table is the shape an answer is actually made of — one row per period,
one column per series, aligned on the canonical spine. Two rules make it safe to
read. A period a series did not publish is **null**, never carried forward and
never zero, because a flat line drawn from a forward fill is indistinguishable
from a real one. And every column is written with a lineage id, so any cell can
be traced back to the bronze bytes it rests on.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from kkb_agent.core import Frequency, WeeklyAnchor
from kkb_agent.lakehouse.lineage import EdgeKind, Lineage, NodeKind
from kkb_agent.lakehouse.periods import spine
from kkb_agent.lakehouse.records import Observation

GOLD_SCHEMA = """
CREATE TABLE IF NOT EXISTS gold_cells (
    table_id        TEXT NOT NULL,
    column_name     TEXT NOT NULL,
    period_start    DATE NOT NULL,
    period_end      DATE NOT NULL,
    value           DOUBLE,
    column_node_id  TEXT NOT NULL,
    PRIMARY KEY (table_id, column_name, period_end)
);
"""


class GoldError(ValueError):
    """A gold table was requested in a way that would misrepresent the inputs."""


@dataclass(frozen=True, slots=True)
class GoldColumn:
    """One series placed on the table's spine, with what it actually covered."""

    name: str
    node_id: str
    observed: int
    expected: int

    @property
    def missing(self) -> int:
        return self.expected - self.observed

    @property
    def complete(self) -> bool:
        return self.observed == self.expected


@dataclass(frozen=True, slots=True)
class GoldTable:
    """A period-indexed table plus the coverage and lineage behind each column."""

    table_id: str
    periods: list[tuple[date, date]]
    columns: dict[str, GoldColumn]
    cells: dict[str, dict[date, float | None]]

    def row(self, period_end: date) -> dict[str, float | None]:
        return {name: self.cells[name].get(period_end) for name in self.columns}

    def incomplete_columns(self) -> list[str]:
        return [name for name, column in sorted(self.columns.items()) if not column.complete]


def build_gold(
    table_id: str,
    columns: Mapping[str, Sequence[Observation]],
    *,
    frequency: Frequency,
    first_end: date,
    last_end: date,
    anchor: WeeklyAnchor | None = None,
    lineage: Lineage,
    upstream: Mapping[str, Sequence[tuple[str, EdgeKind]]],
) -> GoldTable:
    """Place each series on one spine and record a lineage node per column.

    `upstream` names, per column, the lineage nodes the column derives from —
    typically its silver series and the transform that produced it. A column
    with no upstream is refused: an untraceable column is exactly what DEC-118
    forbids, and it is cheaper to fail here than to discover it in a demo.
    """
    if not table_id.strip():
        raise GoldError("A gold table needs an id")
    if not columns:
        raise GoldError("A gold table needs at least one column")
    periods = spine(frequency, first_end, last_end, anchor=anchor)
    period_ends = [end for _, end in periods]
    known = set(period_ends)

    built: dict[str, GoldColumn] = {}
    cells: dict[str, dict[date, float | None]] = {}
    for name, observations in columns.items():
        parents = list(upstream.get(name, ()))
        if not parents:
            raise GoldError(f"Column {name!r} has no upstream lineage; it would be untraceable")
        supplied = {item.period_end: item.value for item in observations}
        if len(supplied) != len(observations):
            raise GoldError(f"Column {name!r} has duplicate periods")
        stray = sorted(set(supplied) - known)
        if stray:
            raise GoldError(
                f"Column {name!r} has {len(stray)} observation(s) off the table's spine, "
                f"first {stray[0].isoformat()}"
            )
        # Absent and explicitly-missing periods are both null. Neither is
        # filled forward: a flat line from a fill looks exactly like real data.
        column_cells = {end: supplied.get(end) for end in period_ends}
        observed = sum(1 for value in column_cells.values() if value is not None)
        node = lineage.record(
            NodeKind.COLUMN,
            name,
            attributes={
                "table_id": table_id,
                "frequency": frequency.value,
                "first_period": period_ends[0].isoformat(),
                "last_period": period_ends[-1].isoformat(),
                "observed": str(observed),
                "expected": str(len(period_ends)),
            },
            upstream=parents,
        )
        built[name] = GoldColumn(name, node, observed=observed, expected=len(period_ends))
        cells[name] = column_cells
    return GoldTable(table_id, periods, built, cells)


def persist_gold(connection: object, table: GoldTable) -> int:
    """Write the table's cells, with each cell carrying its column's lineage id."""
    rows = []
    for name, column in table.columns.items():
        for start, end in table.periods:
            rows.append([table.table_id, name, start, end, table.cells[name][end], column.node_id])
    connection.executemany(  # type: ignore[attr-defined]
        "INSERT OR REPLACE INTO gold_cells VALUES (?, ?, ?, ?, ?, ?)", rows
    )
    return len(rows)
