"""Explicit projection of a gated turn and its exactly published workspace value."""

from __future__ import annotations

import re
from uuid import UUID, uuid5

from kkb_agent.agent.claim_qualifiers import has_amount_context, is_list_marker
from kkb_agent.agent.discovery import CLARIFICATION_TEXT, MISSING_SERIES_ROUTES
from kkb_agent.agent.executor import ExecutionOutcome
from kkb_agent.agent.loop import Answered
from kkb_agent.agent.presentation import display_value
from kkb_agent.agent.verifier import AnswerStatus
from kkb_agent.api.contracts import (
    MAX_RESPONSE_BYTES,
    MAX_VALUES,
    Answer,
    Cell,
    Proof,
    Result,
    SeriesChoice,
    SeriesSelection,
    unavailable_proof,
)
from kkb_agent.catalog.mappings import ReviewedSeries
from kkb_agent.catalog.search import CatalogSearchOutput
from kkb_agent.core import AnalyticalResult


class OutputRefused(ValueError):
    """Fixed boundary failure; never include the rejected output."""


# Prevent accidental locator/path/credential presentation. This is deliberately
# conservative and not a general secret detector; raw internals are excluded by
# construction. Literal credentials known to the operator can be supplied too.
_INTERNAL = re.compile(
    r"https?://\S+|file://\S+|[A-Za-z]:[\\/]\S+|(?:^|\s)/(?:home|tmp|var|Users)/\S+"
    r"|(?:bearer\s+\S+)|(?:api[_-]?key|token|password|secret)\s*[:=]\s*\S+",
    re.IGNORECASE,
)


def safe_text(
    text: str,
    *,
    limit: int = 8192,
    secrets: tuple[str, ...] = (),
    shown_urls: frozenset[str] = frozenset(),
) -> str:
    """`shown_urls` are addresses this turn's own web search returned: they are the answer
    to "webde ara", and the reader needs them to ask for a page to be read. Live
    2026-09-21 every one of them was replaced by the placeholder, under a sentence telling
    the reader to write the address in the next question."""
    if len(text) > limit or len(text.encode("utf-8")) > limit * 4:
        raise OutputRefused("output_limit")

    def hidden(found: re.Match[str]) -> str:
        return found.group() if found.group() in shown_urls else "[gizli bilgi kaldırıldı]"

    cleaned = _INTERNAL.sub(hidden, text)
    for secret in secrets:
        if secret:
            cleaned = cleaned.replace(secret, "[gizli bilgi kaldırıldı]")
    return "".join(c for c in cleaned if ord(c) >= 32 or c in "\n\t")


def _searched_urls(answered: Answered) -> frozenset[str]:
    """The https addresses this turn's web_search steps returned, and nothing else."""
    found: set[str] = set()
    for item in answered.outcome.results:
        if item.tool != "web_search":
            continue
        for candidate in getattr(item.output, "candidates", ()) or ():
            url = str(getattr(candidate, "url", "") or "")
            if url.startswith("https://") and not any(c.isspace() for c in url):
                found.add(url)
    return frozenset(found)


def _owned_proof(proof: Proof | None, version: str) -> Proof:
    """A proof must describe exactly this published version, or none is shown."""
    if proof is None:
        return unavailable_proof()
    canonical = Proof.model_validate_json(proof.model_dump_json())
    if canonical.steps and canonical.steps[0].result_version != version:
        raise OutputRefused("publication_mismatch")
    return canonical


