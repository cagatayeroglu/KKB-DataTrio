"""FastAPI app factory with a local-only, bounded ASGI ingress boundary."""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, Header, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from kkb_agent.api.contracts import (
    MAX_BODY_BYTES,
    MAX_DOCUMENT_BYTES,
    ConversationDeleted,
    ConversationDetail,
    ConversationList,
    ConversationSummary,
    ConversationUpdate,
    DatasetDetail,
    DatasetRequest,
    DirectoryRefreshResult,
    DocumentAdmitted,
    DocumentFromUrl,
    Error,
    ErrorCode,
    Feedback,
    FeedbackList,
    FeedbackRequest,
    Health,
    KnowledgeList,
    OwnerCreated,
    PromptParts,
    Question,
    Reference,
    Result,
    RunDetail,
    RunList,
    RunProgress,
    RunsDeleted,
    RuntimeSettings,
    SearchTrial,
    SeriesIdentity,
    SeriesNoteHistory,
    SeriesNoteRequest,
    SeriesUses,
    SeriesValues,
    SessionCreated,
    SettingsUpdate,
    Slug,
    TraceConversationList,
    TraceStepFull,
    Turn,
    VectorIndexStatus,
)
from kkb_agent.api.knowledge_service import KnowledgeService
from kkb_agent.api.prepared import PreparedStatus
from kkb_agent.api.prompts import prompt_parts
from kkb_agent.api.service import AnalysisService, ServiceError
from kkb_agent.core.models import ContractModel
from kkb_agent.ingest.fetched import DOCUMENT_MEDIA_TYPES

Token = Annotated[str, Header(alias="X-KKB-Session-Token", min_length=43, max_length=43)]
#: The browser's own key: it lists and reopens the conversations it created.
OwnerToken = Annotated[str, Header(alias="X-KKB-Owner-Token", min_length=43, max_length=43)]
#: The only route whose body is not JSON (M10-04); every other POST stays JSON-only.
DOCUMENT_ROUTE = re.compile(r"/v1/sessions/[a-f0-9]{32}/documents\Z")
#: The one JSON route allowed a larger body: a knowledge-base dataset (DEC-157).
KNOWLEDGE_DATASET_ROUTE = re.compile(r"/v1/knowledge/datasets\Z")
MAX_KNOWLEDGE_BODY_BYTES = 1024 * 1024
#: The two routes with a query string: listing a browser's own conversations, and
#: trying a question against its own catalogue.
LIST_ROUTE = re.compile(r"/v1/conversations\Z")
TRACE_LIST_ROUTE = re.compile(r"/v1/trace-conversations\Z")
SEARCH_ROUTE = re.compile(r"/v1/knowledge/search\Z")
#: The knowledge list takes its tab, province, search text and page as a query string.
KNOWLEDGE_LIST_ROUTE = re.compile(r"/v1/knowledge\Z")
MAX_QUERY_BYTES = 1024
#: Methods that may carry a body; a body anywhere else is refused.
BODY_METHODS = ("POST", "PATCH")


class Empty(ContractModel):
    pass


def failure(code: ErrorCode, status: int) -> JSONResponse:
    return JSONResponse(Error(error=code).model_dump(), status_code=status)


