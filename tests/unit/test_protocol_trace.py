"""QA-21: every iteration's trace holds the exchange itself, both ways.

Live 2026-09-23 (run 5bb0f99d) every `iteration` and `decision` step of the jury's
A1 turn had no detail: the trace said how many bytes went to the model and never
which turns, which tool schemas or which options, nor what came back. A reviewer
could not check what the model had been shown. What is recorded now is the request
as it is posted — roles, content, `tool_calls`, `tool_call_id`, the tool menu, the
model options — and the completion as the provider handed it over, never the
model's hidden reasoning; redacted and capped by the tracer like any other detail.
"""

from __future__ import annotations

import json

import httpx
import pytest
from pydantic import BaseModel, ConfigDict, SecretStr

from kkb_agent.agent.executor import ToolResult, ToolStatus
from kkb_agent.agent.observer import MAX_DETAIL_CHARS, Tracer
from kkb_agent.agent.registry import ToolRegistry, ToolSpec
from kkb_agent.agent.trust_loop import run_turn
from kkb_agent.llm import scripted
from kkb_agent.llm.config import ProviderConfig
from kkb_agent.llm.kloudeks import KloudeksProvider
from kkb_agent.llm.provider import ToolCall, TransportError

MODEL = "deepseek-ai/DeepSeek-V4.1-Flash"
CANARY = "sk-canary-credential-never-recorded"
HIDDEN = "GIZLI-DUSUNCE-METNI"


class Echo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str


def echo_registry() -> ToolRegistry:
    def run(arguments, context):  # noqa: ARG001 - tool contract
        return ToolResult(ToolStatus.SUCCESS, "", "echo", output={"got": arguments.text})

    registry = ToolRegistry()
    registry.register(ToolSpec(name="echo", description="Echo.", arguments=Echo, run=run))
    return registry


def iterations(tracer: Tracer) -> list:
    return [e for e in tracer.events if e.stage == "loop" and e.name == "iteration"]


def call(identifier: str, name: str, arguments: dict) -> ToolCall:
    return ToolCall(identifier, name, json.dumps(arguments, ensure_ascii=False))


class TestTheNativeHistoryIsOnRecord:
    def test_the_second_request_carries_the_call_and_its_answer_paired(self):
        provider = scripted(
            (call("c1", "echo", {"text": "merhaba"}),),
            (call("c2", "finish", {"answer": "tamam"}),),
        )
        tracer = Tracer()
        run_turn(
            "soru",
            provider=provider,
            registry=echo_registry(),
            instructions="talimat",
            tracer=tracer,
        )

        first, second = iterations(tracer)
        one, two = json.loads(first.detail), json.loads(second.detail)
        assert first.attributes["request_source"] == "loop"
        assert first.attributes["detail_chars"] == len(first.detail)
        assert first.attributes["detail_clipped"] is False

        # What came back the first time: the call exactly as the platform made it.
        assert one["response"]["tool_calls"] == [
            {"id": "c1", "name": "echo", "arguments": '{"text": "merhaba"}'}
        ]
        assert "reasoning" not in one["response"]

        # What went out the second time: the whole exchange, paired by the call id.
        request = two["request"]
        assert [m["role"] for m in request["messages"]] == ["system", "user", "assistant", "tool"]
        asked, answered = request["messages"][2], request["messages"][3]
        assert asked["tool_calls"] == [
            {"id": "c1", "name": "echo", "arguments": '{"text": "merhaba"}'}
        ]
        assert answered["tool_call_id"] == "c1"
        assert '"got": "merhaba"' in answered["content"]
        # The record is what the provider received, turn for turn.
        assert [m["content"] for m in request["messages"]] == [m.content for m in provider.seen[1]]
        # The tool schemas offered, the finishing call among them.
        names = [entry["function"]["name"] for entry in request["tools"]]
        assert names == ["echo", "finish"]
        assert request["tools"][0]["function"]["parameters"]["required"] == ["text"]

    def test_the_decision_records_how_the_reply_was_read(self):
        provider = scripted(
            (call("c1", "echo", {"text": "merhaba"}),),
            (call("c2", "finish", {"answer": "tamam"}),),
        )
        tracer = Tracer()
        run_turn(
            "soru", provider=provider, registry=echo_registry(), instructions="", tracer=tracer
        )

        first = next(e for e in tracer.events if e.stage == "loop" and e.name == "decision")
        assert json.loads(first.detail)["actions"] == [
            {"id": "a1", "tool": "echo", "arguments": {"text": "merhaba"}, "call_id": "c1"}
        ]


class TestARequestThatFailedIsStillOnRecord:
    def test_the_input_is_kept_when_nothing_came_back(self):
        class Failing:
            def complete(self, messages, **options):  # noqa: ARG002 - provider shape
                raise TransportError("Kloudeks transport failure (502)")

        tracer = Tracer()
        with pytest.raises(TransportError):
            run_turn(
                "hangi seri?",
                provider=Failing(),
                registry=echo_registry(),
                instructions="",
                tracer=tracer,
            )
        [iteration] = iterations(tracer)
        assert iteration.status == "failed"
        record = json.loads(iteration.detail)
        assert "response" not in record
        assert record["request"]["messages"][-1] == {"role": "user", "content": "hangi seri?"}