def project_result(
    published: AnalyticalResult,
    *,
    turn_id: str,
    secrets: tuple[str, ...] = (),
    proof: Proof | None = None,
) -> Result:
    """The public table for a published value: deterministic from the turn and the digest.

    Read back from a stored publication after a restart, it yields the very same
    `result_ref` and `version` the conversation's messages recorded, so a
    reopened conversation shows the table it showed then, proof included.
    """
    namespace = UUID(hex=turn_id)
    canonical = AnalyticalResult.model_validate_json(published.model_dump_json())
    if len(canonical.values) > MAX_VALUES:
        raise OutputRefused("output_limit")
    version = canonical.digest()
    return Result(
        result_ref=uuid5(namespace, version).hex,
        version=version,
        kind=canonical.kind,
        claim_kind=canonical.claim_kind,
        cells=tuple(
            Cell(
                cell_id=uuid5(namespace, f"{version}:{slot}").hex,
                slot=slot,
                label=safe_text(value.label, limit=240, secrets=secrets),
                value=value.value,
                display=display_value(value),
                unit=safe_text(value.unit, limit=240, secrets=secrets) if value.unit else None,
                scale=value.scale,
                measure=value.measure,
                period=value.period,
                samples=value.samples,
                lag=value.lag,
            )
            for slot, value in enumerate(canonical.values)
        ),
        hidden_columns=_hidden_columns(canonical, secrets),
        proof=_owned_proof(proof, version),
    )


def _hidden_columns(result: AnalyticalResult, secrets: tuple[str, ...]) -> tuple[str, ...]:
    """The columns a `replace` asked not to show, as far as the table still holds them."""
    asked = result.parameters.get("hidden_columns")
    if not isinstance(asked, list):
        return ()
    held = {value.label for value in result.values}
    return tuple(
        safe_text(label, limit=240, secrets=secrets)
        for label in asked
        if isinstance(label, str) and label in held
    )[:32]


#: How many catalogue entries a clarification lists; the search itself returns at most ten.
MAX_LISTED_CANDIDATES = 6
#: The neighbours shown beside a chosen entry: everything else one search returned.
MAX_OTHER_CANDIDATES = 9
_FREQUENCY_WORDS = {
    "daily": "günlük",
    "business_day": "iş günü",
    "weekly": "haftalık",
    "twice_monthly": "ayda iki",
    "monthly": "aylık",
    "quarterly": "üç aylık",
    "semiannual": "altı aylık",
    "annual": "yıllık",
}
_KIND_WORDS = {"stock": "bakiye (stok)", "flow": "akım", "rate": "oran", "index": "endeks"}
_SCALE_WORDS = {"thousand": "bin", "million": "milyon", "billion": "milyar"}


def _candidate_words(series: ReviewedSeries) -> tuple[str, str]:
    """One catalogue entry as a person reads it: its name, and who publishes it and how."""
    record = series.record
    # The three BDDK housing components share a title; the label tells them apart.
    component = next((label for label in record.labels if label in ("TP", "YP", "TOTAL")), None)
    name = record.title + (f" [{component}]" if component else "")
    if series.geography:
        name += f" ({series.geography})"
    publisher = record.group.publisher if record.group and record.group.publisher else None
    source = record.provider + (
        f"/{publisher}" if publisher and publisher != record.provider else ""
    )
    # A datagroup says what a bare series title leaves out ("TOPLAM" of which table?).
    family = (
        record.group.group_title
        if record.group and record.group.group_title and record.group.group_title != record.title
        else None
    )
    unit = " ".join(part for part in (_SCALE_WORDS.get(record.scale.value), record.unit) if part)
    facts = [
        family,
        source,
        _FREQUENCY_WORDS.get(record.frequency.value),
        unit or None,
        _KIND_WORDS.get(record.stock_flow.value),
    ]
    return name, ", ".join(fact for fact in facts if fact)


def _candidate_line(series: ReviewedSeries) -> str:
    name, facts = _candidate_words(series)
    return f"- {name} — {facts}"


def _named(value: object, found: set[str]) -> None:
    if isinstance(value, str):
        found.add(value)
    elif isinstance(value, dict):
        for item in value.values():
            _named(item, found)
    elif isinstance(value, list | tuple):
        for item in value:
            _named(item, found)


