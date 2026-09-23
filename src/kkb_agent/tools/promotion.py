"""Turning a table this conversation analysed into a series the agent keeps (DEC-183).

A monthly table arrives with a question - uploaded, or read from an https address the
person wrote - is analysed, and is then lost with the turn. The knowledge base already
keeps such a series (DEC-157), but only through its own page and its own form, so the
person who just analysed the table has to type it in again.

This is the same save, reached from the conversation, and it is deliberately in two
stages. **Analysing a document is not permission to keep it.** The first call writes
nothing: it reads the column through the strict loaders every other path uses, settles
what only one answer fits (one date column, one value column, a slug from the title,
the range and the count computed here), and hands back a proposal the *server* holds.
The person sees three short lines and says yes or no; the save then writes the held
proposal rather than anything a model composed a second time.

What a person is asked is kept to what is genuinely open. Nobody is shown
`aggregation`, `cumulative` or `base_year`: the reader says whether the number is the
balance at the end of the month or what happened during it, and that maps here, once,
deterministically.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

from kkb_agent.agent.executor import ExecutionContext, ToolResult, ToolStatus, analytical
from kkb_agent.agent.registry import ToolSpec
from kkb_agent.core import Frequency, ResultStatus
from kkb_agent.ingest.attached import Attachment
from kkb_agent.pdf_ocr import OcrProvider
from kkb_agent.tools._document_column import ColumnRefused, RowRules, month_end, read_month_values
from kkb_agent.tools._document_value import grids
from kkb_agent.tools.web_url import choose_document, library_name, read_attachment

#: A promotion saves one monthly value series. More than that is more than one decision.
FREQUENCY: Final = "monthly"
MAX_TITLE_CHARS: Final = 80
MAX_DESCRIPTION_CHARS: Final = 500
MAX_ALIASES: Final = 8
#: Half a column's readable cells deciding its kind is enough: a month column with a
#: stray note in it is still the month column, and a value column with a blank is still
#: the value column. Below that nothing is settled and the reader is asked.
SHARE_TO_DECIDE: Final = 0.5

#: What the reader says about a number, and the contract it means. The four readings
#: are the ones a monthly financial table actually holds; each maps to exactly one
#: stock/flow kind and one aggregation, so nothing here is inferred at save time.
MEANINGS: Final = {
    "period_end_balance": ("stock", "last", "none"),
    "monthly_total": ("flow", "sum", "none"),
    "rate": ("rate", "average", "none"),
    "index": ("index", "last", "none"),
}
#: The reader's word for a unit, and the one the store keeps. A person writes "TL" and
#: "yüzde"; the contract's closed vocabulary is `TRY` and `percent` (`lakehouse/semantics`).
#: A word that is not here is not guessed at: the promotion refuses and the person is
#: asked, which is the rule for every unresolved meaning in this system.
UNIT_WORDS: Final = {
    "tl": "TRY",
    "try": "TRY",
    "₺": "TRY",
    "lira": "TRY",
    "usd": "USD",
    "dolar": "USD",
    "$": "USD",
    "eur": "EUR",
    "euro": "EUR",
    "avro": "EUR",
    "€": "EUR",
    "yüzde": "percent",
    "yuzde": "percent",
    "percent": "percent",
    "%": "percent",
    "puan": "percent",
    "adet": "count",
    "sayı": "count",
    "sayi": "count",
    "count": "count",
    "kişi": "count",
    "kisi": "count",
    "endeks": "index",
    "index": "index",
    "oran": "ratio",
    "ratio": "ratio",
}


#: A scale said in front of a unit ("milyon TL"), and the stored scale it names.
SCALE_WORDS: Final = {
    "bin": "thousand",
    "milyon": "million",
    "milyar": "billion",
    "thousand": "thousand",
    "million": "million",
    "billion": "billion",
}


def unit_for(word: str, scale: object = None) -> str | None:
    """The stored unit a reader's word means, or None when it means nothing certain.

    "milyon TL" is a unit said with its scale, as the column header itself says it. It is
    read as TL when the scale in front agrees with the declared one; a different one is two
    answers to one question, and nothing certain. Live 2026-09-21: the planner passed
    unit="milyon TL" with scale="million", the offer was refused as UNIT_NOT_RECOGNISED
    and the reader was shown a sentence that said nothing.
    """
    parts = word.strip().casefold().split()
    if len(parts) == 2 and parts[0] in SCALE_WORDS:
        declared = getattr(scale, "value", scale)
        if declared is not None and declared != SCALE_WORDS[parts[0]]:
            return None
        parts = parts[1:]
    return UNIT_WORDS.get(" ".join(parts))


#: How a stored unit is said back to the person. Anything else is said as it is stored.
_UNIT_SAID: Final = {"TRY": "TL", "USD": "USD", "EUR": "EUR", "percent": "yüzde"}


def _said_unit(unit: str) -> str:
    """The stored unit in the reader's words, with no scale in it."""
    return _UNIT_SAID.get(unit, unit)


