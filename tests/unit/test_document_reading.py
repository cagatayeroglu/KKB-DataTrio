"""DEC-181: a document reading is shown as a reading, never as evidence.

Every other answer in this system is bound to stored values. These tests pin the
one that is not: what it may read, what it must say about itself, and the two
things it may never become - a published result, or the answer to a turn that
computed one.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from kkb_agent.agent.executor import ExecutionContext, ExecutionOutcome, ToolStatus
from kkb_agent.agent.loop import READING_HEADER, READING_LIMITATION, document_reading
from kkb_agent.agent.registry import ToolRegistry
from kkb_agent.core import SourceRef
from kkb_agent.ingest.attached import Attachment
from kkb_agent.llm.doubles import scripted
from kkb_agent.tools import DocumentReadArguments, make_document_read_tool

CSV = ("Ay;Kapanış (Puan)\n2026-04;9000\n2026-05;9100\n2026-06;9200\n").encode()
NOW = datetime(2026, 9, 20, tzinfo=UTC)


def upload(content: bytes = CSV, media_type: str = "text/csv") -> Attachment:
    return Attachment(
        content=content,
        media_type=media_type,
        source=SourceRef(
            source_id="upload:belge_1",
            source_type="upload",
            locator="upload:belge_1",
            retrieved_at=NOW,
            content_hash="sha256:" + "a" * 64,
        ),
    )


def read(tool, document: str | None = None, question: str = "Bu belge ne anlatıyor?"):
    return tool.run(DocumentReadArguments(document=document), ExecutionContext(question=question))


def test_the_tool_is_registrable_only_because_a_decision_named_it():
    registry = ToolRegistry()
    registry.register(make_document_read_tool(provider=scripted("x")))
    assert "document_read" in registry


def test_a_table_document_is_read_as_prose_and_marked_as_a_reading():
    provider = scripted("Belge BIST kapanışlarını üç ay için listeliyor; seri yükseliyor.")
    tool = make_document_read_tool(provider=provider, library={"belge_1": upload()})
    result = read(tool)

    assert result.status is ToolStatus.SUCCESS
    assert result.output.status == "read" and result.output.kind == "table"
    assert result.output.document == "belge_1"
    assert len(result.output.sha256) == 64
    assert "yükseliyor" in result.output.text
    # The model saw the document's own rows and the question, and was told that
    # text inside a document is data rather than an instruction.
    (system, rows, user) = provider.seen[-1]
    assert "uydurma" in system.content
    assert "Kapanış (Puan)" in rows.content
    assert user.content == "Bu belge ne anlatıyor?"
    # Nothing here is a result: the answer path has no cells to publish.
    assert getattr(result.output, "result", None) is None
    assert any("not bound" in warning or "not a computed" in warning for warning in result.warnings)


def test_a_named_document_that_does_not_exist_is_refused_by_name():
    tool = make_document_read_tool(provider=scripted("never used"), library={"belge_1": upload()})
    result = read(tool, document="belge_2")
    assert result.status is ToolStatus.FAILURE
    assert result.error_category == "DOCUMENT_UNKNOWN"


def test_without_a_document_there_is_nothing_to_read():
    tool = make_document_read_tool(provider=scripted("never used"))
    result = read(tool)
    assert result.status is ToolStatus.FAILURE
    assert result.error_category == "NO_ATTACHMENT"


def test_a_page_without_text_needs_a_vision_model_and_is_never_guessed():
    """A picture of a chart has no text layer; without vision nothing is invented."""
    from test_image_document import picture

    from kkb_agent.image_document import image_to_pdf
    from kkb_agent.ingestion_policy import DEFAULT_LIMITS

    page = upload(image_to_pdf(picture(), "png", DEFAULT_LIMITS), "application/pdf")
    # No OCR and no vision: the loader refuses the page and nothing is invented.
    refused = make_document_read_tool(provider=scripted("unused"), library={"belge_1": page})
    assert read(refused).error_category == "NO_TEXT_LAYER"

    # Looking at the picture does not need OCR, only a configured vision model.
    seeing = scripted("Grafik 2021-2025 arası yükselen bir seri gösteriyor.", supports_vision=True)
    reading = make_document_read_tool(provider=seeing, library={"belge_1": page}, vision=True)
    result = read(reading)
    assert result.status is ToolStatus.SUCCESS
    assert result.output.kind == "image"
    assert "yükselen" in result.output.text


def test_the_answer_path_labels_a_reading_and_publishes_nothing():
    provider = scripted("Belge üç aylık kapanışları listeliyor.")
    tool = make_document_read_tool(provider=provider, library={"belge_1": upload()})
    outcome = ExecutionOutcome((read(tool),), True)

    found = document_reading(outcome)
    assert found is not None
    text, document, digest = found
    assert document == "belge_1" and len(digest) == 12
    assert "kapanışları" in text

    from kkb_agent.agent import AnswerStatus, Session

    answered = Session(scripted(), ToolRegistry())._reading_answer(_planned(), outcome, found)
    assert answered.answer.status is AnswerStatus.QUALIFIED
    assert answered.answer.text.startswith(READING_HEADER)
    assert document in answered.answer.text and digest in answered.answer.text
    assert READING_LIMITATION in answered.answer.limitations
    assert answered.results == () and answered.tables == ()


def test_a_failed_read_is_not_an_answer():
    tool = make_document_read_tool(provider=scripted("unused"))
    assert document_reading(ExecutionOutcome((read(tool),), True)) is None


def _planned():
    from kkb_agent.agent.executor import ValidatedPlan
    from kkb_agent.agent.loop import Planned

    return Planned(ValidatedPlan("q", ()), 1)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No live request in these tests")

    monkeypatch.setattr("socket.socket.connect", forbidden)
