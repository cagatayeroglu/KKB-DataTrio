"""The knowledge base counts past the catalogue's size (live 2026-09-23).

Entries a search had opened in the EVDS directory took the knowledge base past
10,000 entries; the page's counts failed their own bound, every page answered 500,
and the knowledge page showed "Analiz tamamlanamadı" under an endless spinner.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kkb_agent.api.contracts import KnowledgeList
from kkb_agent.catalog.records import MAX_CATALOG_SERIES

DIGEST = "0" * 64


def test_a_page_of_a_knowledge_base_larger_than_the_catalogue_bound_is_valid():
    many = MAX_CATALOG_SERIES + 2_345
    page = KnowledgeList(
        catalog_digest=DIGEST,
        reviewed_digest=DIGEST,
        listed_series=many,
        total=many,
        page=1,
        page_size=50,
        counts={"all": many, "listed": many - 10, "reviewed": 10},
    )
    assert page.total == many and page.counts["all"] == many


def test_a_count_is_still_bounded():
    with pytest.raises(ValidationError):
        KnowledgeList(catalog_digest=DIGEST, reviewed_digest=DIGEST, total=-1)
