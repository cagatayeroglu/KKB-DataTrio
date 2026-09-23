"""A monthly table of the conversation is kept in the knowledge base as a document is.

Live 2026-09-23: a Borsa İstanbul XTUMY endpoint was read into `analiz_1` and the person
asked for it to be saved; `promote_series` was offered only beside a kept document, so
the model saw no way to write and said so. Made-up figures; the address is a shape only.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from kkb_agent.agent.executor import ExecutionContext, ToolStatus
from kkb_agent.core import (
    AnalyticalResult,
    Frequency,
    Period,
    ResultEvidence,
    ResultKind,
    ResultStatus,
    ResultValue,
    Scale,
    SourceRef,
    StockFlow,
)
from kkb_agent.core.results import TransformationRecord
from kkb_agent.tools.promotion import (
    RESULT_REFERENCE,
    PromoteSeriesArguments,
    PromotionReceipt,
    make_promote_series_tool,
)

ENDPOINT = "https://www.example-borsa.test/api/endeks/xtumy?from=2025-01-01&token=SECRET"


def month(m: int) -> Period:
    end = date(2025, m + 1, 1).toordinal() - 1 if m < 12 else date(2025, 12, 31).toordinal()
    return Period(start=date(2025, m, 1), end=date.fromordinal(end), frequency=Frequency.MONTHLY)


def table(*columns: tuple[str, str]) -> AnalyticalResult:
    return AnalyticalResult(
        result_id="web_url:xtumy",
        kind=ResultKind.SERIES,
        status=ResultStatus.COMPUTED,
        tool="web_url",
        values=[
            ResultValue(
                label=label,
                value=1000.0 + m + index,
                unit=unit,
                scale=Scale.ONE,
                measure=StockFlow.UNKNOWN,
                period=month(m),
            )
            for index, (label, unit) in enumerate(columns)
            for m in (1, 2, 3)
        ],
        evidence=ResultEvidence(
            input_refs=["web"],
            sources=[
                SourceRef(
                    source_id="web:xtumy",
                    source_type="web_url",
                    locator=ENDPOINT,
                    retrieved_at=datetime(2026, 9, 23, 15, 41, tzinfo=UTC),
                    content_hash="sha256:" + "a" * 64,
                )
            ],
            transformations=[
                TransformationRecord(
                    operation="daily_to_monthly",
                    parameters={"keep": "last"},
                    input_refs=["web"],
                    output_ref="xtumy",
                )
            ],
        ),
    )


def tool(saved: list):
    def save(proposal):
        saved.append(proposal)
        return PromotionReceipt(series_id=f"USER:{proposal.slug}.v1", observations=3)

    return make_promote_series_tool(
        session_id="s1", attachment=None, library={}, propose=lambda _: None, save=save
    )


def keep(outputs, **arguments):
    saved: list = []
    spec = tool(saved)
    base = {
        "title": "BIST TÜM (XTUMY) ay sonu kapanış",
        "unit": "puan",
        "meaning": "index",
        "base_year": 1986,
        "result": "analiz_1",
        "save_now": True,
    }
    parsed = PromoteSeriesArguments.model_validate({**base, **arguments})
    return spec.run(parsed, ExecutionContext("kaydet", outputs=outputs)), saved


def test_a_published_table_is_saved_with_where_it_came_from():
    result, saved = keep({"analiz_1": table(("BIST TÜM kapanış (XTUMY)", "unknown"))})
    assert result.status is ToolStatus.SUCCESS and result.output.status == "saved"
    (proposal,) = saved
    assert proposal.document_ref == RESULT_REFERENCE + "analiz_1"
    assert proposal.unit == "index"  # index points, not a percentage
    assert [end for end, _ in proposal.observations] == [
        date(2025, 1, 31),
        date(2025, 2, 28),
        date(2025, 3, 31),
    ]
    where = dict(proposal.provenance)
    # The address without its query: a token in it is never kept.
    assert where["source_url"] == "https://www.example-borsa.test/api/endeks/xtumy"
    assert "SECRET" not in repr(proposal.provenance)
    assert where["transformations"] == "daily_to_monthly"
    assert where["table"] == "analiz_1"


def test_a_table_of_several_columns_asks_which_one():
    columns = (("TP", "TRY"), ("YP", "TRY"))
    outputs = {"analiz_1": table(*columns)}
    result, saved = keep(outputs, unit="TL", meaning="period_end_balance", base_year=None)
    assert result.status is ToolStatus.FAILURE and "VALUE_COLUMN_NOT_SETTLED" in result.warnings
    result, saved = keep(
        outputs, unit="TL", meaning="period_end_balance", base_year=None, column="YP"
    )
    assert result.output.status == "saved" and saved[0].value_column == "YP"


@pytest.mark.parametrize(
    "arguments, code",
    [
        # The table says TL; the person's USD contradicts it.
        ({"unit": "USD", "meaning": "period_end_balance", "base_year": None}, "UNIT_DISAGREES"),
        ({"result": "analiz_9"}, "RESULT_NOT_FOUND"),
        ({"column": "Yok"}, "COLUMN_NOT_FOUND"),
        ({"base_year": None}, "INDEX_NEEDS_BASE_YEAR"),
    ],
)
def test_what_is_unsettled_is_refused_and_nothing_is_saved(arguments, code):
    result, saved = keep({"analiz_1": table(("Bakiye", "TRY"))}, **arguments)
    assert result.status is ToolStatus.FAILURE and code in result.warnings
    assert saved == []
