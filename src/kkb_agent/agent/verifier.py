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
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING, Final

import duckdb

from kkb_agent.agent.claim_qualifiers import SCALE_WORDS as SCALE_WORDS
from kkb_agent.agent.claim_qualifiers import (
    absence_fault,
    amount_qualifiers,
    causal_fault,
    clause_context,
    comovement_count_identity_fault,
    fold,
    has_amount_context,
    identity_fault,
    is_base_notation,
    is_date_token,
    is_list_marker,
    period_fault,
    table_count_identity_fault,
    unit_fault,
    value_meaning,
)
from kkb_agent.agent.literal import exposes_literal_identity, literal_proof, literal_text
from kkb_agent.agent.presentation import endpoint_observations
from kkb_agent.core import (
    AnalyticalResult,
    ClaimKind,
    Frequency,
    Period,
    ResultStatus,
    ResultValue,
    Scale,
)
from kkb_agent.lakehouse.result_evidence import execution_proof

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
#:
#: The sign may be the typographic minus, U+2212, as well as the ASCII hyphen. A model
#: writing for a reader uses it: live 2026-09-23 the jury's A1 answer wrote its monthly
#: differences with it, the sign was not part of the match, and five correct negative
#: figures were each reported as a positive one no tool had returned (QA-20). A minus
#: glued to a preceding digit or word is still not a sign — that is the lookbehind — so
#: a range written with it between two years stays two years.
MINUS: Final = "\u2212"
NUMBER = re.compile(r"(?<![\w.,])[+\-\u2212]?(?:\d{1,3}(?:[.,  ]\d{3})+|\d+)(?:[.,]\d+)?(?![\w])")

#: Relative closeness required to call a written number the same as a stored one.
#: A written figure is usually rounded, so exact equality would reject correct
#: answers; this permits presentation rounding and nothing more.
DEFAULT_TOLERANCE = 5e-4

#: Calendar-like integers; attached amount qualifiers disable the exception.
YEAR_RANGE = range(1900, 2101)

#: A window this long is described in years as well as in its own periods.
MONTHS_IN_YEAR: Final = 12


class Binding(StrEnum):
    #: Bound to a named value of a specific result: the only binding that
    #: establishes *which* figure was quoted rather than that one like it exists.
    RESULT = "result"
    CELL = "cell"
    OBSERVATION = "observation"
    CONTEXT = "context"
    YEAR = "year"
    UNBOUND = "unbound"


# A line break always ends a claim: a table row or list item is its own sentence, so
# one row's period can never qualify a number on another row.
_SENTENCE_BREAK: Final = re.compile(r"[.!?]\s|\n")


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
    #: The result and value this number was bound to, when it was bound to one.
    result_id: str | None = None
    value_label: str | None = None
    #: Why a number that *was* found is still not presentable — a contradicted
    #: scale, a contradicted period, semantics the result never established.
    faults: tuple[str, ...] = ()

    @property
    def supported(self) -> bool:
        """Bound *and* free of contradictions. Finding a match is not enough.

        A figure quoted as million when the series is published in thousand
        was found in the data and is still wrong by a factor of a thousand.
        """
        return self.binding is not Binding.UNBOUND and not self.faults


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
    cleaned = cleaned.replace(MINUS, "-")
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
    """Every quantity in the answer, in the order it appears.

    A list marker is not a quantity. "(1)" and "(2)" in a sentence that names two
    tools measure nothing, and treating them as claims withheld the sentence that
    answered the question (live 2026-09-20).
    """
    found: list[WrittenNumber] = []
    for match in NUMBER.finditer(text):
        value = parse_written(match.group())
        if value is None:
            continue
        if is_list_marker(text, match.start(), match.end()) or is_base_notation(
            text, match.start(), match.end()
        ):
            continue
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
        calendar_allowed = accept_years and not has_amount_context(
            answer, number.start, number.start + len(number.text)
        )
        verdicts.append(_bind(number, connection, permitted, tolerance, calendar_allowed))

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


# --------------------------------------------------------------------------
# M8-06/07: binding a claim to one result rather than to the whole store.
#
# `verify` above answers "does a number like this exist anywhere?". That is a
# weak question, and it accepts a right-looking figure taken from the wrong
# series, the wrong period or the wrong scale. The functions below answer the
# question that matters: "is this the number this analysis produced, and does
# the sentence around it agree with what the analysis established?".
# --------------------------------------------------------------------------


def _sentence_around(text: str, position: int) -> tuple[str, int]:
    """The sentence a number sits in, which bounds every contextual check.

    Scanning a fixed character window instead would drag in a neighbouring
    sentence's year and reject a correct answer, and a verifier that rejects
    correct answers gets switched off.
    """
    start = 0
    for match in _SENTENCE_BREAK.finditer(text, 0, position):
        start = match.end()
    end = len(text)
    tail = _SENTENCE_BREAK.search(text, position)
    if tail is not None:
        end = tail.start()
    return text[start:end], start


def _scale_fault(answer: str, number: WrittenNumber, value: ResultValue) -> str | None:
    """Catch a figure quoted at a scale the data does not carry.

    This is the BDDK/FinTürk trap at the presentation layer: the bulletins
    publish million TRY and FinTürk thousand, so "milyon" attached to a
    thousand-scaled value is a thousandfold error that survives every check
    based on the value alone.
    """
    written, _ = amount_qualifiers(answer, number.start, number.start + len(number.text))
    if written is None:
        return None
    if value.scale is Scale.UNKNOWN:
        return (
            f"{number.text!r} is written as {written.value!r}, but the result never "
            "established a scale for it"
        )
    if written is not value.scale:
        return (
            f"{number.text!r} is written as {written.value!r} while the value is "
            f"recorded as {value.scale.value}"
        )
    return None


#: One comma and three digits after it: "512,259". Alone it is ambiguous, and the gate reads it
#: as thousands grouping; after a scale word the value does not carry, Turkish means a decimal.
_TURKISH_DECIMAL_OF_THREE = re.compile(r"[+\-\u2212]?\d{1,3},\d{3}")


