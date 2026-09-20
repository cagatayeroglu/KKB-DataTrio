"""Frozen, offline Turkish paraphrase cases for candidate order and safe confidence.

These are adjudicated semantic expectations, not record-ID lookup answers. Once used
to change ranking, this becomes development evidence; a later independent holdout
is still needed for a general quality-gain claim. No model or embedding is called.
"""

from dataclasses import dataclass
from pathlib import Path

import pytest

from kkb_agent.catalog.hybrid import CatalogDenseStage, search_hybrid_catalog
from kkb_agent.catalog.lance_index import DenseHit
from kkb_agent.catalog.mappings import load_reviewed_snapshot
from kkb_agent.catalog.search import CatalogCandidate, CatalogSearchArguments, search_catalog
from kkb_agent.catalog.vectors import QueryVector, VectorProfile
from kkb_agent.core import StockFlow

CATALOG = Path(__file__).parents[2] / "docs/catalog/prepared_v3.json"


@dataclass(frozen=True)
class Case:
    query: str
    first_family: str | None
    auto_safe: bool
    forbidden_before: tuple[str, ...] = ()
    expected_concept: str | None = None
    base_year: int | None = None
    geography: str | None = None
    component: str | None = None
    rate_basis: str | None = None
    include_archived: bool = False
    clarification: bool = True


CASES = (
    Case("toplam konut kredisi", "housing_stock", False, ("housing_rate", "cpi_division")),
    Case("konut kredisi bakiyesi", "housing_stock", True, ("housing_rate",)),
    Case("ev kredisi stoku", "housing_stock", False, ("housing_rate", "cpi_division")),
    Case(
        "vatandaşın çektiği ev kredisi miktarı",
        "housing_stock",
        False,
        ("housing_rate", "cpi_division"),
    ),
    Case(
        "bankaların verdiği konut finansmanı",
        "housing_stock",
        False,
        ("housing_rate", "cpi_division"),
    ),
    Case("yeni konut kredileri", None, False),
    # This reviewed concept has no mapped disbursement-amount identity. A rate is not it.
    Case("yeni verilen konut kredisi tutarı", None, False, expected_concept="housing_disbursement"),
    Case("konut kredisi faiz oranı", "housing_rate", False, ("housing_stock",)),
    Case(
        "yeni konut kredisi faizi",
        "housing_rate",
        True,
        ("housing_stock",),
        rate_basis="new_credit",
    ),
    Case("ihtiyaç kredisi bakiyesi", None, False),
    Case("vatandaşların kullandığı ihtiyaç kredileri", None, False),
    Case("yeni ihtiyaç kredisi", None, False),
    Case("ihtiyaç kredisi faiz oranı", "personal_rate", False, ("housing_stock",)),
    Case("konut kredisi miktarı", "housing_stock", False, ("housing_rate",)),
    Case("ev kredisi", "housing_credit", False, ("cpi_division",)),
    Case("toplam mevcut konut kredisi", "housing_stock", True, ("housing_rate",)),
    Case("bu ay yeni verilen konut kredisi", None, False),
    Case("Türkiye konut fiyat endeksi", "housing_index", True, ("housing_stock",)),
    Case("İstanbul konut fiyat endeksi", "housing_index", True, geography="İstanbul"),
    Case("2025 bazlı TÜFE", "cpi_level", True, base_year=2025),
    Case("2003 bazlı TÜFE", "cpi_level", True, base_year=2003),
    Case("toplam konut kredisi bakiyesi", "housing_stock", True, component="total"),
    Case(
        "konut kredisi bakiyesi",
        "housing_stock",
        True,
        include_archived=True,
        forbidden_before=("archived",),
    ),
)


def family(candidate: CatalogCandidate) -> str:
    record = candidate.series.record
    groups = set(candidate.family_ids)
    if record.status.value == "archived":
        return "archived"
    if record.stock_flow is StockFlow.STOCK and "housing_amount" in groups:
        return "housing_stock"
    if record.stock_flow is StockFlow.RATE and "housing_rates" in groups:
        return "housing_rate"
    if record.stock_flow is StockFlow.RATE and any(
        concept == "personal_rate_scope" or concept.startswith("new_loan_tp_ktf10")
        for concept in candidate.concept_ids
    ):
        return "personal_rate"
    if record.stock_flow is StockFlow.INDEX and "housing_prices" in groups:
        return "housing_index"
    if record.stock_flow is StockFlow.INDEX and "consumer_prices" in groups:
        return "cpi_level"
    if "cpi_divisions" in groups:
        return "cpi_division"
    return "other"


