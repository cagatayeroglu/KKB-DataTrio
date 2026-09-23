"""The answer, written by the same model, checked without being cut.

The old arrangement called a separate writer and then deleted from its draft any
sentence holding a number the verifier could not bind. That check was sound and
its placement was not: over one day of live turns it removed five correct
sentences — four months listed with their four correct balances, a movement
whose direction Turkish puts in the verb, a figure the writer had said was
rounded, and the two most relevant search results because a publication id sat
in a URL. Each was a true sentence, and the reader was told instead that nothing
verifiable could be produced.

So the verification stays and the deletion goes. Every figure is still bound to
what the tools returned; a figure that does not bind is reported beside the
answer rather than taking its sentence with it. A model that invents a number is
still visible, and a model that writes a correct sentence keeps it.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final

from duckdb import DuckDBPyConnection

from kkb_agent.agent.executor import analytical
from kkb_agent.agent.observer import Tracer
from kkb_agent.agent.presentation import display_value
from kkb_agent.agent.trust_loop import (
    NOT_RUN,
    TurnOutcome,
    _describe,
    _outline,
    observed_payload,
    traced_complete,
)
from kkb_agent.agent.trust_prompt import EXHAUSTED, WRITER
from kkb_agent.agent.verifier import MINUS, Binding, result_faults, verify_claims
from kkb_agent.catalog.search import CatalogSearchOutput
from kkb_agent.core import AnalyticalResult
from kkb_agent.llm.provider import LLMProvider, Message, ProviderError, Role
from kkb_agent.tools.inspect_result import InspectOutput, document_passages, document_tables

#: How much of one tool's output the writer is shown before it is clipped.
MAX_EVIDENCE_CHARS = 20_000

#: Said once, beside the answer, when a figure could not be bound to a result.
UNVERIFIED: Final = "Şu sayı araç sonuçlarına bağlanamadı, okurken dikkate alın: "

#: The fault a result raises for having been produced by a tool that is not on the
#: trusted-producer list, rather than for anything wrong with its figures. On this
#: branch the model reaches for whatever tool fits, including ones that record no
#: execution of their own, so a result built by one of them raises it every time.
#: Reported once, beside the answer; it does not unbind a figure.
_UNATTESTED: Final = "Numeric analytical result lacks matching trusted producer execution evidence"

#: Put before the evidence when the service that gathered it could not be asked to
#: write about it. The turn is not lost for that: what the tools returned is here.
#: It says nothing about a table. This text is written before anything is published,
#: so it cannot know whether anything will be, and it used to say a table had been
#: when the turn held only a page of text (QA-15). Whether a table was published is
#: said by the layer that publishes it: the answer carries that table, or a notice
#: that none was.
INTERRUPTED: Final = (
    "Modele yapılan yazım isteği geri dönmedi, bu yüzden aşağıda yorum yok. "
    "Bu turda araçların döndürdüğü sonuçların kısa özeti:\n\n"
)

#: Said once when results carry no execution attestation.
UNATTESTED_NOTE: Final = (
    "Şu tabloların üretim kanıtı soy kütüğünde doğrulanamadı (sayılar yine de araç "
    "sonuçlarına bağlandı): "
)


@dataclass(slots=True)
class Answer:
    """What the reader gets: the model's own text, plus what could not be checked."""

    text: str
    published: str | None = None
    limitations: list[str] = field(default_factory=list)
    #: Figures the verifier could not bind. Reported, never removed.
    unverified: list[str] = field(default_factory=list)
    #: Figures found, written exactly so, in a document this turn read; with where.
    #: Quoted, not verified: the unit, period and meaning are not checked by finding them.
    quoted: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


#: Tools whose result is a series, cell or table as its source holds it: read, not built.
SOURCE_READS: Final = frozenset({"lakehouse", "web_url", "document_read", "web_search"})


def _default_publication(results: dict[str, AnalyticalResult]) -> str | None:
    """What the reader is shown when the model names nothing: the last result built.

    A read is evidence, not an answer. Live 2026-09-23 A3 named no publication and the
    last thing it had read — an eight-row rate series, fetched to check a month — became
    the conversation's newest table, `analiz_3`, in place of anything the question asked
    for. A table a transformation or computation built this turn is still shown; a series
    read on the way is shown only when the model names it.
    """
    built = [name for name, result in results.items() if result.tool not in SOURCE_READS]
    return built[-1] if built else None


def _behind(published: str | None, outcome: TurnOutcome) -> set[str] | None:
    """The steps the published result was built from, itself included, by the ids the
    model passed between them. None when nothing this turn is published."""
    steps = {item.action.id: item.action for item in outcome.observations}
    if published not in steps:
        return None
    found: set[str] = set()
    waiting = [published]
    while waiting:
        step = waiting.pop()
        if step in found or step not in steps:
            continue
        found.add(step)
        waiting.extend(_named(steps[step].arguments))
    return found


