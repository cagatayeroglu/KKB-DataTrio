"""Reviewed metric meaning for Borsa Istanbul index-close JSON endpoints only.

The field name ``clval`` alone proves nothing. This mapping requires the official
HTTPS origin, its named index page, the page-declared endpoint shape and matching
index identities in every fetched record. Other documents remain unresolved.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

from kkb_agent.core import Scale, StockFlow
from kkb_agent.ingest.json_table import RecordTable

_HOSTS = frozenset({"borsaistanbul.com", "www.borsaistanbul.com"})
_PAGE_CODES = {"/endeks/xtumy": "XTUMY", "/endeks/xu100": "XU100"}
#: What the reviewed index is called on its own page, for a readable column.
_PAGE_TITLES = {"XTUMY": "BIST TÜM kapanış (XTUMY)", "XU100": "BIST 100 kapanış (XU100)"}


@dataclass(frozen=True, slots=True)
class ReviewedMetric:
    unit: str
    scale: Scale
    measure: StockFlow
    source: str
    #: How the column is named for a reader; the raw field name proves nothing.
    title: str | None = None


def bist_index_close_metrics(
    page_url: str, endpoint_url: str, records: RecordTable
) -> dict[str, ReviewedMetric]:
    """Return a typed ``clval`` only for the two reviewed index-close paths."""
    page, endpoint = urlsplit(page_url), urlsplit(endpoint_url)
    code = _PAGE_CODES.get(page.path.rstrip("/").lower())
    if (
        code is None
        or page.scheme != "https"
        or page.netloc not in _HOSTS
        or page.query
        or page.fragment
        or endpoint.scheme != "https"
        or endpoint.netloc != page.netloc
        or endpoint.path != "/graphic.php"
        or endpoint.fragment
    ):
        return {}
    query = parse_qs(endpoint.query, keep_blank_values=True)
    if query != {"veriTuru": ["endeks-graphic"], "indexCode": [code]}:
        return {}
    if not {"indexName", "clval", "hisTs"} <= set(records.headers):
        return {}
    identity = records.headers.index("indexName")
    if not records.rows or any(row[identity] != code for row in records.rows):
        return {}
    return {
        "clval": ReviewedMetric(
            unit="index_points",
            scale=Scale.ONE,
            measure=StockFlow.INDEX,
            source=f"reviewed Borsa Istanbul {code} index-close mapping",
            title=_PAGE_TITLES[code],
        )
    }