def is_family(candidate: CatalogCandidate, expected: str) -> bool:
    found = family(candidate)
    return found == expected or (
        expected == "housing_credit" and found in {"housing_stock", "housing_rate"}
    )


@pytest.fixture(scope="module")
def snapshot():
    return load_reviewed_snapshot(CATALOG.read_bytes())


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.query)
def test_frozen_lexical_paraphrase_order_and_confidence(snapshot, case):
    output = search_catalog(
        snapshot,
        CatalogSearchArguments(query=case.query, include_archived=case.include_archived),
    )
    assert output.clarification_required is case.clarification
    if case.expected_concept is not None:
        assert output.status == "UNRESOLVED"
        assert not output.candidates
        assert case.expected_concept in {c.concept_id for c in output.concepts}
        assert output.top_candidate == "none"
        return
    if case.first_family is not None:
        assert output.candidates, case.query
        assert is_family(output.candidates[0], case.first_family)
        ranked = [family(candidate) for candidate in output.candidates]
        first = next(
            i
            for i, candidate in enumerate(output.candidates)
            if is_family(candidate, case.first_family)
        )
        assert all(
            forbidden not in ranked or first < ranked.index(forbidden)
            for forbidden in case.forbidden_before
        )
    if case.auto_safe:
        assert output.top_candidate == "unambiguous"
    else:
        assert output.top_candidate in ("ambiguous", "unconfirmed", "none")
    if case.base_year is not None:
        assert output.candidates[0].series.record.base_year == case.base_year
    if case.geography is not None:
        assert output.candidates[0].series.geography == case.geography
    if case.component is not None:
        assert case.component in {
            label.lower() for label in output.candidates[0].series.record.labels
        }
    if case.rate_basis is not None:
        assert output.candidates[0].series.rate_basis == case.rate_basis


class FixedDenseIndex:
    """Adversarial deterministic stage order, not a quality claim about real vectors."""

    def __init__(self, snapshot, profile):
        self.snapshot_sha256 = snapshot.content_sha256
        self.profile = profile
        self.by_id = {s.record.series_id: s for s in snapshot.series}

    def search(self, query, *, eligible_ids, limit):
        # CPI noun overlap leads the dense fixture; then rate, stock, others.
        # Its order has no query-specific answer and cannot grant MATCH.
        priority = {"cpi_division": 0, "housing_rate": 1, "housing_stock": 2}

        def key(series_id):
            item = self.by_id[series_id]
            if item.record.stock_flow is StockFlow.STOCK:
                group = "housing_stock"
            elif item.record.stock_flow is StockFlow.RATE:
                group = "housing_rate"
            elif "TUKFIY2025.05" in series_id:
                group = "cpi_division"
            else:
                group = "other"
            return priority.get(group, 3), series_id

        ranked = sorted(eligible_ids, key=key)[:limit]
        return [DenseHit(series_id, i, i / 100.0) for i, series_id in enumerate(ranked, 1)]


@pytest.mark.parametrize(
    ("query", "expected_family", "safe"),
    [
        ("ev kredisi stoku", "housing_stock", False),
        ("ev kredisi", "housing_stock", False),
        ("yeni konut kredisi faizi", "housing_rate", True),
    ],
)
def test_fixture_dense_order_never_becomes_selection_authority(
    snapshot, query, expected_family, safe
):
    profile = VectorProfile(
        model="kkbhackathon2026/Qwen3-Embedding-8B",
        dimension=4096,
        input_policy_id="paraphrase-offline-fixture-v1",
        origin="offline_fixture",
    )
    dense = CatalogDenseStage(
        FixedDenseIndex(snapshot, profile),
        lambda _: QueryVector(profile=profile, values=(1.0, *([0.0] * 4095))),
    )
    output = search_hybrid_catalog(snapshot, CatalogSearchArguments(query=query), dense)
    assert output.retrieval_mode == "hybrid" and output.dense_status == "success"
    assert family(output.candidates[0]) == expected_family
    assert output.clarification_required
    assert (output.top_candidate == "unambiguous") is safe