def _rescaled(
    number: WrittenNumber, written: Scale | None, value: ResultValue, tolerance: float
) -> bool:
    """Whether the figure is the value itself, written at another explicit scale.

    "Bu değeri milyar TL olarak yaz": 512.259 milyon TL is 512,259 milyar TL, and the gate
    withheld the correct conversion because the figure matched no stored number at the
    stored scale (N44, live G3 2026-09-22). Only an explicit scale word that differs from a
    known recorded scale is converted, and only by the exact power of ten between them, so
    the model's own "0,512259 milyar TL" (a thousandfold error, live G3b) still matches
    nothing. "512,259" after such a word is read the Turkish way, as a decimal; every
    other written form keeps the reading `parse_written` gave it.

    Writing a figure at a **coarser** scale spends digits: 49.046 milyon TL is 49,046
    milyar, and an answer that says "49,0 milyar" has not approximated out of vagueness
    but written the number that scale can hold. The binding tolerance is 0.05%, sized to
    catch a mistyped digit, so it refused a conversion the answer was right to make (live
    2026-09-22, six correct months reported as unbound). Such a figure binds when it is
    the correct rounding at the precision it was written to — the same test
    `_rounds_as_written` applies, justified here by the scale rather than by a hedge word,
    because "49,0 milyar" already states how precise it is. A rounding that is wrong at
    that precision, and the thousandfold error above, still match nothing.
    """
    if written is None or value.scale in (Scale.UNKNOWN, written):
        return False
    reading = number.value
    if _TURKISH_DECIMAL_OF_THREE.fullmatch(number.text.strip()):
        reading = float(number.text.strip().replace(MINUS, "-").replace(",", "."))
    exact = value.value * value.scale.factor
    if _close(reading * written.factor, exact, tolerance):
        return True
    if written.factor <= value.scale.factor:
        return False
    return round(exact / written.factor, _written_decimals(number.text)) == reading


def _semantics_fault(number: WrittenNumber, value: ResultValue) -> str | None:
    if not value.semantics_are_unresolved:
        return None
    missing = "unit" if value.unit is None else "scale"
    return f"{number.text!r} rests on a value whose {missing} the result left unresolved"


def _result_faults(result: AnalyticalResult, minimum_samples: int | None) -> list[str]:
    """What disqualifies the whole result, before any number is looked at."""
    faults: list[str] = []
    if result.status is not ResultStatus.COMPUTED:
        faults.append(
            f"The result is {result.status.value} and establishes no value: "
            f"{result.reason or 'no reason recorded'}"
        )
    if minimum_samples is not None:
        used = result.samples.used if result.samples is not None else 0
        if used < minimum_samples:
            faults.append(f"{used} observations is below the {minimum_samples} this claim requires")
    return faults


def _evidence_faults(result: AnalyticalResult, connection: DuckDBPyConnection) -> list[str]:
    """Resolve the references the result preserved, instead of trusting them.

    An evidence reference that does not resolve is worse than an absent one: it
    reads as provenance in every panel that renders it while pointing at
    nothing. Table names and lineage nodes are the two forms a producer writes
    today, and both are checked against the database.
    """
    if result.evidence is None:
        return []
    faults: list[str] = []
    known = {
        str(row[0])
        for row in connection.execute("SELECT table_name FROM information_schema.tables").fetchall()
    }
    node = result.evidence.lineage_node
    if node is not None:
        found = connection.execute(
            "SELECT 1 FROM lineage_nodes WHERE node_id = ?", [node]
        ).fetchone()
        if found is None:
            faults.append(f"Lineage node {node!r} is referenced but not stored")
    for reference in result.evidence.input_refs:
        if reference in known:
            continue
        found = connection.execute(
            "SELECT 1 FROM lineage_nodes WHERE node_id = ?", [reference]
        ).fetchone()
        if found is None:
            faults.append(f"Input reference {reference!r} resolves to no table and no lineage node")
    return faults


def _stored_value(
    connection: DuckDBPyConnection,
    label: str,
    period_end: date,
    *,
    result_version: str,
    period_start: date,
) -> float | None:
    """A source cell, or gold materialized from exactly this immutable result.

    A derived label is reusable across windows and versions. Its spelling and
    month cannot identify a materialization; the producer-signed result digest can.
    """
    row = connection.execute(
        "SELECT value FROM silver_observations WHERE series_id = ? AND period_end = ?",
        [label, period_end],
    ).fetchone()
    if row is not None and row[0] is not None:
        return float(row[0])
    row = connection.execute(
        "SELECT g.value FROM gold_cells g JOIN lineage_nodes n ON n.node_id = g.column_node_id "
        "WHERE g.column_name = ? AND g.period_start = ? AND g.period_end = ? "
        "AND json_extract_string(n.attributes, '$.result_version') = ?",
        [label, period_start, period_end, result_version],
    ).fetchone()
    if row is not None and row[0] is not None:
        return float(row[0])
    return None


def recheck_against_store(
    result: AnalyticalResult,
    connection: DuckDBPyConnection,
    *,
    tolerance: float = DEFAULT_TOLERANCE,
) -> tuple[str, ...]:
    """Recompute what can be recomputed, on a path the model did not write.

    Only values that name a series and a period can be rechecked; an aggregate
    labelled `value` has no identity to look up and is skipped rather than
    guessed at. This is a second read of the same store, not an independent
    derivation, so it catches a wrong join, a wrong period or an altered
    figure — and it does not catch a wrong number that was stored wrongly.
    """
    faults: list[str] = []
    version = result.digest()
    for value in result.values:
        if value.period is None:
            continue
        stored = _stored_value(
            connection,
            value.label,
            value.period.end,
            result_version=version,
            period_start=value.period.start,
        )
        if stored is None:
            continue
        if not _close(value.value, stored, tolerance):
            faults.append(
                f"{value.label!r} at {value.period.end.isoformat()} is stored as {stored} "
                f"but the result reports {value.value}"
            )
    return tuple(faults)


