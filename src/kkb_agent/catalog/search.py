"""M13-04: bounded offline lexical discovery, not observation/claim evidence.

An operator supplies reviewed bytes. No SQL, FTS extension, network, model or
filesystem operation occurs. Small-corpus BM25 uses k1=1.2, b=.75 and positive
log(1+(N-df+.5)/(df+.5)) IDF; no stemming/stopwords or holdout tuning.
"""

from collections import Counter
from collections.abc import Callable, Sequence
from math import log
from typing import Final, Literal

from pydantic import Field, StrictBool, StrictInt, StrictStr, field_validator

from kkb_agent.catalog.mappings import (
    Concept,
    ReviewedSeries,
    ReviewedSnapshot,
    is_listed_series,
    is_source_group,
)
from kkb_agent.catalog.normalization import normalize_search_text
from kkb_agent.catalog.ranking import (
    intent_key,
    named_measure_kind,
    rerank_by_reviewed_intent,
    rerank_widened,
)
from kkb_agent.catalog.records import (
    MAX_CATALOG_CONCEPTS,
    MAX_CATALOG_SERIES,
    CatalogRecord,
    CatalogStatus,
)
from kkb_agent.core import Frequency, StockFlow
from kkb_agent.core.models import ContractModel

SearchMethod = Literal["reviewed_alias", "reviewed_phrase", "bm25", "dense"]
SearchStatus = Literal["MATCH", "PARTIAL", "UNRESOLVED", "NO_MATCH", "FILTERED_OUT"]
#: Whether the first candidate is the default the request leaves. "unambiguous":
#: the reviewed-intent order puts it strictly first (the aggregate over TP/YP
#: components, the national series over regions, the current over the archived)
#: and every shown candidate shares a reviewed concept or family with it;
#: "ambiguous": candidates tie on an axis the request did not name, or span
#: unrelated concepts; "unconfirmed": no reviewed concept matched the wording, so
#: every candidate is only a neighbour by shared words or by meaning and the
#: catalogue may not hold the requested measure at all (DEC-172: "dolar kuru" found
#: one USD loan-rate series and called it the unambiguous default); "none": nothing
#: was found. Deterministic, from reviewed metadata only; the planner still checks
#: declared semantics against the question.
TopCandidate = Literal["unambiguous", "ambiguous", "unconfirmed", "none"]


class CatalogSearchArguments(ContractModel):
    query: StrictStr = Field(min_length=1, max_length=512, repr=False)
    max_results: StrictInt = Field(default=10, ge=1, le=10)
    source: StrictStr | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description=(
            "Provider (EVDS, BDDK) or a publisher the reviewed title/labels name (TÜİK, "
            "TCMB). Omit when unsure: a filter that matches nothing returns FILTERED_OUT "
            "with no candidates"
        ),
    )
    frequency: Frequency | None = None
    include_archived: StrictBool = False

    @field_validator("query", "source")
    @classmethod
    def nonblank(cls, value: str | None) -> str | None:
        if value is not None and (
            not normalize_search_text(value) or any(ord(c) < 32 or ord(c) == 127 for c in value)
        ):
            raise ValueError("expected nonblank text without controls")
        return value


class ConceptMatch(ContractModel):
    concept_id: str
    family_ids: tuple[str, ...]
    resolution: Literal["MAPPED", "PARTIAL", "UNRESOLVED"]
    unresolved: tuple[str, ...]
    conditions: tuple[str, ...]


class BandChoice(ContractModel):
    """One maturity column of a candidate's row, readable as a series of its own.

    It names its parent row, the table, and the currency the row is in, read from the
    band's own record. Live 2026-09-23 (B1 on 8012) two rows' bands were listed side by
    side as bare `{band, series_id}` pairs; the model took the DTH row's bands for the TP
    row's, summed foreign-currency deposits as TP maturity groups, and spent its call
    budget searching for the TP bands it had already been shown.
    """

    band: StrictStr
    series_id: StrictStr
    #: The row this band is a column of, without the band: "TP Mevduat / ... Yerleşik".
    row: StrictStr | None = None
    table: StrictStr | None = None
    #: "TP" or "YP" when the row's own name says which; None when it says neither.
    currency: Literal["TP", "YP"] | None = None


