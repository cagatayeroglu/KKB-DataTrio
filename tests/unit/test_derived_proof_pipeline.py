"""Real producers, execution proof, writer gate and workspace publication together."""

import json
import math
from calendar import monthrange
from datetime import UTC, date, datetime, timedelta

import pytest

from kkb_agent.agent import AnswerStatus, Session, ToolRegistry, Workspace
from kkb_agent.agent.verifier import result_faults
from kkb_agent.core import (
    Aggregation,
    CumulativeKind,
    Frequency,
    Scale,
    SourceRef,
    StockFlow,
    WeeklyAnchor,
)
from kkb_agent.lakehouse import Observation, SeriesSemantics, open_lakehouse
from kkb_agent.lakehouse.lineage import EdgeKind, NodeKind
from kkb_agent.lakehouse.result_evidence import execution_proof
from kkb_agent.llm import scripted
from kkb_agent.llm.provider import TransportError
from kkb_agent.tools import make_causality_tool, make_lakehouse_tool, make_table_transform_tool


@pytest.mark.parametrize("operation", ["association", "granger"])
@pytest.mark.parametrize("writer_failure", [False, True])
def test_weekly_monthly_join_causality_can_publish_with_real_proof(
    tmp_path, operation, writer_failure
):
    with open_lakehouse(tmp_path / "lake") as lake:
        artifact = lake.record_artifact(
            b"offline",
            source=SourceRef(
                source_id="fixture", source_type="http-json", locator="https://example.test/series"
            ),
            media_type="text/plain",
            recorded_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        monthly = SeriesSemantics(
            unit="index",
            scale=Scale.ONE,
            frequency=Frequency.MONTHLY,
            observation=StockFlow.INDEX,
            cumulative=CumulativeKind.NONE,
            aggregation=Aggregation.LAST,
            base_year=2020,
        )
        weekly = SeriesSemantics(
            unit="percent",
            scale=Scale.ONE,
            frequency=Frequency.WEEKLY,
            observation=StockFlow.RATE,
            cumulative=CumulativeKind.NONE,
            aggregation=Aggregation.AVERAGE,
            anchor=WeeklyAnchor.FRIDAY,
        )
        for identity, semantics in [("index", monthly), ("rate", weekly)]:
            lake.register_series(
                identity, title=identity, semantics=semantics, artifact_id=artifact.artifact_id
            )
            raw_node = lake.lineage.record(
                NodeKind.SOURCE_FILE,
                "Synthetic offline source",
                attributes={"artifact_id": artifact.artifact_id},
            )
            lake.lineage.record(
                NodeKind.SERIES,
                identity,
                attributes={
                    "artifact_id": artifact.artifact_id,
                    "series_id": identity,
                    "parser": "fixture",
                },
                upstream=[(raw_node, EdgeKind.DERIVES_FROM)],
            )
        months = [
            date(2021 + i // 12, i % 12 + 1, monthrange(2021 + i // 12, i % 12 + 1)[1])
            for i in range(48)
        ]
        lake.append_observations(
            "index",
            [Observation(d.replace(day=1), d, 100 + i + math.sin(i)) for i, d in enumerate(months)],
        )
        days = [date(2021, 1, 1) + timedelta(weeks=i) for i in range(209)]
        lake.append_observations(
            "rate",
            [
                Observation(d - timedelta(days=6), d, 10 + math.sin(i * 0.19) + i * 0.01)
                for i, d in enumerate(days)
            ],
        )
        workspace = Workspace.open(lake.connection, "derived")
        registry = ToolRegistry()
        for tool in (
            make_lakehouse_tool(lake.connection, lineage=lake.lineage),
            make_table_transform_tool(lake.connection, workspace, lineage=lake.lineage),
            make_causality_tool(lake.connection, workspace=workspace, lineage=lake.lineage),
        ):
            registry.register(tool)

        def step(identity, tool, args, deps=()):
            return {"step_id": identity, "tool": tool, "arguments": args, "depends_on": list(deps)}

        steps = [
            step("r", "lakehouse", {"series": ["rate"]}),
            step("i", "lakehouse", {"series": ["index"]}),
            step(
                "m",
                "table_transform",
                {
                    "operation": "resample",
                    "source": "r",
                    "column": "rate",
                    "week_assignment": "by_end",
                },
                ["r"],
            ),
            step(
                "j",
                "table_transform",
                {"operation": "join_table", "source": "i", "other": "m"},
                ["i", "m"],
            ),
            step(
                "c",
                "causality",
                {
                    "operation": operation,
                    "source": "j",
                    "left_column": "index",
                    "right_column": "rate monthly average (by_end)",
                },
                ["j"],
            ),
        ]
        provider = scripted(
            json.dumps({"question": "İlişkiyi ölç", "steps": steps}),
            TransportError("offline")
            if writer_failure
            else "İlişki hesaplandı; nedensellik göstermez.",
        )
        answer = Session(provider, registry).answer(
            "İlişkiyi ölç", lake.connection, workspace=workspace, remember="analysis"
        )
        result = answer.results[-1]
        assert result.status.value == "computed", result
        assert execution_proof(result, lake.connection)
        from kkb_agent.api.proof import build_proof

        assert build_proof(lake.connection, result).availability == "available", build_proof(
            lake.connection, result
        ).gaps
        assert result_faults({"analysis": result}, lake.connection) == {}
        assert answer.answer.status is AnswerStatus.ACCEPTED
        assert workspace.names() == ["analysis"]
        tampered = result.model_copy(
            update={
                "values": [result.values[0].model_copy(update={"value": 777.0}), *result.values[1:]]
            }
        )
        assert not execution_proof(tampered, lake.connection)


@pytest.mark.parametrize("kind", ["csv", "xlsx"])
def test_document_summary_publishes_with_resolvable_proof(tmp_path, kind):
    import io

    from fastapi.testclient import TestClient
    from openpyxl import Workbook
    from test_document_table import BASE, ask, runtime, step

    from kkb_agent.core import ResultStatus

    provider = scripted(
        step("read", "web_url", attached=True, period_column="Ay", value_columns=["Faiz"]),
        "Tablo hazır.",
        step(
            "s",
            "table_transform",
            operation="summarize",
            source="analiz_1",
            column="Faiz",
            aggregation="mean",
            requested_aggregation="mean",
        ),
        "Özet hazır.",
    )
    runner, app = runtime(tmp_path, provider)
    if kind == "csv":
        content = b"Ay,Faiz (%)\n2024-01,4\n2024-02,5\n"
        mime = "text/csv"
    else:
        book = Workbook()
        book.active.append(["Ay", "Faiz (%)"])
        book.active.append(["2024-01", 4])
        book.active.append(["2024-02", 5])
        output = io.BytesIO()
        book.save(output)
        book.close()
        content = output.getvalue()
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    with TestClient(app, base_url=BASE) as client:
        created = client.post("/v1/sessions", json={}).json()
        sid = created["session_id"]
        headers = {"X-KKB-Session-Token": created["token"]}
        uploaded = client.post(
            f"/v1/sessions/{sid}/documents",
            content=content,
            headers={**headers, "Content-Type": mime},
        ).json()
        first = ask(
            client,
            sid,
            headers,
            "Ekli Ay Faiz tablosunu oku",
            document_ref=uploaded["document_ref"],
        )
        assert first["answer"]["status"] == "accepted", first
        second = ask(client, sid, headers, "Faiz ortalaması nedir?")
        assert second["answer"]["status"] == "accepted", json.dumps(
            second["answer"], ensure_ascii=False
        )
        assert second["answer"]["result"]["proof"]["availability"] == "available"
        with open_lakehouse(runner.run_root / sid / "lake") as lake:
            result = Workspace.open(lake.connection, sid).value_of("analiz_2")
            assert result.status is ResultStatus.COMPUTED
            assert result.values[0].value == 4.5
            assert result_faults({"summary": result}, lake.connection) == {}


def test_cumulative_or_missing_carrier_is_never_defaulted_to_levels():
    from test_table_summary import source

    from kkb_agent.analytics import associate
    from kkb_agent.lakehouse.column_contract import KEY, encode
    from kkb_agent.tools.causality import _column_of

    table = source()
    assert isinstance(_column_of(table, "credit"), str)
    declaration = SeriesSemantics(
        unit="TRY",
        scale=Scale.MILLION,
        frequency=Frequency.MONTHLY,
        observation=StockFlow.FLOW,
        cumulative=CumulativeKind.YEARLY_RESET,
        aggregation=Aggregation.SUM,
    )
    table = table.model_copy(
        update={"parameters": {KEY: {"credit": encode(declaration, column_id="credit")}}}
    )
    column = _column_of(table, "credit")
    assert not isinstance(column, str)
    assert column.semantics.cumulative is CumulativeKind.YEARLY_RESET
    outcome = associate(
        column.observations,
        column.semantics,
        column.observations,
        column.semantics,
        left_id="a",
        right_id="b",
        start=None,
        end=None,
        input_refs=("silver_observations",),
    )
    assert outcome.status.value != "computed"
