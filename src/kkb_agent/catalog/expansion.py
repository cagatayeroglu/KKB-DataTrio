"""Found source datagroups are opened into their series before the planner sees them (DEC-177).

A datagroup is a catalogue entry so that search can find it by meaning ("dolar kuru" ->
"Döviz Kurları"), but it is not something a plan can read: a plan names series. Search
therefore carries datagroups apart from its candidates, and this module replaces them by
series the source lists under them. The planner chooses among real identities only. All of
this is code; the model never names a datagroup or a code that a search did not return.

Meaning finds the right datagroup among the nearest ten, not reliably first (measured on the
live index, 2026-09-19: "ABD doları TL kuru" puts "Döviz Kurları" fourth, behind datagroups
whose *unit* is the dollar). So every found datagroup is opened and their series are ranked
in one pool by the words of the question: what a series is called decides, the datagroup's
rank only breaks ties. The pool and the search's own candidates then take turns within the
ten places a result has, so neither can crowd the other out.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from math import log
from typing import Final

from kkb_agent.catalog.discovered import DiscoveredStore, listed_entry
from kkb_agent.catalog.mappings import SOURCE_GROUP_INFIX
from kkb_agent.catalog.normalization import normalize_search_text
from kkb_agent.catalog.ranking import intent_key
from kkb_agent.catalog.records import MAX_CATALOG_SERIES
from kkb_agent.catalog.search import CatalogCandidate, CatalogSearchOutput
from kkb_agent.ingest.evds_series import ReviewedEvdsSeries

#: The places a result has, and the pooled series that are declared and ordered for them.
MAX_CANDIDATES: Final = 10
MAX_POOL: Final = 200
#: How a national series names itself in a source title, normalized.
NATIONAL_NAMES: Final = ("turkiye", "turkey", "tcmb")
_SHORTEST_STEM: Final = 3
#: What may follow a stem in a title word, after search normalisation folded ı/ü/ş to i/u/s:
#: plural, possessive and case endings ("kur|lar|i", "kredi|si", "banka|lar|i|nin"). Anything
#: else is another word: "kuru|luslar" (institutions), "euro|bondlari", "issiz|lik".
_SUFFIXES: Final = re.compile(r"(?:l[ae]r|[sny]?[iu]n?|[dt][ae]n?|[ny][ae]|l[iu]|ki)*")


def _same_word(left: str, right: str) -> bool:
    """Equal, or one Turkish stem under different endings: "kuru"/"kurlari", "faiz"/"faizi"."""
    if left == right:
        return True
    shared = 0
    for a, b in zip(left, right, strict=False):
        if a != b:
            break
        shared += 1
    # The stem may itself end where the endings begin ("kur|u" and "kur|lari"), so every
    # split point from the shared beginning back to the shortest stem is tried.
    return any(
        _SUFFIXES.fullmatch(left[stem:]) and _SUFFIXES.fullmatch(right[stem:])
        for stem in range(shared, _SHORTEST_STEM - 1, -1)
    )


def _contains_national(title: str) -> bool:
    words = normalize_search_text(title).split()
    return any(word.startswith(name) for word in words for name in NATIONAL_NAMES)


def rank_series(
    query: str, series: Sequence[ReviewedEvdsSeries]
) -> list[tuple[float, ReviewedEvdsSeries]]:
    """Given order, moved up by the query words a series' names carry (rarer counts more).

    A series is read as EVDS shows it, under its datagroup: "Döviz Kurları > (USD) ABD Doları
    (Döviz Alış)". The series title alone never says "kur", the datagroup title does.
    """
    wanted = normalize_search_text(query).split()
    texts = [
        normalize_search_text(f"{item.datagroup_title} {item.title} {item.title_eng}").split()
        for item in series
    ]
    total = len(series)
    holders = {
        word: sum(any(_same_word(word, other) for other in text) for text in texts)
        for word in set(wanted)
    }
    scored: list[tuple[float, int, ReviewedEvdsSeries]] = []
    for position, (item, words) in enumerate(zip(series, texts, strict=True)):
        score = 0.0
        for word in wanted:
            if any(_same_word(word, other) for other in words):
                score += log(1 + (total - holders[word] + 0.5) / (holders[word] + 0.5))
        scored.append((score, position, item))
    scored.sort(key=lambda entry: (-entry[0], entry[1]))
    return [(score, item) for score, _, item in scored]


def _pool(
    query: str, groups: Sequence[CatalogCandidate], store: DiscoveredStore, shown: set[str]
) -> list[CatalogCandidate]:
    """The series of every found datagroup, best first for this question."""
    listed: list[ReviewedEvdsSeries] = []
    origin: dict[str, CatalogCandidate] = {}
    for group in groups:
        code = group.series.record.series_id.split(SOURCE_GROUP_INFIX, 1)[1]
        for item in store.series_of(code):
            if item.series_id not in shown and item.series_id not in origin:
                origin[item.series_id] = group
                listed.append(item)
    # Datagroups come in the order meaning ranked them and series in the source's own
    # order, so an equal score keeps the nearer datagroup and the source's first series.
    ranked = rank_series(query, listed)
    # Ten datagroups can list thousands of series; only the ones the question's words reach
    # (or, when they reach none, the head of the nearest datagroups) are worth declaring.
    reached = [entry for entry in ranked if entry[0] > 0]
    head = (reached or ranked)[:MAX_POOL]
    entries = {item.series_id: listed_entry(item) for _, item in head}
    position = {item.series_id: index for index, (_, item) in enumerate(head)}

    def order(entry: tuple[float, ReviewedEvdsSeries]) -> tuple[object, ...]:
        score, item = entry
        archive, conflicts, *rest = intent_key(query, entries[item.series_id])
        # A series that contradicts what the question names (another currency, a stock
        # where a flow was asked) goes below every one that does not; the words of the
        # question decide among the rest, and the reviewed-intent key breaks their ties.
        # Among equals the national series is the default, as for any candidate: a question
        # that names no country means Türkiye (one that names one scores its name above).
        abroad = not _contains_national(entries[item.series_id].record.title)
        return (archive, conflicts, -score, abroad, *rest, position[item.series_id])

    # Best first, but no datagroup twice before every datagroup had its turn: the planner
    # then sees the best series of several datagroups (the policy rate itself beside the
    # survey of expectations about it), not five neighbours of one table.
    by_group: dict[str, list[tuple[float, ReviewedEvdsSeries]]] = {}
    for entry in sorted(head, key=order):
        by_group.setdefault(entry[1].datagroup, []).append(entry)
    chosen: list[tuple[float, ReviewedEvdsSeries]] = []
    turn = 0
    while len(chosen) < MAX_CANDIDATES and any(turn < len(lane) for lane in by_group.values()):
        chosen.extend(lane[turn] for lane in by_group.values() if turn < len(lane))
        turn += 1
    return [
        origin[item.series_id].model_copy(
            update={
                "series": entries[item.series_id],
                "bm25_score": round(score, 12),
                "matched_terms": (),
            }
        )
        for score, item in chosen[:MAX_CANDIDATES]
    ]


def expand_groups(
    query: str, output: CatalogSearchOutput, store: DiscoveredStore | None
) -> CatalogSearchOutput:
    """`output` with its datagroups replaced by their series, and none left behind.

    Without a store (official fetching is off) datagroups are only removed: an entry nobody
    can read is never shown to the planner.
    """
    if not output.groups:
        return output
    if store is None:
        return output.model_copy(update={"groups": ()})
    shown = {item.series.record.series_id for item in output.candidates}
    lanes = [list(output.candidates), _pool(query, output.groups, store, shown)]
    merged: list[CatalogCandidate] = []
    turn = 0
    while len(merged) < MAX_CANDIDATES and any(turn < len(lane) for lane in lanes):
        for lane in lanes:
            if turn < len(lane) and len(merged) < MAX_CANDIDATES:
                merged.append(lane[turn])
        turn += 1
    candidates = tuple(
        item.model_copy(update={"rank": rank}) for rank, item in enumerate(merged, start=1)
    )
    opened = len(lanes[1])
    # A reviewed match keeps its signal; opened series are neighbours, never a default.
    signal = (
        output.top_candidate
        if output.top_candidate in ("unambiguous", "ambiguous")
        else ("unconfirmed" if candidates else "none")
    )
    return output.model_copy(
        update={
            "candidates": candidates,
            "groups": (),
            "total_candidates": min(output.total_candidates + opened, MAX_CATALOG_SERIES),
            "truncated": output.truncated or len(merged) < len(output.candidates) + opened,
            "clarification_required": output.clarification_required or opened > 0,
            "top_candidate": signal,
        }
    )