def _row_currency(row: str) -> Literal["TP", "YP"] | None:
    """The currency a bulletin row names itself in: "TP ...", "YP ...", "Döviz Tevdiat ..."."""
    words = set(normalize_search_text(row).split())
    tp = "tp" in words
    yp = "yp" in words or {"doviz", "tevdiat"} <= words
    if tp != yp:
        return "TP" if tp else "YP"
    return None


def band_choice(band: str, record: CatalogRecord) -> BandChoice:
    """A band with its parent row, table and currency, as its own record states them."""
    suffix = f" ({band})"
    row = record.title[: -len(suffix)] if record.title.endswith(suffix) else record.title
    return BandChoice(
        band=band,
        series_id=record.series_id,
        row=row,
        table=record.group.group_title if record.group is not None else None,
        currency=_row_currency(row),
    )


class CatalogCandidate(ContractModel):
    series: ReviewedSeries
    concept_ids: tuple[str, ...]
    family_ids: tuple[str, ...]
    observation_kind: Literal["unknown"] = "unknown"  # absent from CatalogRecord
    rank: int = Field(ge=1, le=10)
    bm25_score: float | None = Field(ge=0)
    matched_terms: tuple[str, ...]
    method: SearchMethod
    retrieval_sources: tuple[Literal["lexical", "dense"], ...] = ("lexical",)
    lexical_rank: int | None = Field(default=None, ge=1, le=10)
    dense_rank: int | None = Field(default=None, ge=1, le=10)
    cosine_distance: float | None = Field(default=None, ge=-0.000001, le=2.000001)
    #: The maturity columns of this candidate's row that the search also reached, each a
    #: series of its own (`fold_bands`). Listed here rather than as candidates beside it.
    bands: tuple[BandChoice, ...] = ()


#: Datagroups one search carries for expansion: a stage's whole budget. Measured on the
#: live index (2026-09-19) the right datagroup is always among the ten nearest by meaning
#: and not always among the first three ("ABD doları TL kuru": fourth, behind groups whose
#: unit is the dollar). An unopened datagroup costs one source read, once per installation.
MAX_GROUPS = 10


class CatalogSearchOutput(ContractModel):
    status: SearchStatus
    candidates: tuple[CatalogCandidate, ...] = Field(default=(), max_length=10)
    #: Source datagroups found for the query (DEC-177). They are containers, not series: no
    #: plan can read one, so they never sit among `candidates`. `catalog.expansion` replaces
    #: them by their series, or drops them, before a planner sees the result.
    groups: tuple[CatalogCandidate, ...] = Field(default=(), max_length=MAX_GROUPS)
    concepts: tuple[ConceptMatch, ...] = Field(default=(), max_length=MAX_CATALOG_CONCEPTS)
    total_candidates: int = Field(ge=0, le=MAX_CATALOG_SERIES)
    truncated: bool
    clarification_required: bool
    excluded_archived_count: int = Field(ge=0, le=MAX_CATALOG_SERIES)
    snapshot_version: str
    snapshot_sha256: str
    retrieval_version: Literal["m13-04-lexical-v1", "m13-05-combined-v1"] = "m13-04-lexical-v1"
    top_candidate: TopCandidate = "none"
    #: Filters the tool dropped because nothing matched with them (`tools.catalog_search`).
    relaxed_filters: tuple[Literal["source", "frequency"], ...] = ()
    retrieval_mode: Literal["lexical_only", "hybrid", "lexical_degraded"] = "lexical_only"
    combination_policy: Literal[
        "lexical-v1", "reviewed-match-order-v1", "alternating-archive-tier-v1"
    ] = "lexical-v1"
    dense_status: Literal["not_configured", "skipped_no_eligible", "success", "failed"] = (
        "not_configured"
    )
    dense_failure: Literal["snapshot_mismatch", "embedding_failed", "index_failed"] | None = None
    embedding_origin: Literal["offline_fixture", "kloudeks"] | None = None
    input_policy_id: str | None = None
    profile_sha256: str | None = None
    lexical_total_candidates: int | None = Field(default=None, ge=0, le=MAX_CATALOG_SERIES)
    dense_total_candidates: int | None = Field(default=None, ge=0, le=MAX_CATALOG_SERIES)
    # What this reply *is*, never what a tool may do. A listing is discovery metadata:
    # its ranking is untrusted, it carries no observations, and it is not evidence for
    # a figure. Whether a series may be read is decided where it is read — the read
    # tools and the acquisition route apply their own checks, and the planned path
    # its discovery rule — and none of them consults this reply. It used to say
    # `observation_fetch_authorized: false`, which described the listing and read as a
    # prohibition: live 2026-09-23 the model quoted it, concluded it was not allowed to
    # read any value, and answered a deposit question with "I cannot produce a single
    # number" without trying to read one.
    untrusted_metadata: Literal[True] = True
    observations_included: Literal[False] = False
    analytical_evidence: Literal[False] = False