class TestACapIsSaid:
    def test_a_request_beyond_the_ceiling_is_marked_clipped(self):
        provider = scripted((call("c1", "finish", {"answer": "tamam"}),))
        tracer = Tracer()
        run_turn(
            "x" * (MAX_DETAIL_CHARS + 10),
            provider=provider,
            registry=ToolRegistry(),
            instructions="",
            tracer=tracer,
        )
        [iteration] = iterations(tracer)
        assert iteration.attributes["detail_clipped"] is True
        assert iteration.attributes["detail_chars"] > MAX_DETAIL_CHARS
        assert len(iteration.detail) == MAX_DETAIL_CHARS
        assert iteration.detail.endswith("more characters]")
        # The reply is written first, so the cap takes the request's tail, not it.
        assert iteration.detail.startswith('{"response": ')


class TestSecretsStayOutOfTheProtocolRecord:
    def test_a_secret_is_redacted_however_deeply_json_escaped(self):
        """A secret with a quote and a backslash reaches the record escaped, twice over.

        A tool's observation is JSON inside a tool turn's content, and that turn is JSON
        inside the record: a plain `replace` of the secret matched neither form.
        """
        plain, quoted = "PLAIN-SECRET-123", 'SIR"DEGERI\\yol'
        provider = scripted(
            (call("c1", "echo", {"text": quoted}),),
            (call("c2", "finish", {"answer": "tamam"}),),
        )
        tracer = Tracer(redactions=(plain, quoted))
        run_turn(
            f"soru {plain}",
            provider=provider,
            registry=echo_registry(),
            instructions="",
            tracer=tracer,
        )

        for event in tracer.events:
            recorded = (event.detail or "") + json.dumps(event.attributes, ensure_ascii=False)
            assert "PLAIN-SECRET" not in recorded, event.name
            assert "DEGERI" not in recorded, event.name
        second = iterations(tracer)[1]
        assert "[redacted]" in second.detail
        json.loads(second.detail)  # Still a readable record after redaction.


def kloudeks(*replies: httpx.Response) -> tuple[KloudeksProvider, list[bytes]]:
    posted: list[bytes] = []
    queue = list(replies)

    def server(request: httpx.Request) -> httpx.Response:
        posted.append(request.content)
        return queue.pop(0)

    config = ProviderConfig(
        base_url="https://mia.csp.kloudeks.com/v1",
        credential=SecretStr(CANARY),
        planner_model=MODEL,
        router_model=MODEL,
    )
    return KloudeksProvider(config, transport=httpx.MockTransport(server)), posted


def asked_for(identifier: str, name: str, arguments: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "content": None,
                        # Returned by the platform, and not what a trace keeps.
                        "reasoning_content": HIDDEN,
                        "tool_calls": [
                            {
                                "id": identifier,
                                "type": "function",
                                "function": {"name": name, "arguments": arguments},
                            }
                        ],
                    },
                }
            ],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 12,
                "completion_tokens_details": {"reasoning_tokens": 5},
            },
        },
    )


class TestTheWireBodyIsWhatWasPosted:
    def test_each_recorded_request_equals_the_body_on_the_wire(self):
        provider, posted = kloudeks(
            asked_for("call-1", "echo", '{"text": "merhaba"}'),
            asked_for("call-2", "finish", '{"answer": "tamam"}'),
        )
        tracer = Tracer()
        run_turn(
            "soru",
            provider=provider,
            registry=echo_registry(),
            instructions="talimat",
            context={"today": "Bugünün tarihi: 2026-09-23."},
            tracer=tracer,
        )

        recorded = iterations(tracer)
        assert len(recorded) == len(posted) == 2
        for event, body in zip(recorded, posted, strict=True):
            assert event.attributes["request_source"] == "wire"
            assert json.loads(event.detail)["request"] == json.loads(body)

        second = json.loads(posted[1])
        # Every system turn joined into one, the pair tied by the platform's own id.
        assert [m["role"] for m in second["messages"]] == ["system", "user", "assistant", "tool"]
        assert second["messages"][2]["tool_calls"] == [
            {
                "id": "call-1",
                "type": "function",
                "function": {"name": "echo", "arguments": '{"text": "merhaba"}'},
            }
        ]
        assert second["messages"][3]["tool_call_id"] == "call-1"
        assert second["model"] == MODEL and second["tool_choice"] == "auto"

        reply = json.loads(recorded[0].detail)["response"]
        assert reply["finish_reason"] == "tool_calls"
        assert reply["usage"] == {
            "prompt_tokens": 120,
            "completion_tokens": 12,
            "reasoning_tokens": 5,
        }
        everything = "".join((e.detail or "") + json.dumps(e.attributes) for e in tracer.events)
        # The credential rides in a header and a body never holds it, redaction or not.
        assert CANARY not in everything
        # Hidden reasoning is returned by the platform and is not recorded.
        assert HIDDEN not in everything

    def test_a_failed_post_keeps_the_body_that_was_sent(self):
        provider, posted = kloudeks(httpx.Response(502))
        tracer = Tracer()
        with pytest.raises(TransportError):
            run_turn(
                "soru",
                provider=provider,
                registry=echo_registry(),
                instructions="talimat",
                tracer=tracer,
            )
        [iteration] = iterations(tracer)
        assert iteration.attributes["error_reason"] == "Kloudeks transport failure (502)"
        assert json.loads(iteration.detail)["request"] == json.loads(posted[0])
