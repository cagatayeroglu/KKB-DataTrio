"""Deterministic reviewed-metadata intent ordering for catalog candidates.

This is a stable post-order policy: it never creates/removes candidates or
changes similarity scores and it does not turn proximity into a reviewed match.
Only explicit query qualifiers with a typed/reviewed counterpart can move an
item. Unknown candidate semantics remain neutral rather than inferred.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from kkb_agent.catalog.mappings import ReviewedSeries
from kkb_agent.catalog.normalization import normalize_search_text
from kkb_agent.catalog.records import CatalogStatus
from kkb_agent.core import StockFlow

Currency = Literal["try", "foreign", "eur", "usd", "total"]
Inclusion = Literal["included", "excluded"]
RateBasis = Literal["new_credit", "outstanding_portfolio"]
RateMeasure = Literal["interest", "profit_share"]
ArchiveIntent = Literal["archived", "current"]


def _phrases(*values: str) -> tuple[str, ...]:
    return tuple(normalize_search_text(value) for value in values)


RATE = _phrases("faiz", "faizi", "interest", "interest rate", "kâr payı", "profit share", "rate")
STOCK = _phrases("bakiye", "stok", "hacim", "balance", "outstanding balance")
OUTSTANDING = _phrases("stok", "mevcut", "portföy", "outstanding", "existing")
NEW = _phrases("akım", "yeni", "newly issued", "new loan", "flow")
EXCLUDED = _phrases("hariç", "kapsam dışı", "excluding", "excluded", "without")
INCLUDED = _phrases("dahil", "kapsayan", "including", "included", "with overdraft")
ARCHIVED = _phrases(
    "arşiv", "arşivde", "güncellenmeyen", "artık güncellenmeyen", "discontinued", "archived"
)
CURRENT = _phrases("güncel", "aktif", "current", "currently updated")
OLD_BASE = _phrases("eski baz", "eski temel", "old base", "önceki baz")
NEW_BASE = _phrases("güncel baz", "yeni baz", "latest base", "current base")
BASE_MARKER = _phrases("baz", "bazlı", "temel yıl", "temel yıllı", "base", "base year")
INTEREST = _phrases("faiz", "interest")
PROFIT_SHARE = _phrases("kâr payı", "kar payi", "profit share", "profit-share")

CURRENCY: tuple[tuple[Currency, tuple[str, ...]], ...] = (
    ("total", _phrases("toplam", "tp ve yp", "total")),
    ("eur", _phrases("avro", "euro", "eur")),
    ("usd", _phrases("abd doları", "dolar cinsi", "usd")),
    ("foreign", _phrases("yabancı para", "döviz cinsi", "yp")),
    (
        "try",
        _phrases(
            "türk lirası", "türk parası", "tl cinsi", "try denominated", "try-denominated", "tp"
        ),
    ),
)
CANDIDATE_CURRENCY: tuple[tuple[Currency, tuple[str, ...]], ...] = (
    ("total", _phrases("total", "toplam")),
    ("eur", _phrases("avro", "euro", "eur")),
    ("usd", _phrases("abd doları", "usd")),
    ("foreign", _phrases("yabancı para", "yp")),
    ("try", _phrases("türk lirası", "türk parası", "tl", "try")),
)


def _contains(text: str, phrases: tuple[str, ...]) -> bool:
    padded = f" {text} "
    return any(f" {phrase} " in padded for phrase in phrases)


def _currency(text: str) -> Currency | None:
    return next((value for value, phrases in CURRENCY if _contains(text, phrases)), None)


@dataclass(frozen=True, slots=True)
class _QueryIntent:
    kind: StockFlow | None
    rate_basis: RateBasis | None
    inclusion: Inclusion | None
    currency: Currency | None
    rate_measure: RateMeasure | None
    archive: ArchiveIntent | None
    base_year: int | None
    base_order: Literal["oldest", "newest"] | None


def _query_intent(query: str) -> _QueryIntent:
    text = normalize_search_text(query)
    kind = (
        StockFlow.RATE
        if _contains(text, RATE)
        else StockFlow.STOCK
        if _contains(text, STOCK)
        else None
    )
    rate_basis: RateBasis | None = None
    if kind is StockFlow.RATE:
        if _contains(text, OUTSTANDING):
            rate_basis = "outstanding_portfolio"
        elif _contains(text, NEW):
            rate_basis = "new_credit"
    inclusion: Inclusion | None = None
    if _contains(text, EXCLUDED):
        inclusion = "excluded"
    elif _contains(text, INCLUDED):
        inclusion = "included"
    rate_measure: RateMeasure | None = None
    if _contains(text, PROFIT_SHARE):
        rate_measure = "profit_share"
    elif _contains(text, INTEREST):
        rate_measure = "interest"
    archive: ArchiveIntent | None = None
    if _contains(text, ARCHIVED):
        archive = "archived"
    elif _contains(text, CURRENT):
        archive = "current"
    years = (
        [int(value) for value in re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", text)]
        if _contains(text, BASE_MARKER)
        else []
    )
    base_order: Literal["oldest", "newest"] | None = None
    if _contains(text, OLD_BASE):
        base_order = "oldest"
    elif _contains(text, NEW_BASE):
        base_order = "newest"
    return _QueryIntent(
        kind=kind,
        rate_basis=rate_basis,
        inclusion=inclusion,
        currency=_currency(text),
        rate_measure=rate_measure,
        archive=archive,
        base_year=years[0] if len(years) == 1 else None,
        base_order=base_order,
    )


@dataclass(frozen=True, slots=True)
class _CandidateIntent:
    kind: StockFlow | None
    rate_basis: RateBasis | None
    inclusion: Inclusion | None
    currency: Currency | None
    rate_measure: RateMeasure | None


def _candidate_intent(item: ReviewedSeries) -> _CandidateIntent:
    record = item.record
    text = normalize_search_text(" ".join([record.title, record.description or "", *record.labels]))
    exact_labels = {normalize_search_text(label) for label in record.labels}
    currency: Currency | None
    if "total" in exact_labels:
        currency = "total"
    elif "yp" in exact_labels:
        currency = "foreign"
    elif "tp" in exact_labels:
        currency = "try"
    else:
        display_text = normalize_search_text(" ".join([record.title, *record.labels]))
        currency = next(
            (value for value, phrases in CANDIDATE_CURRENCY if _contains(display_text, phrases)),
            None,
        )
    inclusion: Inclusion | None = None
    if _contains(text, EXCLUDED):
        inclusion = "excluded"
    elif _contains(text, INCLUDED):
        inclusion = "included"
    rate_measure: RateMeasure | None = None
    # Profit-share wording wins because its reviewed notes may contrast it with
    # interest explicitly ("profit-share ... not deposit-bank interest").
    if _contains(text, PROFIT_SHARE):
        rate_measure = "profit_share"
    elif _contains(text, INTEREST):
        rate_measure = "interest"
    return _CandidateIntent(
        kind=record.stock_flow if record.stock_flow is not StockFlow.UNKNOWN else None,
        rate_basis=item.rate_basis if item.rate_basis != "unknown" else None,
        inclusion=inclusion,
        currency=currency,
        rate_measure=rate_measure,
    )


def _semantic_key(intent: _QueryIntent, item: ReviewedSeries) -> tuple[int, int, int, int, int]:
    candidate = _candidate_intent(item)
    conflicts = 0
    matches = 0
    for wanted, actual in (
        (intent.kind, candidate.kind),
        (intent.rate_basis, candidate.rate_basis),
        (intent.currency, candidate.currency),
        (intent.rate_measure, candidate.rate_measure),
    ):
        if wanted is not None and actual is not None:
            if wanted == actual:
                matches += 1
            else:
                conflicts += 1
    if intent.inclusion is not None and candidate.inclusion is not None:
        if intent.inclusion == candidate.inclusion:
            matches += 1
        else:
            conflicts += 1
    archive_rank = int(
        (intent.archive == "archived") != (item.record.status is CatalogStatus.ARCHIVED)
    )
    if intent.archive is None:
        archive_rank = int(item.record.status is CatalogStatus.ARCHIVED)
    base_missing = 0
    base_rank = 0
    if intent.base_year is not None and item.record.base_year is not None:
        base_rank = int(item.record.base_year != intent.base_year)
    elif intent.base_order == "oldest" and item.record.base_year is not None:
        base_rank = item.record.base_year
    elif intent.base_order == "newest" and item.record.base_year is not None:
        base_rank = -item.record.base_year
    elif intent.base_year is not None or intent.base_order is not None:
        base_missing = 1
    return archive_rank, conflicts, base_missing, base_rank, -matches


def rerank_by_reviewed_intent[T](
    query: str, items: list[T], *, reviewed_series: Callable[[T], ReviewedSeries]
) -> list[T]:
    """Stable ordering by explicit query/candidate metadata compatibility."""
    intent = _query_intent(query)
    return sorted(items, key=lambda item: _semantic_key(intent, reviewed_series(item)))