#: Shortest final alias word that may carry a suffix: "tufe" + "yi", never "tl" + "ref".
_MIN_SUFFIXED_STEM = 4


def _phrase_in(alias: str, words: list[str]) -> bool:
    """A reviewed alias as whole words of the query; its last word may carry suffixes.

    Turkish inflects the head of a noun phrase, which is its last word: "konut kredisi
    faizi" is asked as "konut kredisi faizini göster" or "... faizinin seyri". Whole-word
    matching alone missed every such question, so a request the catalogue holds looked
    no different from one it does not (DEC-172). Earlier words stay exact.
    """
    wanted = alias.split()
    last = wanted[-1]
    for start in range(len(words) - len(wanted) + 1):
        window = words[start : start + len(wanted)]
        if window[:-1] == wanted[:-1] and (
            window[-1] == last or (len(last) >= _MIN_SUFFIXED_STEM and window[-1].startswith(last))
        ):
            return True
    return False


def _concept_matches(snapshot: ReviewedSnapshot, key: str) -> tuple[list[Concept], SearchMethod]:
    exact = [c for c in snapshot.concepts if any(a.normalized == key for a in c.aliases)]
    if exact:
        return exact, "reviewed_alias"
    # Longest contained phrase wins over its generic substring; identical alias
    # collisions and disjoint concepts remain sets, not last-write-wins entries.
    words = key.split()
    phrases = {
        a.normalized
        for c in snapshot.concepts
        for a in c.aliases
        if a.normalized and _phrase_in(a.normalized, words)
    }
    maximal = {p for p in phrases if not any(p != q and f" {p} " in f" {q} " for q in phrases)}
    return [c for c in snapshot.concepts if any(a.normalized in maximal for a in c.aliases)], (
        "reviewed_phrase" if maximal else "bm25"
    )


def _terms(item: ReviewedSeries, concepts: list[Concept]) -> Counter[str]:
    record = item.record
    # Only positive reviewed aliases and canonical/display text are indexed.
    # Exclusion notes/UNRESOLVED contexts are not positive retrieval evidence.
    text = " ".join(
        [record.title, record.description or "", *record.labels]
        + [a.original for c in concepts for a in c.aliases]
    )
    return Counter(normalize_search_text(text).split())


#: The words a question names a calendar by, already in search form. Fineness is the order:
#: a coarser calendar is derived from a finer one by resampling, never the other way round.
_CALENDAR_WORDS: Final = (
    (Frequency.DAILY, 0, ("gunluk", "gun bazinda", "daily")),
    (Frequency.WEEKLY, 1, ("haftalik", "hafta bazinda", "haftalar itibariyla", "weekly")),
    (Frequency.MONTHLY, 2, ("aylik", "ay bazinda", "monthly")),
    (Frequency.QUARTERLY, 3, ("ceyreklik", "uc aylik", "quarterly")),
    (Frequency.ANNUAL, 4, ("yillik", "annual", "yearly")),
)
_FINENESS: Final = {
    **{calendar: order for calendar, order, _ in _CALENDAR_WORDS},
    Frequency.BUSINESS_DAY: 0,
}


