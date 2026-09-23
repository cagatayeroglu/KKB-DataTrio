"""QA-33: a CSV served as `text/plain` is read as the table it is, and nothing else is.

Code hosts serve raw files as `text/plain; charset=utf-8`, and live 2026-09-23 a real
monthly CSV at such an address was refused as CONTENT_TYPE four times, so it could be
neither read nor kept. Plain text is now accepted from an address and read only as a CSV
that passes every CSV check with at least two columns; a page, prose, a ragged or
oversized table, a non-UTF-8 declaration and an upload declared as plain text are refused
exactly as before.
"""

from __future__ import annotations

import io
import json
from dataclasses import replace
from http.client import HTTPResponse
from uuid import uuid4

import pytest
from test_dataset_promotion import SLUG, TITLE, stack  # noqa: F401
from test_document_upload import runtime, session, upload
from test_knowledge_from_conversation import call, empty_conversation

from kkb_agent.agent.trust_loop import FINISH
from kkb_agent.core import SourceRef
from kkb_agent.ingest._bounded_response import ResponseRejected, read_response
from kkb_agent.ingest.fetched import (
    DOCUMENT_MEDIA_TYPES,
    FETCHED_MEDIA_TYPES,
    PLAIN_TEXT_NOT_A_TABLE,
    TEXT_PLAIN,
    kept_media_type,
    load_document,
)
from kkb_agent.ingest.safe_fetch import FetchCode, FetchLimits, FetchRequest, FetchSuccess
from kkb_agent.ingestion_policy import DEFAULT_LIMITS, AdmissionError, RejectionCode

SOURCE = SourceRef(
    source_id="web:plain", source_type="web_url", locator="https://example.org/a.csv"
)
#: The shape of the live file: a month column and a value column, served as text.
AIRLINE = b"Month,Passengers\n1949-01,112\n1949-02,118\n1949-03,132\n"
ADDRESS = "https://raw.example.org/datasets/airline-passengers.csv"


def plain(content: bytes, **options):
    return load_document(content, TEXT_PLAIN, source=SOURCE, **options)


def test_a_csv_served_as_plain_text_is_read_as_a_table():
    loaded = plain(AIRLINE)
    assert loaded.status == "loaded"
    assert loaded.table.headers == ("Month", "Passengers") and len(loaded.table.rows) == 3
    assert kept_media_type(TEXT_PLAIN, loaded) == "text/csv"


def test_a_page_served_as_plain_text_is_refused_before_it_is_parsed():
    with pytest.raises(AdmissionError) as refused:
        plain(b"\n  <!DOCTYPE html><html><body>404, not, found</body></html>\n")
    assert refused.value.code is RejectionCode.UNSUPPORTED_FORMAT


def test_one_column_of_text_is_not_a_table_even_with_a_declared_separator():
    loaded = plain(b"bir satir\nikinci satir\nucuncu satir\n", delimiter=",")
    assert (loaded.status, loaded.code) == ("rejected", PLAIN_TEXT_NOT_A_TABLE)
    assert kept_media_type(TEXT_PLAIN, loaded) == TEXT_PLAIN  # never kept as a document


def test_prose_without_a_separator_is_not_guessed_at():
    loaded = plain(b"Bu bir aciklama metnidir.\nTablo degildir.\n")
    assert loaded.status != "loaded"
    assert kept_media_type(TEXT_PLAIN, loaded) == TEXT_PLAIN


def test_a_ragged_table_is_still_refused():
    loaded = plain(b"Month,Passengers\n1949-01,112\n1949-02,118,extra\n1949-03,132\n")
    assert loaded.status != "loaded"


def test_the_byte_budget_still_applies():
    loaded = plain(AIRLINE, limits=replace(DEFAULT_LIMITS, max_bytes=16))
    assert loaded.status != "loaded"


