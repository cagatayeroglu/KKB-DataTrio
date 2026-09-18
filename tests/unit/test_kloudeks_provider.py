"""M4-07: the Kloudeks transport, and where the key is allowed to go.

No networking. Every test runs the real `httpx` client against an in-process
`MockTransport`, so what is exercised is the provider's own request building,
destination checks, status mapping and parsing — not a mock of them.

The destination rule is the point (DEC-129, SEC-KLO-01): the MIA key may reach
one host over https, through fixed paths, for configured models only. Nothing a
user or a model writes can move it, a redirect cannot carry it away, and no
error message repeats it, the prompt or what the server said back.
"""

from __future__ import annotations

import base64
import json
from types import SimpleNamespace

import httpx
import pytest
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from kkb_agent.agent import AnalyticalPlan, Session, ToolRegistry, ToolResult, ToolSpec, ToolStatus
from kkb_agent.llm import (
    APPROVED_HOSTS,
    CapabilityUnavailable,
    ConfigurationError,
    KloudeksProvider,
    LLMProvider,
    Message,
    ModelUnavailable,
    ProviderConfig,
    ProviderError,
    RateLimited,
    Refused,
    Role,
    SchemaViolation,
    TransportError,
    approved_base_url,
    kloudeks,
)
from kkb_agent.llm import config as env
from kkb_agent.llm.structured import schema_instructions

DEC_129_URL = "https://mia.csp.kloudeks.com/v1"
CHAT_MODEL = "kkbhackathon2026/Qwen3.8-27B"
EMBED_MODEL = "kkbhackathon2026/Qwen3-Embedding-8B"
CANARY = "zzz-canary-must-never-be-printed-zzz"
PROMPT = "gizli prompt metni: konut kredisi"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def config(**changes) -> ProviderConfig:
    settings = {
        "base_url": DEC_129_URL,
        "credential": SecretStr(CANARY),
        "planner_model": CHAT_MODEL,
        "router_model": CHAT_MODEL,
        "vision_model": CHAT_MODEL,
        "embedding_model": EMBED_MODEL,
    }
    settings.update(changes)
    return ProviderConfig(**settings)