def named_calendar(key: str) -> Frequency | None:
    """The one calendar a normalized question names, or None when it names none or several."""
    padded = f" {key} "
    named = {
        calendar
        for calendar, _, words in _CALENDAR_WORDS
        if any(f" {word} " in padded for word in words)
    }
    return next(iter(named)) if len(named) == 1 else None


def finer_than_reviewed(
    snapshot: ReviewedSnapshot, mapped: set[str], calendar: Frequency | None, query: str
) -> bool:
    """The question names a calendar finer than the matched concept has, and one that exists.

    A monthly series holds no weeks, so a reviewed concept that exists only monthly cannot
    answer "haftalık ...": it stops bounding the candidates (DEC-182). The other direction
    is ordinary work, not a reason to look elsewhere: "aylık" over a weekly reviewed series
    is a resample of that series. And the bound is kept when no series of the named calendar
    is titled with a word of the question: "haftalık TÜFE" has no weekly series to go to, so
    the monthly index is still the answer, with its calendar said. A series the question's
    own qualifiers contradict does not count: a weekly interest rate is nowhere to go for
    "haftalık konut kredisi bakiyesi".
    """
    if calendar is None or not mapped:
        return False
    known = [
        _FINENESS[item.record.frequency]
        for item in snapshot.series
        if item.record.series_id in mapped and item.record.frequency in _FINENESS
    ]
    if not known or _FINENESS[calendar] >= min(known):
        return False
    asked = set(normalize_search_text(query).split()) - {
        part for _, _, words in _CALENDAR_WORDS for word in words for part in word.split()
    }
    return any(
        item.record.frequency is calendar
        and not is_source_group(item)
        and asked & set(normalize_search_text(item.record.title).split())
        and not intent_key(query, item)[1]  # no qualifier of the question contradicts it
        for item in snapshot.series
    )


def scoped_to_named_calendar(
    snapshot: ReviewedSnapshot, arguments: CatalogSearchArguments
) -> tuple[CatalogSearchArguments, bool]:
    """The arguments a search really runs with, and whether the reviewed bound was lifted.

    One decision for the word search and the combined search, so both look at the same
    series: when `finer_than_reviewed`, the search runs among series of the named calendar.
    A calendar filter the caller set is kept.
    """
    key = normalize_search_text(arguments.query)
    matches, _ = _concept_matches(snapshot, key)
    mapped = {sid for c in matches for sid in c.candidate_series_ids}
    calendar = named_calendar(key)
    if not finer_than_reviewed(snapshot, mapped, calendar, arguments.query):
        return arguments, False
    if arguments.frequency is None:
        arguments = arguments.model_copy(update={"frequency": calendar})
    return arguments, True


def named_calendar_first[T](
    query: str, ordered: Sequence[T], *, reviewed_series: Callable[[T], ReviewedSeries]
) -> list[T]:
    """Neighbours of the calendar the question names come first; nothing is removed.

    Only for a search no reviewed concept bounds: every candidate is then a neighbour, and
    "haftalık ihtiyaç kredisi" is nearer to the weekly series than to the monthly one of
    the same name. The order within each calendar is kept.
    """
    calendar = named_calendar(normalize_search_text(query))
    if calendar is None:
        return list(ordered)
    return sorted(ordered, key=lambda item: reviewed_series(item).record.frequency is not calendar)


#: The last few catalogues' search text. A catalogue is immutable and named by its content
#: digest, and with the sources' listings in it (8,000 entries with FinTürk) folding every
#: entry's words again for every search was most of a search's time.
_INDEXED: dict[str, tuple[dict[str, list[Concept]], dict[str, Counter[str]]]] = {}
_INDEXED_KEPT: Final = 4