def _as_named(
    results: AnalyticalResult | Sequence[AnalyticalResult] | Mapping[str, AnalyticalResult],
) -> dict[str, AnalyticalResult]:
    """Accept one result, several, or several under workspace names.

    A name is how an answer about a table refers to its columns, so when the
    caller has one — the workspace slot — it is kept and reported in the
    verdict. Without one, the result's own id is the name.
    """
    if isinstance(results, AnalyticalResult):
        return {results.result_id: results}
    if isinstance(results, Mapping):
        return dict(results)
    return {item.result_id: item for item in results}


def result_faults(
    named: Mapping[str, AnalyticalResult],
    connection: DuckDBPyConnection | None = None,
    *,
    tolerance: float = DEFAULT_TOLERANCE,
    minimum_samples: int | None = None,
) -> dict[str, tuple[str, ...]]:
    """What disqualifies each result, before any number is looked at.

    Keyed by name and prefixed with it, because "which column is broken" is
    the first thing an operator needs and the last thing a flat list of
    reasons tells them.
    """
    found: dict[str, tuple[str, ...]] = {}
    for name, result in named.items():
        faults = _result_faults(result, minimum_samples)
        try:
            if result.claim_kind is ClaimKind.LITERAL_SOURCE_VALUE:
                if not literal_proof(result, connection):
                    faults.append(
                        "Literal source value does not resolve to its exact recorded cell"
                    )
            elif result.status is ResultStatus.COMPUTED and not execution_proof(result, connection):
                faults.append(
                    "Numeric analytical result lacks matching trusted producer execution evidence"
                )
            if connection is not None:
                faults.extend(_evidence_faults(result, connection))
                faults.extend(recheck_against_store(result, connection, tolerance=tolerance))
        except (duckdb.Error, ValueError, TypeError, AttributeError, RuntimeError):
            faults.append("Evidence resolver unavailable or invalid; result cannot be verified")
        if faults:
            found[name] = tuple(f"{name}: {fault}" for fault in faults)
    return found


def verify_claims(
    answer: str,
    results: AnalyticalResult | Sequence[AnalyticalResult] | Mapping[str, AnalyticalResult],
    connection: DuckDBPyConnection | None = None,
    *,
    allowed: Iterable[float] = (),
    context_counts: Iterable[WindowCount] = (),
    tolerance: float = DEFAULT_TOLERANCE,
    accept_years: bool = True,
    minimum_samples: int | None = None,
    written_precision: bool = False,
    lenient_periods: bool = False,
) -> Verdict:
    """Gate an answer against the results it claims to describe.

    `written_precision` also binds a figure written with decimals that is the value
    correctly rounded to those decimals (QA-22). Off by default: the planned path hands
    its writer display phrases to copy exactly and withholds a rounded one by design;
    the loop's report, which names an unbound figure instead of removing it, turns it on.

    Unlike `verify`, a number here must belong to one of **these** results, to
    the caller's justified context, or be a year. There is deliberately no
    fallback to searching the whole store: "some cell holds a number like
    that" is the weak guarantee this function exists to replace.

    Disqualification is per result rather than per answer. A broken
    `konut_faiz` must not silence a sound claim about `konut_stok`; it faults
    exactly the numbers resting on it. Only when **every** result is
    disqualified does the whole draft fall — which is also what happens when
    there is one result and it is the broken one.
    """
    named = _as_named(results)
    permitted = [float(value) for value in allowed]
    limitations = [
        "Numbers are bound to these results' values, not to any stored value",
        "No external cross-check was performed",
        "Explicit identifiers, calendar and financial qualifiers use a bounded deterministic "
        "vocabulary; arbitrary prose and causal meaning are not proved",
    ]
    if connection is None:
        limitations.append("No store recheck was run: no database connection was supplied")
    else:
        limitations.append(
            "The store recheck is a second read keyed on series and period, not an "
            "independent derivation: it catches a wrong join, period or altered figure, "
            "not a value that was stored wrongly"
        )

    disqualified = result_faults(
        named, connection, tolerance=tolerance, minimum_samples=minimum_samples
    )
    for name, result in named.items():
        if result.unresolved_semantics:
            limitations.append(
                f"{name} declares unresolved semantics: " + "; ".join(result.unresolved_semantics)
            )

    counted = (*window_counts(named.values()), *context_counts)
    verdicts = [
        _bind_to_results(
            answer,
            number,
            named,
            disqualified,
            permitted,
            counted,
            tolerance,
            accept_years,
            written_precision,
            lenient_periods,
        )
        for number in extract_numbers(answer)
    ]

    rejected: list[str] = []
    if exposes_literal_identity(answer, list(named.values())):
        rejected.append("Internal document proof identifiers are not answer text")
    # What the gate guarantees is figures: every number in the answer is a value a tool
    # computed, with its unit, scale and period. Wording is the writer's. The word lists
    # that used to withhold a sentence for its vocabulary (cause, absence, superlatives,
    # endpoint direction) could not tell a denial from an assertion, withheld the hedged
    # reading the writer is asked for, and cost the turn its table; `WORDING_RULES`
    # restores them for a caller that wants the old contract.
    for start, end in _sentence_spans(answer) if WORDING_RULES else ():
        if fault := causal_fault(answer[start:end]):
            rejected.append(fault)
        if fault := _observation_fault(
            answer[start:end],
            {name: result for name, result in named.items() if name not in disqualified},
        ):
            rejected.append(fault)
    if named and len(disqualified) == len(named):
        # Nothing in the draft can be trusted, including its unnumbered prose,
        # because the prose describes the same broken analysis.
        for faults in disqualified.values():
            rejected.extend(faults)
    for item in verdicts:
        if item.binding is Binding.UNBOUND:
            rejected.append(f"{item.number.text!r} does not match any value in these results")
        rejected.extend(item.faults)
    return Verdict(not rejected, tuple(verdicts), tuple(limitations), tuple(rejected))


def verify_result(
    answer: str,
    result: AnalyticalResult,
    connection: DuckDBPyConnection | None = None,
    **options: object,
) -> Verdict:
    """Gate an answer against one result: `verify_claims` with a single entry."""
    return verify_claims(answer, result, connection, **options)  # type: ignore[arg-type]