def series_selection(
    answered: Answered, *, secrets: tuple[str, ...] = ()
) -> SeriesSelection | None:
    """The neighbour candidates this turn's plan went on to use, and the ones it left.

    A search without a reviewed match returns neighbours and the planner judges them by their
    declared title and kind. The person is told which entry that judgement picked and what
    else the same search showed, so a wrong pick is one sentence away from being corrected.
    Nothing here is model text: the entries are this turn's own search results and the choice
    is read from the identities the executed plan names.
    """
    named: set[str] = set()
    for validated in answered.planned.plan.steps:
        if validated.step.tool != "catalog_search":
            _named(validated.step.arguments, named)
    chosen: dict[str, SeriesChoice] = {}
    others: dict[str, SeriesChoice] = {}
    for item in answered.outcome.results:
        if item.tool != "catalog_search" or not isinstance(item.output, CatalogSearchOutput):
            continue
        if item.output.top_candidate == "unambiguous":
            continue
        for candidate in item.output.candidates:
            identity = candidate.series.record.series_id
            name, facts = _candidate_words(candidate.series)
            choice = SeriesChoice(
                series_id=identity,
                title=safe_text(name, limit=400, secrets=secrets),
                detail=safe_text(facts, limit=400, secrets=secrets),
            )
            (chosen if identity in named else others).setdefault(identity, choice)
    if not chosen:
        return None
    left = [item for identity, item in others.items() if identity not in chosen]
    return SeriesSelection(
        chosen=tuple(chosen.values())[:12], others=tuple(left)[:MAX_OTHER_CANDIDATES]
    )


def _quotes_a_figure(text: str) -> bool:
    """A digit that measures something; the "(1)" and "(2)" of two choices only count them.

    A planner that names the axis it cannot settle writes the choices as a list. The
    filter below read those markers as figures, so the owner's run of the reference
    first turn showed the generic "several series fit" in place of the planner's own
    "(1) yeni kullandırılan, akım ... (2) stok ..." (stored trace, 2026-09-20).
    """
    # A year or a date in the planner's own question measures nothing ("2020 sonrası
    # için hangi seriyi kullanayım?", "2025-12 fiyatlarıyla mı?"); it used to send the
    # whole question back to the fixed text. Any other number is a figure nothing computed.
    undated = re.sub(r"\b\d{4}-\d{2}(?:-\d{2})?\b|\b\d{1,2}[./]\d{1,2}[./]\d{4}\b", " ", text)
    for found in re.finditer(r"\d+(?:[.,]\d+)*", undated):
        if is_list_marker(undated, found.start(), found.end()):
            continue
        token = found.group()
        a_year = token.isdigit() and 1900 <= int(token) <= 2100
        if not a_year or has_amount_context(undated, found.start(), found.end()):
            return True
    return False


def clarification_text(
    reason: str,
    outcome: ExecutionOutcome,
    proposed: str | None = None,
    *,
    secrets: tuple[str, ...] = (),
) -> str:
    """Prefer a safe specific question; retain the deterministic catalogue fallback.

    A bare "several series fit" or "not found" left the person guessing what exists
    (DEC-172). The lines come from reviewed catalogue records this turn's own searches
    returned, in their order; nothing here is model text and no figure is quoted.
    """
    # Planner prose is not evidence. A numeric statement, locator or causal claim
    # in it cannot be bound by the ordinary answer verifier, so do not show it.
    # This intentionally rejects even a harmless date rather than certifying an
    # unverified figure in a clarification. The markers of a list of choices are not
    # figures, and are the one kind of digit let through.
    if proposed is not None:
        specific = proposed.strip()
        # The planner's own question is shown as it wrote it: "2020 sonrası için hangi
        # seriyi kullanayım?" used to be replaced by a generic sentence because it holds a
        # digit. An amount, a locator or a secret still sends it back to the fixed text.
        if (
            specific
            and not _quotes_a_figure(specific)
            and not re.search(r"https?://", specific, re.I)
            and "[gizli bilgi kaldırıldı]" not in safe_text(specific, limit=1500, secrets=secrets)
        ):
            return specific
    text = CLARIFICATION_TEXT[reason]
    if reason not in ("ambiguous_series", "missing_series"):
        return text
    seen: dict[str, str] = {}
    for item in outcome.results:
        if item.tool != "catalog_search" or not isinstance(item.output, CatalogSearchOutput):
            continue
        for candidate in item.output.candidates:
            seen.setdefault(candidate.series.record.series_id, _candidate_line(candidate.series))
    lines = list(seen.values())[:MAX_LISTED_CANDIDATES]
    if lines:
        heading = (
            "Bilgi tabanındaki uygun kayıtlar:"
            if reason == "ambiguous_series"
            else "Bilgi tabanındaki en yakın kayıtlar (istediğiniz ölçüm bunlar olmayabilir):"
        )
        text = "\n".join([text, heading, *lines])
    if reason == "missing_series":
        text = "\n".join([text, MISSING_SERIES_ROUTES])
    return text


