"""Owner-authorized live rehearsal launcher with a hard Kloudeks request ceiling.

Same prepared runner/service/app as `python -m kkb_agent.api --serve`, wrapped so
that at most `--max-model-requests` chat completions leave the process during
its lifetime, with `KLOUDEKS_MAX_ATTEMPTS=1` required (one HTTP request per
completion, no automatic retry). Query embeddings have a separate opt-in ceiling;
passage embedding and vision remain refused. A safe ledger
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
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import uvicorn
from pydantic import BaseModel

from kkb_agent.api.__main__ import literal_config
from kkb_agent.api.app import create_app
from kkb_agent.api.prepared import PreparedRunner, read_catalog
from kkb_agent.api.service import AnalysisService
from kkb_agent.catalog.embedding import (
    RUNTIME_QUERY_POLICY,
    profile_for,
    query_embedder,
    require_model,
)
from kkb_agent.catalog.hybrid import CatalogDenseStage
from kkb_agent.catalog.lance_index import LocalCatalogIndex
from kkb_agent.catalog.mappings import load_reviewed_snapshot
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
_LEDGER_LOCK = threading.Lock()


def record(ledger: Path, entry: dict[str, object]) -> None:
    with _LEDGER_LOCK, ledger.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry) + "\n")


_CATEGORIES = (
    ("ambiguous", "ambiguous"),
    ("does not identify", "identity_header"),
    ("absence", "absence"),
    ("causal", "causal"),
    ("identit", "identity"),
    ("identifier", "identity"),
    ("unit", "unit_scale"),
    ("currency", "unit_scale"),
    ("scale", "unit_scale"),
    ("period", "period"),
    ("does not match", "unmatched_number"),
)


def reason_category(reason: str) -> str:
    """Code-owned reason text to a fixed category; no draft text is kept."""
    folded = reason.lower()
    return next((name for key, name in _CATEGORIES if key in folded), "other")


@contextmanager
def record_gate_outcomes(ledger: Path) -> Iterator[None]:
    """Observe Session's gate result: status and omission categories only."""
    from kkb_agent.agent import loop

    # Observe the loop's imported binding, not the verifier's exported function.
    gate = loop.gate_answer  # type: ignore[attr-defined]

    def observed(*args: Any, **kwargs: Any) -> Any:
        answer = gate(*args, **kwargs)
        categories: dict[str, int] = {}
        for item in answer.omitted:
            for reason in item.reasons:
                name = reason_category(reason)
                categories[name] = categories.get(name, 0) + 1
        record(
            ledger,
            {
                "gate": answer.status.value,
                "omitted_sentences": len(answer.omitted),
                "categories": dict(sorted(categories.items())),
            },
        )
        return answer

    loop.gate_answer = observed  # type: ignore[attr-defined]
    try:
        yield
    finally:
        loop.gate_answer = gate  # type: ignore[attr-defined]


class RequestBudget:
    """Reserve before dispatch, including failures; inner transport must use one attempt."""

    def __init__(self, inner: LLMProvider, limit: int, ledger: Path, *, embedding_limit: int = 0):
        validate_limits(limit, embedding_limit)
        self._inner, self._limit, self._ledger = inner, limit, ledger
        self._embedding_limit = embedding_limit
        self._used = self._embedding_used = 0
        self._lock = threading.Lock()

    @property
    def used(self) -> int:
        with self._lock:
            return self._used

    @property
    def embedding_used(self) -> int:
        with self._lock:
            return self._embedding_used

    def _record(self, entry: dict[str, object]) -> None:
        record(self._ledger, entry)

    def _reserve(self, kind: str) -> int:
        with self._lock:
            embedding = kind == "embedding"
            used = self._embedding_used if embedding else self._used
            limit = self._embedding_limit if embedding else self._limit
            if used >= limit:
                self._record({"call": None, "kind": kind, "outcome": "budget_refused"})
                raise ProviderError("Request budget exhausted")
            call = used + 1
            if embedding:
                self._embedding_used = call
            else:
                self._used = call
            # If recording fails, no provider call is dispatched. A started entry
            # remains evidence even if the process stops before the outcome record.
            self._record({"call": call, "kind": kind, "outcome": "started"})
            return call

    def _failure(self, call: int, kind: str, start: float, error: Exception) -> None:
        self._record(
            {
                "call": call,
                "kind": kind,
                "outcome": "provider_error"
                if isinstance(error, ProviderError)
                else "unexpected_error",
                "ms": round((time.monotonic() - start) * 1000),
            }
        )

    def complete(
        self,
        messages: Sequence[Message],
        *,
        model: str | None = None,
        schema: type[BaseModel] | None = None,
    ) -> Completion:
        kind = "structured" if schema is not None else "text"
        call = self._reserve(kind)
        start = time.monotonic()
        try:
            completion = self._inner.complete(messages, model=model, schema=schema)
        except Exception as error:
            self._failure(call, kind, start, error)
            raise
        self._record(
            {
                "call": call,
                "kind": kind,
                "outcome": "ok",
                "attempts": completion.attempts,
                "finish": completion.finish_reason
                if completion.finish_reason
                in (None, "stop", "length", "content_filter", "tool_calls", "function_call")
                else "other",
                "ms": round((time.monotonic() - start) * 1000),
            }
        )
        return completion

    def embed(self, texts: Sequence[str], *, kind: EmbeddingKind) -> list[list[float]]:
        if (
            kind != "query"
            or len(texts) != 1
            or not isinstance(texts[0], str)
            or not texts[0].strip()
        ):
            self._record({"call": None, "kind": "embedding", "outcome": "capability_refused"})
            raise CapabilityUnavailable("Only one nonempty query per embedding request is allowed")
        call = self._reserve("embedding")
        start = time.monotonic()
        try:
            vectors = self._inner.embed(texts, kind=kind)
        except Exception as error:
            self._failure(call, "embedding", start, error)
            raise
        self._record(
            {
                "call": call,
                "kind": "embedding",
                "outcome": "ok",
                "texts": 1,
                "ms": round((time.monotonic() - start) * 1000),
            }
        )
        return vectors

    def vision(self, image_bytes: bytes, prompt: str) -> Completion:
        self._record({"call": None, "kind": "vision", "outcome": "capability_refused"})
        raise CapabilityUnavailable("Vision is not authorized in this rehearsal")


