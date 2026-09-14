"""One live question, end to end, on synthetic data (M4-15).

    python -m kkb_agent.live_check

Builds a throwaway lakehouse with two synthetic monthly series, registers the
four implemented brief tools against it, and asks one question through
`Session.answer` with the live Kloudeks provider — planning, validation, tool
execution, drafting and the verifier gate, exactly as the product runs them —
then prints a JSON report of what each stage did. The key never appears; the
data is synthetic, so the plan and the gated answer are shown as they are.

No gate calls this. A run makes a few live calls under an explicit operator
authorization (SEC-KLO-01); the offline tests drive `run_live_check` with a
scripted provider instead.

M7-19 adds explicit `--document --question '...URL...'` mode with the same
Session path and no synthetic seed. Its report contains only bounded metadata;
success requires a retained numeric claim bound to the fetched document's cell.
The application never reads .env; a separately approved operator run may export
configuration before invoking the command.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import BaseModel

from kkb_agent.agent import AnswerStatus, PlanningFailed, Session, ToolRegistry
from kkb_agent.agent.executor import ExecutionContext, ToolResult, ToolStatus
from kkb_agent.agent.loop import Answered
from kkb_agent.agent.registry import ToolSpec
from kkb_agent.agent.verifier import Binding, verify_claims
from kkb_agent.agent.workspace import Workspace
from kkb_agent.catalog.mappings import MAX_SNAPSHOT_BYTES, load_reviewed_snapshot
from kkb_agent.core import (
    DIMENSIONLESS,
    Aggregation,
    CumulativeKind,
    Frequency,
    Scale,
    SourceRef,
    StockFlow,
)
from kkb_agent.ingest.fetched import DOCUMENT_MEDIA_TYPES
from kkb_agent.ingest.prepared_series import prepared_series_names
from kkb_agent.ingest.safe_fetch import FetchCode, safe_fetch
from kkb_agent.ingestion_policy import RejectionCode
from kkb_agent.lakehouse import Observation, SeriesSemantics, open_lakehouse
from kkb_agent.lakehouse.lineage import EdgeKind, Lineage, NodeKind
from kkb_agent.lakehouse.store import DATABASE_NAME, Lakehouse
from kkb_agent.llm import (
    Completion,
    EmbeddingKind,
    KloudeksProvider,
    LLMProvider,
    Message,
    ProviderError,
)
from kkb_agent.tools import (
    make_anomaly_tool,
    make_catalog_search_tool,
    make_causality_tool,
    make_change_detection_tool,
    make_lakehouse_tool,
    make_table_transform_tool,
)
from kkb_agent.tools.web_url import Fetcher, WebUrlOutput, make_web_url_tool

#: The planner has no series catalog yet (M13), so the question names its series.
QUESTION = (
    "Konut kredisi stoğu (seri kimliği: bddk:konut) 2026-04-30 ile 2026-06-30 "
    "arasında ne kadar değişti?"
)

#: The organizer's reference Turn 1 question (kick-off deck, 7 September 2026).
TURN_ONE_QUESTION = (
    "2021-2025 yılları arasındaki 60 aylık veriden Türkiye'de kullanılan toplam konut "
    "kredilerinin dağılımını aylık olarak gösteriniz. Buna ek olarak konut kredisi faiz "
    "oranlarını da gösteriniz. Burada faiz oranlarının düştüğü dönemlerde kredi miktarı nasıl "
    "değişim göstermiş, faiz oranı düştüğü halde kredi miktarının yükselmediği dönemler olmuş mu?"
)
TURN_ONE_NAME = "konut_kredisi_ve_faiz"

#: The organizer's reference Turn 2 question, asked after Turn 1 was published.
TURN_TWO_QUESTION = (
    "Konut kredisi ve faiz oranları tablosunu bozmadan sadece konut kredisi tutarlarını "
    "enflasyondan arındırır mısın?"
)
TURN_TWO_NAME = "konut_kredisi_ve_faiz_reel"

#: Preserve the existing table, then examine directions, not a causal estimate.
TURN_THREE_QUESTION = (
    "Mevcut tabloyu bozmadan Konut Fiyat Endeksi sütununu ekle. Faizlerin düştüğü aylarda, "
    "konut fiyatları yükselirken enflasyondan arındırılmış kredi bakiyesinin artmadığı "
    "dönemleri incele. Bu birlikte hareketin kredi artmamasını açıklamaya yetip yetmediğini "
    "değerlendir."
)
TURN_THREE_NAME = "konut_kredisi_ve_faiz_reel_kfe"

#: Synthetic figures in the reference scenario's shape; not source data.
SERIES = {
    "bddk:konut": (
        SeriesSemantics(
            unit="TRY",
            scale=Scale.MILLION,
            frequency=Frequency.MONTHLY,
            observation=StockFlow.STOCK,
            cumulative=CumulativeKind.NONE,
            aggregation=Aggregation.LAST,
        ),
        {date(2026, 4, 30): 767314.0, date(2026, 5, 31): 782918.0, date(2026, 6, 30): 801438.0},
    ),
    "evds:TP.KTF12": (
        SeriesSemantics(
            unit="percent",
            scale=Scale.ONE,
            frequency=Frequency.MONTHLY,
            observation=StockFlow.RATE,
            cumulative=CumulativeKind.NONE,
            aggregation=Aggregation.AVERAGE,
        ),
        {date(2026, 4, 30): 40.0, date(2026, 5, 31): 43.2, date(2026, 6, 30): 46.75},
    ),
}

Clock = Callable[[], float]


@dataclass
class _Counting:
    """Passes calls through, remembering how many attempts each completion took.

    `Session` reports plan-validation rounds, not the schema repairs inside a
    completion; this is how the report shows what the question cost the model.
    """

    inner: LLMProvider
    attempts: list[int] = field(default_factory=list)

    def complete(
        self,
        messages: Sequence[Message],
        *,
        model: str | None = None,
        schema: type[BaseModel] | None = None,
    ) -> Completion:
        completion = self.inner.complete(messages, model=model, schema=schema)
        self.attempts.append(completion.attempts)
        return completion

    def embed(self, texts: Sequence[str], *, kind: EmbeddingKind) -> list[list[float]]:
        return self.inner.embed(texts, kind=kind)

    def vision(self, image_bytes: bytes, prompt: str) -> Completion:
        return self.inner.vision(image_bytes, prompt)


def run_live_check(
    provider: LLMProvider,
    root: Path,
    *,
    question: str = QUESTION,
    clock: Clock = time.perf_counter,
) -> dict[str, object]:
    """Ask one question through the whole product against a fresh synthetic lakehouse."""
    with open_lakehouse(root) as lake:
        artifact = lake.record_artifact(
            b'{"synthetic": true}',
            source=SourceRef(source_id="synthetic", source_type="fixture", locator="live-check"),
            media_type="application/json",
            recorded_at=datetime.now(UTC),
        )
        for series_id, (semantics, published) in SERIES.items():
            lake.register_series(
                series_id, title=series_id, semantics=semantics, artifact_id=artifact.artifact_id
            )
            lake.append_observations(
                series_id,
                [
                    Observation(date(end.year, end.month, 1), end, value)
                    for end, value in published.items()
                ],
            )
        registry = ToolRegistry()
        for make in (
            make_lakehouse_tool,
            make_change_detection_tool,
            make_anomaly_tool,
            make_causality_tool,
        ):
            registry.register(make(lake.connection, lineage=lake.lineage))

        counted = _Counting(provider)
        session = Session(counted, registry)
        started = clock()
        try:
            answered = session.answer(question, lake.connection)
        except (PlanningFailed, ProviderError) as error:
            return {
                "question": question,
                "failed": type(error).__name__,
                # Planner and provider messages carry categories and schema
                # locations, never the key.
                "detail": str(error),
                "plan_rejections": list(session.rejections),
                "completions": list(counted.attempts),
                "latency_ms": round((clock() - started) * 1000),
                "passed": False,
            }
        latency = round((clock() - started) * 1000)

    return _answer_report(question, answered, counted, latency)


def _answer_report(
    question: str, answered: Answered, counted: _Counting, latency: int
) -> dict[str, object]:
    gated = answered.answer
    report: dict[str, object] = {
        "question": question,
        # Attempts per completed model call, in order: planning, then drafting.
        "completions": list(counted.attempts),
        "plan": {
            "attempts": answered.planned.attempts,
            "rejections": list(answered.planned.rejections),
            "steps": [
                {
                    "tool": item.step.tool,
                    "arguments": item.arguments.model_dump(mode="json", exclude_unset=True),
                }
                for item in answered.planned.plan.steps
            ],
        },
        "tools": [
            {"tool": result.tool, "status": result.status.value, "error": result.error_category}
            for result in answered.outcome.results
        ],
        "results": [
            {"kind": result.kind.value, "status": result.status.value}
            for result in answered.results
        ],
        "answer": {
            "status": gated.status.value,
            "text": gated.text,
            "withheld": [list(item.reasons) for item in gated.omitted],
            "abstention": gated.abstention,
        },
        "latency_ms": latency,
        "passed": gated.status in (AnswerStatus.ACCEPTED, AnswerStatus.QUALIFIED),
    }
    if answered.planned.discovery_plan is not None:
        report["discovery"] = {
            "rounds": answered.planned.discovery_rounds,
            "steps": [
                {"step_id": v.step.step_id, "query": v.arguments.model_dump(mode="json")}
                for v in answered.planned.discovery_plan.steps
            ],
            "clarification": answered.planned.plan.clarification,
        }
    return report


def run_prepared_check(
    provider: LLMProvider,
    prepared_root: Path,
    workdir: Path,
    *,
    question: str = TURN_ONE_QUESTION,
    turns: int = 1,
    catalog_bytes: bytes | None = None,
    clock: Clock = time.perf_counter,
) -> dict[str, object]:
    """Ask the organizer turns over a private copy of the prepared pool (M6-25, M5-20).

    The prepared root must be closed and unchanged for the duration of copying;
    this is an operator dataset copy, not a snapshot of a running database.
    The copy keeps runtime lineage, execution evidence and workspace writes out
    of the prepared root. Tools see reviewed names for the series it holds.
    With `turns=2` or `3`, later questions follow in the same workspace only
    after the previous result was published. One turn keeps the single-report shape.
    """
    if not (prepared_root / DATABASE_NAME).is_file():
        return {"passed": False, "configuration": "prepared_root_missing"}
    if turns not in (1, 2, 3):
        return {"passed": False, "configuration": "unsupported_turns"}
    try:
        catalog_tool = (
            make_catalog_search_tool(snapshot_bytes=catalog_bytes)
            if catalog_bytes is not None
            else None
        )
    except (ValueError, TypeError):
        return {"passed": False, "configuration": "catalog_configuration_failed"}
    root = workdir / "lake"
    try:
        shutil.copytree(prepared_root, root)
    except (OSError, shutil.Error):
        # Do not call the model or expose filesystem details on a failed copy.
        return {"passed": False, "configuration": "prepared_copy_failed"}
    with open_lakehouse(root) as lake:
        names = prepared_series_names(lake.connection)
        workspace = Workspace.open(lake.connection)
        registry = ToolRegistry()
        if catalog_tool is not None:
            registry.register(catalog_tool)
        registry.register(make_lakehouse_tool(lake.connection, lineage=lake.lineage))
        registry.register(
            make_change_detection_tool(
                lake.connection, lineage=lake.lineage, series_names=names, workspace=workspace
            )
        )
        registry.register(
            make_table_transform_tool(
                lake.connection, workspace, lineage=lake.lineage, series_names=names
            )
        )
        for make in (make_anomaly_tool, make_causality_tool):
            registry.register(make(lake.connection, lineage=lake.lineage))
        plan = [
            (question, TURN_ONE_NAME),
            (TURN_TWO_QUESTION, TURN_TWO_NAME),
            (TURN_THREE_QUESTION, TURN_THREE_NAME),
        ][:turns]
        reports: list[dict[str, object]] = []
        for asked, name in plan:
            report = _prepared_turn(provider, registry, lake, workspace, asked, name, clock)
            report["prepared_series"] = len(names)
            # A qualified answer can be visible without publishing trusted state.
            # Even the final turn must be publishable to pass this rehearsal.
            report["passed"] = report["passed"] is True and name in workspace.names()
            if name == TURN_THREE_NAME and name in workspace.names():
                report["relationship_checked"] = _turn_three_relationship(workspace.value_of(name))
                report["passed"] = report["passed"] and report["relationship_checked"]
            reports.append(report)
            if name not in workspace.names():
                break
    if turns == 1:
        return reports[0]
    return {
        "turns": reports,
        "passed": len(reports) == turns and all(item["passed"] is True for item in reports),
    }


def _turn_three_relationship(result: object) -> bool:
    """Intent-specific rehearsal acceptance; generic runtime tools stay source-neutral."""
    from kkb_agent.core import AnalyticalResult

    if not isinstance(result, AnalyticalResult) or result.evidence is None:
        return False
    records = result.evidence.transformations
    real_columns = {r.output_ref for r in records if r.operation == "deflate"}
    rate_columns = {"EVDS:TP.KTF12"} | {
        r.output_ref
        for r in records
        if r.operation == "align_weekly_to_monthly" and r.input_refs == ["EVDS:TP.KTF12"]
    }
    return (
        any(r.operation == "add_series" for r in records)
        and any(v.label == "EVDS:TP.KFE.TR" for v in result.values)
        and any(
            r.operation == "table_co_movement"
            and r.parameters.get("driver_column") == "EVDS:TP.KFE.TR"
            and r.parameters.get("driver_direction") == "up"
            and r.parameters.get("target_column") in real_columns
            and r.parameters.get("target_direction") == "non_increasing"
            and r.parameters.get("when_column") in rate_columns
            and r.parameters.get("when_direction") == "down"
            for r in records
        )
    )


def _prepared_turn(
    provider: LLMProvider,
    registry: ToolRegistry,
    lake: Lakehouse,
    workspace: Workspace,
    question: str,
    name: str,
    clock: Clock,
) -> dict[str, object]:
    counted = _Counting(provider)
    session = Session(counted, registry, catalog_continuation="catalog_search" in registry)
    started = clock()
    try:
        answered = session.answer(question, lake.connection, workspace=workspace, remember=name)
    except (PlanningFailed, ProviderError) as error:
        return {
            "question": question,
            "failed": type(error).__name__,
            "detail": str(error),
            "plan_rejections": list(session.rejections),
            "completions": list(counted.attempts),
            "latency_ms": round((clock() - started) * 1000),
            "passed": False,
        }
    latency = round((clock() - started) * 1000)
    report = _answer_report(question, answered, counted, latency)
    report["published"] = workspace.names()
    # Public prepared-pool figures only; bounded for diagnosis of withheld prose.
    answer_report = report["answer"]
    if isinstance(answer_report, dict):
        answer_report["withheld_text"] = [item.text[:300] for item in answered.answer.omitted]
    report["tables"] = [
        {
            "columns": list(table.columns),
            "rows": len(table.rows),
            "first": table.rows[0][0],
            "last": table.rows[-1][0],
        }
        for table in answered.tables
    ]
    if answered.results:
        final = answered.results[-1]
        report["result"] = {
            "values": len(final.values),
            "counts": {
                value.label: value.value for value in final.values if value.unit == DIMENSIONLESS
            },
            "transformations": [
                record.operation
                for record in (final.evidence.transformations if final.evidence else [])
            ],
        }
    return report


def _digest(value: str) -> str:
    # Result IDs may include a document's sheet name. Never print them raw.
    return hashlib.sha256(value.encode()).hexdigest()


def _document_evidence(output: WebUrlOutput, lineage: Lineage) -> bool:
    """Resolve the selected transform and its source in this session's store."""
    result, source = output.result, output.source
    if result is None or result.evidence is None or source is None or output.status != "loaded":
        return False
    cell = result.evidence.lineage_node
    if not cell or not lineage.exists(cell):
        return False
    node = lineage.node(cell)
    if node.kind is not NodeKind.TRANSFORM or node.label != "web_url_cell":
        return False
    for parent, edge in lineage.parents(cell):
        original = lineage.node(parent)
        if (
            edge is EdgeKind.DERIVES_FROM
            and parent in result.evidence.input_refs
            and original.kind is NodeKind.SOURCE_FILE
            and original.label == source.source_id
            and original.attributes.get("content_hash") == source.content_hash
            and source.content_hash
        ):
            return True
    return False


