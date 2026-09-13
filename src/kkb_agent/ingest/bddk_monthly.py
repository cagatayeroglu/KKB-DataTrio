"""M3-05 offline selector identity and reviewed monthly housing metadata.

No retrieval, observation parsing/storage or planner registration. A selector
fingerprint says which selection was described, not whether it is supported.
Only the separately reviewed subset below may produce a CatalogRecord.
"""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal

from pydantic import AwareDatetime, ConfigDict, Field, StrictBool, StrictInt, StringConstraints

from kkb_agent.catalog.records import CatalogRecord, SourceGroup
from kkb_agent.core import CumulativeKind, Frequency, Scale, SourceRef, StockFlow
from kkb_agent.core.models import ContractModel

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


def _reviewed(selector: BddkSelector) -> BddkSelector:
    selector = BddkSelector.model_validate(selector)
    if (
        selector.bulletin_family != "monthly"
        or selector.table != 4
        or selector.row != 2
        or selector.bank_group != 10001
        or selector.presentation_currency != "TL"
        or selector.geography is not None
    ):
        raise UnreviewedSelector("Selector is outside the reviewed monthly housing scope")
    return selector


def monthly_housing_catalog(selector: BddkSelector) -> CatalogRecord:
    """Map an explicit reviewed selector to candidate declarations, never values.

    source_series_id is a labelled canonical composite selector because BDDK
    publishes no source-native series code here. SourceRef cites the immutable
    inventory supporting these declarations, not a pretend retrieved payload.
    Active state, full coverage and aggregation permissions remain unknown.
    """
    selector = _reviewed(selector)
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
    selector = _reviewed(selector)
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