class Server:
    """Stands in for the endpoint: records every request, replays responses."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def bodies(self) -> list[dict]:
        return [json.loads(request.content) for request in self.requests]


def chat(text, finish="stop", **message) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text, **message},
                    "finish_reason": finish,
                }
            ]
        },
    )


def provider(server: Server, **changes) -> KloudeksProvider:
    return KloudeksProvider(config(**changes), transport=httpx.MockTransport(server))


def ask(target: KloudeksProvider, **kwargs):
    return target.complete([Message(Role.USER, PROMPT)], **kwargs)


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str
    limit: int = Field(ge=1)


class TestTheKeyGoesToOneDestination:
    def test_a_completion_goes_to_the_dec_129_chat_endpoint_with_the_key(self):
        server = Server(chat("merhaba"))
        result = ask(provider(server))

        (request,) = server.requests
        assert str(request.url) == "https://mia.csp.kloudeks.com/v1/chat/completions"
        assert request.method == "POST"
        assert request.headers["authorization"] == f"Bearer {CANARY}"
        assert result.text == "merhaba"
        assert result.model == CHAT_MODEL

    def test_the_request_names_the_configured_model_and_carries_the_conversation(self):
        server = Server(chat("ok"))
        provider(server).complete([Message(Role.SYSTEM, "kurallar"), Message(Role.USER, PROMPT)])

        (body,) = server.bodies()
        assert body["model"] == CHAT_MODEL
        assert body["messages"] == [
            {"role": "system", "content": "kurallar"},
            {"role": "user", "content": PROMPT},
        ]
        assert body["temperature"] == 0.0
        assert "response_format" not in body
        # A memory/safety ceiling, generous enough never to truncate a real call.
        assert body["max_tokens"] == 16384

    def test_leading_system_turns_travel_as_one(self):
        # M4-15's live run: the served model answers 400 to two system
        # messages, and the product sends its instructions and tool list as
        # two. They are joined in order; the rest of the turn is untouched.
        server = Server(chat("ok"))
        provider(server).complete(
            [
                Message(Role.SYSTEM, "talimat"),
                Message(Role.SYSTEM, "araçlar"),
                Message(Role.USER, PROMPT),
                Message(Role.ASSISTANT, "önceki cevap"),
                Message(Role.USER, "düzelt"),
            ]
        )

        (body,) = server.bodies()
        assert body["messages"] == [
            {"role": "system", "content": "talimat\n\naraçlar"},
            {"role": "user", "content": PROMPT},
            {"role": "assistant", "content": "önceki cevap"},
            {"role": "user", "content": "düzelt"},
        ]

    def test_a_turn_without_system_messages_is_sent_as_it_is(self):
        server = Server(chat("ok"))
        ask(provider(server))
        assert server.bodies()[0]["messages"] == [{"role": "user", "content": PROMPT}]

    @pytest.mark.parametrize(
        "url",
        [
            "https://api.openai.com/v1",
            "https://mia.csp.kloudeks.com.evil.test/v1",
            "https://evil.test/v1?host=mia.csp.kloudeks.com",
            "https://mia.csp.kloudeks.com:8443/v1",
            "https://mia.csp.kloudeks.com/v2",
            "https://mia.csp.kloudeks.com/v1#fragment",
            "https://localhost/v1",
            "https://127.0.0.1/v1",
            "http://mia.csp.kloudeks.com/v1",
        ],
    )
    def test_any_other_destination_is_refused_before_a_request_exists(self, url):
        server = Server()
        with pytest.raises(ConfigurationError):
            provider(server, base_url=url)
        assert server.requests == []

    def test_credentials_in_the_url_are_refused_without_being_repeated(self):
        with pytest.raises(ConfigurationError) as refused:
            approved_base_url("https://user:secret-in-url@mia.csp.kloudeks.com/v1")
        assert "secret-in-url" not in str(refused.value)

    @pytest.mark.parametrize(
        "url", ["https://mia.csp.kloudeks.com/v1/", "https://MIA.csp.kloudeks.com/v1"]
    )
    def test_harmless_spellings_normalize_to_the_one_endpoint(self, url):
        assert approved_base_url(url) == DEC_129_URL

    def test_the_approved_host_is_dec_129s_and_only_that(self):
        assert APPROVED_HOSTS == frozenset({"mia.csp.kloudeks.com"})

    @pytest.mark.parametrize("model", ["gpt-4o", "https://evil.test/v1", EMBED_MODEL])
    def test_a_model_the_configuration_does_not_name_is_refused(self, model):
        server = Server(chat("never sent"))
        with pytest.raises(CapabilityUnavailable) as refused:
            ask(provider(server), model=model)
        assert server.requests == []
        assert model not in str(refused.value)

    def test_a_base_url_changed_after_construction_still_cannot_receive_the_key(self):
        # Belt and braces: the destination is checked on every request, so a
        # client mutated after the constructor's check still refuses.
        server = Server(chat("never sent"))
        target = provider(server)
        target._client.base_url = httpx.URL("https://evil.test/v1")
        with pytest.raises(ConfigurationError, match="outside the DEC-129 endpoint"):
            ask(target)
        assert server.requests == []

    def test_a_redirect_is_not_followed(self):
        server = Server(httpx.Response(307, headers={"location": "https://evil.test/steal"}))
        with pytest.raises(TransportError, match="redirect"):
            ask(provider(server))
        assert len(server.requests) == 1

    def test_the_client_ignores_redirects_and_the_environment(self):
        client = provider(Server())._client
        assert client.follow_redirects is False
        assert client.trust_env is False


class TestFailuresMapWithoutLeaking:
    @pytest.mark.parametrize(
        ("status", "error"),
        [
            (401, ConfigurationError),
            (403, ModelUnavailable),
            (404, ModelUnavailable),
            (429, RateLimited),
            (408, TransportError),
            (500, TransportError),
            (503, TransportError),
            (400, ProviderError),
        ],
    )
    def test_statuses_map_to_the_taxonomy_and_never_echo_the_body(self, status, error):
        echo = httpx.Response(status, json={"error": f"echo {PROMPT} {CANARY}"})
        with pytest.raises(error) as raised:
            ask(provider(Server(echo)))
        message = str(raised.value)
        assert str(status) in message
        assert PROMPT not in message and CANARY not in message

    def test_a_rate_limit_is_raised_not_answered_by_another_provider(self):
        server = Server(httpx.Response(429))
        with pytest.raises(RateLimited):
            ask(provider(server))
        assert [request.url.host for request in server.requests] == ["mia.csp.kloudeks.com"]

    @pytest.mark.parametrize("fault", [httpx.ConnectError, httpx.ReadTimeout])
    def test_transport_faults_become_transport_errors(self, fault):
        server = Server(fault(f"{PROMPT} {CANARY}"))
        with pytest.raises(TransportError) as raised:
            ask(provider(server))
        assert fault.__name__ in str(raised.value)
        assert PROMPT not in str(raised.value) and CANARY not in str(raised.value)

    def test_an_oversized_declared_body_is_refused(self, monkeypatch):
        monkeypatch.setattr(kloudeks, "MAX_RESPONSE_BYTES", 64)
        with pytest.raises(ProviderError, match="size limit"):
            ask(provider(Server(chat("x" * 200))))

    def test_an_oversized_streamed_body_is_refused(self, monkeypatch):
        monkeypatch.setattr(kloudeks, "MAX_RESPONSE_BYTES", 64)
        streamed = httpx.Response(200, content=iter([b"x" * 50, b"x" * 50]))
        with pytest.raises(ProviderError, match="size limit"):
            ask(provider(Server(streamed)))

    def test_a_body_past_the_deadline_is_abandoned(self, monkeypatch):
        clock = iter([0.0, 1_000.0])
        monkeypatch.setattr(kloudeks, "time", SimpleNamespace(monotonic=lambda: next(clock)))
        with pytest.raises(TransportError, match="deadline"):
            ask(provider(Server(chat("late"))))

    @pytest.mark.parametrize(
        "response",
        [
            httpx.Response(200, content=b"not json"),
            httpx.Response(200, json=["a", "list"]),
            httpx.Response(200, json={"choices": []}),
            httpx.Response(200, json={"choices": [{"message": {"content": None}}]}),
        ],
    )
    def test_a_malformed_body_is_a_provider_error(self, response):
        with pytest.raises(ProviderError):
            ask(provider(Server(response)))

    @pytest.mark.parametrize(
        "response",
        [chat("", finish="content_filter"), chat(None, refusal="bunu yanıtlayamam")],
    )
    def test_a_refusal_is_a_product_outcome(self, response):
        with pytest.raises(Refused):
            ask(provider(Server(response)))

    def test_the_key_never_appears_in_a_representation(self):
        target = provider(Server())
        assert CANARY not in repr(target)
        assert CANARY not in repr(target._config)


class TestStructuredOutputStaysLocal:
    def test_the_repair_loop_runs_over_the_real_transport(self):
        server = Server(
            chat('```json\n{"tool": "lakehouse"}\n```'),
            chat('{"tool": "lakehouse", "limit": 5}'),
        )
        result = ask(provider(server), schema=Plan)

        assert result.parsed == Plan(tool="lakehouse", limit=5)
        assert result.attempts == 2
        retry = server.bodies()[1]["messages"]
        assert retry[-2] == {"role": "assistant", "content": '```json\n{"tool": "lakehouse"}\n```'}
        assert retry[-1]["role"] == "user" and "rejected" in retry[-1]["content"]

    def test_the_attempt_budget_is_the_configured_one(self):
        server = Server(chat("{}"), chat("{}"))
        with pytest.raises(SchemaViolation, match="2 attempt"):
            ask(provider(server, max_attempts=2), schema=Plan)
        assert len(server.requests) == 2

    def test_json_mode_is_asked_for_only_when_configured_and_a_schema_is_wanted(self):
        server = Server(chat('{"tool": "t", "limit": 1}'), chat("düz metin"))
        target = provider(server, structured_output=True)
        ask(target, schema=Plan)
        ask(target)

        with_schema, without = server.bodies()
        assert with_schema["response_format"] == {"type": "json_object"}
        assert "response_format" not in without


class TestEmbeddings:
    def test_vectors_come_back_in_input_order(self):
        server = Server(
            httpx.Response(
                200,
                json={
                    "data": [
                        {"index": 1, "embedding": [0.0, 1.0]},
                        {"index": 0, "embedding": [1.0, 0.0]},
                    ]
                },
            )
        )
        vectors = provider(server).embed(["birinci", "ikinci"], kind="passage")

        assert vectors == [[1.0, 0.0], [0.0, 1.0]]
        (request,) = server.requests
        assert str(request.url) == "https://mia.csp.kloudeks.com/v1/embeddings"
        assert server.bodies() == [
            {"model": EMBED_MODEL, "input": ["birinci", "ikinci"], "encoding_format": "float"}
        ]

    def test_no_query_or_passage_prefix_is_invented(self):
        # Q-K-05: no convention is documented for this model, so both kinds
        # send the text exactly as given.
        reply = {"data": [{"index": 0, "embedding": [0.5]}]}
        server = Server(httpx.Response(200, json=reply), httpx.Response(200, json=reply))
        target = provider(server)
        target.embed(["konut"], kind="query")
        target.embed(["konut"], kind="passage")

        assert [body["input"] for body in server.bodies()] == [["konut"], ["konut"]]

    @pytest.mark.parametrize(
        "content",
        [
            b'{"data": []}',
            b'{"data": [{"index": 0, "embedding": [NaN]}]}',
            b'{"data": [{"index": 0, "embedding": [true]}]}',
            b'{"data": [{"index": 0, "embedding": []}]}',
            b'{"data": [{"index": 5, "embedding": [1.0]}]}',
        ],
    )
    def test_a_malformed_vector_is_refused(self, content):
        with pytest.raises(ProviderError):
            provider(Server(httpx.Response(200, content=content))).embed(["x"], kind="query")

    def test_vectors_of_different_dimensions_are_refused(self):
        reply = {"data": [{"index": 0, "embedding": [1.0]}, {"index": 1, "embedding": [1.0, 2.0]}]}
        with pytest.raises(ProviderError, match="dimensions"):
            provider(Server(httpx.Response(200, json=reply))).embed(["a", "b"], kind="query")

    def test_nothing_is_sent_for_nothing_or_without_a_model(self):
        server = Server()
        assert provider(server).embed([], kind="query") == []
        with pytest.raises(CapabilityUnavailable, match="embedding"):
            provider(server, embedding_model=None).embed(["x"], kind="query")
        assert server.requests == []


class TestVision:
    def test_an_image_travels_inline_beside_the_prompt(self):
        server = Server(chat("bir tablo"))
        result = provider(server).vision(PNG, "tabloyu oku")

        (body,) = server.bodies()
        (message,) = body["messages"]
        image, text = message["content"]
        assert image["image_url"]["url"] == "data:image/png;base64," + base64.b64encode(PNG).decode(
            "ascii"
        )
        assert text == {"type": "text", "text": "tabloyu oku"}
        assert body["model"] == CHAT_MODEL
        assert result.text == "bir tablo"

    def test_a_jpeg_is_labelled_as_one(self):
        server = Server(chat("ok"))
        provider(server).vision(b"\xff\xd8\xff\xe0rest", "oku")
        url = server.bodies()[0]["messages"][0]["content"][0]["image_url"]["url"]
        assert url.startswith("data:image/jpeg;base64,")

    @pytest.mark.parametrize(
        ("image", "match"), [(b"", "No image"), (b"GIF89a....", "PNG and JPEG")]
    )
    def test_what_cannot_be_sent_is_refused_locally(self, image, match):
        server = Server()
        with pytest.raises(ProviderError, match=match):
            provider(server).vision(image, "oku")
        assert server.requests == []

    def test_an_oversized_image_is_refused_locally(self, monkeypatch):
        monkeypatch.setattr(kloudeks, "MAX_IMAGE_BYTES", 8)
        with pytest.raises(ProviderError, match="size limit"):
            provider(Server()).vision(PNG, "oku")

    def test_vision_needs_a_configured_model(self):
        with pytest.raises(CapabilityUnavailable, match="vision"):
            provider(Server(), vision_model=None).vision(PNG, "oku")


class TestItIsTheProductsProvider:
    def test_it_satisfies_the_protocol(self):
        assert isinstance(provider(Server()), LLMProvider)

    def test_it_builds_from_the_environment(self, monkeypatch):
        for name, value in {
            env.BASE_URL: DEC_129_URL,
            env.CREDENTIAL: CANARY,
            env.PLANNER_MODEL: CHAT_MODEL,
            env.ROUTER_MODEL: CHAT_MODEL,
        }.items():
            monkeypatch.setenv(name, value)
        with KloudeksProvider.from_env() as built:
            assert str(built._client.base_url) == DEC_129_URL + "/"

    def test_a_question_is_planned_through_the_real_transport(self):
        class LakehouseArgs(BaseModel):
            model_config = ConfigDict(extra="forbid")
            series: str

        registry = ToolRegistry()
        registry.register(
            ToolSpec(
                "lakehouse",
                "Query the lakehouse",
                LakehouseArgs,
                lambda arguments, context: ToolResult(ToolStatus.SUCCESS, "s1", "lakehouse"),
            )
        )
        plan = {
            "question": "konut kredisi",
            "steps": [{"step_id": "s1", "tool": "lakehouse", "arguments": {"series": "konut"}}],
        }
        server = Server(chat(json.dumps(plan)))
        planned = Session(provider=provider(server), registry=registry).plan("konut kredisi")

        assert [item.step.tool for item in planned.plan.steps] == ["lakehouse"]
        assert server.bodies()[0]["messages"][-1] == {"role": "user", "content": "konut kredisi"}
        assert len(server.requests) == 1  # In-process MockTransport, never a live call.
        messages = server.bodies()[0]["messages"]
        assert [message["role"] for message in messages] == ["system", "user"]
        assert messages[0]["content"].count(schema_instructions(AnalyticalPlan)) == 1
        assert messages[0]["content"].count("Available tools:\n") == 1


class TestWhatACallCost:
    """Live trace 2026-09-18: most of a slow call was hidden reasoning nobody could see."""

    @staticmethod
    def costed(text, completion, reasoning_tokens=None, **message):
        response = chat(text, **message)
        document = json.loads(response.content)
        usage = {"prompt_tokens": 100, "completion_tokens": completion}
        if reasoning_tokens is not None:
            usage["completion_tokens_details"] = {"reasoning_tokens": reasoning_tokens}
        document["usage"] = usage
        return httpx.Response(200, json=document)

    def test_usage_and_reasoning_are_summed_over_repair_attempts(self):
        server = Server(
            self.costed('{"tool": "x"}', 300, 250, reasoning="first thought"),
            self.costed('{"tool": "x", "limit": 1}', 90, 40, reasoning_content="second"),
        )
        result = ask(provider(server), schema=Plan)

        assert result.parsed == Plan(tool="x", limit=1)
        assert (result.usage.prompt_tokens, result.usage.completion_tokens) == (200, 390)
        assert result.usage.reasoning_tokens == 290
        assert result.reasoning == "first thought\n\n---\n\nsecond"
        assert "first thought" not in result.text

    def test_a_platform_that_reports_nothing_leaves_both_empty(self):
        result = ask(provider(Server(chat("düz metin"))))
        assert result.usage is None and result.reasoning is None

    def test_both_calls_reason_by_default_and_each_can_be_switched_off(self):
        server = Server(chat('{"tool": "t", "limit": 1}'), chat("cümle"))
        target = provider(server)
        ask(target, schema=Plan)
        ask(target)
        planned, written = server.bodies()
        assert "chat_template_kwargs" not in planned
        assert "chat_template_kwargs" not in written

        server = Server(chat('{"tool": "t", "limit": 1}'), chat("cümle"))
        target = provider(server, planner_thinking=False)
        ask(target, schema=Plan)
        ask(target)
        planned, written = server.bodies()
        assert planned["chat_template_kwargs"] == {"enable_thinking": False}
        assert "chat_template_kwargs" not in written

        server = Server(chat('{"tool": "t", "limit": 1}'), chat("cümle"))
        target = provider(server, writer_thinking=False)
        ask(target, schema=Plan)
        ask(target)
        planned, written = server.bodies()
        assert "chat_template_kwargs" not in planned
        assert written["chat_template_kwargs"] == {"enable_thinking": False}


def test_a_completion_ceiling_below_a_real_call_is_refused_but_a_generous_one_is_used():
    """The ceiling guards runaway generation; it may not be set low enough to truncate."""
    with pytest.raises(ConfigurationError):
        config(max_output_tokens=1024)

    server = Server(chat("ok"))
    provider(server, max_output_tokens=20000).complete([Message(Role.USER, PROMPT)])
    (body,) = server.bodies()
    assert body["max_tokens"] == 20000
