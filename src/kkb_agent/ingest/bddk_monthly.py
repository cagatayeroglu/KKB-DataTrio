"""M3-05 offline selector identity and the monthly metadata a selector is accepted against.

No retrieval, observation parsing/storage or planner registration. A selector
fingerprint says which selection was described, not whether it is supported.
Two subsets may produce a CatalogRecord: the separately reviewed housing rows, and
(DEC-176) rows of the bulletin's own pinned listing whose caption unit is known and whose
measured year-boundary behaviour agrees with the rest of their table.
"""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal

from pydantic import AwareDatetime, ConfigDict, Field, StrictBool, StrictInt, StringConstraints

from kkb_agent.catalog.records import CatalogRecord, SourceGroup
from kkb_agent.core import CumulativeKind, Frequency, Scale, SourceRef, StockFlow
from kkb_agent.core.models import ContractModel
from kkb_agent.ingest.bddk_monthly_directory import DIRECTORY, DIRECTORY_SHA256

SelectorNumber = Annotated[StrictInt, Field(ge=1, le=99999)]
Geography = Annotated[
    str, StringConstraints(strict=True, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")
]
MetadataText = Annotated[str, StringConstraints(strict=True, max_length=256)]

# Existing reviewed inventory, not synthetic fixtures or an observation source.
INVENTORY_REVISION = "904e22dd9e70100e0a7b69b02aa08dffb5daa905"
INVENTORY_SHA256 = "a85c6a3c9acc5429e17734544d8a776b3eb39462ab62567771a726fc3f413df2"
HOUSING_LABEL = "Tüketici Kredileri - Konut"
COLUMN_HEADERS = ("", "", "", "BasitFont", "TP", "YP", "Toplam")
HOUSING_TABLE, HOUSING_ROW = 4, 2
SECTOR = 10001

# -- The bulletin's own listing (DEC-176) ---------------------------------------------------
#: Caption units this adapter can declare. Any other caption text leaves a table unsupported.
_CAPTION_UNITS = {"milyon TL": ("TRY", Scale.MILLION), "bin TL": ("TRY", Scale.THOUSAND)}
#: What a row's measured January behaviour says it publishes, when its table agrees.
_BEHAVIOUR = {
    "never": (StockFlow.STOCK, CumulativeKind.NONE),
    "always": (StockFlow.FLOW, CumulativeKind.YEARLY_RESET),
}


def _digest_of_listing() -> str:
    canonical = json.dumps(DIRECTORY, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


if _digest_of_listing() != DIRECTORY_SHA256:  # pragma: no cover - a hand-edited listing
    raise RuntimeError("BDDK monthly directory does not match its pinned digest")


def _table_behaviour(table: dict[str, object]) -> str | None:
    """The behaviour most measured rows of a table share: its family, read from evidence.

    The income statement resets every January and position tables never do; that is
    measured per row by the harvest, not declared here. A table without a clear majority
    (two thirds of its measured rows) has no family, and none of its rows is supported.
    """
    rows = table["rows"]
    assert isinstance(rows, dict)
    measured = [entry["resets"] for entry in rows.values() if entry["resets"] in _BEHAVIOUR]
    for behaviour in _BEHAVIOUR:
        if measured and measured.count(behaviour) * 3 >= len(rows) * 2:
            return behaviour
    return None


class DirectoryRow(ContractModel):
    """One supported row of the listing, with everything the adapter declares for it."""

    model_config = ConfigDict(frozen=True)

    table: SelectorNumber
    row: SelectorNumber
    table_title: MetadataText
    label: MetadataText
    unit_text: MetadataText
    unit: str
    scale: Scale
    stock_flow: StockFlow
    cumulative: CumulativeKind


def _supported_rows() -> dict[tuple[int, int], DirectoryRow]:
    found: dict[tuple[int, int], DirectoryRow] = {}
    for number, table in DIRECTORY["tables"].items():
        if tuple(table["headers"]) != COLUMN_HEADERS or table["unit_text"] not in _CAPTION_UNITS:
            continue  # another layout, or a unit this adapter cannot declare
        behaviour = _table_behaviour(table)
        if behaviour is None:
            continue
        unit, scale = _CAPTION_UNITS[table["unit_text"]]
        stock_flow, cumulative = _BEHAVIOUR[behaviour]
        for row, entry in table["rows"].items():
            if entry["resets"] != behaviour:
                continue  # unmeasured, mixed, or unlike its table: listed, never fetched
            found[int(number), int(row)] = DirectoryRow(
                table=int(number),
                row=int(row),
                table_title=table["title"],
                label=entry["label"],
                unit_text=table["unit_text"],
                unit=unit,
                scale=scale,
                stock_flow=stock_flow,
                cumulative=cumulative,
            )
    return found


#: (table, row) -> what is declared for it. Built once from the pinned listing.
SUPPORTED_ROWS: dict[tuple[int, int], DirectoryRow] = _supported_rows()


class BddkSelector(ContractModel):
    """Versioned selector syntax, NOT a source-native code or trusted metadata.

    All varying dimensions are explicit. Geography is null where inapplicable;
    other geography tokens and bulletin families can be fingerprinted but are
    not reviewed by this monthly slice. No period, title or clock participates.
    """

    model_config = ConfigDict(frozen=True)

    provider: Literal["BDDK"] = "BDDK"
    bulletin_family: Literal["monthly", "weekly", "finturk"]
    table: SelectorNumber
    row: SelectorNumber
    bank_group: SelectorNumber
    presentation_currency: Literal["TL", "USD"]
    value_dimension: Literal["TP", "YP", "TOTAL"]
    geography: Geography | None = None

    def canonical_selector(self) -> str:
        # Revalidate even objects produced by model_copy/model_construct.
        checked = BddkSelector.model_validate(self)
        payload = {"schema": "bddk-selector-v1", **checked.model_dump(mode="json")}
        return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

    def internal_id(self) -> str:
        digest = hashlib.sha256(self.canonical_selector().encode("utf-8")).hexdigest()
        return f"BDDK:selector:v1:{digest}"


class UnreviewedSelector(ValueError):
    """This fingerprint has no reviewed metadata in the bounded housing slice."""


def _is_housing(selector: BddkSelector) -> bool:
    return (selector.table, selector.row) == (HOUSING_TABLE, HOUSING_ROW)


def _reviewed(selector: BddkSelector) -> BddkSelector:
    """The sector aggregate in TL, for the reviewed housing row or a supported listed row."""
    selector = BddkSelector.model_validate(selector)
    if (
        selector.bulletin_family != "monthly"
        or selector.bank_group != SECTOR
        or selector.presentation_currency != "TL"
        or selector.geography is not None
        or not (_is_housing(selector) or (selector.table, selector.row) in SUPPORTED_ROWS)
    ):
        raise UnreviewedSelector("Selector is outside the supported monthly bulletin scope")
    return selector


def _housing(selector: BddkSelector) -> BddkSelector:
    """The separately reviewed housing rows only; a listed row has its own record."""
    selector = _reviewed(selector)
    if not _is_housing(selector):
        raise UnreviewedSelector("Selector is outside the reviewed monthly housing scope")
    return selector


_COMPONENTS: tuple[Literal["TP", "YP", "TOTAL"], ...] = ("TP", "YP", "TOTAL")


def supported_selectors() -> tuple[BddkSelector, ...]:
    """Every selector this adapter accepts: each supported row, in its three components."""
    rows = {(HOUSING_TABLE, HOUSING_ROW), *SUPPORTED_ROWS}
    return tuple(
        BddkSelector(
            bulletin_family="monthly",
            table=table,
            row=row,
            bank_group=SECTOR,
            presentation_currency="TL",
            value_dimension=component,
        )
        for table, row in sorted(rows)
        for component in _COMPONENTS
    )


def monthly_housing_catalog(selector: BddkSelector) -> CatalogRecord:
    """Map an explicit reviewed selector to candidate declarations, never values.

    source_series_id is a labelled canonical composite selector because BDDK
    publishes no source-native series code here. SourceRef cites the immutable
    inventory supporting these declarations, not a pretend retrieved payload.
    Active state, full coverage and aggregation permissions remain unknown.
    """
    selector = _housing(selector)
    return CatalogRecord(
        series_id=selector.internal_id(),
        provider="BDDK",
        source_series_id="selector-v1:" + selector.canonical_selector(),
        title=HOUSING_LABEL,
        source=SourceRef(
            source_id="bddk:monthly-housing-selector-v1",
            source_type="repository_inventory",
            locator=f"repo:{INVENTORY_REVISION}:docs/BDDK_SOURCE.md",
            content_hash=INVENTORY_SHA256,
        ),
        description=(
            "Reviewed monthly period-end outstanding stock; not disbursement. "
            "Internal composite selector, not an official BDDK series code. "
            "A candidate is not a natural-language selection or calculation permission."
        ),
        labels=("Aylık Bülten", "Sektör", selector.value_dimension, "Sunum para birimi: TL"),
        group=SourceGroup(group_id="4", group_title="Tüketici Kredileri", publisher="BDDK"),
        unit="TRY",
        scale=Scale.MILLION,
        frequency=Frequency.MONTHLY,
        stock_flow=StockFlow.STOCK,
        cumulative=CumulativeKind.NONE,
    )


_COMPONENT_WORDS = {
    "TP": "TP (Türk parası, TL cinsi)",
    "YP": "YP (yabancı para, döviz cinsi; TL karşılığı)",
    "TOTAL": "Toplam (TP + YP)",
}


def monthly_directory_catalog(selector: BddkSelector) -> CatalogRecord:
    """Declarations for a supported listed row: from the listing, never from a response.

    Title and table come from the bulletin's own labels, unit and scale from the caption,
    and the stock/flow and cumulative declaration from the row's measured year-boundary
    behaviour agreeing with its table's (DEC-176). Nothing here was reviewed row by row,
    and the description says so.
    """
    selector = _reviewed(selector)
    row = SUPPORTED_ROWS[selector.table, selector.row]
    # Turkish first: people ask in Turkish, and the words a kind is asked by ("bakiyesi",
    # "tutarı", "kümülatif") are what word search can match. They describe the kind, the
    # same for every row of it; nothing here is an alias kept for one series.
    behaviour = (
        "Yıl içi kümülatif dönem tutarı: her Ocak'ta sıfırlanır (incelenen her yıl sınırında "
        "ölçüldü); aylık tutar için kümülatiften akıma çevrilir. Year-to-date total that "
        "resets every January."
        if row.cumulative is CumulativeKind.YEARLY_RESET
        else "Ay sonu bakiye (stok): bakiyesi, tutarı, hacmi; kullandırım ya da akım değildir "
        "(incelenen yıl sınırlarında hiç sıfırlanmadı). Month-end outstanding position."
    )
    return CatalogRecord(
        series_id=selector.internal_id(),
        provider="BDDK",
        source_series_id="selector-v1:" + selector.canonical_selector(),
        title=row.label,
        source=SourceRef(
            source_id="bddk:monthly-directory-v1",
            source_type="repository_inventory",
            locator="repo:src/kkb_agent/ingest/bddk_monthly_directory.py",
            content_hash=DIRECTORY_SHA256,
        ),
        description=(
            f"BDDK Aylık Bülten, {row.table_title} tablosu, satır {row.row}: {row.label}. "
            f"Bileşen: {_COMPONENT_WORDS[selector.value_dimension]}. {behaviour} "
            "Kaynağın kendi listesinden: birim tablo başlığından, davranış ölçümden; satır satır "
            "incelenmedi. Internal composite selector, not an official BDDK code."
        ),
        labels=("Aylık Bülten", "Sektör", selector.value_dimension, "Sunum para birimi: TL"),
        group=SourceGroup(group_id=str(row.table), group_title=row.table_title, publisher="BDDK"),
        unit=row.unit,
        scale=row.scale,
        frequency=Frequency.MONTHLY,
        stock_flow=row.stock_flow,
        cumulative=row.cumulative,
    )


def reviewed_monthly_catalog(selector: BddkSelector) -> CatalogRecord:
    """Adapter review boundary: the reviewed housing rows, then the pinned listing.

    Broader mappings belong here, not in request/range/storage code. A caller cannot
    provide its own metadata or invent a supported selector. The housing rows keep their
    separately reviewed record byte for byte: the reviewed catalogue snapshot holds it.
    """
    selector = BddkSelector.model_validate(selector)
    if _is_housing(selector):
        return monthly_housing_catalog(selector)
    return monthly_directory_catalog(selector)


class MonthlyPeriod(ContractModel):
    """Request/response context, deliberately outside the stable selector."""

    model_config = ConfigDict(frozen=True)

    year: Annotated[StrictInt, Field(ge=2002, le=2100)]
    month: Annotated[StrictInt, Field(ge=1, le=12)]


class MonthlyHousingMetadata(ContractModel):
    """Bounded metadata projection for a later response parser to supply.

    Not the full wire response. The later adapter must establish that headers,
    caption and row fields all come from the same successful response, validate
    full row cardinality/shape and parse values separately. No cell values,
    colModels invention, live payload admission or Observation is exposed here.
    """

    model_config = ConfigDict(frozen=True)

    success: StrictBool
    caption: MetadataText
    column_headers: Annotated[tuple[MetadataText, ...], Field(min_length=7, max_length=7)]
    row_number: SelectorNumber
    row_label: MetadataText
    bank_group_label: MetadataText
    retrieved_at: AwareDatetime | None = None


class MetadataMismatch(ValueError):
    """Metadata differs from the reviewed shape; never guess units or selectors."""


def validate_monthly_housing_metadata(
    selector: BddkSelector,
    metadata: MonthlyHousingMetadata,
    *,
    requested_period: MonthlyPeriod,
) -> None:
    """Check the metadata projection only; never mint identity from response text.

    Caption period must match the request. Unknown caption/unit variants fail
    closed rather than inheriting MILLION TRY. Headers are ordered: presentation
    currency TL does not select the TP component. Retrieval time is provenance
    context only and cannot affect selector identity or inventory provenance.
    """
    selector = _housing(selector)
    metadata = MonthlyHousingMetadata.model_validate(metadata)
    period = MonthlyPeriod.model_validate(requested_period)
    expected_caption = f"Tüketici Kredileri (milyon TL), Dönem:{period.year}/{period.month}"
    if (
        not metadata.success
        or metadata.caption != expected_caption
        or metadata.column_headers != COLUMN_HEADERS
        or metadata.row_number != selector.row
        or metadata.row_label != HOUSING_LABEL
        or metadata.bank_group_label != "Sektör"
    ):
        raise MetadataMismatch("Response metadata does not match the reviewed monthly selection")


def _words(text: str) -> str:
    return " ".join(text.split())


def validate_monthly_directory_metadata(
    selector: BddkSelector,
    metadata: MonthlyHousingMetadata,
    *,
    requested_period: MonthlyPeriod,
) -> None:
    """The response must still be the listed table, unit, row and label, for this period.

    A bulletin that renumbers a row, renames it or changes a caption unit fails closed
    here instead of storing another measure under this identity. Whitespace runs are the
    only difference tolerated: the source itself writes some captions with two spaces.
    """
    selector = _reviewed(selector)
    row = SUPPORTED_ROWS[selector.table, selector.row]
    metadata = MonthlyHousingMetadata.model_validate(metadata)
    period = MonthlyPeriod.model_validate(requested_period)
    expected_caption = f"{row.table_title} ({row.unit_text}), Dönem:{period.year}/{period.month}"
    if (
        not metadata.success
        or _words(metadata.caption) != expected_caption
        or metadata.column_headers != COLUMN_HEADERS
        or metadata.row_number != selector.row
        or _words(metadata.row_label) != row.label
        or metadata.bank_group_label != "Sektör"
    ):
        raise MetadataMismatch("Response metadata does not match the listed monthly selection")


def validate_reviewed_monthly_metadata(
    selector: BddkSelector, metadata: MonthlyHousingMetadata, *, requested_period: MonthlyPeriod
) -> None:
    """Dispatch the source-specific review, independently of generic ingestion."""
    if _is_housing(BddkSelector.model_validate(selector)):
        validate_monthly_housing_metadata(selector, metadata, requested_period=requested_period)
    else:
        validate_monthly_directory_metadata(selector, metadata, requested_period=requested_period)
