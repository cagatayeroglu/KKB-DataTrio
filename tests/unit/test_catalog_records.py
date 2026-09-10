"""Offline M13-01 declarations, using synthetic source shapes; no adapters."""

import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from kkb_agent.catalog import (
    AggregationPolicy,
    CatalogRecord,
    CatalogStatus,
    CoverageRange,
    SourceGroup,
)
from kkb_agent.core import (
    Aggregation,
    CumulativeKind,
    Frequency,
    Scale,
    StockFlow,
    WeeklyAnchor,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "sources"


def identity(**overrides: object) -> dict:
    return {
        "series_id": "catalog:synthetic-1",
        "provider": "unfamiliar-provider",
        "source_series_id": "Original.Code.1",
        "title": "Özgün seri başlığı",
        "source": {
            "source_id": "metadata:synthetic-1",
            "source_type": "fixture",
            "locator": "memory://synthetic/catalog",
        },
        **overrides,
    }


def test_evds_like_record_preserves_source_permissions_and_raw_preview() -> None:
    series = json.loads((FIXTURES / "evds/series_records.json").read_text())[0]
    group = json.loads((FIXTURES / "evds/datagroup_records.json").read_text())[0]
    record = CatalogRecord.model_validate(
        identity(
            series_id="catalog:evds:" + series["SERIE_CODE"],
            provider="EVDS",
            source_series_id=series["SERIE_CODE"],
            title=series["SERIE_NAME"],
            group=SourceGroup(
                group_id=group["DATAGROUP_CODE"],
                group_title=group["DATAGROUP_TYPE"],
                publisher=group["DATASOURCE"],
            ),
            labels=(series["FREQUENCY_STR"],),
            frequency=Frequency.WEEKLY,
            weekly_anchor=WeeklyAnchor.FRIDAY,
            stock_flow=StockFlow.RATE,
            unit="percent",
            scale=Scale.ONE,
            aggregation=AggregationPolicy(
                default=Aggregation.AVERAGE,
                average=True,
                sum=False,
                first=True,
                last=True,
                min=True,
                max=True,
            ),
            sample_values=("46,750", None, 0, 46.75),
            coverage=CoverageRange(start=date(2026, 1, 2), end=date(2026, 6, 26)),
        )
    )
    restored = CatalogRecord.model_validate_json(record.model_dump_json())
    assert restored == record
    assert restored.aggregation.sum is False
    assert restored.aggregation.average is True
    assert restored.weekly_anchor is WeeklyAnchor.FRIDAY
    assert restored.sample_values == ("46,750", None, 0, 46.75)
    assert restored.group.publisher == "BANKALAR"
    assert restored.status is CatalogStatus.UNKNOWN  # Absence of Arşiv is not ACTIVE.
    assert restored.cumulative is CumulativeKind.UNKNOWN


@pytest.mark.parametrize(
    ("filename", "kind", "cumulative"),
    [
        ("monthly_stock_2026_01.json", StockFlow.STOCK, CumulativeKind.NONE),
        ("monthly_ytd_2026_01.json", StockFlow.FLOW, CumulativeKind.YEARLY_RESET),
    ],
)
def test_bddk_monthly_caption_and_per_series_semantics(filename, kind, cumulative) -> None:
    payload = json.loads((FIXTURES / "bddk" / filename).read_text())["Json"]
    row = payload["data"]["rows"][0]
    record = CatalogRecord.model_validate(
        identity(
            provider="BDDK",
            # Test-owned selector, not a claim of an official BDDK series code.
            source_series_id="synthetic-monthly-selector:" + filename,
            title=row["cell"][2],
            labels=(payload["caption"],),
            group=SourceGroup(group_id="synthetic-monthly", group_title="Aylık Bülten"),
            frequency=Frequency.MONTHLY,
            unit="TRY",
            scale=Scale.MILLION,
            stock_flow=kind,
            cumulative=cumulative,
            sample_values=(row["cell"][-1],),
        )
    )
    restored = CatalogRecord.model_validate_json(record.model_dump_json())
    assert restored == record
    assert restored.labels == (payload["caption"],)
    assert restored.stock_flow is kind
    assert restored.cumulative is cumulative
    assert restored.aggregation.default is Aggregation.UNKNOWN


@pytest.mark.parametrize(
    ("group_id", "frequency", "anchor", "unit", "scale"),
    [
        ("weekly", Frequency.WEEKLY, WeeklyAnchor.FRIDAY, "TRY", Scale.MILLION),
        ("finturk", Frequency.QUARTERLY, None, "TRY", Scale.THOUSAND),
        ("finturk", Frequency.QUARTERLY, None, "percent", Scale.ONE),
        ("finturk", Frequency.QUARTERLY, None, None, Scale.UNKNOWN),
    ],
)
def test_bddk_display_context_does_not_force_one_unit_or_frequency(
    group_id, frequency, anchor, unit, scale
) -> None:
    displays = json.loads((FIXTURES / "bddk/display_cases.json").read_text())
    label = (
        displays["weekly"]["options"][0]["caption"]
        if group_id == "weekly"
        else displays["finturk"]["display_metadata"][2]["table"]
    )
    record = CatalogRecord.model_validate(
        identity(
            provider="BDDK",
            labels=(label,),
            group=SourceGroup(group_id=group_id),
            frequency=frequency,
            weekly_anchor=anchor,
            unit=unit,
            scale=scale,
        )
    )
    assert record.unit == unit
    assert record.scale is scale
    assert record.frequency is frequency
    assert record.cumulative is CumulativeKind.UNKNOWN


def test_unknowns_are_explicit_and_titles_are_never_interpreted() -> None:
    record = CatalogRecord.model_validate(
        identity(title="Arşiv: aylık stok milyon TL (2003=100)", labels=("SUMABLE: 1",))
    )
    data = record.model_dump(mode="json")
    for field in ("frequency", "stock_flow", "cumulative", "scale", "status"):
        assert data[field] == "unknown"
    for field in ("unit", "weekly_anchor", "base_year", "description"):
        assert data[field] is None
    assert data["coverage"] == {"start": None, "end": None}
    assert data["sample_values"] == []
    assert data["aggregation"] == dict.fromkeys(
        ("sum", "average", "first", "last", "min", "max"), None
    ) | {"default": "unknown"}
    assert CatalogRecord.model_validate_json(record.model_dump_json()) == record


def test_same_display_name_keeps_distinct_original_series_ids() -> None:
    series = json.loads((FIXTURES / "evds/series_records.json").read_text())[2:4]
    records = [
        CatalogRecord.model_validate(
            identity(
                provider="EVDS",
                series_id="catalog:" + item["SERIE_CODE"],
                source_series_id=item["SERIE_CODE"],
                title=item["SERIE_NAME"],
            )
        )
        for item in series
    ]
    assert records[0].title == records[1].title
    assert records[0].source_series_id != records[1].source_series_id
    assert records[0].series_id != records[1].series_id
    assert records[0] != records[1]


@pytest.mark.parametrize("status", list(CatalogStatus))
def test_declared_status_and_index_base_round_trip(status) -> None:
    group = json.loads((FIXTURES / "evds/datagroup_records.json").read_text())[2]
    record = CatalogRecord.model_validate(
        identity(
            status=status,
            group={"group_id": group["DATAGROUP_CODE"], "group_title": group["DATAGROUP_TYPE"]},
            stock_flow=StockFlow.INDEX,
            base_year=2003,
            labels=("2003=100",),
        )
    )
    restored = CatalogRecord.model_validate_json(record.model_dump_json())
    assert restored.status is status
    assert restored.base_year == 2003
    assert "Arşiv" in restored.group.group_title


@pytest.mark.parametrize("field", ["series_id", "provider", "source_series_id", "title", "source"])
def test_missing_identity_rejected(field) -> None:
    data = identity()
    del data[field]
    with pytest.raises(ValidationError):
        CatalogRecord.model_validate(data)


@pytest.mark.parametrize("field", ["series_id", "provider", "source_series_id", "title"])
@pytest.mark.parametrize("value", ["", " \t\n", 123, b"id", None])
def test_invalid_identity_rejected(field, value) -> None:
    with pytest.raises(ValidationError):
        CatalogRecord.model_validate(identity(**{field: value}))


def test_original_text_and_ids_are_not_normalized() -> None:
    record = CatalogRecord.model_validate(
        identity(source_series_id=" Mixed.Case.İı ", title="  İSTANBUL / ışıK  ")
    )
    assert record.source_series_id == " Mixed.Case.İı "
    assert record.title == "  İSTANBUL / ışıK  "


@pytest.mark.parametrize("frequency", list(Frequency))
def test_all_existing_frequencies_supported_without_invented_anchor(frequency) -> None:
    record = CatalogRecord.model_validate(identity(frequency=frequency))
    assert record.frequency is frequency
    assert record.weekly_anchor is None


@pytest.mark.parametrize("anchor", [WeeklyAnchor.FRIDAY, WeeklyAnchor.WEDNESDAY])
def test_weekly_anchors_round_trip(anchor) -> None:
    record = CatalogRecord.model_validate(identity(frequency="weekly", weekly_anchor=anchor))
    assert CatalogRecord.model_validate_json(record.model_dump_json()).weekly_anchor is anchor


def test_contradictory_frequency_and_forbidden_default_rejected() -> None:
    with pytest.raises(ValidationError, match="weekly anchor"):
        CatalogRecord.model_validate(identity(frequency="monthly", weekly_anchor="friday"))
    with pytest.raises(ValidationError, match="explicitly forbidden"):
        AggregationPolicy(default="sum", sum=False)
    assert AggregationPolicy(default="average").average is None


@pytest.mark.parametrize("flag", [0, 1, "false", "true"])
def test_source_flags_require_explicit_boolean_mapping(flag) -> None:
    with pytest.raises(ValidationError):
        AggregationPolicy(sum=flag)


def test_coverage_validates_order_and_keeps_partial_unknowns() -> None:
    with pytest.raises(ValidationError, match="Coverage end"):
        CoverageRange(start="2026-02-01", end="2026-01-01")
    assert CoverageRange(start="2026-01-01").end is None
    assert CoverageRange(end="2026-01-01").start is None
    assert CoverageRange(start="2026-01-01", end="2026-01-01").start == date(2026, 1, 1)


@pytest.mark.parametrize("values", [[True], [float("nan")], [float("inf")], [{}], [[1]], [0] * 21])
def test_preview_rejects_coercion_nonfinite_nested_or_oversized_values(values) -> None:
    with pytest.raises(ValidationError):
        CatalogRecord.model_validate(identity(sample_values=values))


def test_samples_stay_raw_bounded_and_missing_is_distinct_from_zero() -> None:
    samples = ("46,750", "1.234,56", "1,234.56", "", None, 0, "=1+1")
    record = CatalogRecord.model_validate(identity(sample_values=samples))
    restored = CatalogRecord.model_validate_json(record.model_dump_json())
    assert restored.sample_values == samples
    assert len(CatalogRecord.model_validate(identity(sample_values=[0] * 20)).sample_values) == 20


def test_nested_defaults_are_independent() -> None:
    first = CatalogRecord.model_validate(identity())
    second = CatalogRecord.model_validate(identity())
    first.aggregation.sum = False
    first.group.group_id = "custom"
    first.coverage.start = date(2026, 1, 1)
    assert second.aggregation.sum is None
    assert second.group.group_id is None
    assert second.coverage.start is None


def test_serialization_is_deterministic_across_input_key_order() -> None:
    data = identity(labels=["İstanbul", "Özgün"], sample_values=["46,750", None])
    first = CatalogRecord.model_validate(data)
    second = CatalogRecord.model_validate(dict(reversed(list(data.items()))))
    assert first.model_dump_json() == second.model_dump_json()
    assert first.model_dump_json() == first.model_dump_json()
    assert "İstanbul" in first.model_dump_json()


@pytest.mark.parametrize(
    "extra",
    [{"raw_payload": {}}, {"SERIE_CODE": "wire-key"}, {"embedding": [0.1]}, {"aliases": ["x"]}],
)
def test_wire_payloads_and_future_retrieval_fields_are_not_contract_fields(extra) -> None:
    with pytest.raises(ValidationError):
        CatalogRecord.model_validate(identity(**extra))