#: What a clause has to name before one of the harness's own counts may be quoted in
#: it. A count that is merely *a* number the harness holds is not a number the sentence
#: may use for anything: over a five-year monthly window the counts are 60 and 5, and
#: without this "5 dönem yayımlanmamıştı" was accepted although nothing was missing, and
#: "60 farklı seri incelendi" although one series was read. Each count now answers only
#: to its own word, so a true sentence passes and the same digits in the wrong role do
#: not. The words are matched on folded text, so case and dotted/dotless i do not matter.
_COUNT_WORDS: Final = {
    "months": (
        "ay",
        "ayda",
        "ayı",
        "ayın",
        "aylık",
        "aylar",
        "aylarda",
        "month",
        "months",
        "monthly",
    ),
    "years": (
        "yıl",
        "yılda",
        "yılı",
        "yılın",
        "yıllık",
        "yıllar",
        "sene",
        "senede",
        "year",
        "years",
    ),
    "weeks": ("hafta", "haftada", "haftanın", "haftalık", "haftalar", "week", "weeks", "weekly"),
    "days": ("gün", "günde", "günün", "günlük", "günler", "day", "days", "daily"),
    "lags": ("lag", "lags", "gecikme", "gecikmeli"),
    "used": ("gözlem", "gözlemi", "gözlemle", "gözlemde", "observation", "observations"),
    "missing": (
        "eksik",
        "eksikti",
        "eksiktir",
        "yayımlanmamış",
        "yayımlanmamıştı",
        "atlanan",
        "atlandı",
        "missing",
    ),
    "excluded": ("dışlanan", "dışlandı", "çıkarılan", "çıkarıldı", "excluded"),
}
#: Folded once here rather than spelled folded above, where a hand-written "dislandi"
#: for "dışlandı" would silently never match.
COUNT_WORDS: Final = {
    role: frozenset(fold(w) for w in words) for role, words in _COUNT_WORDS.items()
}
_COUNT_CLAUSE_CONNECTORS: Final = frozenset({"ve", "veya", "ama", "fakat", "and", "or", "but"})


#: Words that make the number before them an amount, a rate or a multiple. The amount
#: vocabulary in `claim_qualifiers` reads "60 milyar" and not "60 milyarlık", and knows
#: neither a bare "puan" nor "kat"; a count is never followed by any of them.
_NEVER_A_COUNT: Final = re.compile(
    r"(?:milyar|milyon|trilyon|katrilyon)\w*|bin|binlik|binlerce|puan\w*"
    r"|kat|kati|katina|katindan|katlik|tl|lira\w*|usd|dolar\w*|euro|avro|sterlin\w*"
)


def _nearest_count_role(words: Iterable[str], *, behind: bool = False) -> str | None:
    """The first role before another count or a conjoined claim owns this number.

    Read backwards (`behind`), a role word that itself follows a number belongs to that
    number: in "60 aylık dönemde 60 ..." the months are the first 60's, and lend the
    second nothing.
    """
    listed = list(words)
    for index, word in enumerate(listed):
        if index >= 5 or word in _COUNT_CLAUSE_CONNECTORS or word.isdecimal():
            break
        for role, vocabulary in COUNT_WORDS.items():
            if word in vocabulary:
                owned = behind and index + 1 < len(listed) and listed[index + 1].isdecimal()
                return None if owned else role
    return None


@dataclass(frozen=True, slots=True)
class WindowCount:
    """A quantity the harness counted, and the role a sentence must give it."""

    value: float
    role: str

    def named_in(self, clause: str, start: int, end: int) -> bool:
        """A role must attach locally; another number's role grants no licence."""
        after = re.findall(r"\w+", fold(clause[end:]))
        if after and _NEVER_A_COUNT.fullmatch(after[0]):
            return False
        following = _nearest_count_role(after)
        if following is not None:
            return following == self.role
        preceding = _nearest_count_role(
            reversed(re.findall(r"\w+", fold(clause[:start]))), behind=True
        )
        return preceding == self.role


def prompt_counts(question: str) -> tuple[WindowCount, ...]:
    """Only explicit non-financial count roles may be quoted from a question.

    Dates use the existing calendar binding. A prompt is never evidence of an
    analytical amount, rate, scale or result; those must bind to typed producers.
    """
    found = []
    for number in extract_numbers(question):
        end = number.start + len(number.text)
        if has_amount_context(question, number.start, end):
            continue
        for role in COUNT_WORDS:
            count = WindowCount(number.value, role)
            if count.named_in(question, number.start, end):
                found.append(count)
    return tuple(found)


def window_counts(results: Iterable[AnalyticalResult]) -> tuple[WindowCount, ...]:
    """How much data a result rests on, as the harness itself counted it.

    "2021-2025 arasındaki 60 aylık veride …" is a true sentence about the window
    this analysis covers, and the 60 in it is not a claim about any figure. It is
    also not a value of any result, so every such sentence was withheld whole and
    the answer began mid-thought. These counts come from the result's own sample
    counts and the span of its coverage, so quoting one is quoting the harness.

    Two things keep that from becoming a licence. A count binds only where a year
    binds, with no amount qualifier attached, so "60 milyon TL" is still a figure
    that must be one of the result's values. And it binds only in a clause that
    names its role, so the months of a window cannot be quoted as a count of
    series and the periods read cannot be quoted as periods missing.
    """
    found: set[WindowCount] = set()
    for result in results:
        if result.samples is not None:
            found.update(
                WindowCount(float(count), role)
                for count, role in (
                    (result.samples.used, "used"),
                    (result.samples.missing, "missing"),
                    (result.samples.excluded, "excluded"),
                )
                if count
            )
        if result.coverage is not None:
            found.update(_span_counts(result.coverage))
        found.update(_lag_counts(result))
    return tuple(sorted(found, key=lambda count: (count.value, count.role)))


#: How a period unit is said, for a lag the harness itself applied.
_LAG_ROLE: Final = {
    Frequency.MONTHLY: "months",
    Frequency.WEEKLY: "weeks",
    Frequency.DAILY: "days",
    Frequency.BUSINESS_DAY: "days",
}