class LocalBoundary:
    """Body limits before JSON parsing, fixed Host/Origin and non-cacheable output.

    This is not public-host authentication. Launch on loopback only until the
    separately reviewed deployment/auth boundary exists. Forwarded headers never
    alter these accepted origins. No wildcard CORS, cookies or query credentials.
    """

    def __init__(self, app: ASGIApp, *, port: int = 8000):
        if type(port) is not int or not 1024 <= port <= 65535:
            raise ValueError("Invalid local port")
        self.app = app
        self.hosts = {f"localhost:{port}", f"127.0.0.1:{port}"}
        self.origins = {"http://" + host for host in self.hosts}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers: dict[bytes, list[bytes]] = {}
        for name, value in scope["headers"]:
            headers.setdefault(name.lower(), []).append(value)
        response_started = False

        async def guarded_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                message = dict(message)
                message["headers"] = [
                    *message.get("headers", []),
                    (b"cache-control", b"no-store"),
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
                ]
            await send(message)

        async def reject(code: ErrorCode, status: int) -> None:
            await failure(code, status)(scope, receive, guarded_send)

        try:
            host = headers.get(b"host", [])
            origin = headers.get(b"origin", [])
            if (
                len(host) != 1
                or host[0].decode("ascii") not in self.hosts
                or len(origin) > 1
                or (origin and origin[0].decode("ascii") not in self.origins)
                or headers.get(b"sec-fetch-site") == [b"cross-site"]
            ):
                await reject("forbidden", 403)
                return
            query = scope.get("query_string") or b""
            queried = scope["method"] == "GET" and bool(
                LIST_ROUTE.fullmatch(scope["path"])
                or TRACE_LIST_ROUTE.fullmatch(scope["path"])
                or SEARCH_ROUTE.fullmatch(scope["path"])
                or KNOWLEDGE_LIST_ROUTE.fullmatch(scope["path"])
            )
            if (query and not (queried and len(query) <= MAX_QUERY_BYTES)) or any(
                len(headers.get(key, [])) > 1
                for key in (
                    b"content-length",
                    b"content-type",
                    b"x-kkb-session-token",
                    b"x-kkb-owner-token",
                    b"last-event-id",
                )
            ):
                await reject("invalid_request", 400)
                return
            document = scope["method"] == "POST" and bool(DOCUMENT_ROUTE.fullmatch(scope["path"]))
            dataset = scope["method"] == "POST" and bool(
                KNOWLEDGE_DATASET_ROUTE.fullmatch(scope["path"])
            )
            limit = (
                MAX_DOCUMENT_BYTES
                if document
                else MAX_KNOWLEDGE_BODY_BYTES
                if dataset
                else MAX_BODY_BYTES
            )
            declared = int(headers.get(b"content-length", [b"0"])[0])
            if declared < 0 or declared > limit:
                await reject("body_too_large", 413)
                return
            media_type = (
                headers.get(b"content-type", [b""])[0].split(b";", 1)[0].strip().lower().decode()
            )
            if scope["method"] in BODY_METHODS and (
                media_type not in DOCUMENT_MEDIA_TYPES
                if document
                else media_type != "application/json"
            ):
                await reject("invalid_request", 415)
                return
        except (UnicodeError, ValueError):
            await reject("invalid_request", 400)
            return
        body = bytearray()
        try:
            async with asyncio.timeout(30 if document or dataset else 5):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    if len(body) + len(chunk) > limit:
                        await reject("body_too_large", 413)
                        return
                    body.extend(chunk)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            await reject("invalid_request", 408)
            return
        if scope["method"] not in BODY_METHODS and body:
            await reject("invalid_request", 400)
            return
        sent = False

        async def buffered_receive() -> Message:
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        try:
            await self.app(scope, buffered_receive, guarded_send)
        except Exception:
            # Do not bubble raw exception text into the ASGI server's logger.
            # Once streaming started, close without fabricating a second response.
            if not response_started:
                await failure("internal_error", 500)(scope, receive, guarded_send)