#: A proposal read from a table of the conversation, not from a document: its reference.
RESULT_REFERENCE: Final = "result:"


def _address(locator: str) -> str | None:
    """A source's public address - scheme, host and path - or None when it is not one."""
    parts = urlsplit(locator)
    if parts.scheme != "https" or not parts.hostname or "@" in parts.netloc:
        return None
    return f"https://{parts.netloc}{parts.path}"


#: How each reading is said back to the person, in the summary they approve.
MEANING_WORDS: Final = {
    "period_end_balance": "ay sonundaki bakiye",
    "monthly_total": "ay boyunca gerçekleşen tutar",
    "rate": "oran",
    "index": "endeks",
}


class PromoteSeriesArguments(BaseModel):
    """What to keep, in the reader's own words rather than in the store's."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(
        min_length=1,
        max_length=MAX_TITLE_CHARS,
        description="The series name in Turkish, as the person would say it: 'Şirket geliri'",
    )
    unit: str = Field(
        min_length=1,
        max_length=32,
        description=(
            "The unit the numbers are in: TL, USD, percent, adet. Read it from the document "
            "when the document states it, and ask the person when it does not; never guess"
        ),
    )
    scale: Literal["one", "thousand", "million", "billion"] = Field(
        default="one", description="Whether the figures are plain, thousands, millions or billions"
    )
    meaning: Literal["period_end_balance", "monthly_total", "rate", "index"] = Field(
        description=(
            "What one number is: the balance standing at the end of the month "
            "(period_end_balance), the amount that happened during it (monthly_total), a rate, "
            "or an index. Ask the person in those words when the document does not settle it"
        )
    )
    document: str | None = Field(
        default=None,
        pattern=r"^belge_[0-9]{1,2}$",
        description="Which document to read (belge_1, ...); may be left out when there is one",
    )
    result: str | None = Field(
        default=None,
        pattern=r"^(a[0-9]{1,4}|analiz_[0-9]{1,4})$",
        description=(
            "Instead of a document: a monthly table of this conversation to keep a column "
            "of - a result of this question (a3) or a published one (analiz_1). An address "
            "read into a table (a JSON or CSV endpoint) is kept this way"
        ),
    )
    column: str | None = Field(
        default=None,
        max_length=300,
        description="With `result`: the column to keep; leave it out when the table has one",
    )
    period_column: str | None = Field(
        default=None,
        max_length=120,
        description="The month column's header; leave it out when the table has only one",
    )
    value_column: str | None = Field(
        default=None,
        max_length=120,
        description="The value column's header; leave it out when the table has only one",
    )
    sheet: str | None = Field(default=None, max_length=120, description="Which sheet, if several")
    year: int | None = Field(
        default=None, ge=1900, le=2100, description="The year, when the months do not carry one"
    )
    base_year: int | None = Field(
        default=None, ge=1900, le=2100, description="An index's base year; required for an index"
    )
    table: int | None = Field(
        default=None,
        ge=1,
        le=200,
        description=(
            "Which table of the document, numbered over the whole document as inspect numbers "
            "them without a page; leave it out to use the first"
        ),
    )
    description: str | None = Field(
        default=None,
        max_length=MAX_DESCRIPTION_CHARS,
        description="One or two Turkish sentences on what the series is, for later searches",
    )
    aliases: list[str] = Field(
        default_factory=list,
        max_length=MAX_ALIASES,
        description="Other names a person might search it by, in Turkish",
    )
    save_now: bool = Field(
        default=False,
        description=(
            "true only when the person's own message asked for this to be saved, kept or "
            "added to the knowledge base; then it is saved at once. Reading or analysing a "
            "document is not such a request: leave it false and the person approves a summary"
        ),
    )


@dataclass(frozen=True, slots=True)
class PromotionProposal:
    """What would be saved, and the exact bytes it was read from.

    Held by the server between the two turns. The confirmation saves this; it never
    reassembles the contract from what a model writes the second time.
    """

    slug: str
    title: str
    unit: str
    scale: str
    stock_flow: str
    aggregation: str
    cumulative: str
    base_year: int | None
    session_id: str
    document_ref: str
    document_sha256: str
    period_column: str
    value_column: str
    sheet: str | None
    year: int | None
    observations: tuple[tuple[date, float | None], ...]
    summary: str
    description: str | None = None
    aliases: tuple[str, ...] = ()
    #: Where the numbers were read (`knowledge.store.DatasetVersion.provenance`).
    provenance: tuple[tuple[str, str], ...] = ()


#: What the vectors do after a save, as the receipt says it.
IndexState = Literal["refreshing", "lexical", "unchanged"]

_INDEX_SAID: Final[dict[str, str]] = {
    "refreshing": (
        "Anlamsal arama indeksi arka planda yenileniyor; o bitene kadar seri adıyla ve "
        "takma adlarıyla bulunur."
    ),
    "lexical": "Bu kurulumda anlamsal arama indeksi yok; seri adıyla ve takma adlarıyla bulunur.",
    "unchanged": "Anlamsal arama indeksi otomatik yenilenmedi; seri adıyla bulunur.",
}


@dataclass(frozen=True, slots=True)
class PromotionReceipt:
    """What a save actually wrote. Not an `AnalyticalResult`: nothing was computed."""

    series_id: str
    observations: int
    #: Whether meaning-based search will find it, and when; said, never assumed.
    index: IndexState = "unchanged"

    def said(self) -> str:
        """The confirmation sentence, written by code and the same every time."""
        return (
            f"`{self.series_id}` bilgi tabanına kaydedildi. {self.observations} aylık gözlem "
            f"sonraki analizlerde kullanılabilir. {_INDEX_SAID[self.index]}"
        )


@dataclass(frozen=True, slots=True)
class PromotionOffer:
    """The tool's own output: a question to the reader, never an analytical result."""

    status: Literal["proposed", "refused", "saved"]
    code: str | None = None
    summary: str = ""
    slug: str = ""
    observations: int = 0
    #: With `saved`: the catalogue identity the series is now read by.
    series_id: str = ""