def validate_limits(chat: int, embedding: int) -> None:
    if type(chat) is not int or not 1 <= chat <= 15:
        raise ValueError("Chat request ceiling must be between 1 and 15")
    if type(embedding) is not int or not 0 <= embedding <= 15:
        raise ValueError("Embedding request ceiling must be between 0 and 15")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared-root", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8128)
    parser.add_argument("--max-model-requests", type=int, required=True)
    parser.add_argument("--enable-model-requests", action="store_true", required=True)
    parser.add_argument("--catalog-index", type=Path)
    parser.add_argument("--max-embedding-requests", type=int, default=0)
    parser.add_argument("--enable-embedding-requests", action="store_true")
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    args = parser.parse_args(argv)
    try:
        validate_limits(args.max_model_requests, args.max_embedding_requests)
    except ValueError as error:
        parser.error(str(error))
    dense_enabled = args.max_embedding_requests > 0
    if dense_enabled != args.enable_embedding_requests or dense_enabled != bool(args.catalog_index):
        parser.error(
            "Hybrid rehearsal requires an index, positive embedding budget and embedding opt-in"
        )
    if not 1024 <= args.port <= 65535:
        parser.error("Port must be between 1024 and 65535")
    try:
        return serve(args)
    except Exception:
        # Never expose configuration values, source paths, prompts or transport errors.
        print(json.dumps({"ready": False, "error": "configuration_or_runtime_unavailable"}))
        return 2


def serve(args: argparse.Namespace) -> int:
    config = literal_config(args.env_file)
    approved_base_url(config.base_url)
    # Observed Kloudeks completions can take several minutes; bound, never unlimited.
    if config.max_attempts != 1 or not 1 <= config.request_timeout <= 900:
        raise ValueError("Rehearsal requires one attempt and a finite timeout up to 900 seconds")
    catalog_bytes = read_catalog(args.catalog.absolute())
    snapshot = load_reviewed_snapshot(catalog_bytes)
    index = None
    if args.catalog_index:
        require_model(config.embedding_model)
        index = LocalCatalogIndex.open(
            args.catalog_index.absolute(), snapshot, profile_for(RUNTIME_QUERY_POLICY, "kloudeks")
        )
    ledger = args.ledger.absolute()
    ledger.parent.mkdir(parents=True, exist_ok=True)
    # Preserve prior evidence; choose a fresh --ledger path for each new run.
    with ledger.open("x", encoding="utf-8") as stream:
        stream.write(
            json.dumps(
                {
                    "run": "started",
                    "chat_limit": args.max_model_requests,
                    "embedding_limit": args.max_embedding_requests,
                    "timeout_seconds": config.request_timeout,
                    "max_attempts": 1,
                    "catalog_retrieval": "hybrid" if index is not None else "lexical",
                    "catalog_snapshot": snapshot.content_sha256,
                }
            )
            + "\n"
        )
    with KloudeksProvider(config) as provider, record_gate_outcomes(ledger):
        budget = RequestBudget(
            provider, args.max_model_requests, ledger, embedding_limit=args.max_embedding_requests
        )
        dense = (
            None
            if index is None
            else CatalogDenseStage(
                index, query_embedder(budget, RUNTIME_QUERY_POLICY, origin="kloudeks")
            )
        )
        runner = PreparedRunner(
            budget,
            args.prepared_root.absolute(),
            args.state_root.absolute(),
            catalog_bytes=catalog_bytes,
            catalog_dense=dense,
            redactions=(config.credential.get_secret_value(),),
        )
        service = AnalysisService(runner, mode="kloudeks", selected_runner=runner.selected)
        try:
            app = create_app(service, port=args.port, prepared=runner.status)
            print(
                json.dumps(
                    {
                        "ready": True,
                        "port": args.port,
                        "limit": args.max_model_requests,
                        "embedding_limit": args.max_embedding_requests,
                        "catalog_retrieval": "hybrid" if index is not None else "lexical",
                    }
                )
            )
            uvicorn.run(
                app,
                host="127.0.0.1",
                port=args.port,
                workers=1,
                access_log=False,
                proxy_headers=False,
                log_level="warning",
                limit_concurrency=32,
                timeout_keep_alive=5,
            )
        finally:
            service.close()
            record(
                ledger,
                {
                    "run": "stopped",
                    "chat_used": budget.used,
                    "embedding_used": budget.embedding_used,
                },
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