# Existing loader codes, allowlisted for operator output only. This does not
# change admission/parser behavior or expose arbitrary WebUrlOutput.code text.
_DOCUMENT_CODES = frozenset(code.value for code in RejectionCode) | {
    "EMPTY_TABLE",
    "MALFORMED_TABLE",
    "PARSER_FAILED",
    "PARSING_DECLARATION_REQUIRED",
    "UNSUPPORTED_DELIMITER",
    "UNSUPPORTED_CELL",
    "EMPTY_DOCUMENT",
    "ENCRYPTED",
    "MALFORMED_DOCUMENT",
    "NO_TEXT_LAYER",
    "NO_STATIC_CONTENT",
    "UNSUPPORTED_TABLE",
    "OCR_FAILED",
    "OCR_EMPTY",
    "OCR_INCOMPLETE",
}


def run_document_check(
    provider: LLMProvider,
    root: Path,
    *,
    question: str,
    fetch: Fetcher = safe_fetch,
    clock: Clock = time.perf_counter,
) -> dict[str, object]:
    """One document question through Session.answer; no URL or content in the report.

    The default fetch/provider are live only when an operator explicitly invokes
    this mode. Offline callers inject the existing fetch boundary and provider.
    The lakehouse is deliberately not seeded with the synthetic mode's figures.
    """
    started = clock()
    stages: list[dict[str, object]] = []
    documents: list[tuple[WebUrlOutput, bool]] = []
    counted = _Counting(provider)
    report: dict[str, object] = {
        "mode": "document",
        "passed": False,
        "stages": stages,
        "completions": counted.attempts,
    }
    with open_lakehouse(root) as lake:

        def observe(spec: ToolSpec) -> ToolSpec:
            def run(arguments: BaseModel, context: ExecutionContext) -> ToolResult:
                before = clock()
                result = spec.run(arguments, context)
                entry: dict[str, object] = {
                    "stage": "tool",
                    "tool": spec.name,
                    "status": result.status.value,
                    "elapsed_ms": round((clock() - before) * 1000),
                }
                if spec.name == "web_url" and isinstance(result.output, WebUrlOutput):
                    output = result.output
                    resolved = result.status is ToolStatus.SUCCESS and _document_evidence(
                        output, lake.lineage
                    )
                    documents.append((output, resolved))
                    entry.update(
                        {
                            "loaded": output.status == "loaded",
                            "cell_selected": output.result is not None,
                            "lineage_resolved": resolved,
                            "media_type": output.media_type
                            if output.media_type in DOCUMENT_MEDIA_TYPES
                            else None,
                            "failure": result.error_category
                            if result.error_category
                            in {
                                "url_not_in_question",
                                "fetch_failed",
                                "not_admitted",
                                "needs_input",
                            }
                            else None,
                            # WebUrlOutput.code is a string shared with parser
                            # outcomes. Export only allowlisted existing codes,
                            # never arbitrary diagnostic text or source data.
                            "document_code": output.code
                            if result.error_category in {"not_admitted", "needs_input"}
                            and output.code in _DOCUMENT_CODES
                            else None,
                            "fetch_code": output.code
                            if result.error_category == "fetch_failed"
                            and output.code in {code.value for code in FetchCode}
                            else None,
                        }
                    )
                    if output.source is not None:
                        entry["source_digest"] = _digest(output.source.source_id)
                        entry["content_digest"] = _digest(output.source.content_hash or "")
                    if output.result is not None:
                        entry["result_digest"] = _digest(output.result.result_id)
                        entry["coordinates"] = {
                            key: value
                            for key, value in output.result.parameters.items()
                            if key in {"page", "table", "row_index", "column_index"}
                            and type(value) is int
                        }
                stages.append(entry)
                return result

            return replace(spec, run=run)

        registry = ToolRegistry()
        for make in (
            make_lakehouse_tool,
            make_change_detection_tool,
            make_anomaly_tool,
            make_causality_tool,
        ):
            registry.register(observe(make(lake.connection, lineage=lake.lineage)))
        registry.register(observe(make_web_url_tool(fetch=fetch, lineage=lake.lineage)))
        session = Session(counted, registry)
        try:
            answered = session.answer(question, lake.connection)
        except (PlanningFailed, ProviderError) as error:
            report["failure"] = (
                "planning_failed" if isinstance(error, PlanningFailed) else "provider_failed"
            )
            report["plan_rejections"] = len(session.rejections)
        else:
            gated = answered.answer
            # Session.answer without a workspace drafts against its last result.
            # Recheck ONLY retained text: the original verdict can contain a
            # supported number in a sentence withheld for another bad number.
            last = answered.results[-1] if answered.results else None
            verification_started = clock()
            retained = (
                verify_claims(gated.text, {"result": last}, lake.connection) if last else None
            )
            bound = (
                sum(
                    1
                    for item in retained.numbers
                    if item.supported
                    and item.binding is Binding.RESULT
                    and any(
                        resolved
                        and output.result is not None
                        and output.result.evidence is not None
                        and output.result == last
                        and item.result_id == output.result.result_id
                        and item.lineage_node == output.result.evidence.lineage_node
                        for output, resolved in documents
                    )
                )
                if retained
                else 0
            )
            report.update(
                {
                    "plan_repairs": answered.planned.attempts - 1,
                    "answer_status": gated.status.value,
                    "withheld_sentences": len(gated.omitted),
                    "document_numeric_claims": bound,
                    "passed": gated.status in (AnswerStatus.ACCEPTED, AnswerStatus.QUALIFIED)
                    and bound > 0,
                }
            )
            stages.append(
                {
                    "stage": "verification",
                    "status": "passed" if report["passed"] else "failed",
                    "elapsed_ms": round((clock() - verification_started) * 1000),
                }
            )
    report["elapsed_ms"] = round((clock() - started) * 1000)
    return report


