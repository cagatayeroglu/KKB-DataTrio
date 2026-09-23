"""A read document stays reachable: through the writer, through `inspect`, to its end.

QA-13..16 (Codex, f02c382), on the real output shapes rather than dicts standing in
for them. Tests 1, 2, 3, 4 and 6 are Codex's own, assertion for assertion. The fifth
is restated: as written it asked the *first* one-row window of a 50,000-character
line to contain the line's last characters, which no window can do — a window
starts where it starts. What QA-16 asks for is a way to the end, so that is what it
checks: the rows say where to continue, and continuing reaches the tail.
"""

from __future__ import annotations

import json
from datetime import date

from test_trust_seam import observation, page

from kkb_agent.agent.executor import ExecutionContext, ToolStatus
from kkb_agent.agent.registry import ToolRegistry
from kkb_agent.agent.trust_answer import write_answer
from kkb_agent.agent.trust_loop import MAX_OBSERVATION_CHARS, TurnOutcome, _describe
from kkb_agent.agent.trust_session import TrustSession
from kkb_agent.llm import scripted
from kkb_agent.llm.provider import ToolCall, TransportError
from kkb_agent.pdf_loader import PdfDocument, PdfPage
from kkb_agent.tools.inspect_result import (
    MAX_WINDOW_CHARS,
    InspectArguments,
    make_inspect_tool,
)
from kkb_agent.tools.web_url import WebUrlOutput


def look(held: object, **window: int):
    return make_inspect_tool().run(
        InspectArguments(source="doc", **window), ExecutionContext("read", outputs={"doc": held})
    )


def pdf(*pages: PdfPage) -> WebUrlOutput:
    return WebUrlOutput(
        "loaded", media_type="application/pdf", document=PdfDocument("synthetic:doc", None, pages)
    )


def test_inspect_html_window_reaches_later_content():
    result = look(page("first\nlast-marker"), offset=1, limit=1)
    assert result.status is ToolStatus.SUCCESS
    assert result.output.values == [{"line": 1, "text": "last-marker"}]


def test_inspect_can_read_actual_pdf_output_shape():
    result = look(pdf(PdfPage(1, 100, 100, True, "pdf-marker", ())))
    assert result.status is ToolStatus.SUCCESS, result
    assert "pdf-marker" in json.dumps(result.output.model_dump())


def test_fallback_writer_sees_real_web_output_content():
    provider = scripted("Summary")
    outcome = TurnOutcome(observations=[observation(page("writer-content-marker"))])
    write_answer("summarize", outcome, provider=provider)
    assert "writer-content-marker" in "\n".join(m.content for m in provider.seen[0])


def test_provider_outage_does_not_claim_nonexistent_table_publication():
    provider = scripted(TransportError("offline"))
    outcome = TurnOutcome(observations=[observation("plain text only")], exhausted="provider")
    answer = write_answer("summarize", outcome, provider=provider)
    assert "tablo yayımlandı" not in answer.text.lower()


def test_one_long_line_is_recoverable_through_inspect():
    """QA-16, restated: from the first window, the end of the line is reachable."""
    held = page("x" * 50000 + "tail-marker")
    first = look(held, limit=1)
    assert first.status is ToolStatus.SUCCESS
    assert first.output.more and first.output.next_offset == 1
    # The first window is not clipped on its way to the model: continuing is possible.
    assert '"clipped": true' not in _describe(first, "a2").lower()
    last = look(held, offset=first.output.rows - 1, limit=1)
    assert "tail-marker" in _describe(last, "a3")
    assert last.output.values[0]["part"] == last.output.values[0]["parts"] == first.output.rows


def test_session_supplies_configured_date_to_model():
    provider = scripted((ToolCall("f", "finish", '{"answer":"done"}'),))
    TrustSession(provider, ToolRegistry(), today=date(2026, 9, 23)).answer("today?")
    assert "2026-09-23" in "\n".join(m.content for m in provider.seen[0])


class TestWhereAWindowIs:
    def test_a_pdf_window_names_its_page(self):
        result = look(
            pdf(
                PdfPage(1, 100, 100, True, "birinci sayfa", ()),
                PdfPage(2, 100, 100, True, "ikinci sayfa", ()),
            )
        )
        assert [(row["page"], row["text"]) for row in result.output.values] == [
            (1, "birinci sayfa"),
            (2, "ikinci sayfa"),
        ]

    def test_a_page_read_by_ocr_is_read_back_and_says_so(self):
        scanned = PdfPage(3, 100, 100, False, "", (), ocr_text="taranmış sayfa metni")
        result = look(pdf(scanned))
        assert result.output.values == [
            {"page": 3, "ocr": True, "line": 0, "text": "taranmış sayfa metni"}
        ]

    def test_a_pdf_with_no_text_at_all_is_not_offered_as_read_text(self):
        result = look(pdf(PdfPage(1, 100, 100, False, "", ())))
        assert result.status is ToolStatus.FAILURE

    def test_no_window_is_clipped_on_its_way_to_the_model(self):
        """Many long rows stop at the window budget, not at the observation clip."""
        held = page("\n".join("y" * 3_900 for _ in range(40)))
        result = look(held, limit=60)
        shown = sum(len(str(row["text"])) for row in result.output.values)
        assert shown <= MAX_WINDOW_CHARS < MAX_OBSERVATION_CHARS
        assert result.output.more and result.output.next_offset == len(result.output.values)
        assert '"clipped": true' not in _describe(result, "a4").lower()

    def test_every_row_is_reached_exactly_once_by_following_next_offset(self):
        held = page("a" * 9_000 + "\nkısa\n" + "b" * 13_000)
        seen: list[str] = []
        offset: int | None = 0
        while offset is not None:
            result = look(held, offset=offset, limit=2)
            seen.extend(str(row["text"]) for row in result.output.values)
            offset = result.output.next_offset
        assert "".join(seen) == "a" * 9_000 + "kısa" + "b" * 13_000