def _lag_counts(result: AnalyticalResult) -> set[WindowCount]:
    """A lag this result was computed with, in the periods its own table counts.

    "12 aylık değişim 28,97" reports a change the harness computed with lag=12, and the
    12 in it is that parameter, not a figure of any series. Withheld, the sentence took
    the change with it (live 2026-09-22). It binds like any other count: only where a
    clause names its role, and never with an amount word attached.

    A lag is also a count in its own right, whatever the frequency it was measured at:
    "en fazla 4 gecikme" names the parameter, not four months. Reading it only through
    the frequency's role left a causality answer unable to say how many lags it used,
    because a result whose frequency has no role, or which records the lag on its values
    instead of in a transformation, produced nothing to bind to.
    (Taken from PR #316, which found the same gap.)
    """
    frequency = result.coverage.frequency if result.coverage is not None else None
    if frequency is None:
        frequency = next(
            (value.period.frequency for value in result.values if value.period is not None), None
        )
    role = _LAG_ROLE.get(frequency) if frequency is not None else None
    found: set[WindowCount] = set()
    lags = {value.lag for value in result.values if value.lag is not None}
    if result.evidence is not None:
        for record in result.evidence.transformations:
            lag = record.parameters.get("lag")
            if isinstance(lag, int) and not isinstance(lag, bool) and lag > 0:
                lags.add(lag)
    for lag in lags:
        found.add(WindowCount(float(lag), "lags"))
        if role is not None:
            found.add(WindowCount(float(lag), role))
    return found


