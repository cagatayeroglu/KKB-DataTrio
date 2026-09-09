"""The verifier: no number leaves without a cell behind it (M8, DEC-119).

The first rule is the one that matters. Every number in an answer must resolve
to a value actually stored in the lakehouse, or the answer is rejected. Not
annotated, not hedged — rejected. A hallucinated figure that reaches the user is
worse than no answer, because the evidence panel then certifies it.

Number extraction has to read the way a Turkish answer is written, and that is
not the same as the way Python writes floats. `801.438` is eight hundred and one
thousand four hundred and thirty-eight; `46,75` is forty-six and three quarters.
Reading either the other way is a thousandfold error that still looks plausible,
which is exactly the failure the EVDS inspection found in the source data.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from duckdb import DuckDBPyConnection

#: A number as written: either grouped in threes, or a plain run of digits, with
#: an optional decimal part. Anchored on non-digit boundaries so an identifier
#: like `TP.KTF12` is not mistaken for a quantity.
#:
#: The grouped form is tried first so `801.438` reads as one figure rather than
#: `801` followed by a fragment. A plain alternative is essential: without it a
#: number longer than three digits and written without separators — `801438` —
#: would not match at all, and an unmatched number is one the verifier never
#: checks, which is the worst possible failure for a gate like this.
NUMBER = re.compile(r"(?<![\w.,])[+-]?(?:\d{1,3}(?:[.,  ]\d{3})+|\d+)(?:[.,]\d+)?(?![\w])")

#: Relative closeness required to call a written number the same as a stored one.
#: A written figure is usually rounded, so exact equality would reject correct
#: answers; this permits presentation rounding and nothing more.
DEFAULT_TOLERANCE = 5e-4

#: Four-digit integers in this span are read as years unless a cell matches.
YEAR_RANGE = range(1900, 2101)


class Binding(StrEnum):
    CELL = "cell"
    OBSERVATION = "observation"
    CONTEXT = "context"
    YEAR = "year"
    UNBOUND = "unbound"


@dataclass(frozen=True, slots=True)
class WrittenNumber:
    """A quantity as it appears in the answer, and what it parsed to."""

    text: str
    value: float
    start: int

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return self.text


@dataclass(frozen=True, slots=True)
class NumberVerdict:
    number: WrittenNumber
    binding: Binding
    lineage_node: str | None = None
    source: str | None = None

    @property
    def supported(self) -> bool:
        return self.binding is not Binding.UNBOUND


@dataclass(frozen=True, slots=True)
class Verdict:
    """Whether an answer may be shown, and why."""

    accepted: bool
    numbers: tuple[NumberVerdict, ...]
    limitations: tuple[str, ...] = ()
    rejected: tuple[str, ...] = field(default_factory=tuple)

    @property
    def unbound(self) -> tuple[WrittenNumber, ...]:
        return tuple(item.number for item in self.numbers if not item.supported)

    def lineage_nodes(self) -> tuple[str, ...]:
        seen: list[str] = []
        for item in self.numbers:
            if item.lineage_node and item.lineage_node not in seen:
                seen.append(item.lineage_node)
        return tuple(seen)


def parse_written(text: str) -> float | None:
    """Read a number the way it was written, or return None if it is ambiguous.

    Turkish writes `801.438` for a thousands-grouped integer and `46,75` for a
    decimal, and English does the reverse. When the separators present make both
    readings possible, this refuses rather than picking one — an ambiguous
    figure in an answer is a defect in the answer, not a puzzle to solve.
    """
    cleaned = text.replace(" ", "").replace(" ", "").replace("+", "")
    negative = cleaned.startswith("-")
    cleaned = cleaned.lstrip("-")
    if not cleaned:
        return None
    dots, commas = cleaned.count("."), cleaned.count(",")

    if dots and commas:
        # The rightmost separator is the decimal point in either convention.
        decimal = "." if cleaned.rfind(".") > cleaned.rfind(",") else ","
        grouping = "," if decimal == "." else "."
        if not _groups_are_valid(cleaned, grouping, decimal):
            return None
        cleaned = cleaned.replace(grouping, "").replace(decimal, ".")
    elif dots or commas:
        separator = "." if dots else ","
        count = dots or commas
        head, _, tail = cleaned.rpartition(separator)
        if count > 1 or len(tail) == 3:
            # Groups of three: thousands, in either convention.
            if not _groups_are_valid(cleaned, separator, None):
                return None
            cleaned = cleaned.replace(separator, "")
        else:
            cleaned = f"{head}.{tail}"
    try:
        value = float(cleaned)
    except ValueError:  # pragma: no cover - the pattern admits only numerals
        return None
    return -value if negative else value


def _groups_are_valid(text: str, grouping: str, decimal: str | None) -> bool:
    integer = text.split(decimal)[0] if decimal else text
    head, *rest = integer.split(grouping)
    return bool(head) and len(head) <= 3 and all(len(part) == 3 for part in rest)


def extract_numbers(text: str) -> list[WrittenNumber]:
    """Every quantity in the answer, in the order it appears."""
    found: list[WrittenNumber] = []
    for match in NUMBER.finditer(text):
        value = parse_written(match.group())
        if value is not None:
            found.append(WrittenNumber(match.group(), value, match.start()))
    return found


def verify(
    answer: str,
    connection: DuckDBPyConnection,
    *,
    allowed: Iterable[float] = (),
    tolerance: float = DEFAULT_TOLERANCE,
    accept_years: bool = True,
) -> Verdict:
    """Bind every number in `answer` to stored data, or reject the answer.

    `allowed` holds quantities the caller has already justified — figures from
    the question itself, or a period count it computed. Everything else must be
    in the lakehouse. Years are recognized separately so that "2021-2025 arası"
    does not require a cell, and that recognition is switchable because a year
    can also be a value.
    """
    permitted = [float(value) for value in allowed]
    verdicts: list[NumberVerdict] = []
    for number in extract_numbers(answer):
        verdicts.append(_bind(number, connection, permitted, tolerance, accept_years))

    unbound = [item for item in verdicts if not item.supported]
    rejected = tuple(f"{item.number.text!r} does not match any stored value" for item in unbound)
    limitations = (
        "Numbers are bound to stored cells; no second-path recomputation was run",
        "No external cross-check was performed",
    )
    return Verdict(not unbound, tuple(verdicts), limitations, rejected)


def _bind(
    number: WrittenNumber,
    connection: DuckDBPyConnection,
    permitted: Sequence[float],
    tolerance: float,
    accept_years: bool,
) -> NumberVerdict:
    if any(_close(number.value, value, tolerance) for value in permitted):
        return NumberVerdict(number, Binding.CONTEXT)

    cell = connection.execute(
        "SELECT column_node_id, table_id, column_name FROM gold_cells"
        " WHERE value IS NOT NULL AND abs(value - ?) <= abs(?) * ? + 1e-9"
        " LIMIT 1",
        [number.value, number.value, tolerance],
    ).fetchone()
    if cell is not None:
        return NumberVerdict(
            number, Binding.CELL, lineage_node=str(cell[0]), source=f"{cell[1]}.{cell[2]}"
        )

    observation = connection.execute(
        "SELECT series_id FROM silver_observations"
        " WHERE value IS NOT NULL AND abs(value - ?) <= abs(?) * ? + 1e-9"
        " LIMIT 1",
        [number.value, number.value, tolerance],
    ).fetchone()
    if observation is not None:
        return NumberVerdict(number, Binding.OBSERVATION, source=str(observation[0]))

    if accept_years and float(number.value).is_integer() and int(number.value) in YEAR_RANGE:
        return NumberVerdict(number, Binding.YEAR)

    return NumberVerdict(number, Binding.UNBOUND)


def _close(left: float, right: float, tolerance: float) -> bool:
    return abs(left - right) <= abs(right) * tolerance + 1e-9
