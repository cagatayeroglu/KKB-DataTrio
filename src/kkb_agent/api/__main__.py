"""Explicit operator startup: read-only readiness or a loopback Kloudeks service."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections.abc import Sequence
from pathlib import Path

import uvicorn

from kkb_agent.api.app import create_app
from kkb_agent.api.prepared import PreparedRunner, _local, inspect_pool, read_catalog
from kkb_agent.api.service import AnalysisService
from kkb_agent.api.store import DATABASE_NAME as STORE_NAME
from kkb_agent.api.store import ConversationStore
from kkb_agent.catalog.mappings import load_reviewed_snapshot
from kkb_agent.ingest.safe_fetch import safe_fetch
from kkb_agent.llm import KloudeksProvider, ProviderConfig, approved_base_url

MAX_REQUEST_TIMEOUT = 900.0


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
        "--enable-uploads",
        action="store_true",
        help="Accept CSV/XLSX/PDF/HTML uploads attached to one question; off by default",
    )
    parser.add_argument(
        "--enable-web-url",
        action="store_true",
        help="Let questions read a web address they contain, through safe fetch; off by default",
    )
    parser.add_argument(
        "--enable-ocr",
        action="store_true",
        help=(
            "OCR PDF pages without a text layer through the DEC-129 OCR model; tables count "
            "only when their columns add up (DEC-149); off by default"
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
        # Live Kloudeks completions took up to 207 s on 2026-09-15; bounded, not unlimited.
        if (
            not math.isfinite(config.request_timeout)
            or not 1 <= config.request_timeout <= MAX_REQUEST_TIMEOUT
            or not 1 <= config.max_attempts <= 3
        ):
            raise ValueError("Local service provider budget refused")
        if args.enable_ocr and config.ocr_model is None:
            raise ValueError("OCR needs the DEC-129 OCR model configured")
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
                        "uploads": args.enable_uploads,
                        "ocr": args.enable_ocr,
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
                    index, query_embedder(provider, RUNTIME_QUERY_POLICY, origin="kloudeks")
                )
            # Conversations, their messages and uploads outlive this process.
            store = ConversationStore(args.state_root.absolute() / STORE_NAME)
            runner = PreparedRunner(
                provider,
                root,
                args.state_root.absolute(),
                catalog_bytes=catalog_bytes,
                redactions=(config.credential.get_secret_value(),),
                catalog_dense=dense,
                web_url_fetch=safe_fetch if args.enable_web_url else None,
                document_uploads=args.enable_uploads,
                document_ocr=provider if args.enable_ocr else None,
                store=store,
            )
            service = AnalysisService(
                runner,
                mode="kloudeks",
                selected_runner=runner.selected,
                document_store=runner.admit_document if args.enable_uploads else None,
                store=store,
            )
            app = create_app(service, port=args.port, prepared=runner.status)
            print(
                json.dumps(
                    {
                        "ready": True,
                        "host": "127.0.0.1",
                        "port": args.port,
                        "model_checked": False,
                        "catalog_retrieval": retrieval,
                        "web_url": args.enable_web_url,
                        "uploads": args.enable_uploads,
                        "ocr": args.enable_ocr,
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