def slug_for(title: str) -> str:
    """A stable store name from the title: the same words give the same slug.

    The store's own shape, not a prettier one: it begins with a letter and holds
    letters, digits and underscores, three to forty characters (`knowledge/store.py`).
    Turkish letters are folded rather than dropped, so "Şirket geliri" is
    `sirket_geliri` and two different titles do not become the same name.
    """
    folded = unicodedata.normalize("NFKD", title.casefold())
    swapped = folded.translate(str.maketrans("ıçğöşü", "icgosu"))
    plain = "".join(c for c in swapped if not unicodedata.combining(c))
    words = re.sub(r"_{2,}", "_", re.sub(r"[^a-z0-9]+", "_", plain)).strip("_")
    trimmed = re.sub(r"^[^a-z]+", "", words)[:39]
    return trimmed if len(trimmed) >= 3 else f"{trimmed}_veri"[:39]


def _kinds(
    headers: Sequence[object],
    rows: Sequence[Sequence[object]],
    rules: RowRules,
    year: int | None,
) -> tuple[list[str], list[str]]:
    """Which headers read as months, and which read as numbers.

    A column decides its own kind from its cells rather than from its name, because a
    header is the document's word and the document is untrusted. A column that is both
    - a year written as a bare number - is counted as a month and not as a value.
    """
    months: list[str] = []
    values: list[str] = []
    for index, raw in enumerate(headers):
        header = str(raw)
        cells = [row[index] for row in rows if index < len(row) and str(row[index]).strip()]
        if not cells:
            continue
        as_month = sum(1 for cell in cells if month_end(cell, year) is not None)
        if as_month >= len(cells) * SHARE_TO_DECIDE:
            months.append(header)
            continue
        readable = 0
        for cell in cells:
            try:
                rules.number(cell)
            except (ColumnRefused, ValueError, TypeError):
                continue
            readable += 1  # a cell the strict reader accepts, not one that looks numeric
        if readable >= len(cells) * SHARE_TO_DECIDE:
            values.append(header)
    return months, values