def _span_counts(period: Period) -> set[WindowCount]:
    """The periods a window holds, and its whole years when it holds a year or more."""
    months = (period.end.year - period.start.year) * MONTHS_IN_YEAR + (
        period.end.month - period.start.month + 1
    )
    counts: set[WindowCount] = set()
    if period.frequency in (Frequency.DAILY, Frequency.BUSINESS_DAY, Frequency.WEEKLY):
        days = (period.end - period.start).days + 1
        weekly = period.frequency is Frequency.WEEKLY
        counts.add(WindowCount(float(days // 7 if weekly else days), "weeks" if weekly else "days"))
    if months >= 1:
        counts.add(WindowCount(float(months), "months"))
    if months >= MONTHS_IN_YEAR:
        counts.add(WindowCount(float(months // MONTHS_IN_YEAR), "years"))
    return counts


#: Turkish puts the direction of a change in the verb, not in the figure's sign.
_FELL = re.compile(r"(azal|düş|dus|gerile|geriled|eksil|daral|kayb)\w*", re.I)
_ROSE = re.compile(r"(art[ıiy]|yüksel|yuksel|büyü|buyu|çık|cik)\w*", re.I)


def _signed_as_written(clause: str, written: float, stored: float) -> bool:
    """Whether a positive figure is this negative value said the Turkish way.

    An analyst writes "faiz 0,40 puan geriledi", never "faiz -0,40 puan geriledi":
    the minus sign lives in the verb, and writing both would say it twice. Matching
    on the signed value alone, the gate refused "bakiye 522 milyon TL azalırken faiz
    0,4030 yüzde puan geriledi" against the -522.0 and -0.403 the tool had returned,
    and withheld four correct sentences of one answer (live 2026-09-22).

    The magnitude still has to match exactly, and every other check — period, unit,
    scale, identity — is applied to the value as before. Only the sign is read from
    the words instead of from the digits.
    """
    if written <= 0 or stored == 0:
        return False
    return bool(_FELL.search(clause)) if stored < 0 else bool(_ROSE.search(clause))


#: Wording that tells the reader the figure is rounded.
_APPROXIMATE = re.compile(
    r"(civar\w*|yaklaşık|yaklasik|dolay\w*|aşağı yukarı|asagi yukari|kabaca|~)", re.I
)


def _written_decimals(text: str) -> int:
    """How precisely the figure was written, in decimal places."""
    fraction = text.rsplit(",", 1)[-1] if "," in text else ""
    return len(fraction) if fraction.isdigit() else 0


def _rounds_as_written(clause: str, number: WrittenNumber, stored: float) -> bool:
    """Whether a figure the clause calls approximate is this value, correctly rounded.

    "faiz oranı yüzde 42 civarında" is how an analyst writes 42.088, and the reader is
    told it is rounded. The binding tolerance is 0.05%, sized to catch a mistyped digit
    rather than to permit rounding, so 42 found no value and 18 did not reach 17.985:
    two sentences that were true, readable and honest about their own precision were
    withheld (live 2026-09-22).

    The rounding still has to be right at the precision the writer chose, so "yüzde 19
    civarında" for 17.985 is refused exactly as before. Every other check on the value
    is unchanged.
    """
    if not _APPROXIMATE.search(clause):
        return False
    return round(stored, _written_decimals(number.text)) == number.value


def _rounded_to_written_places(number: WrittenNumber, stored: float) -> bool:
    """Whether a figure written with decimals is this value, rounded to those decimals.

    "−3,73" is how a report writes −3.7271133; the decimals are the writer's own
    statement of precision, just as a hedge word is for a whole number. The binding
    tolerance is 0.05% of the value, sized to catch a mistyped digit, so on a small
    rate it is narrower than half a unit in the second decimal: live 2026-09-23 three
    correct monthly changes (−3,73, −1,30, −2,45) were reported to the reader as figures
    no tool had returned (QA-22).

    Limited to what was written: at least one decimal, a figure that is not zero, the
    sign the value has, and the rounding exactly right at that precision — so −3,80 for
    −3.727 and +3,73 for it are still refused, and a whole number still needs its hedge
    word. Scale, unit, period and identity are checked afterwards exactly as before.
    """
    places = _written_decimals(number.text)
    if places < 1 or number.value == 0 or (number.value < 0) != (stored < 0):
        return False
    return round(stored, places) == number.value


def _bind_to_results(
    answer: str,
    number: WrittenNumber,
    named: Mapping[str, AnalyticalResult],
    disqualified: Mapping[str, tuple[str, ...]],
    permitted: Sequence[float],
    counted: Sequence[WindowCount],
    tolerance: float,
    accept_years: bool,
    written_precision: bool = False,
    lenient_periods: bool = False,
) -> NumberVerdict:
    end = number.start + len(number.text)
    amount_context = has_amount_context(answer, number.start, end)
    if (
        accept_years
        and not amount_context
        and (
            is_date_token(answer, number.start, end)
            or (number.value.is_integer() and int(number.value) in YEAR_RANGE)
        )
    ):
        return NumberVerdict(number, Binding.YEAR)
    sentence, sentence_start = _sentence_around(answer, number.start)
    clause, prefix = clause_context(sentence, number.start - sentence_start)
    written_scale, _ = amount_qualifiers(answer, number.start, end)
    candidates: list[NumberVerdict] = []
    meanings: list[str] = []
    for name, result in named.items():
        node = result.evidence.lineage_node if result.evidence is not None else None
        for value in result.values:
            approximate = _rounds_as_written(clause, number, value.value)
            # The same value, written at another explicit scale, is still that value.
            rescaled = _rescaled(number, written_scale, value, tolerance)
            # Rounded to the decimals it was written with, its direction in the figure
            # or, for an unsigned figure, in the verb, as an exact match may be.
            rounded = written_precision and (
                _rounded_to_written_places(number, value.value)
                or (
                    _rounded_to_written_places(number, abs(value.value))
                    and _signed_as_written(clause, number.value, value.value)
                )
            )
            if (
                not rescaled
                and not _close(number.value, value.value, tolerance)
                and not (
                    _close(number.value, abs(value.value), tolerance)
                    and _signed_as_written(clause, number.value, value.value)
                )
                and not approximate
                and not rounded
            ):
                continue
            # One rounded figure may stand for several months the clause names together
            # ("Şubat ve Mayıs 2021'de faiz yüzde 18 civarında"), and it is true exactly
            # when every one of them rounds to it. Checked here, the period is supported;
            # checked one value at a time, each month refused the other's.
            spread = approximate and all(
                round(other.value, _written_decimals(number.text)) == number.value
                for other in result.values
                if other.label == value.label
                and other.period is not None
                and period_fault(clause, prefix, other) is None
            )
            faults = tuple(
                fault
                for fault in (
                    None if rescaled else _scale_fault(answer, number, value),
                    None
                    if spread
                    else period_fault(
                        clause,
                        prefix,
                        value,
                        _price_references(result, value),
                        position=number.start - sentence_start - len(prefix),
                        lenient=lenient_periods,
                    ),
                    unit_fault(answer, number.start, end, value),
                    identity_fault(clause, prefix, name, result, value, named),
                    table_count_identity_fault(clause, result, value),
                    comovement_count_identity_fault(clause, result, value),
                    None
                    if (
                        result.claim_kind is ClaimKind.LITERAL_SOURCE_VALUE
                        and name not in disqualified
                        and answer.strip() == literal_text(result)
                    )
                    else _semantics_fault(number, value),
                )
                if fault is not None
            )
            # A number resting on a disqualified result is not presentable,
            # however well it matches: the result it came from is the problem.
            meanings.append(value_meaning(result, value))
            candidates.append(
                NumberVerdict(
                    number,
                    Binding.RESULT,
                    lineage_node=node,
                    source=name,
                    result_id=result.result_id,
                    value_label=value.label,
                    faults=faults + disqualified.get(name, ()),
                )
            )

    supported = [candidate for candidate in candidates if candidate.supported]
    if len(supported) == 1:
        return supported[0]
    if (
        len(supported) > 1
        and len({m for c, m in zip(candidates, meanings, strict=True) if c.supported}) == 1
    ):
        # The same measure with the same figure in several results is one fact, not a choice
        # between two. Live 2026-09-21: two co-movements over one table both count "59
        # transitions compared"; every sentence quoting a count they share was withheld.
        # Compared by what the value means, not by its label: each comparison prefixes its
        # counts with its own identity, so their labels never agree.
        return supported[0]
    if len(supported) > 1:
        return NumberVerdict(
            number,
            Binding.UNBOUND,
            faults=(
                "Ambiguous result/value identity: multiple values match the explicit qualifiers",
            ),
        )
    if candidates:
        # Preserve a failed single binding for diagnostics. No failed candidate
        # may fall through to caller context or the calendar exception.
        if len(candidates) == 1:
            return candidates[0]
        return NumberVerdict(
            number,
            Binding.UNBOUND,
            faults=tuple(
                dict.fromkeys(fault for candidate in candidates for fault in candidate.faults)
            ),
        )
    if any(_close(number.value, value, tolerance) for value in permitted):
        return NumberVerdict(number, Binding.CONTEXT)
    if not amount_context and any(
        _close(number.value, count.value, tolerance)
        and count.named_in(
            clause,
            number.start - sentence_start - len(prefix),
            end - sentence_start - len(prefix),
        )
        for count in counted
    ):
        return NumberVerdict(number, Binding.CONTEXT)
    return NumberVerdict(number, Binding.UNBOUND)


# --------------------------------------------------------------------------
# M8-10: the gate itself.
#
# Verification that nothing routes through is a report, not a gate. Everything
# below decides what may actually be shown, and the decision is mechanical: a
# sentence carrying a number the verifier could not support is withheld, what
# survives is qualified by the verdict's own limitations, and an answer with
# nothing left becomes an abstention rather than a shorter claim.
# --------------------------------------------------------------------------


class AnswerStatus(StrEnum):
    ACCEPTED = "accepted"
    QUALIFIED = "qualified"
    ABSTAINED = "abstained"


class OmissionCode(StrEnum):
    """Why a sentence was withheld, as a category rather than as prose.

    Reason text quotes the draft's own wording — an unmatched number is
    reported as the token the model wrote — so an operator log that kept the
    reasons would keep answer text. These codes carry the same diagnosis
    without it.
    """

    AMBIGUOUS = "ambiguous"
    IDENTITY_HEADER = "identity_header"
    ABSENCE = "absence"
    CAUSAL = "causal"
    IDENTITY = "identity"
    UNIT_SCALE = "unit_scale"
    PERIOD = "period"
    UNMATCHED_NUMBER = "unmatched_number"
    OTHER = "other"


#: Ordered: a reason may contain several keys, and the first match wins. The
#: narrower phrases precede the substrings they would otherwise be caught by.
_OMISSION_KEYS: Final = (
    ("ambiguous", OmissionCode.AMBIGUOUS),
    ("does not identify", OmissionCode.IDENTITY_HEADER),
    ("absence", OmissionCode.ABSENCE),
    ("causal", OmissionCode.CAUSAL),
    ("identit", OmissionCode.IDENTITY),
    ("identifier", OmissionCode.IDENTITY),
    ("is written as", OmissionCode.UNIT_SCALE),
    ("unit", OmissionCode.UNIT_SCALE),
    ("currency", OmissionCode.UNIT_SCALE),
    ("scale", OmissionCode.UNIT_SCALE),
    ("period", OmissionCode.PERIOD),
    ("does not match", OmissionCode.UNMATCHED_NUMBER),
)

#: Reasons quote the figure or qualifier they reject as a repr.
_QUOTED: Final = re.compile(r"'[^']*'")


def omission_code(reason: str) -> OmissionCode:
    """Classify one code-owned reason string. Never returns any of its text.

    Quoted spans are dropped before matching. Every reason that rejects a
    figure or an explicit qualifier embeds the draft's own wording, and
    classifying on that would let the answer pick its own category.
    """
    folded = _QUOTED.sub(" ", reason).lower()
    return next((code for key, code in _OMISSION_KEYS if key in folded), OmissionCode.OTHER)


@dataclass(frozen=True, slots=True)
class OmittedNumber:
    """An unsupported quantity in a withheld sentence, without its wording.

    The parsed value, its binding and the categories that disqualified it are
    what localize a withheld claim afterwards; the token as the model wrote it
    is deliberately absent, so this record cannot rebuild draft text.
    """

    value: float
    binding: Binding
    result_id: str | None = None
    value_label: str | None = None
    codes: tuple[OmissionCode, ...] = ()


@dataclass(frozen=True, slots=True)
class OmittedSentence:
    """A sentence withheld from the answer, and why it was withheld.

    Withholding is recorded rather than performed silently. An answer that
    quietly loses a sentence is indistinguishable from one that never made the
    claim, and the operator needs to see the difference.

    `text` and `reasons` stay available in-process for the answer itself.
    `index` and `numbers` are the content-free part: an operator log keeps
    those and the categories, never the sentence. `index` counts non-empty
    sentences of the draft from zero, and is -1 when the whole draft was
    disqualified at once rather than sentence by sentence.
    """

    text: str
    reasons: tuple[str, ...]
    index: int = -1
    numbers: tuple[OmittedNumber, ...] = ()

    @property
    def codes(self) -> tuple[OmissionCode, ...]:
        """Distinct reason categories, in the order the reasons were recorded."""
        return tuple(dict.fromkeys(omission_code(reason) for reason in self.reasons))


@dataclass(frozen=True, slots=True)
class GatedAnswer:
    """What may be shown, what was withheld, and what must be said alongside."""

    status: AnswerStatus
    text: str
    verdict: Verdict
    omitted: tuple[OmittedSentence, ...] = ()
    limitations: tuple[str, ...] = ()
    #: Set when nothing is presentable: the reason to show instead of an answer.
    abstention: str | None = None

    @property
    def presentable(self) -> bool:
        return self.status is not AnswerStatus.ABSTAINED


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    """Every sentence as a (start, end) span, covering the whole string."""
    spans: list[tuple[int, int]] = []
    start = 0
    for match in _SENTENCE_BREAK.finditer(text):
        spans.append((start, match.start() + 1))
        start = match.end()
    if start < len(text):
        spans.append((start, len(text)))
    return spans or [(0, len(text))]


_ENDPOINT_DIRECTION = re.compile(
    r"\b(?:ilk|başlangıç)\b.*\b(?:son|bitiş)\b.*\b"
    r"(?P<up>artt\w*|yüksel\w*|yuksel\w*)\b|"
    r"\b(?:ilk|başlangıç)\b.*\b(?:son|bitiş)\b.*\b"
    r"(?P<down>azal\w*|düşt\w*|dust\w*)\b",
    re.I,
)
_ENDPOINT_NEGATION = re.compile(
    r"\b(?:ilk|başlangıç)\b.*\b(?:son|bitiş)\b.*\b"
    r"(?:artmad\w*|yükselmed\w*|yukselmed\w*|azalmad\w*|düşmed\w*|dusmed\w*)\b",
    re.I,
)
_UNVERIFIED_AGGREGATE = re.compile(
    r"\b(?:en\s+(?:belirgin|büyük|yüksek|sert)\s+(?:artış|düşüş)|"
    r"(?:artış|düşüş)l[ae]rin\s+(?:çoğu|büyük\s+bölümü)|"
    r"ivme\s+(?:zayıfla|güçlen)|rekor\s+(?:artış|düşüş))",
    re.I,
)


#: Whether a sentence may be withheld for its vocabulary alone. Off: the gate binds
#: figures and leaves wording to the writer (2026-09-21, trust-the-model).
WORDING_RULES = False


def _observation_fault(sentence: str, named: Mapping[str, AnalyticalResult]) -> str | None:
    """Only check bounded descriptions; arbitrary prose is not semantic proof."""
    folded = fold(sentence)
    if _UNVERIFIED_AGGREGATE.search(folded):
        return "Unsupported aggregate observation: no typed summary binds this wording"
    if _ENDPOINT_NEGATION.search(folded):
        return "Unsupported endpoint direction: a negated movement needs separate typed evidence"
    match = _ENDPOINT_DIRECTION.search(folded)
    if match is None:
        return None
    wanted = "rose" if match.group("up") else "fell"
    options = [obs for result in named.values() for obs in endpoint_observations(result)]
    if len(options) == 1 and options[0].direction == wanted:
        return None
    named_options = [
        obs
        for obs in options
        if re.search(r"(?<!\w)" + re.escape(fold(obs.label)) + r"(?!\w)", folded)
    ]
    if len(named_options) == 1 and named_options[0].direction == wanted:
        return None
    return "Unsupported endpoint direction: no unique comparable typed observation"


def _price_references(result: AnalyticalResult, value: ResultValue) -> tuple[date, ...]:
    """Recorded deflation reference months for exactly this value's column."""
    if result.evidence is None:
        return ()
    found = []
    for record in result.evidence.transformations:
        reference = record.parameters.get("reference_period")
        if record.operation == "deflate" and record.output_ref == value.label:
            try:
                found.append(date.fromisoformat(str(reference)))
            except ValueError:
                continue
    return tuple(found)


def _omitted_number(item: NumberVerdict) -> OmittedNumber:
    """Reduce one rejected number to its content-free diagnosis.

    An unbound number carries no fault of its own: the reason naming it is
    built from the draft's token, so the category is supplied here instead.
    """
    codes = tuple(dict.fromkeys(omission_code(fault) for fault in item.faults))
    return OmittedNumber(
        item.number.value,
        item.binding,
        item.result_id,
        item.value_label,
        codes or (OmissionCode.UNMATCHED_NUMBER,),
    )


def gate_answer(
    draft: str,
    results: AnalyticalResult | Sequence[AnalyticalResult] | Mapping[str, AnalyticalResult],
    connection: DuckDBPyConnection | None = None,
    *,
    allowed: Iterable[float] = (),
    context_counts: Iterable[WindowCount] = (),
    tolerance: float = DEFAULT_TOLERANCE,
    accept_years: bool = True,
    minimum_samples: int | None = None,
) -> GatedAnswer:
    """Decide what of `draft` may be shown, given what `results` established.

    The order of the three outcomes is not arbitrary. When **every** result
    failed as a whole — established nothing, evidence does not resolve, values
    disagree with the store — the prose is describing the same broken analysis,
    so no sentence survives. When only some failed, or none did, the gate falls
    back to withholding the individual sentences whose numbers did not bind,
    which is what lets a sound column still be reported beside a broken one.
    """
    named = _as_named(results)
    verdict = verify_claims(
        draft,
        named,
        connection,
        allowed=allowed,
        context_counts=context_counts,
        tolerance=tolerance,
        accept_years=accept_years,
        minimum_samples=minimum_samples,
    )
    limitations = verdict.limitations

    broken = result_faults(named, connection, tolerance=tolerance, minimum_samples=minimum_samples)
    if named and len(broken) == len(named):
        disqualifying = [fault for faults in broken.values() for fault in faults]
        # Nothing in the draft can be trusted, including its unnumbered prose,
        # because the prose describes the same broken analysis.
        return GatedAnswer(
            AnswerStatus.ABSTAINED,
            "",
            verdict,
            omitted=(OmittedSentence(draft.strip(), tuple(disqualifying)),)
            if draft.strip()
            else (),
            limitations=limitations,
            abstention="; ".join(disqualifying),
        )

    failures: dict[tuple[int, int], list[str]] = {}
    spans = _sentence_spans(draft)
    computed = any(
        result.status is ResultStatus.COMPUTED and result.values for result in named.values()
    )
    missing_samples = len(named) == 1 and any(
        result.status is ResultStatus.COMPUTED
        and result.samples is not None
        and result.samples.missing > 0
        for result in named.values()
    )
    for span in spans:
        if exposes_literal_identity(draft[span[0] : span[1]], list(named.values())):
            failures.setdefault(span, []).append(
                "Internal document proof identifiers are not answer text"
            )
        if not WORDING_RULES:
            continue
        if fault := causal_fault(draft[span[0] : span[1]]):
            failures.setdefault(span, []).append(fault)
        if fault := _observation_fault(
            draft[span[0] : span[1]],
            {name: result for name, result in named.items() if name not in broken},
        ):
            failures.setdefault(span, []).append(fault)
        if computed and (
            fault := absence_fault(draft[span[0] : span[1]], missing_samples=missing_samples)
        ):
            failures.setdefault(span, []).append(fault)
    unsupported: dict[tuple[int, int], list[NumberVerdict]] = {}
    for item in verdict.numbers:
        if item.supported:
            continue
        for span in spans:
            if span[0] <= item.number.start < span[1]:
                reasons = failures.setdefault(span, [])
                reasons.extend(
                    item.faults
                    or (f"{item.number.text!r} does not match any value in these results",)
                )
                unsupported.setdefault(span, []).append(item)
                break

    kept: list[str] = []
    omitted: list[OmittedSentence] = []
    position = 0
    # How each kept sentence is joined to the one before it: the draft's own line or
    # paragraph break where it had one, a space otherwise. Joined with spaces alone, the
    # figures, the interpretation, the assumption and the system's note reached the reader
    # as one block of text (live 2026-09-21).
    joints: list[str] = []
    read_to = 0
    for span in spans:
        raw = draft[span[0] : span[1]]
        sentence = raw.strip()
        if not sentence:
            continue
        gap = draft[read_to : span[0]] + raw[: len(raw) - len(raw.lstrip())]
        read_to = span[0] + len(raw.rstrip())
        joint = "\n\n" if gap.count("\n") > 1 else "\n" if "\n" in gap else " "
        if span in failures:
            omitted.append(
                OmittedSentence(
                    sentence,
                    tuple(failures[span]),
                    position,
                    tuple(_omitted_number(item) for item in unsupported.get(span, ())),
                )
            )
        else:
            kept.append(sentence)
            joints.append(joint)
        position += 1

    if not kept:
        return GatedAnswer(
            AnswerStatus.ABSTAINED,
            "",
            verdict,
            omitted=tuple(omitted),
            limitations=limitations,
            abstention=(
                "No sentence in the answer could be supported by these results"
                if omitted
                else "The answer was empty"
            ),
        )
    status = AnswerStatus.QUALIFIED if omitted else AnswerStatus.ACCEPTED
    text = kept[0] + "".join(
        joint + sentence for joint, sentence in zip(joints[1:], kept[1:], strict=True)
    )
    return GatedAnswer(status, text, verdict, tuple(omitted), limitations)
