"""Explicit Qwen3 embedding input policies and catalog/query embedding (M13-05).

Policies are named, reviewed declarations, never defaults. `qwen3-plain-v1` sends
normalized text unchanged for passages and queries. `qwen3-instruct-query-v1`
follows the Qwen3-Embedding model card convention: passages unchanged, queries as
``Instruct: <task>\\nQuery:<text>``. Kloudeks has not answered Q-K-05, so both are
measured rather than assumed. Only an operator-constructed LLMProvider is called;
no endpoint, credential or hosted fallback is chosen here.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from kkb_agent.catalog.lance_index import build_catalog_index
from kkb_agent.catalog.mappings import ReviewedSnapshot, load_reviewed_snapshot
from kkb_agent.catalog.vectors import (
    DIMENSION,
    CatalogVectors,
    QueryVector,
    SeriesVector,
    VectorProfile,
    catalog_documents,
)
from kkb_agent.llm.provider import LLMProvider, ProviderError

MODEL: Literal["kkbhackathon2026/Qwen3-Embedding-8B"] = "kkbhackathon2026/Qwen3-Embedding-8B"
TASK = (
    "Given a Turkish or English question about financial or economic data, "
    "retrieve the official statistical time series that answers it"
)
Origin = Literal["offline_fixture", "kloudeks"]


@dataclass(frozen=True, slots=True)
class InputPolicy:
    policy_id: str
    passage: Callable[[str], str]
    query: Callable[[str], str]


POLICIES = {
    "qwen3-plain-v1": InputPolicy("qwen3-plain-v1", lambda text: text, lambda text: text),
    "qwen3-instruct-query-v1": InputPolicy(
        "qwen3-instruct-query-v1",
        lambda text: text,
        lambda text: f"Instruct: {TASK}\nQuery:{text}",
    ),
}


def policy(policy_id: str) -> InputPolicy:
    try:
        return POLICIES[policy_id]
    except KeyError:
        raise ValueError("unknown embedding input policy") from None


def profile_for(policy_id: str, origin: Origin) -> VectorProfile:
    return VectorProfile(
        model=MODEL, dimension=4096, input_policy_id=policy(policy_id).policy_id, origin=origin
    )


def _checked(vectors: list[list[float]], expected: int) -> list[tuple[float, ...]]:
    if len(vectors) != expected or any(len(vector) != DIMENSION for vector in vectors):
        raise ProviderError("embedding count or dimension does not match the request")
    return [tuple(vector) for vector in vectors]


@dataclass
class EmbeddingStats:
    requests: int = 0
    texts: int = 0
    seconds: float = 0.0


def embed_catalog(
    provider: LLMProvider,
    snapshot: ReviewedSnapshot,
    policy_id: str,
    *,
    origin: Origin,
    batch_size: int = 16,
    stats: EmbeddingStats | None = None,
) -> CatalogVectors:
    """One vector per reviewed catalog document, in stable ID order."""
    if type(batch_size) is not int or not 1 <= batch_size <= 64:
        raise ValueError("batch size must be between 1 and 64")
    chosen = policy(policy_id)
    documents = catalog_documents(snapshot)
    stats = stats if stats is not None else EmbeddingStats()
    values: list[tuple[float, ...]] = []
    for start in range(0, len(documents), batch_size):
        batch = documents[start : start + batch_size]
        began = time.perf_counter()
        vectors = provider.embed([chosen.passage(item.text) for item in batch], kind="passage")
        stats.seconds += time.perf_counter() - began
        stats.requests += 1
        stats.texts += len(batch)
        values.extend(_checked(vectors, len(batch)))
    return CatalogVectors(
        snapshot_sha256=snapshot.content_sha256,
        profile=profile_for(policy_id, origin),
        vectors=tuple(
            SeriesVector(series_id=item.series_id, text_sha256=item.text_sha256, values=vector)
            for item, vector in zip(documents, values, strict=True)
        ),
    )


def query_embedder(
    provider: LLMProvider,
    policy_id: str,
    *,
    origin: Origin,
    stats: EmbeddingStats | None = None,
) -> Callable[[str], QueryVector]:
    """Embed normalized query text under the declared policy; repeated text is cached."""
    chosen = policy(policy_id)
    profile = profile_for(policy_id, origin)
    stats = stats if stats is not None else EmbeddingStats()
    cache: dict[str, QueryVector] = {}

    def embed(text: str) -> QueryVector:
        if text not in cache:
            began = time.perf_counter()
            vectors = provider.embed([chosen.query(text)], kind="query")
            stats.seconds += time.perf_counter() - began
            stats.requests += 1
            stats.texts += 1
            cache[text] = QueryVector(profile=profile, values=_checked(vectors, 1)[0])
        return cache[text]

    return embed


def main(argv: Sequence[str] | None = None) -> int:
    """Build a real local catalog index generation; makes embedding requests."""
    parser = argparse.ArgumentParser(description="Build a Kloudeks catalog index generation")
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--policy", choices=sorted(POLICIES), required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--enable-embedding-requests", action="store_true", required=True)
    args = parser.parse_args(argv)
    from kkb_agent.api.__main__ import literal_config
    from kkb_agent.llm import KloudeksProvider, approved_base_url

    snapshot = load_reviewed_snapshot(args.catalog.absolute().read_bytes())
    config = literal_config(args.env_file)
    approved_base_url(config.base_url)
    stats = EmbeddingStats()
    with KloudeksProvider(config) as provider:
        vectors = embed_catalog(
            provider,
            snapshot,
            args.policy,
            origin="kloudeks",
            batch_size=args.batch_size,
            stats=stats,
        )
    build_catalog_index(args.root.absolute(), snapshot, vectors)
    print(
        json.dumps(
            {
                "built": True,
                "policy": args.policy,
                "snapshot_sha256": snapshot.content_sha256,
                "documents": len(vectors.vectors),
                "embedding_requests": stats.requests,
                "embedding_seconds": round(stats.seconds, 3),
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