def _indexed(
    snapshot: ReviewedSnapshot,
) -> tuple[dict[str, list[Concept]], dict[str, Counter[str]]]:
    """Each series' reviewed concepts and search words, computed once per catalogue."""
    kept = _INDEXED.get(snapshot.content_sha256)
    if kept is None:
        concepts: dict[str, list[Concept]] = {}
        for concept in snapshot.concepts:
            for series_id in concept.candidate_series_ids:
                concepts.setdefault(series_id, []).append(concept)
        kept = (
            concepts,
            {
                item.record.series_id: _terms(item, concepts.get(item.record.series_id, []))
                for item in snapshot.series
            },
        )
        while len(_INDEXED) >= _INDEXED_KEPT:
            _INDEXED.pop(next(iter(_INDEXED)))
        _INDEXED[snapshot.content_sha256] = kept
    return kept


_EVDS_NAMES = frozenset({"tcmb", "cbrt", "merkez bankasi", "central bank", "evds"})


def source_matches(item: ReviewedSeries, source: str) -> bool:
    """`source` names the provider (EVDS, BDDK) or a publisher the reviewed text names.

    A CPI series is provided by EVDS and published by TÜİK, and the reviewed
    labels say so; a planner that filters by the publisher it read in a title
    must not empty the result (live R2, 2026-09-19: `source="TÜİK"` returned
    FILTERED_OUT and the planner fell back to the cross-check series).
    """
    wanted = normalize_search_text(source)
    record = item.record
    # EVDS is the central bank's own data system: a planner that asks for "TCMB" means it
    # (live 2026-09-21: `source="TCMB"` emptied the search for the housing loan rate).
    if wanted in _EVDS_NAMES and record.provider == "EVDS":
        return True
    if normalize_search_text(record.provider) == wanted:
        return True
    named = normalize_search_text(" ".join([record.title, *record.labels]))
    return f" {wanted} " in f" {named} "


#: The one-word places the listed series of a catalogue are published for, by its digest.
_PLACES: dict[str, frozenset[str]] = {}

#: The country is where every national series is, not a place a question narrows to. The
#: monthly and weekly bulletins' entries say "Türkiye", so "Türkiye" became a place, and
#: "Türkiye'de enflasyon" was searched among series marked Türkiye only: every EVDS
#: datagroup, which declares no place, was held back (measured 2026-09-23: 0 of 678).
_COUNTRY = normalize_search_text("Türkiye")


def named_places(snapshot: ReviewedSnapshot, query: str) -> frozenset[str]:
    """The provinces a question names, among those a listed source publishes (DEC-184).

    "İstanbul'da konut kredisi" is a question about İstanbul. A reviewed concept maps
    "konut kredisi" to the national series and would bound the search to them, which held
    every province cell back (live, 2026-09-21: the agent answered that the catalogue has no
    province data). A place is one word of the question equal to a listed series' place;
    "Yurt Dışı" is two ordinary words and never scopes a search.
    """
    places = _PLACES.get(snapshot.content_sha256)
    if places is None:
        places = frozenset(
            place
            for place in (
                normalize_search_text(item.geography or "")
                for item in snapshot.series
                if is_listed_series(item)
            )
            if place and " " not in place and place != _COUNTRY
        )
        while len(_PLACES) >= _INDEXED_KEPT:
            _PLACES.pop(next(iter(_PLACES)))
        _PLACES[snapshot.content_sha256] = places
    return places & set(normalize_search_text(query).split())


def eligible_catalog_series(
    snapshot: ReviewedSnapshot, args: CatalogSearchArguments
) -> tuple[ReviewedSeries, ...]:
    """Shared declared metadata filtering, independent of ranking method.

    A question that names provinces is searched among the series of those provinces, in the
    word search and the combined search alike. An entry that declares no place stays: an
    EVDS datagroup declares none and may hold exactly the province's series ("İstanbul
    konut satışları" is an EVDS datagroup of per-province sales), so only an entry known to
    be another place's is held back.
    """
    places = named_places(snapshot, args.query)
    return tuple(
        s
        for s in snapshot.series
        if (args.include_archived or s.record.status is not CatalogStatus.ARCHIVED)
        and (args.source is None or source_matches(s, args.source))
        and (args.frequency is None or s.record.frequency is args.frequency)
        and (not places or not s.geography or normalize_search_text(s.geography) in places)
    )


