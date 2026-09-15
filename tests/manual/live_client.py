"""Owner-authorized live rehearsal launcher with a hard Kloudeks request ceiling.

Same prepared runner/service/app as `python -m kkb_agent.api --serve`, wrapped so
that at most `--max-model-requests` chat completions leave the process during
its lifetime, with `KLOUDEKS_MAX_ATTEMPTS=1` required (one HTTP request per
completion, no automatic retry). Embedding and vision are refused. A safe ledger
of call index, structured/text kind, outcome category and elapsed time, plus
each gate status with omission reason categories (no messages, answers, draft
sentences or credentials), is written to `artifacts/live-rehearsal-ledger.jsonl`.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import uvicorn
from pydantic import BaseModel

from kkb_agent.api.__main__ import literal_config
from kkb_agent.api.app import create_app
from kkb_agent.api.prepared import PreparedRunner, read_catalog
from kkb_agent.api.service import AnalysisService
from kkb_agent.llm import KloudeksProvider, approved_base_url
from kkb_agent.llm.provider import (
    CapabilityUnavailable,
    Completion,
    EmbeddingKind,
    LLMProvider,
    Message,
    ProviderError,
)

LEDGER = Path(__file__).resolve().parents[2] / "artifacts" / "live-rehearsal-ledger.jsonl"
_CATEGORIES = (
    ("absence", "absence"),
    ("causal", "causal"),
    ("identit", "identity"),
    ("identifier", "identity"),
    ("unit", "unit_scale"),
    ("currency", "unit_scale"),
    ("scale", "unit_scale"),
    ("period", "period"),
    ("ambiguous", "ambiguous"),
    ("does not match", "unmatched_number"),
)


def reason_category(reason: str) -> str:
    """Code-owned reason text to a fixed category; no draft text is kept."""
    folded = reason.lower()
    return next((name for key, name in _CATEGORIES if key in folded), "other")


def record_gate_outcomes(ledger: Path) -> None:
    """Observe Session's gate result: status and omission categories only."""
    from kkb_agent.agent import loop

    gate = loop.gate_answer

    def observed(*args: Any, **kwargs: Any) -> Any:
        answer = gate(*args, **kwargs)
        categories: dict[str, int] = {}
        for item in answer.omitted:
            for reason in item.reasons:
                name = reason_category(reason)
                categories[name] = categories.get(name, 0) + 1
        with ledger.open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    {
                        "gate": answer.status.value,
                        "omitted_sentences": len(answer.omitted),
                        "categories": dict(sorted(categories.items())),
                    }
                )
                + "\n"
            )
        return answer

    loop.gate_answer = observed  # type: ignore[assignment]


class RequestBudget:
    """Refuses before dispatch once the ceiling is reached; never retries."""

    def __init__(self, inner: LLMProvider, limit: int, ledger: Path):
        if type(limit) is not int or not 1 <= limit <= 15:
            raise ValueError("Request ceiling must be between 1 and 15")
        self._inner, self._limit, self._ledger = inner, limit, ledger
        self._used = 0
        self._lock = threading.Lock()

    @property
    def used(self) -> int:
        return self._used

    def _record(self, entry: dict[str, object]) -> None:
        with self._ledger.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry) + "\n")

    def complete(
        self,
        messages: Sequence[Message],
        *,
        model: str | None = None,
        schema: type[BaseModel] | None = None,
    ) -> Completion:
        kind = "structured" if schema is not None else "text"
        with self._lock:
            if self._used >= self._limit:
                self._record({"call": None, "kind": kind, "outcome": "budget_refused"})
                raise ProviderError("Model request budget exhausted")
            self._used += 1
            call = self._used
        start = time.monotonic()
        try:
            completion = self._inner.complete(messages, model=model, schema=schema)
        except ProviderError as error:
            elapsed = round((time.monotonic() - start) * 1000)
            self._record(
                {"call": call, "kind": kind, "outcome": type(error).__name__, "ms": elapsed}
            )
            raise
        elapsed = round((time.monotonic() - start) * 1000)
        self._record(
            {
                "call": call,
                "kind": kind,
                "outcome": "ok",
                "attempts": completion.attempts,
                "finish": completion.finish_reason,
                "ms": elapsed,
            }
        )
        return completion

    def embed(self, texts: Sequence[str], *, kind: EmbeddingKind) -> list[list[float]]:
        raise CapabilityUnavailable("Embedding is not authorized in this rehearsal")

    def vision(self, image_bytes: bytes, prompt: str) -> Completion:
        raise CapabilityUnavailable("Vision is not authorized in this rehearsal")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared-root", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8128)
    parser.add_argument("--max-model-requests", type=int, required=True)
    parser.add_argument("--enable-model-requests", action="store_true", required=True)
    args = parser.parse_args(argv)
    config = literal_config(args.env_file)
    approved_base_url(config.base_url)
    # Observed Kloudeks completions can take several minutes; bound, never unlimited.
    if config.max_attempts != 1 or not 1 <= config.request_timeout <= 900:
        parser.error("Set KLOUDEKS_MAX_ATTEMPTS=1 and KLOUDEKS_REQUEST_TIMEOUT<=900")
    LEDGER.parent.mkdir(exist_ok=True)
    LEDGER.write_text("", encoding="utf-8")
    record_gate_outcomes(LEDGER)
    with KloudeksProvider(config) as provider:
        budget = RequestBudget(provider, args.max_model_requests, LEDGER)
        runner = PreparedRunner(
            budget,
            args.prepared_root.absolute(),
            args.state_root.absolute(),
            catalog_bytes=read_catalog(args.catalog.absolute()),
            redactions=(config.credential.get_secret_value(),),
        )
        service = AnalysisService(runner, mode="kloudeks", selected_runner=runner.selected)
        app = create_app(service, port=args.port, prepared=runner.status)
        print(json.dumps({"ready": True, "port": args.port, "limit": args.max_model_requests}))
        try:
            uvicorn.run(app, host="127.0.0.1", port=args.port, workers=1, access_log=False)
        finally:
            service.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
