"""A found source datagroup is opened into its series before the planner sees it (DEC-177).

A datagroup is a catalogue entry so that search can find it by meaning ("dolar kuru" ->
"Döviz Kurları"), but it is not something a plan can read: a plan names series. Search
therefore carries datagroups apart from its candidates, and this module replaces them by the
series the source lists under each, ranked against the same query. The planner chooses among
real identities only. All of this is code; the model never names a datagroup or a code that a
search did not return.

The merged list takes turns: the search's own candidates are one lane and every opened
datagroup is another, so neither a long series list nor a long datagroup can crowd the other
out of the ten places a result has.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import log
from typing import Final

from kkb_agent.catalog.discovered import DiscoveredStore, listed_entry
from kkb_agent.catalog.mappings import SOURCE_GROUP_INFIX
from kkb_agent.catalog.normalization import normalize_search_text
from kkb_agent.catalog.ranking import rerank_by_reviewed_intent
from kkb_agent.catalog.search import CatalogCandidate, CatalogSearchOutput
from kkb_agent.ingest.evds_series import ReviewedEvdsSeries

#: The series one opened datagroup may contribute, and the places a result has.
MAX_SERIES_PER_GROUP: Final = 5
MAX_CANDIDATES: Final = 10
_SHARED_PREFIX: Final = 4


def _same_word(left: str, right: str) -> bool:
    """Equal, or sharing a stem of four letters: "dolar"/"dolari", "kredi"/"kredileri"."""
    if left == right:
        return True
    shared = 0
    for a, b in zip(left, right, strict=False):
        if a != b:
            break
        shared += 1
    return shared >= _SHARED_PREFIX


def rank_series(
    query: str, series: Sequence[ReviewedEvdsSeries]
) -> list[tuple[float, ReviewedEvdsSeries]]:
    """Listed order, moved up by the query words a series' own names carry (rarer counts more)."""
    wanted = normalize_search_text(query).split()
    texts = [normalize_search_text(f"{item.title} {item.title_eng}").split() for item in series]
    total = len(series)
    scored: list[tuple[float, int, ReviewedEvdsSeries]] = []
    for position, (item, words) in enumerate(zip(series, texts, strict=True)):
        score = 0.0
        for word in wanted:
            if any(_same_word(word, other) for other in words):
                holders = sum(any(_same_word(word, other) for other in text) for text in texts)
                score += log(1 + (total - holders + 0.5) / (holders + 0.5))
        scored.append((score, position, item))
    scored.sort(key=lambda entry: (-entry[0], entry[1]))
    return [(score, item) for score, _, item in scored]


def _opened(
    query: str, group: CatalogCandidate, store: DiscoveredStore, shown: set[str]
) -> list[CatalogCandidate]:
    code = group.series.record.series_id.split(SOURCE_GROUP_INFIX, 1)[1]
    ranked = rank_series(query, store.series_of(code))
    scores = {item.code: score for score, item in ranked}
    # The source's own order and the query's words first; what the question says about
    # kind, currency or basis then decides among them, exactly as for any candidate.
    ordered = rerank_by_reviewed_intent(
        query, [item for _, item in ranked], reviewed_series=listed_entry
    )
    lane: list[CatalogCandidate] = []
    for item in ordered:
        if len(lane) == MAX_SERIES_PER_GROUP:
            break
        if item.series_id in shown:
            continue
        shown.add(item.series_id)
        lane.append(
            group.model_copy(
                update={
                    "series": listed_entry(item),
                    "bm25_score": round(scores[item.code], 12),
                    "matched_terms": (),
                }
            )
        )
    return lane


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
    lanes = [list(output.candidates)]
    lanes.extend(_opened(query, group, store, shown) for group in output.groups)
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
    opened = sum(len(lane) for lane in lanes[1:])
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
            "total_candidates": output.total_candidates + opened,
            "truncated": output.truncated or len(merged) < len(output.candidates) + opened,
            "clarification_required": output.clarification_required or opened > 0,
            "top_candidate": signal,
        }
    )