def _unit(arguments: PromoteSeriesArguments) -> str | None:
    """The stored unit of what is kept. An index is counted in index points, whatever the
    person calls them ("puan" is otherwise read as a percentage)."""
    if arguments.meaning == "index" and arguments.unit.strip().casefold() in (
        "puan",
        "endeks",
        "endeks puanı",
        "index",
        "points",
    ):
        return "index"
    return unit_for(arguments.unit, arguments.scale)


def _summary(
    title: str,
    meaning: str,
    unit: str,
    scale: str,
    observations: Sequence[tuple[date, float | None]],
) -> str:
    """The three lines the reader approves; no field name appears in them."""
    scale_word = {"one": "", "thousand": "bin ", "million": "milyon ", "billion": "milyar "}[scale]
    first, last = observations[0][0], observations[-1][0]
    return (
        f"“{title}” serisini aylık, {scale_word}{unit} ve {MEANING_WORDS[meaning]} olarak "
        f"kaydedeceğim.\n"
        f"{_said(first)}–{_said(last)} arasında {len(observations)} gözlem var.\n"
        "Onaylıyor musun?"
    )


#: Month names as a person writes them, for the summary only; nothing parses these.
MONTH_NAMES: Final = (
    "ocak şubat mart nisan mayıs haziran temmuz ağustos eylül ekim kasım aralık".split()
)


def _said(day: date) -> str:
    return f"{MONTH_NAMES[day.month - 1].capitalize()} {day.year}"


