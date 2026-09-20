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
    has_amount_context,
    identity_fault,
    is_date_token,
    is_list_marker,
    period_fault,
    table_count_identity_fault,
    unit_fault,
)
from kkb_agent.agent.literal import exposes_literal_identity, literal_proof, literal_text
from kkb_agent.core import AnalyticalResult, ClaimKind, ResultStatus, ResultValue, Scale
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
NUMBER = re.compile(r"(?<![\w.,])[+-]?(?:\d{1,3}(?:[.,  ]\d{3})+|\d+)(?:[.,]\d+)?(?![\w])")

#: Relative closeness required to call a written number the same as a stored one.
#: A written figure is usually rounded, so exact equality would reject correct
#: answers; this permits presentation rounding and nothing more.
DEFAULT_TOLERANCE = 5e-4

#: Calendar-like integers; attached amount qualifiers disable the exception.
YEAR_RANGE = range(1900, 2101)


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
        if is_list_marker(text, match.start(), match.end()):
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


def _stored_value(connection: DuckDBPyConnection, label: str, period_end: date) -> float | None:
    """Read the value the store holds for one series at one period.

    Keyed on identity rather than magnitude, and written here in fixed SQL, so
    it is independent of whatever statement the model composed to produce the
    result under test.
    """
    for statement in (
        "SELECT value FROM silver_observations WHERE series_id = ? AND period_end = ?",
        "SELECT value FROM gold_cells WHERE column_name = ? AND period_end = ?",
    ):
        row = connection.execute(statement, [label, period_end]).fetchone()
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
    for value in result.values:
        if value.period is None:
            continue
        stored = _stored_value(connection, value.label, value.period.end)
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
    tolerance: float = DEFAULT_TOLERANCE,
    accept_years: bool = True,
    minimum_samples: int | None = None,
) -> Verdict:
    """Gate an answer against the results it claims to describe.

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

    verdicts = [
        _bind_to_results(answer, number, named, disqualified, permitted, tolerance, accept_years)
        for number in extract_numbers(answer)
    ]

    rejected: list[str] = []
    if exposes_literal_identity(answer, list(named.values())):
        rejected.append("Internal document proof identifiers are not answer text")
    for start, end in _sentence_spans(answer):
        if fault := causal_fault(answer[start:end]):
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


def _bind_to_results(
    answer: str,
    number: WrittenNumber,
    named: Mapping[str, AnalyticalResult],
    disqualified: Mapping[str, tuple[str, ...]],
    permitted: Sequence[float],
    tolerance: float,
    accept_years: bool,
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
    candidates: list[NumberVerdict] = []
    for name, result in named.items():
        node = result.evidence.lineage_node if result.evidence is not None else None
        for value in result.values:
            if not _close(number.value, value.value, tolerance):
                continue
            faults = tuple(
                fault
                for fault in (
                    _scale_fault(answer, number, value),
                    period_fault(clause, prefix, value, _price_references(result, value)),
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
    for span in spans:
        if exposes_literal_identity(draft[span[0] : span[1]], list(named.values())):
            failures.setdefault(span, []).append(
                "Internal document proof identifiers are not answer text"
            )
        if fault := causal_fault(draft[span[0] : span[1]]):
            failures.setdefault(span, []).append(fault)
        if computed and (fault := absence_fault(draft[span[0] : span[1]])):
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
    for span in spans:
        sentence = draft[span[0] : span[1]].strip()
        if not sentence:
            continue
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
    return GatedAnswer(status, " ".join(kept), verdict, tuple(omitted), limitations)
