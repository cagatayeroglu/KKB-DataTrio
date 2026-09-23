"""Explicit operator startup: read-only readiness or a loopback Kloudeks service."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path

import uvicorn

from kkb_agent.api.app import create_app
from kkb_agent.api.knowledge_service import KnowledgeService
from kkb_agent.api.prepared import PreparedRunner, _local, inspect_pool, read_catalog
from kkb_agent.api.service import AnalysisService
from kkb_agent.api.store import DATABASE_NAME as STORE_NAME
from kkb_agent.api.store import ConversationStore
from kkb_agent.catalog.directory import source_directory
from kkb_agent.catalog.discovered import DiscoveredStore
from kkb_agent.catalog.mappings import ReviewedSnapshot, load_reviewed_snapshot
from kkb_agent.ingest.acquisition import AcquisitionStore, OfficialSources
from kkb_agent.ingest.safe_fetch import safe_fetch
from kkb_agent.knowledge import DATABASE_NAME as KNOWLEDGE_NAME
from kkb_agent.knowledge import KnowledgeStore
from kkb_agent.llm import KloudeksProvider, ProviderConfig, approved_base_url
from kkb_agent.tools.searxng import SearxngBackend, is_loopback_instance, loopback_fetch

MAX_REQUEST_TIMEOUT = 1800.0
#: Fetched official responses, kept for later conversations (DEC-159).
ACQUIRED_DIRECTORY = "acquired"
#: EVDS series lists read from the source's own directory, one file per datagroup (DEC-177).
DISCOVERED_DIRECTORY = "directory/evds"
#: Built vector generations, one immutable directory per catalogue digest.
GENERATIONS_DIRECTORY = "catalog-index"


def _reported[T](embed: Callable[[str], T]) -> Callable[[str], T]:
    """The query embedder, saying on the console why a question's vector was not made.

    A failed query vector turns the search into words alone, and the search says only
    `embedding_failed`: its contract names no cause, and the page and the turn read that
    contract strictly. Live 2026-09-23, right after a full rebuild, every new query fell
    back that way while the same request from another process came back in 0.2 s; there
    was nothing to tell a timeout from a refusal. One line per failure: the error's class,
    the provider's own fixed wording (never a body, a key or the question) and the time.
    """

    def call(text: str) -> T:
        began = time.perf_counter()
        try:
            return embed(text)
        except Exception as error:
            print(
                json.dumps(
                    {
                        "query_embedding_failed": type(error).__name__,
                        "detail": str(error)[:160],
                        "seconds": round(time.perf_counter() - began, 2),
                    }
                ),
                flush=True,
            )
            raise

    return call


def literal_config(path: Path | None) -> ProviderConfig:
    """Optional operator-local settings, not shell/Python interpolation or global env edits."""
    values = {key: value for key, value in os.environ.items() if key.startswith("KLOUDEKS_")}
    if path is not None:
        with _local(path.absolute()).open("rb") as source:
            content = source.read(64 * 1024 + 1)
        if len(content) > 64 * 1024:
            raise ValueError("Configuration file exceeds its budget")
        seen: set[str] = set()
        for line in content.decode("utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.fullmatch(r"(KLOUDEKS_[A-Z_]+)\s*=\s*(.*)", line)
            if match is None:
                if line.startswith("KLOUDEKS_"):
                    raise ValueError("Malformed Kloudeks setting")
                continue
            key, value = match.groups()
            if key in seen:
                raise ValueError("Duplicate Kloudeks setting")
            seen.add(key)
            if value.startswith(('"', "'")):
                if len(value) < 2 or value[-1] != value[0]:
                    raise ValueError("Unsupported quoted setting")
                value = value[1:-1]
            else:
                value = value.split(" #", 1)[0].rstrip()
            values[key] = value  # Explicit file takes precedence; never evaluate it.
    return ProviderConfig.from_env(values)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="KKB prepared local API; no source fetching unless --enable-web-url"
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--check", action="store_true", help="Read-only readiness; never call a model"
    )
    action.add_argument(
        "--serve", action="store_true", help="Serve locally after explicit enablement"
    )
    parser.add_argument("--prepared-root", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, help="Optional literal Kloudeks settings file")
    parser.add_argument("--state-root", type=Path)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--catalog-index",
        type=Path,
        help="Optional local catalog index generation built with the DEC-142 query policy",
    )
    parser.add_argument("--enable-model-requests", action="store_true")
    parser.add_argument(
        "--no-uploads",
        action="store_true",
        help=(
            "Refuse CSV/XLSX/PDF/HTML uploads attached to a question. They are admitted "
            "by default: each one passes the same admission checks and is stored by "
            "reference, never by its name"
        ),
    )
    parser.add_argument(
        "--enable-web-url",
        action="store_true",
        help="Let questions read a web address they contain, through safe fetch; off by default",
    )
    parser.add_argument(
        "--no-official-acquisition",
        action="store_true",
        help=(
            "Refuse to fetch a reviewed EVDS series or BDDK selector the prepared pool lacks. "
            "Acquisition is on by default (DEC-155, DEC-159): reviewed routes only, fixed "
            "windows, at most twelve a turn, and fetched responses are kept under the state "
            "root for later conversations"
        ),
    )
    parser.add_argument(
        "--no-source-directory",
        action="store_true",
        help=(
            "Search only the reviewed catalogue. By default the sources' own pinned listings "
            "(DEC-176: the BDDK monthly bulletin's tables and rows) are a second catalogue "
            "tier, searched after the reviewed one and fetched on first use by the same "
            "adapters. The vectors must be built once for the larger catalogue"
        ),
    )
    parser.add_argument(
        "--allow-catalog-edits",
        action="store_true",
        help=(
            "Let the knowledge page archive, alias or describe reviewed and listed catalogue "
            "entries. Such a note changes every browser's searches and turns, so it is the "
            "operator's decision (DEC-162): without this flag every browser key reads the "
            "catalogue notes but none may change them; with it, any browser key of this local "
            "installation may, and every edit records its author"
        ),
    )
    parser.add_argument(
        "--searxng-url",
        help=(
            "Register web_search over this publicly reachable SearXNG instance's JSON API "
            "(DEC-158), read through safe_fetch. Results are untrusted discovery metadata "
            "and never authorize web_url; off when absent"
        ),
    )
    parser.add_argument(
        "--searxng-loopback",
        action="store_true",
        help=(
            "The --searxng-url instance is the operator's own on this machine "
            "(http://127.0.0.1:PORT, for example the documented Docker container). Only then "
            "is that one address read over loopback (DEC-180); every address a question or a "
            "page names still goes through safe_fetch, which refuses loopback"
        ),
    )
    parser.add_argument(
        "--trust-loop",
        action="store_true",
        help=(
            "Answer each question with one model-driven loop instead of the planned "
            "turn: the model calls tools, reads what they returned, decides again, and "
            "says when it has enough. The harness dispatches and counts; it does not "
            "decide the order, the phase or when the question is answered"
        ),
    )
    parser.add_argument(
        "--no-ocr",
        action="store_true",
        help=(
            "Refuse to OCR PDF pages without a text layer. OCR follows its configuration: "
            "on when the DEC-129 OCR model is configured, off when it is not, so there is "
            "no second switch to forget. Read tables still count only when their columns "
            "add up (DEC-149)"
        ),
    )
    args = parser.parse_args(argv)
    if args.serve and (not args.enable_model_requests or args.state_root is None):
        parser.error("--serve requires --enable-model-requests and --state-root")
    if args.check and args.enable_model_requests:
        parser.error("--check does not enable model requests")
    if not 1024 <= args.port <= 65535:
        parser.error("--port must be between 1024 and 65535")
    service = None
    try:
        # absolute() preserves links so the preparation boundary can reject them.
        root, catalog_path = args.prepared_root.absolute(), args.catalog.absolute()
        catalog_bytes = read_catalog(catalog_path)
        config = literal_config(args.env_file)
        approved_base_url(config.base_url)
        # Bounded, not unlimited. Live completions took up to 207 s on 2026-09-15; on
        # 2026-09-19 the platform decoded 7-11.5 tokens a second, so a 7-8k-token plan
        # outlived the former 900 s ceiling (4 of 70 calls lost). Attempts only re-ask a
        # malformed answer (complete_with_repair); a timed-out request is never retried.
        if (
            not math.isfinite(config.request_timeout)
            or not 1 <= config.request_timeout <= MAX_REQUEST_TIMEOUT
            or not 1 <= config.max_attempts <= 3
        ):
            raise ValueError("Local service provider budget refused")
        # A capability follows its configuration: OCR is on because a model for it is
        # configured, not because a second flag was remembered. --no-ocr still refuses it.
        ocr_enabled = config.ocr_model is not None and not args.no_ocr
        uploads_enabled = not args.no_uploads
        # Describing a picture needs the chat model, not the OCR one. Live 2026-09-20
        # this deployment had KLOUDEKS_VISION_MODEL pointing at Unlimited-OCR, whose
        # answer to "describe this chart" was "2025 chart [27, 114, 977, 956]": layout,
        # not meaning. Pointed at the chat model the same picture came back read.
        vision_enabled = (
            config.vision_model is not None
            and config.vision_model != config.ocr_model
            and uploads_enabled
        )
        acquisition_enabled = not args.no_official_acquisition
        if args.searxng_loopback and not (
            args.searxng_url and is_loopback_instance(args.searxng_url)
        ):
            parser.error("--searxng-loopback needs --searxng-url http://127.0.0.1:PORT")
        search = None
        if args.searxng_url:
            search = (
                SearxngBackend(args.searxng_url, fetch=loopback_fetch)
                if args.searxng_loopback
                else SearxngBackend(args.searxng_url)
            )
        snapshot = load_reviewed_snapshot(catalog_bytes)
        index = None
        if args.catalog_index is not None:
            # Native vector engine loads only for an explicitly configured index.
            from kkb_agent.catalog.embedding import RUNTIME_QUERY_POLICY, profile_for, require_model
            from kkb_agent.catalog.lance_index import LocalCatalogIndex

            require_model(config.embedding_model)
            index = LocalCatalogIndex.open(
                args.catalog_index.absolute(),
                snapshot,
                profile_for(RUNTIME_QUERY_POLICY, "kloudeks"),
            )
        retrieval = "lexical" if index is None else "hybrid"
        if args.check:
            status = inspect_pool(root, snapshot)
            print(
                json.dumps(
                    {
                        "ready": True,
                        "model_checked": False,
                        "provider_configured": True,
                        "catalog_retrieval": retrieval,
                        "web_url": args.enable_web_url,
                        "uploads": uploads_enabled,
                        "ocr": ocr_enabled,
                        "vision": vision_enabled,
                        "official_acquisition": acquisition_enabled,
                        "web_search": search is not None,
                        "prepared": status.model_dump(mode="json"),
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        with KloudeksProvider(config) as provider:
            dense = None
            if index is not None:
                from kkb_agent.catalog.embedding import RUNTIME_QUERY_POLICY, query_embedder
                from kkb_agent.catalog.hybrid import CatalogDenseStage

                dense = CatalogDenseStage(
                    index,
                    _reported(query_embedder(provider, RUNTIME_QUERY_POLICY, origin="kloudeks")),
                )
            # Conversations, their messages and uploads outlive this process.
            store = ConversationStore(args.state_root.absolute() / STORE_NAME)
            acquired = (
                AcquisitionStore(args.state_root.absolute() / ACQUIRED_DIRECTORY)
                if acquisition_enabled
                else None
            )
            official = OfficialSources(store=acquired) if acquisition_enabled else None
            # The editable knowledge base over the reviewed catalog (DEC-157).
            knowledge = KnowledgeStore(args.state_root.absolute() / KNOWLEDGE_NAME)
            # The sources' own listings as a second catalogue tier (DEC-176), unless refused.
            # The series lists of the EVDS datagroups a search has opened, and the datagroups
            # a refresh found after the pin (DEC-177). Without official fetching nothing
            # opens a datagroup, so nothing is kept.
            discovered = (
                DiscoveredStore(args.state_root.absolute() / DISCOVERED_DIRECTORY)
                if not args.no_source_directory and acquisition_enabled
                else None
            )
            directory = (
                None
                if args.no_source_directory
                else source_directory(discovered.supplement() if discovered is not None else ())
            )
            runner = PreparedRunner(
                provider,
                root,
                args.state_root.absolute(),
                catalog_bytes=catalog_bytes,
                trust_loop=args.trust_loop,
                redactions=(config.credential.get_secret_value(),),
                catalog_dense=dense,
                web_url_fetch=safe_fetch if args.enable_web_url else None,
                document_uploads=uploads_enabled,
                document_ocr=provider if ocr_enabled else None,
                document_vision=vision_enabled,
                store=store,
                official=official,
                knowledge=knowledge,
                search_backend=search,
                source_directory=directory,
                discovered=discovered,
            )
            service = AnalysisService(
                runner,
                mode="kloudeks",
                selected_runner=runner.selected,
                document_store=runner.admit_document if uploads_enabled else None,
                url_document_store=(
                    runner.admit_document_from_url
                    if uploads_enabled and args.enable_web_url
                    else None
                ),
                store=store,
                ocr=ocr_enabled,
                official_acquisition=acquisition_enabled,
                knowledge=True,
                web_search=search is not None,
                web_url=args.enable_web_url,
                model=config.planner_model,
                models=config.chat_models,
                stored_result=runner.published_result,
                session_cleanup=runner.delete_session,
            )
            rebuild = reopen = None
            if index is not None:
                from kkb_agent.catalog.embedding import (
                    RUNTIME_QUERY_POLICY,
                    EmbeddingStats,
                    embed_catalog,
                    profile_for,
                    query_embedder,
                )
                from kkb_agent.catalog.hybrid import CatalogDenseStage
                from kkb_agent.catalog.lance_index import LocalCatalogIndex, build_catalog_index

                generations = args.state_root.absolute() / GENERATIONS_DIRECTORY

                def reopen(catalog: ReviewedSnapshot) -> CatalogDenseStage | None:
                    """The generation already on disk for exactly this catalogue, if any."""
                    directory = generations / catalog.content_sha256
                    if not (directory / "catalog-manifest.json").exists():
                        return None
                    return CatalogDenseStage(
                        LocalCatalogIndex.open(
                            directory, catalog, profile_for(RUNTIME_QUERY_POLICY, "kloudeks")
                        ),
                        _reported(
                            query_embedder(provider, RUNTIME_QUERY_POLICY, origin="kloudeks")
                        ),
                    )

                def rebuild(
                    catalog: ReviewedSnapshot, previous: LocalCatalogIndex | None
                ) -> CatalogDenseStage:
                    """A generation for exactly this catalogue, with the configured profile.

                    Generations are immutable and named by the catalogue they cover,
                    so an earlier one is reopened instead of embedded again, and a
                    failed build never damages the one in use. An entry whose text the
                    generation in use embedded under this same profile keeps its vector;
                    only new or changed entries are embedded.
                    """
                    existing = reopen(catalog)
                    if existing is not None:
                        return existing
                    began = time.perf_counter()
                    stats = EmbeddingStats()
                    vectors = embed_catalog(
                        provider,
                        catalog,
                        RUNTIME_QUERY_POLICY,
                        origin="kloudeks",
                        stats=stats,
                        reuse=previous,
                    )
                    build_catalog_index(generations / catalog.content_sha256, catalog, vectors)
                    built = reopen(catalog)
                    if built is None:  # pragma: no cover - the build above wrote it
                        raise ValueError("generation was not written")
                    # Counts and seconds only: what the build cost, never what it read.
                    print(
                        json.dumps(
                            {
                                "catalog_index_built": catalog.content_sha256[:12],
                                "entries": len(vectors.vectors),
                                "embedded": stats.texts,
                                "reused": stats.reused,
                                "embedding_requests": stats.requests,
                                "embedding_seconds": round(stats.seconds, 1),
                                "seconds": round(time.perf_counter() - began, 1),
                            }
                        ),
                        flush=True,
                    )
                    return built

            knowledge_service = KnowledgeService(
                knowledge,
                store,
                runner.catalog,
                prepared=frozenset(item.series_id for item in runner.status.series),
                acquisition=acquisition_enabled,
                read_document_column=runner.document_column if uploads_enabled else None,
                acquisitions=acquired.acquisitions if acquired is not None else None,
                series_values=runner.series_values,
                dense=dense,
                rebuild_index=rebuild,
                install_index=runner.use_dense,
                reopen_index=reopen,
                source_directory=directory,
                discovered=discovered,
                install_directory=runner.use_directory,
                catalog_edits=args.allow_catalog_edits,
            )
            # The one direction back into the runner: the knowledge base's own
            # validated write, so a conversation's save is the page's save (DEC-183).
            runner.use_promotion(knowledge_service.promote)
            # No model call: a generation built before this restart is simply opened.
            knowledge_service.restore_generation()
            app = create_app(
                service, port=args.port, prepared=runner.status, knowledge=knowledge_service
            )
            print(
                json.dumps(
                    {
                        "ready": True,
                        "host": "127.0.0.1",
                        "port": args.port,
                        "model_checked": False,
                        "catalog_retrieval": retrieval,
                        "web_url": args.enable_web_url,
                        "uploads": uploads_enabled,
                        "ocr": ocr_enabled,
                        "vision": vision_enabled,
                        "official_acquisition": acquisition_enabled,
                        "web_search": search is not None,
                        "conversations": "persistent",
                        "prepared_identities": runner.status.prepared_identities,
                    }
                )
            )
            try:
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
                # A failed server startup must also finish admitted work before
                # closing its shared provider transport.
                service.close()
        return 0
    except Exception:
        # Settings/paths/provider messages can include operator-local context.
        print(json.dumps({"ready": False, "error": "configuration_or_runtime_unavailable"}))
        return 2
    finally:
        if service is not None:
            service.close()


if __name__ == "__main__":
    sys.exit(main())