def _named(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [name for item in value.values() for name in _named(item)]
    if isinstance(value, list):
        return [name for item in value for name in _named(item)]
    return []


def _computed(outcome: TurnOutcome) -> dict[str, AnalyticalResult]:
    """Every analytical result this turn produced, under the id the model gave it."""
    found: dict[str, AnalyticalResult] = {}
    for item in outcome.observations:
        measured = analytical(item.result.output) if item.ok else None
        if measured is not None:
            found[item.action.id] = measured
    return found


def _evidence(outcome: TurnOutcome) -> str:
    """Everything the tools returned, not only what happened to be a table.

    Reporting only `AnalyticalResult` left the writer with nothing to say about a
    page it had just read: a document, a search listing and an `inspect` window
    are evidence too, and "bu PDF'teki verilerle yorumla" is answered from exactly
    those. A failed observation travels as well, so the answer can say what did
    not work rather than implying it was never tried.

    It goes through the same serialization the loop uses. It did not: a page came
    back as a dataclass, `json.dumps(..., default=str)` rendered it by its repr,
    and the repr leaves the document out, so the writer was handed "loaded" and
    nothing that was loaded (QA-14).
    """
    blocks: list[str] = []
    for item in outcome.observations:
        if item.result.error_category in NOT_RUN:
            continue
        payload = item.result.output
        if payload is None:
            if item.result.warnings:
                blocks.append(
                    f"{item.action.id} ({item.action.tool}) sonuç vermedi: "
                    + "; ".join(item.result.warnings)
                )
            continue
        body = json.dumps(observed_payload(payload), ensure_ascii=False, default=str)
        clipped = len(body) > MAX_EVIDENCE_CHARS
        blocks.append(
            f"{item.action.id} ({item.action.tool}): {body[:MAX_EVIDENCE_CHARS]}"
            + (" [kısaltıldı]" if clipped else "")
        )
    return "\n\n".join(blocks)


def write_answer(
    question: str,
    outcome: TurnOutcome,
    *,
    provider: LLMProvider,
    model: str | None = None,
    connection: DuckDBPyConnection | None = None,
    tracer: Tracer | None = None,
    kept: Sequence[str] = (),
) -> Answer:
    """Ask the model to report what its own tools returned, then check the figures.

    `kept` names the tables earlier turns published, so a turn that could not be
    written can still tell the reader those are where they were.
    """
    if outcome.ask:
        return Answer(text=outcome.ask)

    results = _computed(outcome)
    if outcome.reply:
        # The model already wrote the answer, in the same conversation that gathered
        # the evidence. Asking a second call to say it again would cost a turn and
        # separate the words from what they were written against.
        return _checked(Answer(text=outcome.reply), outcome, results, connection)
    evidence = _evidence(outcome)
    messages = [
        Message(Role.SYSTEM, WRITER),
        Message(Role.USER, question),
        Message(Role.USER, evidence or "Bu turda hiçbir araç sonuç döndürmedi."),
    ]
    if outcome.state:
        messages.insert(2, Message(Role.ASSISTANT, outcome.state))
    try:
        draft = traced_complete(
            provider,
            messages,
            model=model,
            tools=None,
            schema=None,
            tracer=tracer,
            stage="answer",
            name="writer",
        ).text.strip()
    except ProviderError:
        # The turn already ended because the service stopped answering, and this is
        # the same service. Losing what the tools returned to a second failure of the
        # one thing already known to be down would throw away the whole turn's work;
        # the reader gets it with the harness saying plainly that no prose could be
        # written for it. A turn that gathered nothing has nothing to deliver, so it
        # fails as it did.
        if not evidence:
            raise
        # Written here, from the tool outputs themselves, so its figures are not the
        # model's claims and there is nothing of them to check; the counts it states
        # (pages, values) would only be reported back as figures no tool returned.
        answer = Answer(text=(INTERRUPTED + _digest(outcome, kept)).strip())
        return _checked(answer, outcome, results, connection, figures=False)
    answer = Answer(text=draft.strip())
    return _checked(answer, outcome, results, connection)


#: Values of one table listed in the fallback; the rest are in the table itself.
MAX_DIGEST_VALUES = 24
#: A tool output this short is shown as it is; a longer one is summarized.
MAX_INLINE_CHARS = 300


def _digest(outcome: TurnOutcome, kept: Sequence[str]) -> str:
    """What the tools returned, said briefly: every table's figures, never a raw dump.

    The fallback used to be every observation as raw JSON. Live 2026-09-23 (A2 on
    92651bc) both model requests of a turn failed to connect, and the reader was handed
    a clipped wall of catalogue-listing JSON in place of an answer. A reader cannot use
    that; they can use which searches ran, what they found, and what a table holds.
    """
    lines = []
    for item in outcome.observations:
        if item.result.error_category in NOT_RUN:
            continue
        head = f"- {item.action.id} ({item.action.tool}{_asked(item.action.arguments)})"
        output = item.result.output
        if not item.ok or output is None:
            reason = "; ".join(item.result.warnings)[:300] or item.result.error_category
            lines.append(f"{head}: sonuç vermedi" + (f" — {reason}" if reason else ""))
            continue
        lines.append(f"{head}: {_summary(output)}")
    if kept:
        lines.append(
            "\nÖnceki turlarda yayımlanan tablolar yerinde duruyor: " + ", ".join(kept) + "."
        )
    return "\n".join(lines)


def _asked(arguments: Mapping[str, object]) -> str:
    words = ", ".join(value for value in arguments.values() if isinstance(value, str))
    return f" «{words[:100]}»" if words else ""


def _summary(output: object) -> str:
    """One observation in a line or a short list, by what it is."""
    measured = analytical(output)
    if measured is not None:
        coverage = (
            f", {measured.coverage.start}..{measured.coverage.end}"
            if measured.coverage is not None
            else ""
        )
        rows = [f"{len(measured.values)} değer{coverage}"]
        for value in measured.values[:MAX_DIGEST_VALUES]:
            when = value.period.end.isoformat() if value.period is not None else ""
            rows.append(f"    {value.label[:60]} {when}: {display_value(value)}")
        if len(measured.values) > MAX_DIGEST_VALUES:
            rows.append(f"    … ve {len(measured.values) - MAX_DIGEST_VALUES} değer daha")
        return "\n".join(rows)
    if isinstance(output, CatalogSearchOutput):
        if not output.candidates:
            return "katalogda aday bulunamadı"
        shown = "; ".join(
            f"{c.series.record.title} ({c.series.record.provider})" for c in output.candidates[:3]
        )
        more = len(output.candidates) - 3
        return f"{len(output.candidates)} aday: {shown}" + (f"; +{more} aday" if more > 0 else "")
    if isinstance(output, InspectOutput):
        return f"{len(output.values)} satır gösterildi ({output.kind}, toplam {output.rows})"
    document = getattr(output, "document", None)
    pages = getattr(document, "pages", None)
    if isinstance(pages, tuple):
        tables = sum(len(getattr(page, "tables", ())) for page in pages)
        return f"belge okundu: {len(pages)} sayfa, {tables} tablo"
    text = getattr(document, "text", None)
    if isinstance(text, str):
        tables = len(getattr(document, "tables", ()) or ())
        return f"sayfa okundu: {len(text)} karakter metin, {tables} tablo"
    rendered = json.dumps(observed_payload(output), ensure_ascii=False, default=str)
    return rendered if len(rendered) <= MAX_INLINE_CHARS else _outline(output)


def _checked(
    answer: Answer,
    outcome: TurnOutcome,
    results: dict[str, AnalyticalResult],
    connection: DuckDBPyConnection | None,
    *,
    figures: bool = True,
) -> Answer:
    """Attach what the turn knows, then report any figure that did not bind."""
    answer.published = outcome.publish or _default_publication(results)
    if outcome.exhausted:
        answer.notes.append(EXHAUSTED.get(outcome.exhausted, outcome.exhausted))
    answer.notes.extend(item.action.note for item in outcome.observations if item.action.note)
    behind = _behind(answer.published, outcome)
    for item in outcome.observations:
        # A call answered without being run is the loop's bookkeeping with the model.
        if item.result.error_category in NOT_RUN:
            continue
        # A table the model built and then built differently was its working, not the
        # reader's. Live 2026-09-23 (A3) a join refused for dropping two months told the
        # model to "clarify or separate the requested outputs"; it joined the other way
        # round and published that, and the reader was still handed the refusal.
        if (
            behind is not None
            and item.action.id not in behind
            and analytical(item.result.output) is not None
        ):
            continue
        answer.limitations.extend(item.result.warnings)

    documents = _documents(outcome) if figures else []
    read = any(_is_document(item.result.output) for item in outcome.observations if item.ok)
    if figures and (results or read) and answer.text:
        # The same binding as before, read as a report: a figure that does not
        # bind is named, and the model's sentence stays where the model put it.
        answer.unverified, answer.quoted, unattested = _report(
            answer.text, results, connection, documents
        )
        if unattested:
            answer.limitations.append(UNATTESTED_NOTE + ", ".join(sorted(unattested)))
        for name, result in results.items():
            answer.limitations.extend(f"{name}: {note}" for note in result.unresolved_semantics)
    return answer


def _figures(
    text: str,
    results: dict[str, AnalyticalResult],
    connection: DuckDBPyConnection | None,
) -> tuple[list[str], list[str]]:
    """Which figures did not bind, and which results were merely unattested.

    The report names figures, because a figure is what a reader can check. The
    whole-draft verdict it replaces said only that something was wrong with the
    answer: live, one unattested table turned a correct six-month series into an
    answer reported as unverifiable in its entirety, which tells the reader to
    distrust six figures that were each exactly what the tool returned.

    An unattested result still binds its numbers. Every other fault — a
    contradicted scale, a period the result never covered, a figure that
    disagrees with the store — is the figure's own and is reported with it.
    """
    reported, _, unattested = _report(text, results, connection, ())
    return reported, unattested


#: Where a figure was found in a read document, if it was: (result id, where, text).
Located = tuple[str, dict[str, object], str]

#: Fewer digits than this are too common to say anything by appearing in a document.
MIN_QUOTED_DIGITS = 3


def _report(
    text: str,
    results: dict[str, AnalyticalResult],
    connection: DuckDBPyConnection | None,
    documents: Sequence[Located],
) -> tuple[list[str], list[str], list[str]]:
    """Unbound figures, figures quoted from a document read this turn, unattested results.

    A figure no tool computed but that stands, written exactly so, in a document this
    turn read is a quotation, and it is said to be one with where it stands — page and
    table. That is all it is: the check finds the characters, not their meaning, so
    nothing about the figure's unit, period or what it counts is confirmed by it, and
    the notice says so. Before, every such figure was reported as "not in the tool
    results", which was untrue of a PDF the turn had just read.
    """
    unattested = (
        [
            name
            for name, faults in result_faults(results, connection).items()
            if any(fault.endswith(_UNATTESTED) for fault in faults)
        ]
        if results
        else []
    )
    reported: list[str] = []
    quoted: list[str] = []
    # A figure rounded correctly to the decimals it is written with binds here (QA-22):
    # this report names what does not bind, it does not withhold it.
    for item in verify_claims(
        text, results, connection, written_precision=True, lenient_periods=True
    ).numbers:
        kept = [fault for fault in item.faults if not fault.endswith(_UNATTESTED)]
        if kept:
            reported.append(f"{item.number.text} ({'; '.join(kept)})")
        elif item.binding is Binding.UNBOUND and not item.faults:
            place = _quoted_from(item.number.text, documents)
            if place is not None:
                quoted.append(f"{item.number.text} ({place})")
            else:
                reported.append(f"{item.number.text} (araç sonuçlarında bu değer yok)")
    return reported, quoted, unattested


def _is_document(output: object) -> bool:
    """Whether a tool returned something read: a document, a page, or a window of one."""
    return isinstance(output, InspectOutput) or bool(document_passages(output))


def _documents(outcome: TurnOutcome) -> list[Located]:
    """The document text the model actually read this turn, piece by piece, tables first.

    What it asked `inspect` for, and a document it was shown whole. Not the rest of a
    long document it saw only as an index: live 2026-09-23 a credit-balance decline the
    model had worked out itself, 17,3, was listed as quoted from a PDF's page 13, where
    17,3 is a luxury-car segment's growth — a page the model never opened (QA-28). A
    figure is a quotation of a passage the model read, or it is not a quotation.
    """
    found: list[Located] = []
    for item in outcome.observations:
        output = item.result.output
        if not item.ok or output is None:
            continue
        if isinstance(output, InspectOutput):
            for row in output.values:
                cells = row.get("cells")
                body = " | ".join(map(str, cells)) if isinstance(cells, list) else row.get("text")
                if isinstance(body, str):
                    found.append((output.source, dict(row), body))
            continue
        if json.loads(_describe(item.result, item.action.id)).get("clipped"):
            continue
        for where, rows in document_tables(output, None):
            found.append((item.action.id, where, "\n".join(" | ".join(row) for row in rows)))
        for where, body in document_passages(output) or ():
            found.append((item.action.id, where, body))
    return found


def _quoted_from(written: str, documents: Sequence[Located]) -> str | None:
    """Where the figure stands, written exactly so, in a document this turn read."""
    token = written.strip().replace(MINUS, "-")
    if sum(character.isdigit() for character in token) < MIN_QUOTED_DIGITS:
        return None
    pattern = re.compile(r"(?<![\d.,])" + re.escape(token) + r"(?![.,]?\d)")
    for source, where, body in documents:
        if pattern.search(body.replace(MINUS, "-")):
            parts = [source]
            if where.get("page") is not None:
                parts.append(f"s. {where['page']}")
            if where.get("table_on_page") is not None:
                parts.append(f"tablo {where['table_on_page']}")
            elif where.get("table") is not None:
                parts.append(f"tablo {where['table']}")
            return ", ".join(parts)
    return None


__all__ = ["Answer", "UNVERIFIED", "write_answer"]