def _place_is_named(series: ReviewedSeries, query_words: set[str]) -> bool:
    """Whether the question names this listed series' place ("İstanbul'da", "Ankara ve ...")."""
    place = normalize_search_text(series.geography or "").split()
    return bool(place) and all(word in query_words for word in place)


def one_per_listed_row[T](
    ordered: Sequence[T], *, reviewed_series: Callable[[T], ReviewedSeries], query: str = ""
) -> list[T]:
    """Keep the first component of each listed row; reviewed entries are all kept.

    A listed BDDK row exists as TP, YP and Toplam, three entries with one title. Ten
    results would otherwise be three rows, three times each. The reviewed-intent order
    has already put first the component the question names, or the total when it names
    none, so the first of each row is the one to show. Reviewed series are untouched:
    their components are told apart by reviewed concepts and defaults (DEC-165).

    A listed province series (FinTürk, DEC-184) exists once per province under one column
    name. Each province the question names is its own row; the provinces it does not name
    are one row, or ten results would be one column in ten arbitrary provinces.
    """
    seen: set[tuple[str, str | None, str]] = set()
    kept: list[T] = []
    words = set(normalize_search_text(query).split())
    for item in ordered:
        series = reviewed_series(item)
        if is_listed_series(series):
            record = series.record
            title = record.title
            if series.geography and title.endswith(" - " + series.geography):
                if not _place_is_named(series, words):
                    title = title.removesuffix(" - " + series.geography)
            row = (record.provider, record.group.group_id if record.group else None, title)
            if row in seen:
                continue
            seen.add(row)
        kept.append(item)
    return kept


#: How a listed maturity column labels itself: "Vade: <its column name>".
_BAND_LABEL: Final = "Vade: "


def _band(series: ReviewedSeries) -> tuple[tuple[str, str | None, str], str] | None:
    """The row a maturity column belongs to, and the column's name; None for any other.

    Read from the record's own metadata: a band says which maturity it is in a label and
    carries its row's title with that name after it, in its row's group.
    """
    record = series.record
    for label in record.labels:
        if label.startswith(_BAND_LABEL):
            name = label.removeprefix(_BAND_LABEL)
            suffix = f" ({name})"
            if record.title.endswith(suffix):
                group = record.group.group_id if record.group else None
                return (record.provider, group, record.title.removesuffix(suffix)), name
    return None


def fold_bands[T](
    ordered: Sequence[T], *, reviewed_series: Callable[[T], ReviewedSeries]
) -> list[tuple[T, list[T]]]:
    """Each candidate with the maturity columns of its row the search reached, in order.

    The bulletin publishes a row's maturity as columns, and each is a series of its own
    (the TP deposits opened for up to a month, for one to three months, …). Listed as
    candidates of their own, seven columns of one row took the room of other rows: live
    fixtures, a question about credit-card balances saw two maturity buckets of a
    liquidity row and not the credit-card row it asked about. Hidden unless the question
    names a maturity, they would be chosen by words. So a band is folded under its row's
    candidate and named there, series ID and all: the row keeps one place, and every
    maturity the search reached is still in front of the model. A band whose row is not
    among the candidates stands for it, with its sibling bands under it.
    """
    kept: list[tuple[T, list[T]]] = []
    rows: dict[tuple[str, str | None, str], int] = {}
    for item in ordered:
        series = reviewed_series(item)
        if _band(series) is None:
            record = series.record
            key = (record.provider, record.group.group_id if record.group else None, record.title)
            rows.setdefault(key, len(kept))
            kept.append((item, []))
    placed: list[tuple[T, list[T]]] = list(kept)
    for item in ordered:
        found = _band(reviewed_series(item))
        if found is None:
            continue
        key, _ = found
        if key in rows:
            placed[rows[key]][1].append(item)
        else:
            rows[key] = len(placed)
            placed.append((item, []))
    # The row's own position decides the order; a band standing for its row keeps its rank.
    position = {id(item): at for at, item in enumerate(ordered)}
    return sorted(placed, key=lambda entry: position[id(entry[0])])