def clarification_choices(
    answered: Answered, *, secrets: tuple[str, ...] = ()
) -> SeriesSelection | None:
    """The entries a series clarification lists, as choices a person can pick with one click."""
    if answered.planned.plan.clarification not in ("ambiguous_series", "missing_series"):
        return None
    seen: dict[str, SeriesChoice] = {}
    for item in answered.outcome.results:
        if item.tool != "catalog_search" or not isinstance(item.output, CatalogSearchOutput):
            continue
        for candidate in item.output.candidates:
            name, facts = _candidate_words(candidate.series)
            seen.setdefault(
                candidate.series.record.series_id,
                SeriesChoice(
                    series_id=candidate.series.record.series_id,
                    title=safe_text(name, limit=400, secrets=secrets),
                    detail=safe_text(facts, limit=400, secrets=secrets),
                ),
            )
    if not seen:
        return None
    return SeriesSelection(others=tuple(seen.values())[:MAX_LISTED_CANDIDATES])


def project_answer(
    answered: Answered,
    *,
    turn_id: str,
    published: AnalyticalResult | None,
    secrets: tuple[str, ...] = (),
    proof: Proof | None = None,
) -> Answer:
    """The caller proves publication by reading its own workspace, not by a flag.

    No candidate result, raw outcome, omitted sentence, verdict exception,
    locator, transformation parameters or source content is serialized.
    """
    gate = answered.answer
    notices = []
    text = ""
    if gate.status is AnswerStatus.ABSTAINED:
        reason = answered.planned.plan.clarification
        text = (
            safe_text(
                clarification_text(
                    reason,
                    answered.outcome,
                    answered.planned.plan.clarification_text,
                    secrets=secrets,
                ),
                secrets=secrets,
            )
            if reason is not None
            else (
                "Bu soru için doğrulanabilir bir sonuç üretilemedi. "
                "Veri kapsamını ve tanımı kontrol edin."
            )
        )
    else:
        text = safe_text(gate.text, secrets=secrets, shown_urls=_searched_urls(answered))
    if gate.omitted:
        notices.append("Doğrulanamayan bazı ifadeler yanıttan çıkarıldı.")
    if gate.limitations:
        # These are gate-owned qualifications, still treated as untrusted text.
        if len(gate.limitations) > 12:
            raise OutputRefused("output_limit")
        notices.extend(safe_text(item, limit=2048, secrets=secrets) for item in gate.limitations)
    result = None
    if published is not None:
        if (
            gate.status is AnswerStatus.ABSTAINED
            or not answered.results
            or published.digest() != answered.results[-1].digest()
        ):
            raise OutputRefused("publication_mismatch")
        result = project_result(published, turn_id=turn_id, secrets=secrets, proof=proof)
    elif gate.status is not AnswerStatus.ABSTAINED and answered.planned.plan.reply is None:
        # A conversational reply never publishes, so saying so would be noise.
        notices.append("Bu turda yeni bir doğrulanmış tablo çalışma alanına yayımlanmadı.")
    answer = Answer(
        status=gate.status,
        text=text,
        omitted_claims=len(gate.omitted),
        notices=tuple(notices),
        result=result,
        selection=(
            series_selection(answered, secrets=secrets)
            if gate.status is not AnswerStatus.ABSTAINED
            else clarification_choices(answered, secrets=secrets)
        ),
    )
    if len(answer.model_dump_json().encode()) > MAX_RESPONSE_BYTES - 4096:
        raise OutputRefused("output_limit")
    return answer
