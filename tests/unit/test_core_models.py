"""Focused M0-01 validation; planner/provider/evaluation cases remain deferred."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from kkb_agent.core import (
    DataContract,
    EvidenceRecord,
    Frequency,
    SourceRef,
    StockFlow,
    TransformationRecord,
    ValidationOutcome,
)


def source_ref() -> SourceRef:
    return SourceRef(
        source_id="synthetic-1",
        source_type="fixture",
        locator="memory://synthetic-input#sheet=Observations",
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_unknown_data_semantics_remain_explicit() -> None:
    contract = DataContract(contract_id="contract-1", source=source_ref(), title="Index")

    assert contract.unit is None
    assert contract.frequency is Frequency.UNKNOWN
    assert contract.stock_flow is StockFlow.UNKNOWN
    assert contract.cumulative is None
    assert contract.time_column is None
    assert contract.time_semantics is None
    assert contract.reset_behavior is None
    restored = DataContract.model_validate_json(contract.model_dump_json())
    assert restored == contract
    assert restored.model_dump(mode="json")["frequency"] == "unknown"
    assert restored.model_dump(mode="json")["cumulative"] is None


def test_contracts_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        SourceRef(
            source_id="synthetic-1",
            source_type="fixture",
            locator="memory://fixture",
            invented_semantics="monthly",
        )


def transformation() -> TransformationRecord:
    return TransformationRecord(
        operation="select_columns",
        parameters={"columns": ["c0", "c1"], "missing_policy": None},
        input_refs=["data:synthetic-original"],
        output_ref="data:synthetic-selected",
    )


def test_provenance_and_explicit_declarations_round_trip() -> None:
    source = source_ref()
    source.content_hash = "synthetic-digest"
    contract = DataContract(
        contract_id="contract-1",
        source=source,
        title="Örnek observations",
        unit="declared-unit",
        frequency="monthly",
        time_column="c0",
        time_semantics="observation_date",
        stock_flow="flow",
        cumulative=False,
        reset_behavior="not_applicable",
        source_period="2026-01",
        transformations=[transformation()],
        semantic_warnings=["Declaration requires independent verification"],
    )
    evidence = EvidenceRecord(
        evidence_id="evidence-1",
        claim="Selected declared columns from the synthetic source",
        sources=[source],
        tool_run_id="run:synthetic-selection",
        transformations=[transformation()],
        period="2026-01",
        columns=["c0", "c1"],
        limitations=["Synthetic declaration only"],
    )
    assert DataContract.model_validate_json(contract.model_dump_json()) == contract
    assert EvidenceRecord.model_validate_json(evidence.model_dump_json()) == evidence
    assert evidence.validation is ValidationOutcome.NOT_RUN
    assert evidence.sources[0].locator.endswith("#sheet=Observations")
    assert evidence.sources[0].retrieved_at == datetime(2026, 1, 1, tzinfo=UTC)
    assert evidence.sources[0].content_hash == "synthetic-digest"
    assert contract.cumulative is False


def test_metadata_does_not_infer_financial_semantics() -> None:
    contract = DataContract(
        contract_id="unfamiliar",
        source=SourceRef(source_id="s1", source_type="unfamiliar", locator="opaque-fragment"),
        title="Monthly cumulative stock in USD",
    )
    assert contract.unit is None
    assert contract.frequency is Frequency.UNKNOWN
    assert contract.stock_flow is StockFlow.UNKNOWN
    assert contract.cumulative is None
    assert contract.source.retrieved_at is None
    assert contract.source.content_hash is None


@pytest.mark.parametrize("cumulative", [None, False, True])
def test_cumulative_unknown_false_true_remain_distinct(cumulative: bool | None) -> None:
    contract = DataContract(
        contract_id="c1", source=source_ref(), title="Example", cumulative=cumulative
    )
    assert contract.cumulative is cumulative
    assert DataContract.model_validate_json(contract.model_dump_json()).cumulative is cumulative


@pytest.mark.parametrize("cumulative", ["false", "true", "unknown", 0, 1, 0.0, 1.0])
def test_cumulative_declarations_are_not_coerced(cumulative: object) -> None:
    with pytest.raises(ValidationError):
        DataContract(contract_id="c1", source=source_ref(), title="Example", cumulative=cumulative)


@pytest.mark.parametrize("field", ["source_id", "source_type", "locator"])
@pytest.mark.parametrize("value", ["", " \t\n", 123, b"bytes"])
def test_source_identifiers_must_be_nonblank_strings(field: str, value: object) -> None:
    values = {"source_id": "s1", "source_type": "fixture", "locator": "memory://fixture"}
    values[field] = value
    with pytest.raises(ValidationError):
        SourceRef.model_validate(values)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("contract_id", " "),
        ("title", ""),
        ("unit", " "),
        ("frequency", "fortnightly-guess"),
        ("stock_flow", "guessed"),
        ("time_column", ""),
        ("reset_behavior", ""),
        ("semantic_warnings", [""]),
        ("confidence", 0.99),
        ("aggregation", "sum"),
    ],
)
def test_invalid_or_deferred_contract_fields_rejected(field: str, value: object) -> None:
    values = {"contract_id": "c1", "source": source_ref(), "title": "Example", field: value}
    with pytest.raises(ValidationError):
        DataContract.model_validate(values)


def test_retrieval_time_requires_timezone_if_present() -> None:
    with pytest.raises(ValidationError):
        SourceRef(
            source_id="s1",
            source_type="fixture",
            locator="opaque",
            retrieved_at=datetime(2026, 1, 1),
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"input_refs": []},
        {"input_refs": [""]},
        {"operation": " "},
        {"output_ref": ""},
        {"parameters": {"bad": object()}},
        {"parameters": {"nested": [float("nan")]}},
        {"parameters": {"nested": [float("inf")]}},
        {"unrecognized": True},
    ],
)
def test_transformation_requires_typed_lineage(changes: dict[str, object]) -> None:
    values = transformation().model_dump() | changes
    with pytest.raises(ValidationError):
        TransformationRecord.model_validate(values)


@pytest.mark.parametrize(
    "changes",
    [
        {"sources": []},
        {"claim": " "},
        {"validation": "assumed_pass"},
        {"columns": [""]},
        {"extra": "ignored"},
    ],
)
def test_invalid_evidence_rejected(changes: dict[str, object]) -> None:
    values = {"evidence_id": "e1", "claim": "A claim", "sources": [source_ref()]} | changes
    with pytest.raises(ValidationError):
        EvidenceRecord.model_validate(values)


def test_mutable_defaults_and_reused_sources_are_independent() -> None:
    shared = source_ref()
    first = DataContract(contract_id="c1", source=shared, title="First")
    second = DataContract(contract_id="c2", source=shared, title="Second")
    first.semantic_warnings.append("Unresolved")
    first.transformations.append(transformation())
    first.source.locator = "memory://other-fragment"
    assert second.semantic_warnings == []
    assert second.transformations == []
    assert second.source.locator == shared.locator
    one = EvidenceRecord(evidence_id="e1", claim="First", sources=[shared])
    two = EvidenceRecord(evidence_id="e2", claim="Second", sources=[shared])
    one.columns.append("c0")
    one.limitations.append("Incomplete")
    one.transformations.append(transformation())
    assert two.columns == two.limitations == two.transformations == []
    a = TransformationRecord(operation="declared", input_refs=["in"], output_ref="out")
    b = TransformationRecord(operation="declared", input_refs=["in"], output_ref="out")
    a.parameters["parameter"] = ["value"]
    assert b.parameters == {}


def test_assignment_and_boundary_revalidation_reject_invalid_state() -> None:
    contract = DataContract(contract_id="c1", source=source_ref(), title="Example")
    with pytest.raises(ValidationError):
        contract.cumulative = "false"
    assert contract.cumulative is None
    # List mutation is not intercepted by Pydantic; validate again at boundaries.
    contract.semantic_warnings.append(123)
    with pytest.raises(ValidationError):
        DataContract.model_validate(contract)
