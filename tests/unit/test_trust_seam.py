"""What the loop owes the model and the reader, at the seams where it was losing it.

Each test here is a defect that a live turn showed and that no scripted test would
have: an observation the model could not see, a call refused over the harness's own
vocabulary, and a turn's work lost to a second failure of a service already known to
be down.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict, Field

from kkb_agent.agent.executor import ToolResult, ToolStatus
from kkb_agent.agent.trust_answer import INTERRUPTED, write_answer
from kkb_agent.agent.trust_loop import (
    MAX_OBSERVATION_CHARS,
    Action,
    AgentStep,
    Observation,
    TurnOutcome,
    _asked_for,
    _describe,
    _observed,
    _without_protocol_keys,
)
from kkb_agent.html_loader import HtmlDocument
from kkb_agent.llm.provider import Completion, Message, Role, ToolCall, TransportError
from kkb_agent.llm.structured import SchemaViolation, complete_with_repair
from kkb_agent.tools.web_url import WebUrlOutput


def observation(output: object, identifier: str = "a1", tool: str = "web_url") -> Observation:
    return Observation(
        Action(id=identifier, tool=tool, call_id="chatcmpl-tool-1"),
        ToolResult(ToolStatus.SUCCESS, identifier, tool, output=output),
    )


def page(text: str) -> WebUrlOutput:
    """A read page, shaped as `web_url` returns one: the content in a repr=False field."""
    return WebUrlOutput(
        "loaded", None, None, "text/html", document=HtmlDocument(source=None, text=text, tables=())
    )


class TestTheModelSeesWhatATookReturned:
    def test_a_page_reaches_the_message_the_model_is_sent(self):
        """Not the serializer's output: the message body of the next request.

        `WebUrlOutput` is a dataclass that keeps `document`, `table` and `links` out
        of its repr, so rendering by `str()` sent a success with nothing in it. Live
        2026-09-23 the model then spent fifteen calls guessing at links on a page
        whose text it already had.
        """
        wanted = "2026 Ağustos Otomobil ve Hafif Ticari Araç Pazar Değerlendirme"
        messages = _observed([observation(page(wanted))], native=True)
        tool_turns = [m for m in messages if m.role is Role.TOOL]
        assert tool_turns, "a tool turn has to carry the result back"
        assert any(wanted in m.content for m in tool_turns)

    def test_the_same_holds_without_native_tool_calls(self):
        wanted = "sayfanın kendi metni"
        messages = _observed([observation(page(wanted))], native=False)
        assert any(wanted in m.content for m in messages)

    def test_a_pydantic_output_still_travels(self):
        class Reply(BaseModel):
            found: str

        rendered = _describe(observation(Reply(found="katalog kaydı")).result, "a2")
        assert "katalog kaydı" in rendered

    def test_a_clipped_observation_says_so_and_keeps_its_id(self):
        """Clipping is visible, and the result stays addressable for a second look."""
        rendered = _describe(observation(page("x" * (MAX_OBSERVATION_CHARS * 2))).result, "a1")
        assert '"clipped": true' in rendered.lower()
        assert '"id": "a1"' in rendered


class TestTheHarnessVocabularyDoesNotEatAnArgument:
    def test_a_word_the_tool_does_not_declare_is_dropped(self):
        class NoId(BaseModel):
            model_config = ConfigDict(extra="forbid")

            address: str = ""

        kept = _without_protocol_keys({"id": "a1", "address": "x"}, NoId.model_fields)
        assert kept == {"address": "x"}

    def test_a_word_the_tool_does_declare_is_kept(self):
        """A tool whose own schema takes `id` must receive the one the model sent."""

        class NeedsId(BaseModel):
            model_config = ConfigDict(extra="forbid")

            id: str = Field(description="this tool really does take an id")

        kept = _without_protocol_keys({"id": "6161"}, NeedsId.model_fields)
        assert kept == {"id": "6161"}
        assert NeedsId.model_validate(kept).id == "6161"


class TestAnInterruptedServiceDoesNotLoseTheTurn:
    def test_what_the_tools_returned_is_delivered_without_the_writer(self):
        """The writer is the service that already stopped answering.

        A turn that ended on a provider failure still has its observations and its
        published table. Asking the same dead service to write prose and then
        propagating its second failure threw all of that away.
        """

        class Dead:
            def complete(self, messages, **options):  # noqa: ARG002 - provider shape
                raise TransportError("the service stopped answering")

        outcome = TurnOutcome(
            observations=[
                observation({"values": [49046, 47218]}, identifier="a1", tool="lakehouse")
            ],
            exhausted="provider",
        )
        answer = write_answer("taşıt kredisi", outcome, provider=Dead())
        assert answer.text.startswith(INTERRUPTED.strip()[:40])
        # Every figure the tools returned is in what the reader gets.
        assert "49046" in answer.text and "47218" in answer.text
        # And the reader is told why there is no prose around them.
        assert any("geri dönmedi" in note for note in answer.notes)

    def test_a_turn_with_nothing_in_hand_still_fails(self):
        class Dead:
            def complete(self, messages, **options):  # noqa: ARG002 - provider shape
                raise TransportError("the service stopped answering")

        with pytest.raises(TransportError):
            write_answer("soru", TurnOutcome(), provider=Dead())


class TestACallTheLoopCouldNotRead:
    def test_the_model_is_shown_what_it_sent_and_the_call_it_answers(self):
        """A refusal the model cannot learn from will be repeated unchanged.

        The platform's own id has to travel too, because the tool turn reporting the
        refusal answers the call the model actually made.
        """
        completion = Completion(
            text="",
            model="m",
            tool_calls=(ToolCall(id="chatcmpl-tool-9", name="web_url", arguments="{not json"),),
        )
        step = _asked_for(completion)
        assert step is not None
        assert [(m.tool, m.call_id, m.sent) for m in step.malformed] == [
            ("web_url", "chatcmpl-tool-9", "{not json")
        ]
        assert step.malformed[0].id == "a1"


class TestProseMayEndATurn:
    def test_prose_is_returned_when_tools_were_offered(self):
        """With tools offered the model has two ways to answer, and prose is one.

        Live 2026-09-23 a turn the model finished in prose died on a schema the prose
        was never meant to satisfy, so a written answer reached the reader as an error.
        """

        def ask(conversation):  # noqa: ARG001 - the ask contract
            return "Taşıt kredisi bakiyesi altı ayda geriledi.", "stop", ()

        completion = complete_with_repair(
            ask,
            [Message(Role.USER, "soru")],
            schema=AgentStep,
            max_attempts=2,
            model="m",
            tolerate_prose=True,
        )
        assert completion.parsed is None
        assert "geriledi" in completion.text
        step = _asked_for(completion)
        assert step is not None and step.done and step.reply == completion.text

    def test_without_tools_a_schema_is_still_a_schema(self):
        def ask(conversation):  # noqa: ARG001 - the ask contract
            return "bu JSON değil", "stop", ()

        with pytest.raises(SchemaViolation):
            complete_with_repair(
                ask, [Message(Role.USER, "soru")], schema=AgentStep, max_attempts=1, model="m"
            )
