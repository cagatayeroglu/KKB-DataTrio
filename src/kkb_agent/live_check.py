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
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import BaseModel

from kkb_agent.agent import AnswerStatus, PlanningFailed, Session, ToolRegistry
from kkb_agent.core import (
    Aggregation,
    CumulativeKind,
    Frequency,
    Scale,
    SourceRef,
    StockFlow,
)
from kkb_agent.lakehouse import Observation, SeriesSemantics, open_lakehouse
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
    make_causality_tool,
    make_change_detection_tool,
    make_lakehouse_tool,
)

#: The planner has no series catalog yet (M13), so the question names its series.
QUESTION = (
    "Konut kredisi stoğu (seri kimliği: bddk:konut) 2026-04-30 ile 2026-06-30 "
    "arasında ne kadar değişti?"
)

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

    gated = answered.answer
    return {
        "question": question,
        # Attempts per completed model call, in order: planning, then drafting.
        "completions": list(counted.attempts),
        "plan": {
            "attempts": answered.planned.attempts,
            "rejections": list(answered.planned.rejections),
            "steps": [
                {"tool": item.step.tool, "arguments": item.arguments.model_dump(mode="json")}
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


def main() -> int:
    try:
        provider = KloudeksProvider.from_env()
    except ProviderError as error:
        # Configuration errors name settings, never their values.
        print(
            json.dumps(
                {"passed": False, "configuration": type(error).__name__, "detail": str(error)}
            )
        )
        return 2
    with provider, tempfile.TemporaryDirectory(prefix="kkb-live-check-") as directory:
        report = run_live_check(provider, Path(directory) / "lake")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":  # pragma: no cover - operator entry point
    sys.exit(main())