def main(argv: Sequence[str] = ()) -> int:
    parser = argparse.ArgumentParser(
        description="Operator smoke; live calls require prior approval."
    )
    parser.add_argument(
        "--document", action="store_true", help="Use the document path instead of synthetic data"
    )
    parser.add_argument("--question", help="Actual document question including its URL")
    parser.add_argument(
        "--prepared-root",
        type=Path,
        help="Ask the organizer Turn 1 question over a copy of this prepared lakehouse",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        help="With --prepared-root: reviewed catalog JSON enabling bounded lexical discovery",
    )
    parser.add_argument(
        "--turns",
        type=int,
        choices=(1, 2, 3),
        default=1,
        help="With --prepared-root: rehearse 1, 2 or all 3 organizer turns in the same workspace",
    )
    arguments, unknown = parser.parse_known_args(argv)
    if unknown:
        parser.error("Unsupported arguments")
    if arguments.catalog is not None and arguments.prepared_root is None:
        parser.error("--catalog requires --prepared-root")
    if arguments.prepared_root is not None:
        if arguments.document or arguments.question is not None:
            parser.error("--prepared-root takes no --document or --question")
    elif arguments.document != (arguments.question is not None):
        # Never echo a question or URL in an error.
        parser.error("--document and --question must be supplied together")
    catalog_bytes = None
    if arguments.catalog is not None:
        try:
            with arguments.catalog.open("rb") as source:
                catalog_bytes = source.read(MAX_SNAPSHOT_BYTES + 1)
            load_reviewed_snapshot(catalog_bytes)
        except (OSError, ValueError, TypeError):
            print(json.dumps({"passed": False, "configuration": "catalog_configuration_failed"}))
            return 2
    try:
        provider = KloudeksProvider.from_env()
    except ProviderError as error:
        # Configuration errors name settings, never their values.
        print(
            json.dumps(
                {"passed": False, "configuration": "provider_configuration_failed"}
                if arguments.document
                else {"passed": False, "configuration": type(error).__name__, "detail": str(error)}
            )
        )
        return 2
    with provider, tempfile.TemporaryDirectory(prefix="kkb-live-check-") as directory:
        if arguments.prepared_root is not None:
            report = run_prepared_check(
                provider,
                arguments.prepared_root,
                Path(directory),
                turns=arguments.turns,
                catalog_bytes=catalog_bytes,
            )
        elif arguments.document:
            report = run_document_check(
                provider, Path(directory) / "lake", question=arguments.question
            )
        else:
            report = run_live_check(provider, Path(directory) / "lake")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":  # pragma: no cover - operator entry point
    sys.exit(main(sys.argv[1:]))