def make_promote_series_tool(
    *,
    session_id: str,
    attachment: Attachment | None,
    library: Mapping[str, Attachment],
    propose: Callable[[PromotionProposal], None],
    references: Mapping[str, str] | None = None,
    ocr: OcrProvider | None = None,
    save: Callable[[PromotionProposal], PromotionReceipt | str] | None = None,
    origin: Callable[[str], Sequence[tuple[str, str]]] | None = None,
) -> ToolSpec:
    """Bind the promotion to one conversation's documents and its proposal store.

    The session is the server's, never an argument: a model cannot name another
    conversation's document, and nothing here takes an owner or a session token.

    `library` and `references` are read when the tool runs, not when it is bound: a
    document read from an address during this very turn is one of the conversation's
    documents by then (QA-29). `save` writes a proposal at once, for a person whose own
    message asked for the save; it answers a receipt or a refusal code. `origin` says
    where a stored document was read from, by its reference.
    """
    documents = library
    #: Display name to the server's own document reference. The proposal records the
    #: reference, because that is what the save looks the document up by again.
    stored: Mapping[str, str] = references if references is not None else {}

    def finish(proposal: PromotionProposal, save_now: bool) -> ToolResult:
        if save_now:
            # The person asked for the save in their own message, so asking them again
            # to approve it only made a second turn out of one request. Everything a
            # proposal is checked for was checked before; the save checks the source
            # again and writes through the knowledge base's one validated route.
            if save is None:
                return _refused("SAVE_UNAVAILABLE")
            receipt = save(proposal)
            if isinstance(receipt, str):
                return _refused(receipt)
            return ToolResult(
                ToolStatus.SUCCESS,
                "promote",
                "promote_series",
                PromotionOffer(
                    "saved",
                    None,
                    receipt.said(),
                    proposal.slug,
                    receipt.observations,
                    receipt.series_id,
                ),
            )
        propose(proposal)
        return ToolResult(
            ToolStatus.SUCCESS,
            "promote",
            "promote_series",
            PromotionOffer(
                "proposed", None, proposal.summary, proposal.slug, len(proposal.observations)
            ),
        )

    def _from_table(arguments: PromoteSeriesArguments, context: ExecutionContext) -> ToolResult:
        """One monthly column of a table this conversation holds, kept as it stands.

        Live 2026-09-23 a Borsa Istanbul endpoint read into `analiz_1` could not be kept:
        only a document could. The months are the table's own; what the table records
        about its unit and scale must agree with what the person says, and where it came
        from - the address, when it was read, what was done to it - is kept beside it.
        """
        name = str(arguments.result)
        table = analytical(context.outputs.get(name))
        if table is None or table.status is not ResultStatus.COMPUTED or not table.values:
            return _refused("RESULT_NOT_FOUND")
        labels = list(dict.fromkeys(value.label for value in table.values))
        names = table.parameters.get("series_names")
        shown = {str(v): k for k, v in names.items()} if isinstance(names, dict) else {}
        wanted = arguments.column
        if wanted is None:
            label = labels[0] if len(labels) == 1 else None
        else:
            label = wanted if wanted in labels else shown.get(wanted)
        if label is None or label not in labels:
            return _refused("VALUE_COLUMN_NOT_SETTLED" if wanted is None else "COLUMN_NOT_FOUND")
        column = [value for value in table.values if value.label == label]
        if any(
            value.period is None or value.period.frequency is not Frequency.MONTHLY
            for value in column
        ):
            return _refused("NO_MONTHLY_ROWS")
        if arguments.meaning == "index" and arguments.base_year is None:
            return _refused("INDEX_NEEDS_BASE_YEAR")
        unit = _unit(arguments)
        if unit is None:
            return _refused("UNIT_NOT_RECOGNISED")
        recorded = {(value.unit, value.scale.value) for value in column}
        if len(recorded) != 1:
            return _refused("UNIT_DISAGREES")
        ((held_unit, held_scale),) = recorded
        # What the table says it holds wins over nothing, never over the person: a column
        # whose unit or scale the table states and the arguments contradict is refused.
        if held_unit not in ("", "unknown") and held_unit != unit:
            return _refused("UNIT_DISAGREES")
        if held_scale != "one" and held_scale != arguments.scale:
            return _refused("UNIT_DISAGREES")
        rows = [(value.period.end, value.value) for value in column if value.period is not None]
        observations = tuple(sorted(rows, key=lambda row: row[0]))
        if len({end for end, _ in observations}) != len(observations):
            return _refused("NO_MONTHLY_ROWS")
        digest = hashlib.sha256(
            json.dumps(
                [table.result_id, label, [[end.isoformat(), v] for end, v in observations]],
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        stock_flow, aggregation, cumulative = MEANINGS[arguments.meaning]
        summary = _summary(
            arguments.title, arguments.meaning, _said_unit(unit), arguments.scale, observations
        )
        evidence = table.evidence
        origin: list[tuple[str, str]] = []
        for source in evidence.sources if evidence is not None else []:
            where = _address(source.locator)
            if where is not None:
                origin.append(("source_url", where))
                if source.retrieved_at is not None:
                    origin.append(("retrieved_at", source.retrieved_at.isoformat()))
                if source.content_hash:
                    origin.append(("sha256", source.content_hash.removeprefix("sha256:")))
                break
        steps = [item.operation for item in (evidence.transformations if evidence else [])]
        proposal = PromotionProposal(
            slug=slug_for(arguments.title),
            title=arguments.title,
            unit=unit,
            scale=arguments.scale,
            stock_flow=stock_flow,
            aggregation=aggregation,
            cumulative=cumulative,
            base_year=arguments.base_year,
            session_id=session_id,
            document_ref=RESULT_REFERENCE + name,
            document_sha256=digest,
            period_column="period",
            value_column=label,
            sheet=None,
            year=None,
            observations=observations,
            summary=summary,
            description=" ".join((arguments.description or "").split()) or None,
            aliases=tuple(" ".join(alias.split()) for alias in arguments.aliases if alias.strip()),
            provenance=(
                *origin,
                ("table", name),
                ("column", label),
                *((("transformations", ", ".join(steps)),) if steps else ()),
            ),
        )
        return finish(proposal, arguments.save_now)

    def run(arguments: BaseModel, context: ExecutionContext) -> ToolResult:
        if not isinstance(arguments, PromoteSeriesArguments):  # pragma: no cover - contract
            raise TypeError("promote_series received arguments it did not declare")
        if arguments.result is not None:
            return _from_table(arguments, context)
        chosen = choose_document(arguments.document, attachment, documents)
        if isinstance(chosen, str):
            return _refused(chosen)
        name = arguments.document or library_name(chosen, documents) or ""
        reference = stored.get(name, name)
        read = read_attachment(chosen, sheet=arguments.sheet, ocr=ocr)
        if read.failure is not None or read.output.source is None:
            return _refused("DOCUMENT_REJECTED")
        try:
            tables = grids(read.output.table, read.output.document)
        except ValueError:
            return _refused("DOCUMENT_REJECTED")
        if not tables:
            return _refused("NO_TABLE_IN_DOCUMENT")
        if arguments.table is not None and arguments.table > len(tables):
            return _refused("TABLE_NOT_FOUND")
        # The first table was the only one ever read, so a PDF whose monthly table was
        # its third could not be kept at all.
        grid = tables[(arguments.table or 1) - 1]
        if arguments.table is not None:
            tables = [grid]
        rules = RowRules.for_grid(grid, year=arguments.year, as_of=None)
        months, values = _kinds(grid.headers, grid.rows, rules, arguments.year)
        period_column = arguments.period_column or (months[0] if len(months) == 1 else None)
        if period_column is None:
            return _refused("PERIOD_COLUMN_NOT_SETTLED" if months else "NO_PERIOD_COLUMN")
        candidates = [header for header in values if header != period_column]
        value_column = arguments.value_column or (candidates[0] if len(candidates) == 1 else None)
        if value_column is None:
            return _refused("VALUE_COLUMN_NOT_SETTLED" if candidates else "NO_VALUE_COLUMN")
        if arguments.meaning == "index" and arguments.base_year is None:
            return _refused("INDEX_NEEDS_BASE_YEAR")
        unit = _unit(arguments)
        if unit is None:
            # The person's own word for a unit nobody here recognises. Storing it as
            # written would put an unresolved meaning in the catalogue; asking is the
            # rule this system already follows everywhere else.
            return _refused("UNIT_NOT_RECOGNISED")
        try:
            rows = read_month_values(
                tables, period_column, value_column, year=arguments.year, as_of=None
            )
        except ColumnRefused as refusal:
            return _refused(str(refusal) or "COLUMN_REFUSED")
        observations = tuple((end, value) for end, value, _ in rows)
        if not observations:
            return _refused("NO_MONTHLY_ROWS")
        digest = (chosen.source.content_hash or "").removeprefix("sha256:")
        if not digest:
            return _refused("DOCUMENT_NOT_HASHED")
        stock_flow, aggregation, cumulative = MEANINGS[arguments.meaning]
        # The stored unit, not the word the planner wrote: `unit_for` strips a scale said
        # in front of it ("milyon TL" -> TRY), while `_summary` adds the scale word itself.
        # Given the raw word the reader was asked to approve "aylık, milyon milyon TL"
        # (live 2026-09-21), although what was saved was right all along.
        summary = _summary(
            arguments.title, arguments.meaning, _said_unit(unit), arguments.scale, observations
        )
        proposal = PromotionProposal(
            slug=slug_for(arguments.title),
            title=arguments.title,
            unit=unit,
            scale=arguments.scale,
            stock_flow=stock_flow,
            aggregation=aggregation,
            cumulative=cumulative,
            base_year=arguments.base_year,
            session_id=session_id,
            document_ref=reference,
            document_sha256=digest,
            period_column=period_column,
            value_column=value_column,
            sheet=arguments.sheet,
            year=arguments.year,
            observations=observations,
            summary=summary,
            description=" ".join((arguments.description or "").split()) or None,
            aliases=tuple(" ".join(alias.split()) for alias in arguments.aliases if alias.strip()),
            provenance=_provenance(
                origin(reference) if origin is not None else (),
                name=name,
                media_type=chosen.media_type,
                location=grid.location,
                sheet=arguments.sheet,
                period_column=period_column,
                value_column=value_column,
            ),
        )
        return finish(proposal, arguments.save_now)

    return ToolSpec(
        name="promote_series",
        description=(
            "Keep one monthly value column of a document in this conversation (uploaded, or "
            "read from an address in this conversation) - or of a monthly table of it, by "
            "`result` (analiz_1, or a3 of this question) - as a series in the knowledge base, "
            "so later conversations find it by name or meaning. With save_now=true - only "
            "when the person's own message asked for it to be saved, kept or added - it is "
            "saved at once and the result says what was saved. Otherwise it writes nothing "
            "and returns a short Turkish summary for the person to approve in their next "
            "message. Never call it because a document was merely read or analysed. The "
            "columns, months, unit and meaning are checked against the document's cells; a "
            "refusal names what is unsettled, so ask the person only about that. Give a "
            "title, and a description and aliases for later searches. One call keeps one "
            "monthly value column: a table of another frequency cannot be kept this way, "
            "say so rather than saving it as monthly."
        ),
        arguments=PromoteSeriesArguments,
        run=run,
    )


def _provenance(
    origin: Sequence[tuple[str, str]],
    *,
    name: str,
    media_type: str,
    location: Mapping[str, object],
    sheet: str | None,
    period_column: str,
    value_column: str,
) -> tuple[tuple[str, str], ...]:
    """Where the numbers were read: the document's origin, then the place inside it."""
    inside = [(f"location_{key}", str(value)) for key, value in location.items()]
    return (
        *origin,
        ("document", name),
        ("media_type", media_type),
        *inside,
        *((("sheet", sheet),) if sheet else ()),
        ("period_column", period_column),
        ("value_column", value_column),
    )


#: The limit of a save from a conversation, as the person is told it. The same words the
#: knowledge page says the same beside its form (`web/lib/client.ts`).
SAVE_LIMIT: Final = (
    "Sohbetten kayıt yalnız aylık dönemli tablolar için ve her seferinde tek bir değer "
    "sütunu kaydeder; birden çok sütun ayrı ayrı istenir. Haftalık, çeyreklik, yıllık ya da "
    "günlük veri Veri ve bilgi tabanı sayfasındaki formdan girilir."
)

#: A refusal said in words the model can pass on, where the code alone is the limit
#: itself: without them a person asking to keep a quarterly table was told nothing
#: about why, and the model had to guess at what the tool could do.
_SAID: Final[dict[str, str]] = {
    "NO_PERIOD_COLUMN": "Tabloda aylık dönem sütunu bulunamadı. " + SAVE_LIMIT,
    "NO_MONTHLY_ROWS": "Tabloda okunabilir aylık satır yok. " + SAVE_LIMIT,
    "PERIOD_COLUMN_NOT_SETTLED": (
        "Tabloda birden çok ay sütunu var; hangisinin dönem olduğunu kişiye sor."
    ),
    "VALUE_COLUMN_NOT_SETTLED": (
        "Tabloda birden çok değer sütunu var ve bir kayıt tek sütun tutar; hangisinin "
        "(ya da her birinin ayrı ayrı) kaydedileceğini kişiye sor."
    ),
}


def _refused(code: str) -> ToolResult:
    said = _SAID.get(code, "")
    return ToolResult(
        ToolStatus.FAILURE,
        "promote",
        "promote_series",
        PromotionOffer("refused", code, said),
        error_category="promotion_refused",
        warnings=(code, *((said,) if said else ())),
    )
