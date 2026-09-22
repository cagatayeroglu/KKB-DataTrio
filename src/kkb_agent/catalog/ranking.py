"""Deterministic reviewed-metadata intent ordering for catalog candidates.

This is a stable post-order policy: it never creates/removes candidates or
changes similarity scores and it does not turn proximity into a reviewed match.
Explicit query qualifiers with a typed/reviewed counterpart decide compatibility.
Complete required read declarations break remaining ties without resolving intent.
Unknown candidate semantics are never inferred.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from kkb_agent.catalog.inspection import unresolved_read_fields
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


RATE = _phrases(
    "faiz",
    "faizi",
    "faizini",
    "faizleri",
    "faizlerini",
    "faiz oranı",
    "faiz oranını",
    "faiz oranları",
    "faiz oranlarını",
    "interest",
    "interest rate",
    "kâr payı",
    "kâr payını",
    "profit share",
    "rate",
)
STOCK = _phrases(
    "bakiye",
    "bakiyesi",
    "bakiyesini",
    "bakiyeleri",
    "bakiyelerini",
    "stok",
    "stoku",
    "stokunu",
    "hacim",
    "hacmi",
    "hacmini",
    "balance",
    "outstanding balance",
)
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
#: The one country this catalog covers; a national series is the default when
#: the question names no place, and a regional variant the person did not ask
#: for is demoted below it. Reviewed geography, not a hand-kept list of cities.
NATIONAL = _phrases("türkiye", "turkey", "türkiye geneli", "ulusal", "nationwide")
#: A query that asks for regional/provincial series generically, without naming
#: one place: then a regional variant is wanted and the national series is not.
REGIONAL = _phrases(
    "bölgesel",
    "bölge bazında",
    "il bazında",
    "iller",
    "şehir bazında",
    "regional",
    "provincial",
    "by province",
    "by city",
)
INTEREST = _phrases("faiz", "faizi", "faizini", "faizleri", "interest")
PROFIT_SHARE = _phrases("kâr payı", "kar payi", "profit share", "profit-share")
AMOUNT = _phrases("miktar", "miktarı", "miktarını", "tutar", "tutarı", "tutarını", "amount")
# A credit subject is not a stock/flow/rate decision. This only separates reviewed
# credit titles from unrelated records with a shared common noun (e.g. "ev").
_CREDIT_STEMS = ("kredi", "finansman", "loan", "mortgage")

CURRENCY: tuple[tuple[Currency, tuple[str, ...]], ...] = (
    ("total", _phrases("toplam", "tp ve yp", "total")),
    ("eur", _phrases("avro", "euro", "eur")),
    ("usd", _phrases("abd doları", "dolar cinsi", "usd")),
    ("foreign", _phrases("yabancı para", "döviz cinsi", "yp")),
    (
        "try",
        _phrases(
            "türk lirası",
            "türk parası",
            "turkish lira",
            "tl cinsi",
            "try denominated",
            "try-denominated",
            "tp",
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


def _contains_nominal_qualifier(text: str, phrases: tuple[str, ...]) -> bool:
    """Recognize locative noun qualifiers, without arbitrary prefix stemming.

    Turkish uses -da/-de/-ta/-te, optionally followed by -ki, to qualify the
    measure. Only the last word inflects; longer unrelated words must not match.
    This refines query intent, not catalog identity or declared semantics.
    """
    return _contains(text, phrases) or any(
        re.search(r"(?<!\S)" + re.escape(phrase) + r"[dt][ae](?:ki)?(?!\S)", text)
        for phrase in phrases
        if len(phrase.split()[-1]) >= 4
    )


def _currency(text: str) -> Currency | None:
    return next((value for value, phrases in CURRENCY if _contains(text, phrases)), None)


def _credit_subject(text: str) -> bool:
    return any(word.startswith(_CREDIT_STEMS) for word in text.split())


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
    #: The normalized query, so a candidate's reviewed geography can be checked
    #: against the exact words the person used.
    text: str
    #: The query asked for regional series generically (no single place named).
    regional: bool
    credit_subject: bool
    #: Amount does not imply stock: a new disbursement amount is a flow.
    credit_amount: bool


def _query_intent(query: str) -> _QueryIntent:
    text = normalize_search_text(query)
    credit_subject = _credit_subject(text)
    kind = (
        StockFlow.RATE
        if _contains(text, RATE)
        else StockFlow.STOCK
        if _contains(text, STOCK)
        or (credit_subject and _contains(text, _phrases("mevcut")) and not _contains(text, NEW))
        else None
    )
    rate_basis: RateBasis | None = None
    if kind is StockFlow.RATE:
        if _contains_nominal_qualifier(text, OUTSTANDING):
            rate_basis = "outstanding_portfolio"
        elif _contains_nominal_qualifier(text, NEW):
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
        text=text,
        regional=_contains(text, REGIONAL),
        credit_subject=credit_subject,
        credit_amount=kind is not StockFlow.RATE and credit_subject and _contains(text, AMOUNT),
    )


@dataclass(frozen=True, slots=True)
class _CandidateIntent:
    kind: StockFlow | None
    rate_basis: RateBasis | None
    inclusion: Inclusion | None
    currency: Currency | None
    rate_measure: RateMeasure | None
    #: A reviewed TP/YP/TOTAL label: the series is one column of a split aggregate.
    #: A denomination in a title ("(TL, Akım, %)") is not a component.
    component: Literal["total", "tp", "yp"] | None
    credit_subject: bool


def _candidate_intent(item: ReviewedSeries) -> _CandidateIntent:
    record = item.record
    text = normalize_search_text(" ".join([record.title, record.description or "", *record.labels]))
    exact_labels = {normalize_search_text(label) for label in record.labels}
    currency: Currency | None
    component: Literal["total", "tp", "yp"] | None = None
    if "total" in exact_labels:
        currency = "total"
        component = "total"
    elif "yp" in exact_labels:
        currency = "foreign"
        component = "yp"
    elif "tp" in exact_labels:
        currency = "try"
        component = "tp"
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
    # A reviewed explanatory contrast after "; not ..." is not an affirmative
    # measure. The title/labels and the positive description still determine it.
    affirmative_description = re.split(
        r";\s*not\b", record.description or "", maxsplit=1, flags=re.I
    )[0]
    affirmative = normalize_search_text(
        " ".join([record.title, *record.labels, affirmative_description])
    )
    if _contains(affirmative, PROFIT_SHARE):
        rate_measure = "profit_share"
    elif _contains(affirmative, INTEREST):
        rate_measure = "interest"
    return _CandidateIntent(
        kind=record.stock_flow if record.stock_flow is not StockFlow.UNKNOWN else None,
        rate_basis=item.rate_basis if item.rate_basis != "unknown" else None,
        inclusion=inclusion,
        currency=currency,
        rate_measure=rate_measure,
        component=component,
        credit_subject=_credit_subject(
            normalize_search_text(" ".join([record.title, *record.labels]))
        ),
    )


def _geography_rank(intent: _QueryIntent, item: ReviewedSeries) -> int:
    """Where a reviewed geography sits when the question does or does not name it.

    A named geography is always preferred (0). When the query asks for regional
    series generically ("bölgesel"), a regional variant is wanted (0) and the
    national series is demoted (2). Otherwise a series with no declared geography
    or a national series the person did not name is the neutral default (1) - so
    a national series is never ranked below an ordinary placeless one - and a
    regional series the person did not ask for is demoted below both (2).
    """
    if item.geography is None:
        return 1
    place = normalize_search_text(item.geography)
    if place and place in intent.text:
        return 0
    national = _contains(place, NATIONAL)
    if intent.regional:
        return 2 if national else 0
    return 1 if national else 2


def _component_rank(intent: _QueryIntent, candidate: _CandidateIntent) -> int:
    """An unrequested TP/YP column sits below its aggregate.

    When the question names no currency, the total (or a series that is not a
    column of a split aggregate) is the default (0) and a reviewed TP/YP column
    the person did not ask for is demoted (1) - the same rule geography
    follows. A named currency is handled by the match/conflict count instead;
    a denomination in a title never makes a series a component.
    """
    if intent.currency is None and candidate.component in ("tp", "yp"):
        return 1
    return 0


def _semantic_key(
    intent: _QueryIntent, item: ReviewedSeries
) -> tuple[int, int, int, int, int, int, int, int, int]:
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
    # A credit amount cannot be the numeric percentage of a credit rate. This
    # demotes rate neighbours, without claiming that a stock is the requested
    # flow amount or changing the reviewed resolution/selection authority.
    if intent.credit_amount and candidate.kind is StockFlow.RATE:
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
    # Last tiebreak: when no base is named, an index on a newer base is the
    # default over the same concept's older base (the statistics office moves the
    # series to the new base and stops the old one). Series without a base year
    # sit at 0 and are never demoted by it.
    base_recency = -(item.record.base_year or 0)
    return (
        archive_rank,
        conflicts,
        int(intent.credit_subject and not candidate.credit_subject),
        _geography_rank(intent, item),
        _component_rank(intent, candidate),
        base_missing,
        base_rank,
        -matches,
        base_recency,
    )


def intent_key(query: str, item: ReviewedSeries) -> tuple[int, ...]:
    """The reviewed-intent order key of one candidate for one query.

    Exposed so search can say whether the first candidate is the unambiguous
    default for the request: it is when its key is strictly better than the
    second candidate's. Ties mean the candidates differ on an axis the request
    did not name, which only the person can settle.
    """
    return _semantic_key(_query_intent(query), item)


def named_measure_kind(query: str) -> StockFlow | None:
    """Only an explicit stock/rate request resolves that axis; amount alone does not."""
    return _query_intent(query).kind


def rerank_by_reviewed_intent[T](
    query: str, items: list[T], *, reviewed_series: Callable[[T], ReviewedSeries]
) -> list[T]:
    """Stable ordering by explicit query/candidate metadata compatibility."""
    intent = _query_intent(query)
    return sorted(
        items,
        key=lambda item: (
            _semantic_key(intent, reviewed_series(item)),
            # Only break semantic ties. An explicit portfolio/flow/currency request
            # still wins over completeness; missing declarations are never filled in.
            # Keep this outside intent_key: readiness cannot resolve semantic ambiguity.
            bool(unresolved_read_fields(reviewed_series(item).record)),
        ),
    )