def top_candidate_signal(
    query: str,
    candidates: Sequence[CatalogCandidate],
    *,
    reviewed_match: bool,
    available_kinds: frozenset[StockFlow] | None = None,
    runner_up: ReviewedSeries | None = None,
) -> TopCandidate:
    """See `TopCandidate`: strictly first by reviewed intent, within one concept or family.

    `reviewed_match` says a reviewed alias or phrase matched the query. Without one the
    candidates are neighbours, however few or however near, and none is a default.
    """
    if not candidates:
        return "none"
    if not reviewed_match:
        return "unconfirmed"
    # A component or currency default cannot settle an unnamed balance-vs-rate
    # question. Check the full eligible set, not only max_results=1's shortlist.
    kinds = available_kinds or frozenset(c.series.record.stock_flow for c in candidates)
    if named_measure_kind(query) is None and StockFlow.STOCK in kinds and StockFlow.RATE in kinds:
        return "ambiguous"
    if len(candidates) == 1:
        if runner_up is not None and not intent_key(query, candidates[0].series) < intent_key(
            query, runner_up
        ):
            return "ambiguous"
        return "unambiguous"
    first, second = (intent_key(query, c.series) for c in candidates[:2])
    if not first < second:
        return "ambiguous"
    groups = [set(c.concept_ids) | set(c.family_ids) for c in candidates]
    return "unambiguous" if set.intersection(*groups) else "ambiguous"