def test_binary_bytes_labelled_as_text_are_refused():
    try:
        loaded = plain(b"\x00\x01\x02,\x03\x04\n\x05,\x06\n\x07,\x08\n")
    except AdmissionError:
        return
    assert loaded.status != "loaded"


def response(content_type: str, body: bytes) -> HTTPResponse:
    class Socket:
        def makefile(self, *args):
            head = (
                f"HTTP/1.1 200 OK\r\nContent-Type: {content_type}\r\n"
                f"Content-Length: {len(body)}\r\n\r\n"
            )
            return io.BytesIO(head.encode() + body)

    answer = HTTPResponse(Socket())  # type: ignore[arg-type]
    answer.begin()
    return answer


@pytest.mark.parametrize(
    ("charset", "accepted"),
    [("", True), ("; charset=utf-8", True), ("; charset=iso-8859-9", False), (";foo=bar", False)],
)
def test_plain_text_is_accepted_from_an_address_only_as_utf_8(charset, accepted):
    request = FetchRequest(
        source_ref="web:plain",
        url="https://example.org/a.csv",
        accepted_media_types=FETCHED_MEDIA_TYPES,
    )
    reply = response(f"text/plain{charset}", AIRLINE)
    if accepted:
        assert read_response(reply, request, FetchLimits()).media_type == TEXT_PLAIN
    else:
        with pytest.raises(ResponseRejected) as refused:
            read_response(reply, request, FetchLimits())
        assert refused.value.code == FetchCode.CONTENT_TYPE


def test_an_upload_declared_as_plain_text_is_still_refused(tmp_path):
    assert TEXT_PLAIN not in DOCUMENT_MEDIA_TYPES
    runner, client = runtime(tmp_path)
    with client:
        sid, headers = session(client)
        refused = upload(client, sid, headers, content=AIRLINE, media_type=TEXT_PLAIN)
    assert refused.status_code == 415


def served_as_text(content: bytes):
    def fetch(request):
        return FetchSuccess(
            source_ref=request.source_ref, content=content, media_type=TEXT_PLAIN, http_status=200
        )

    return fetch


def test_the_live_chain_reads_keeps_and_saves_a_csv_served_as_text(stack):  # noqa: F811
    """QA-33 as it happened, offline: an empty conversation, a raw CSV address, a save."""
    build, store, knowledge, _ = stack
    runner, _ = build(
        call("web_url", url=ADDRESS),
        call(
            "promote_series",
            document="belge_1",
            title=TITLE,
            unit="adet",
            meaning="monthly_total",
            save_now=True,
        ),
        call(FINISH, answer="Kaydedildi."),
    )
    runner._trust_loop = True
    runner._web_url_fetch = served_as_text(AIRLINE)
    runner(empty_conversation(store), uuid4().hex, f"{ADDRESS} verisini oku ve kaydet")
    read_turn = "\n".join(message.content for message in runner._provider.seen[1])
    assert '"kept_as": "belge_1"' in read_turn and "CONTENT_TYPE" not in read_turn
    saved = knowledge.dataset(SLUG)
    assert saved is not None
    assert [o.value for o in saved.observations] == [112.0, 118.0, 132.0]
    assert dict(saved.provenance)["media_type"] == "text/csv"


def test_a_refused_type_says_asking_again_does_not_change_it(stack):  # noqa: F811
    from kkb_agent.ingest.safe_fetch import FetchFailure

    build, store, _, _ = stack
    runner, _ = build(call("web_url", url=ADDRESS), call(FINISH, answer="Okunamadı."))
    runner._trust_loop = True
    runner._web_url_fetch = lambda request: FetchFailure(
        source_ref=request.source_ref, code=FetchCode.CONTENT_TYPE
    )
    runner(empty_conversation(store), uuid4().hex, f"{ADDRESS} verisini oku")
    shown = "\n".join(message.content for message in runner._provider.seen[1])
    assert "does not change what the address serves" in json.loads(json.dumps(shown))