def create_app(
    service: AnalysisService,
    *,
    port: int = 8000,
    prepared: PreparedStatus | None = None,
    knowledge: KnowledgeService | None = None,
) -> FastAPI:
    """No provider creation or model call; the operator supplies the runner."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await asyncio.to_thread(service.close)
            if knowledge is not None:
                # A vector build in progress finishes writing its generation.
                await asyncio.to_thread(knowledge.close)

    app = FastAPI(
        title="KKB DataTrio local API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        debug=False,
    )
    app.add_middleware(LocalBoundary, port=port)
    active_streams: set[str] = set()
    prepared_snapshot = (
        PreparedStatus.model_validate_json(prepared.model_dump_json()) if prepared else None
    )

    @app.exception_handler(ServiceError)
    async def service_error(request: Request, exc: ServiceError) -> JSONResponse:
        return failure(exc.code, exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # FastAPI's default includes the rejected input, which can contain secrets.
        return failure("invalid_request", 422)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        return failure(
            "not_found" if exc.status_code == 404 else "invalid_request", exc.status_code
        )

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception) -> JSONResponse:
        return failure("internal_error", 500)

    @app.get("/v1/health", response_model=Health)
    def health() -> Health:
        return service.health()

    @app.get("/v1/dataset", response_model=PreparedStatus)
    def dataset() -> PreparedStatus:
        service.health()
        if prepared_snapshot is None:
            raise ServiceError("unavailable", 503)
        return prepared_snapshot.model_copy(deep=True)

    @app.post("/v1/owner", response_model=OwnerCreated, status_code=201)
    def create_owner(body: Empty) -> OwnerCreated:
        return service.create_owner()

    @app.post("/v1/sessions", response_model=SessionCreated, status_code=201)
    def create_session(
        body: Empty,
        owner: Annotated[str | None, Header(alias="X-KKB-Owner-Token")] = None,
    ) -> SessionCreated:
        return service.create_session(owner)

    @app.get("/v1/conversations", response_model=ConversationList)
    def conversations(
        owner: OwnerToken,
        archived: bool = False,
        search: Annotated[str | None, Query(max_length=120)] = None,
    ) -> ConversationList:
        return service.conversations(owner, archived=archived, search=search)

    @app.get("/v1/trace-conversations", response_model=TraceConversationList)
    def trace_conversations(
        owner: OwnerToken,
        archived: bool = False,
        search: Annotated[str | None, Query(max_length=120)] = None,
    ) -> TraceConversationList:
        return service.trace_conversations(owner, archived=archived, search=search)

    @app.get("/v1/conversations/{session_id}", response_model=ConversationDetail)
    def conversation(session_id: Reference, token: Token) -> ConversationDetail:
        return service.conversation(session_id, token)

    @app.delete("/v1/conversations/{session_id}", response_model=ConversationDeleted)
    def delete_conversation(session_id: Reference, owner: OwnerToken) -> ConversationDeleted:
        service.delete_conversation(session_id, owner)
        return ConversationDeleted()

    @app.get("/v1/conversations/{session_id}/results/{turn_id}", response_model=Result)
    def stored_result(session_id: Reference, turn_id: Reference, token: Token) -> Result:
        # A published table read back from its receipt; nothing is recomputed.
        return service.stored_result(session_id, token, turn_id)

    @app.get("/v1/conversations/{session_id}/runs", response_model=RunList)
    def runs(session_id: Reference, token: Token) -> RunList:
        return service.runs(session_id, token)

    @app.delete("/v1/conversations/{session_id}/runs", response_model=RunsDeleted)
    def delete_runs(session_id: Reference, owner: OwnerToken) -> RunsDeleted:
        return RunsDeleted(deleted_runs=service.delete_runs(session_id, owner))

    @app.get("/v1/conversations/{session_id}/runs/{run_id}/progress", response_model=RunProgress)
    def run_progress(session_id: Reference, run_id: Reference, token: Token) -> RunProgress:
        # Followed while a turn runs: status and the newest step, no step text.
        return service.run_progress(session_id, run_id, token)

    @app.get("/v1/conversations/{session_id}/runs/{run_id}", response_model=RunDetail)
    def run(session_id: Reference, run_id: Reference, token: Token) -> RunDetail:
        # Reading a trace never starts work: it is a stored record, not a replay.
        return service.run(session_id, run_id, token)

    @app.get(
        "/v1/conversations/{session_id}/runs/{run_id}/steps/{sequence}",
        response_model=TraceStepFull,
    )
    def run_step(
        session_id: Reference,
        run_id: Reference,
        sequence: Annotated[int, Path(ge=1, le=100_000)],
        token: Token,
    ) -> TraceStepFull:
        return service.run_step(session_id, run_id, sequence, token)

    @app.post("/v1/conversations/{session_id}/feedback", response_model=Feedback, status_code=201)
    def rate(session_id: Reference, token: Token, body: FeedbackRequest) -> Feedback:
        return service.rate(session_id, token, body)

    @app.get("/v1/conversations/{session_id}/feedback", response_model=FeedbackList)
    def ratings(session_id: Reference, token: Token) -> FeedbackList:
        return service.ratings(session_id, token)

    @app.patch("/v1/conversations/{session_id}", response_model=ConversationSummary)
    def rename_or_archive(
        session_id: Reference, token: Token, body: ConversationUpdate
    ) -> ConversationSummary:
        return service.update_conversation(session_id, token, body)

    @app.post("/v1/sessions/{session_id}/turns", response_model=Turn, status_code=202)
    def submit(session_id: Reference, body: Question, token: Token) -> Turn:
        return service.submit(session_id, token, body)

    @app.post(
        "/v1/sessions/{session_id}/documents", response_model=DocumentAdmitted, status_code=201
    )
    async def document(session_id: Reference, request: Request, token: Token) -> DocumentAdmitted:
        # The boundary already bounded the body and allowed only document media types.
        media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        content = await request.body()
        return await asyncio.to_thread(
            service.admit_document, session_id, token, media_type, content
        )

    @app.get("/v1/sessions/{session_id}/turns/{turn_id}", response_model=Turn)
    def turn(session_id: Reference, turn_id: Reference, token: Token) -> Turn:
        return service.get_turn(session_id, token, turn_id)

    @app.post(
        "/v1/sessions/{session_id}/documents/from-url",
        response_model=DocumentAdmitted,
        status_code=201,
    )
    def document_from_url(
        session_id: Reference, body: DocumentFromUrl, token: Token
    ) -> DocumentAdmitted:
        # The address is the person's own request; the fetch obeys safe_fetch.
        return service.admit_document_from_url(session_id, token, body.url)

    def _knowledge() -> KnowledgeService:
        if knowledge is None:
            raise ServiceError("unavailable", 503)
        return knowledge

    @app.get("/v1/settings", response_model=RuntimeSettings)
    def settings(owner: OwnerToken) -> RuntimeSettings:
        return service.settings(owner)

    @app.patch("/v1/settings", response_model=RuntimeSettings)
    def update_settings(owner: OwnerToken, body: SettingsUpdate) -> RuntimeSettings:
        # A browser may narrow its own runtime; widening is not expressible here.
        return service.update_settings(owner, body)

    @app.get("/v1/prompts", response_model=PromptParts)
    def prompts(owner: OwnerToken) -> PromptParts:
        # The parts model calls are assembled from, with digests; never an editor.
        service.health()
        return prompt_parts()

    @app.get("/v1/knowledge", response_model=KnowledgeList)
    def knowledge_list(
        owner: OwnerToken,
        tab: Annotated[str, Query(max_length=16)] = "all",
        province: Annotated[str | None, Query(max_length=64)] = None,
        q: Annotated[str | None, Query(max_length=200)] = None,
        page: Annotated[int | None, Query(ge=1, le=1000)] = None,
        page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> KnowledgeList:
        # One page travels; the whole list no longer fits the bridge's response bound.
        return _knowledge().listing(
            owner, tab=tab, province=province, query=q, page=page, page_size=page_size
        )

    @app.get("/v1/knowledge/search", response_model=SearchTrial)
    def knowledge_search(
        owner: OwnerToken, q: Annotated[str, Query(min_length=1, max_length=512)]
    ) -> SearchTrial:
        # A trial runs the same catalogue search a turn runs, and stores nothing.
        return _knowledge().search(owner, q)

    @app.get("/v1/knowledge/index", response_model=VectorIndexStatus)
    def knowledge_index(owner: OwnerToken) -> VectorIndexStatus:
        # What the meaning-based stage holds; reading computes no vector.
        return _knowledge().index_status(owner)

    @app.post("/v1/knowledge/index", response_model=VectorIndexStatus, status_code=202)
    def knowledge_reindex(owner: OwnerToken) -> VectorIndexStatus:
        # Accepted, not done: building calls the embedding model once per entry.
        return _knowledge().rebuild(owner)

    @app.post("/v1/knowledge/directory", response_model=DirectoryRefreshResult)
    def knowledge_directory(owner: OwnerToken) -> DirectoryRefreshResult:
        # Reads the sources' own listings again; no model call, nothing stored in a lakehouse.
        return _knowledge().refresh_directory(owner)

    @app.get("/v1/knowledge/datasets/{slug}", response_model=DatasetDetail)
    def knowledge_dataset(slug: Slug, owner: OwnerToken) -> DatasetDetail:
        return _knowledge().dataset(owner, slug)

    @app.post("/v1/knowledge/datasets", response_model=DatasetDetail, status_code=201)
    def knowledge_save(body: DatasetRequest, owner: OwnerToken) -> DatasetDetail:
        return _knowledge().save_dataset(owner, body)

    @app.post("/v1/knowledge/datasets/{slug}/archive", response_model=DatasetDetail)
    def knowledge_archive(slug: Slug, owner: OwnerToken) -> DatasetDetail:
        return _knowledge().set_status(owner, slug, archived=True)

    @app.post("/v1/knowledge/datasets/{slug}/restore", response_model=DatasetDetail)
    def knowledge_restore(slug: Slug, owner: OwnerToken) -> DatasetDetail:
        return _knowledge().set_status(owner, slug, archived=False)

    @app.get("/v1/knowledge/series/{series_id}/values", response_model=SeriesValues)
    def knowledge_values(series_id: SeriesIdentity, owner: OwnerToken) -> SeriesValues:
        return _knowledge().values(owner, series_id)

    @app.get("/v1/knowledge/series/{series_id}/uses", response_model=SeriesUses)
    def knowledge_uses(series_id: SeriesIdentity, owner: OwnerToken) -> SeriesUses:
        # Reverse lineage: which of this browser's answers rest on the series.
        return _knowledge().uses(owner, series_id)

    @app.get("/v1/knowledge/series/{series_id}/notes", response_model=SeriesNoteHistory)
    def knowledge_notes(series_id: SeriesIdentity, owner: OwnerToken) -> SeriesNoteHistory:
        return _knowledge().note_history(owner, series_id)

    @app.post("/v1/knowledge/series/{series_id}/notes", response_model=SeriesNoteHistory)
    def knowledge_annotate(
        series_id: SeriesIdentity, body: SeriesNoteRequest, owner: OwnerToken
    ) -> SeriesNoteHistory:
        return _knowledge().annotate(owner, series_id, body)

    @app.post(
        "/v1/sessions/{session_id}/turns/{turn_id}/cancel", response_model=Turn, status_code=202
    )
    def cancel(session_id: Reference, turn_id: Reference, token: Token) -> Turn:
        # Accepted, not done: the turn stops at its next checkpoint (poll the turn).
        return service.cancel(session_id, token, turn_id)

    @app.get("/v1/sessions/{session_id}/turns/{turn_id}/events", response_class=StreamingResponse)
    async def events(
        session_id: Reference,
        turn_id: Reference,
        token: Token,
        last: Annotated[int, Header(alias="Last-Event-ID", ge=0, le=3)] = 0,
    ) -> StreamingResponse:
        service.get_turn(session_id, token, turn_id)  # Authenticate before HTTP 200.
        # Async route admission has no await between check/add. At most one
        # stream per session (eight globally), independent of polling requests.
        if session_id in active_streams:
            raise ServiceError("busy", 409)
        active_streams.add(session_id)

        async def stream() -> AsyncIterator[str]:
            after = last
            deadline = time.monotonic() + 30
            try:
                while time.monotonic() < deadline:
                    item = service.get_turn(session_id, token, turn_id)
                    for event in item.events:
                        if event.sequence > after:
                            yield (
                                f"id: {event.sequence}\nevent: turn\n"
                                f"data: {event.model_dump_json()}\n\n"
                            )
                            after = event.sequence
                    if item.state in ("completed", "failed"):
                        return
                    await asyncio.sleep(0.1)
                # Ending a stream does not cancel or retry a running analysis.
                yield ": reconnect or retrieve the existing turn\n\n"
            except ServiceError:
                yield ": service unavailable\n\n"
            finally:
                active_streams.discard(session_id)

        return StreamingResponse(stream(), media_type="text/event-stream")

    return app