def search_catalog(
    snapshot: ReviewedSnapshot, arguments: CatalogSearchArguments, *, bounded: bool = True
) -> CatalogSearchOutput:
    """`bounded`: whether a reviewed alias match closes the candidate set to its concepts.

    The planned path relies on that closure (its planner picks among reviewed candidates).
    The model-driven loop does not: it reads titles and decides, and a closed set hides
    what the alias did not name. Live 2026-09-23 (QA-24) "taşıt kredisi faiz oranı stok"
    matched a reviewed alias whose only member is the new-loan (akım) rate, and the
    outstanding-portfolio (stok) rate the question named was removed from the result —
    found only by an English query. Unbounded, the concept's members come first among
    equals and every other series the words reach is listed beside them, ordered by the
    same qualifier check, so an explicit "stok" still puts an akım series below.
    """
    snapshot = ReviewedSnapshot.model_validate(snapshot)
    args = CatalogSearchArguments.model_validate(arguments)
    key = normalize_search_text(args.query)
    matches, method = _concept_matches(snapshot, key)
    mapped = {sid for c in matches for sid in c.candidate_series_ids}
    args, lifted = scoped_to_named_calendar(snapshot, args)
    if lifted or named_places(snapshot, args.query):
        # The concept exists only on a coarser calendar than the one asked for, or only for
        # the country when provinces were named, so it no longer bounds the search; series
        # of the named calendar or provinces are searched instead, unconfirmed as any
        # neighbour is.
        matches, mapped, method = [], set(), "bm25"
    excluded = (
        sum(
            s.record.status is CatalogStatus.ARCHIVED
            and (not matches or s.record.series_id in mapped)
            for s in snapshot.series
        )
        if not args.include_archived
        else 0
    )
    eligible = eligible_catalog_series(snapshot, args)
    concepts_of, terms_of = _indexed(snapshot)
    concepts_by_id = {s.record.series_id: concepts_of.get(s.record.series_id, []) for s in eligible}
    documents = {s.record.series_id: terms_of[s.record.series_id] for s in eligible}
    query_terms = set(key.split())
    count = len(documents)
    average = sum(sum(d.values()) for d in documents.values()) / count if count else 1.0
    # Counted once per word of the question, not once per series that carries it: with the
    # sources' listings in the catalogue that was millions of lookups a search.
    holders = {term: sum(term in doc for doc in documents.values()) for term in query_terms}
    scores: dict[str, float] = {}
    for sid, doc in documents.items():
        score = 0.0
        for term in sorted(query_terms & doc.keys()):
            df = holders[term]
            idf = log(1 + (count - df + 0.5) / (df + 0.5))
            tf = doc[term]
            score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * sum(doc.values()) / average))
        scores[sid] = round(score, 12)
    ranked = [
        s
        for s in eligible
        if (
            s.record.series_id in mapped
            if matches and bounded
            else s.record.series_id in mapped or scores[s.record.series_id] > 0
        )
    ]
    ranked.sort(
        key=lambda s: (
            s.record.status is CatalogStatus.ARCHIVED,
            -scores[s.record.series_id],
            s.record.series_id,
        )
    )
    # Datagroups declare no kind, unit or currency, so the reviewed-intent order would push
    # every one of them below any series that does. They keep their own relevance order.
    found_groups = [s for s in ranked if is_source_group(s)][:MAX_GROUPS]
    ranked = [s for s in ranked if not is_source_group(s)]
    if matches and not bounded:
        ranked = rerank_widened(
            args.query,
            ranked,
            reviewed_series=lambda item: item,
            reviewed=lambda item: item.record.series_id in mapped,
        )
    else:
        ranked = rerank_by_reviewed_intent(args.query, ranked, reviewed_series=lambda item: item)
    if not matches:
        ranked = named_calendar_first(args.query, ranked, reviewed_series=lambda item: item)
    ranked = one_per_listed_row(ranked, reviewed_series=lambda item: item, query=args.query)
    folded = fold_bands(ranked, reviewed_series=lambda item: item)
    ranked = [item for item, _ in folded]
    bands_of = {
        item.record.series_id: tuple(
            band_choice(found[1], band.record)
            for band in bands
            if (found := _band(band)) is not None
        )
        for item, bands in folded
    }
    unresolved = any(c.unresolved for c in matches)
    status: SearchStatus
    if ranked or found_groups:
        # Token overlap can surface useful candidates, but only a reviewed
        # alias/phrase establishes that the requested concept is represented.
        status = "PARTIAL" if unresolved or not matches else "MATCH"
    elif matches and not mapped:
        status = "UNRESOLVED"
    elif matches and mapped:
        status = "FILTERED_OUT"
    else:
        status = "NO_MATCH"
    candidates = tuple(
        CatalogCandidate(
            series=s,
            concept_ids=tuple(sorted(c.concept_id for c in concepts_by_id[s.record.series_id])),
            family_ids=tuple(
                sorted({f for c in concepts_by_id[s.record.series_id] for f in c.family_ids})
            ),
            rank=i + 1,
            bm25_score=scores[s.record.series_id],
            matched_terms=tuple(sorted(query_terms & documents[s.record.series_id].keys())),
            # A neighbour the words reached is said to be one, beside the reviewed members.
            method=method if not matches or s.record.series_id in mapped else "bm25",
            bands=bands_of.get(s.record.series_id, ()),
        )
        for i, s in enumerate(ranked[: args.max_results])
    )
    return CatalogSearchOutput(
        status=status,
        candidates=candidates,
        groups=tuple(
            CatalogCandidate(
                series=s,
                concept_ids=(),
                family_ids=(),
                rank=i + 1,
                bm25_score=scores[s.record.series_id],
                matched_terms=tuple(sorted(query_terms & documents[s.record.series_id].keys())),
                method=method,
            )
            for i, s in enumerate(found_groups)
        ),
        top_candidate=top_candidate_signal(
            args.query,
            candidates,
            reviewed_match=bool(matches),
            available_kinds=frozenset(s.record.stock_flow for s in ranked),
            runner_up=ranked[1] if len(ranked) > 1 else None,
        ),
        concepts=tuple(
            ConceptMatch(
                concept_id=c.concept_id,
                family_ids=tuple(sorted(c.family_ids)),
                resolution=c.resolution,
                unresolved=c.unresolved,
                conditions=c.conditions,
            )
            for c in sorted(matches, key=lambda c: c.concept_id)
        ),
        total_candidates=len(ranked),
        truncated=len(ranked) > args.max_results,
        # Even one title match is only a candidate, never a verified selection.
        clarification_required=bool(ranked or matches),
        excluded_archived_count=excluded,
        snapshot_version=snapshot.snapshot_version,
        snapshot_sha256=snapshot.content_sha256,
    )
