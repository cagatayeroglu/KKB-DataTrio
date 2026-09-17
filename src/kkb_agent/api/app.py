"""FastAPI app factory with a local-only, bounded ASGI ingress boundary."""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from kkb_agent.api.contracts import (
    MAX_BODY_BYTES,
    MAX_DOCUMENT_BYTES,
    ConversationDetail,
    ConversationList,
    ConversationSummary,
    ConversationUpdate,
    DocumentAdmitted,
    Error,
    ErrorCode,
    Feedback,
    FeedbackList,
    FeedbackRequest,
    Health,
    OwnerCreated,
    Question,
    Reference,
    RunDetail,
    RunList,
    SessionCreated,
    Turn,
)
from kkb_agent.api.prepared import PreparedStatus
from kkb_agent.api.service import AnalysisService, ServiceError
from kkb_agent.core.models import ContractModel
from kkb_agent.ingest.fetched import DOCUMENT_MEDIA_TYPES

Token = Annotated[str, Header(alias="X-KKB-Session-Token", min_length=43, max_length=43)]
#: The browser's own key: it lists and reopens the conversations it created.
OwnerToken = Annotated[str, Header(alias="X-KKB-Owner-Token", min_length=43, max_length=43)]
#: The only route whose body is not JSON (M10-04); every other POST stays JSON-only.
DOCUMENT_ROUTE = re.compile(r"/v1/sessions/[a-f0-9]{32}/documents\Z")
#: The one route with a query string: listing a browser's own conversations.
LIST_ROUTE = re.compile(r"/v1/conversations\Z")
MAX_QUERY_BYTES = 256
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
            listing = scope["method"] == "GET" and bool(LIST_ROUTE.fullmatch(scope["path"]))
            if (query and not (listing and len(query) <= MAX_QUERY_BYTES)) or any(
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
            limit = MAX_DOCUMENT_BYTES if document else MAX_BODY_BYTES
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
            async with asyncio.timeout(30 if document else 5):
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
) -> FastAPI:
    """No provider creation or model call; the operator supplies the runner."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await asyncio.to_thread(service.close)

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

    @app.get("/v1/conversations/{session_id}", response_model=ConversationDetail)
    def conversation(session_id: Reference, token: Token) -> ConversationDetail:
        return service.conversation(session_id, token)

    @app.get("/v1/conversations/{session_id}/runs", response_model=RunList)
    def runs(session_id: Reference, token: Token) -> RunList:
        return service.runs(session_id, token)

    @app.get("/v1/conversations/{session_id}/runs/{run_id}", response_model=RunDetail)
    def run(session_id: Reference, run_id: Reference, token: Token) -> RunDetail:
        # Reading a trace never starts work: it is a stored record, not a replay.
        return service.run(session_id, run_id, token)

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
