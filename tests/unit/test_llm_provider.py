"""M4 regressions for the provider boundary.

No networking anywhere. The point of these is that the planner, router and tools
can be built and exercised before a Kloudeks credential exists, and that the
paths which will actually fail on demo day — malformed JSON, a refusal, a rate
limit, an absent capability — are covered now rather than discovered then.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict, Field

from kkb_agent.llm import (
    CapabilityUnavailable,
    ConfigurationError,
    Message,
    ModelUnavailable,
    ProviderConfig,
    ProviderError,
    RateLimited,
    Refused,
    Role,
    SchemaViolation,
    ScriptedProvider,
    TransportError,
    extract_json,
    parse_structured,
    repair_feedback,
    scripted,
)
from kkb_agent.llm import config as env

# A distinctive canary rather than a realistic key: the repository secret scan
# is meant to flag `secret = "..."` shaped lines, and a test should not have to
# be excused from a control it exists to prove works.
CANARY = "zzz-canary-must-never-be-printed-zzz"
COMPLETE_ENV = {
    env.BASE_URL: "https://kloudeks.example/v1",
    env.CREDENTIAL: CANARY,
    env.PLANNER_MODEL: "big-model",
    env.ROUTER_MODEL: "small-model",
}


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str
    limit: int = Field(ge=1)


def ask(provider, schema=None):
    return provider.complete([Message(Role.USER, "konut kredisi")], schema=schema)


class TestConfigurationComesFromTheEnvironment:
    def test_a_complete_environment_resolves(self):
        config = ProviderConfig.from_env(COMPLETE_ENV)
        assert config.planner_model == "big-model"
        assert config.router_model == "small-model"
        assert config.credential.get_secret_value() == CANARY

    def test_every_missing_setting_is_named_at_once(self):
        with pytest.raises(ConfigurationError) as excinfo:
            ProviderConfig.from_env({env.BASE_URL: "https://x.example"})
        message = str(excinfo.value)
        # One restart should reveal every fault, not the first one.
        for name in (env.CREDENTIAL, env.PLANNER_MODEL, env.ROUTER_MODEL):
            assert name in message

    def test_a_blank_value_counts_as_missing(self):
        with pytest.raises(ConfigurationError, match=env.PLANNER_MODEL):
            ProviderConfig.from_env({**COMPLETE_ENV, env.PLANNER_MODEL: "   "})

    def test_a_plaintext_endpoint_is_refused(self):
        with pytest.raises(ConfigurationError, match="https"):
            ProviderConfig.from_env({**COMPLETE_ENV, env.BASE_URL: "http://kloudeks.example"})

    def test_a_malformed_number_names_the_setting_not_the_value(self):
        with pytest.raises(ConfigurationError) as excinfo:
            ProviderConfig.from_env({**COMPLETE_ENV, env.REQUEST_TIMEOUT: "banana"})
        assert env.REQUEST_TIMEOUT in str(excinfo.value)
        assert "banana" not in str(excinfo.value)

    @pytest.mark.parametrize("raw", ["true", "YES", "1", "on"])
    def test_flags_accept_the_usual_spellings(self, raw):
        assert ProviderConfig.from_env(
            {**COMPLETE_ENV, env.STRUCTURED_OUTPUT: raw}
        ).structured_output

    def test_a_nonsense_flag_is_refused_rather_than_treated_as_false(self):
        with pytest.raises(ConfigurationError, match="boolean"):
            ProviderConfig.from_env({**COMPLETE_ENV, env.STRUCTURED_OUTPUT: "maybe"})

    def test_structured_output_defaults_to_false(self):
        # Until Q-K-03 is answered, assuming JSON mode exists would strand the
        # planner on a platform that does not offer it.
        assert ProviderConfig.from_env(COMPLETE_ENV).structured_output is False


class TestCapabilitiesAreReportedNotAssumed:
    def test_an_absent_model_means_the_capability_is_unavailable(self):
        capabilities = ProviderConfig.from_env(COMPLETE_ENV).capabilities()
        assert capabilities == {
            "complete": True,
            "structured_output": False,
            "embed": False,
            "vision": False,
        }

    def test_configuring_the_models_enables_them(self):
        config = ProviderConfig.from_env(
            {**COMPLETE_ENV, env.EMBEDDING_MODEL: "e5", env.VISION_MODEL: "vlm"}
        )
        assert config.capabilities()["embed"] and config.capabilities()["vision"]


class TestSecretsStayOutOfOutput:
    def test_the_credential_is_not_in_the_representation(self):
        config = ProviderConfig.from_env(COMPLETE_ENV)
        assert CANARY not in repr(config)
        assert CANARY not in str(config)

    def test_the_credential_is_not_in_a_configuration_error(self):
        with pytest.raises(ConfigurationError) as excinfo:
            ProviderConfig.from_env({**COMPLETE_ENV, env.BASE_URL: "http://x.example"})
        assert CANARY not in str(excinfo.value)

    def test_prompt_text_is_not_in_a_message_representation(self):
        # A prompt carries the user's question and selected source rows.
        message = Message(Role.USER, "2021 konut kredisi ve faiz oranları")
        assert "konut" not in repr(message)

    def test_response_text_is_not_in_a_completion_representation(self):
        completion = ask(scripted("sensitive model output"))
        assert "sensitive" not in repr(completion)

    def test_a_schema_violation_names_fields_not_values(self):
        with pytest.raises(SchemaViolation) as excinfo:
            parse_structured('{"tool": "lakehouse", "limit": "GİZLİ_DEĞER"}', Plan)
        message = str(excinfo.value)
        assert "limit" in message
        assert "GİZLİ_DEĞER" not in message


class TestJsonExtraction:
    def test_a_bare_object_passes_through(self):
        assert extract_json('{"a": 1}') == '{"a": 1}'

    def test_a_fenced_object_is_unwrapped(self):
        assert extract_json('```json\n{"a": 1}\n```') == '{"a": 1}'

    def test_preamble_prose_is_discarded(self):
        assert extract_json('Sure, here it is: {"a": 1} Hope that helps!') == '{"a": 1}'

    def test_multiple_objects_are_rejected_rather_than_selecting_one(self):
        with pytest.raises(SchemaViolation, match="multiple or partial"):
            extract_json('{"a": {"b": 2}} trailing {"c": 3}')

    def test_braces_inside_strings_do_not_confuse_the_scan(self):
        assert extract_json('{"a": "} not the end {"}') == '{"a": "} not the end {"}'

    def test_no_object_is_reported_rather_than_guessed(self):
        with pytest.raises(SchemaViolation, match="no JSON object"):
            extract_json("I cannot help with that.")

    def test_an_unterminated_object_is_reported(self):
        with pytest.raises(SchemaViolation, match="unterminated"):
            extract_json('{"a": 1')


class TestStrictValidation:
    def test_a_valid_object_parses(self):
        assert parse_structured('{"tool": "lakehouse", "limit": 5}', Plan).tool == "lakehouse"

    def test_a_trailing_comma_is_punctuation_and_is_repaired(self):
        """The keys and values are the model's own; only the comma is dropped.

        Refusing this cost a whole turn live (2026-09-22): the planner had searched,
        `web_url` had loaded the TCMB decision page, and the continuation that decides
        what to do with it came back with a stray comma, so the answer abstained on a
        page already in hand. Strict validation still runs on the repaired document.
        """
        assert parse_structured('{"tool": "lakehouse", "limit": 5,}', Plan).limit == 5

    def test_an_extra_field_is_rejected_not_ignored(self):
        # A plan that deserializes is not a plan that may be executed.
        with pytest.raises(SchemaViolation, match="extra"):
            parse_structured('{"tool": "lakehouse", "limit": 5, "shell": "rm -rf /"}', Plan)

    def test_a_constraint_violation_is_rejected(self):
        with pytest.raises(SchemaViolation, match="limit"):
            parse_structured('{"tool": "lakehouse", "limit": 0}', Plan)

    def test_a_json_array_is_rejected(self):
        # Rejected during extraction rather than validation: a plan is an
        # object, so a response with no object in it never reaches the schema.
        with pytest.raises(SchemaViolation, match="no JSON object"):
            parse_structured("[1, 2, 3]", Plan)

    def test_the_feedback_states_the_fault_and_the_schema(self):
        feedback = repair_feedback(Plan, "limit: greater_than_equal")
        assert "limit: greater_than_equal" in feedback
        assert "complete schema-valid JSON object only" in feedback


class TestTheRepairLoop:
    def test_a_malformed_first_answer_is_corrected_on_retry(self):
        provider = scripted("not json at all", '{"tool": "lakehouse", "limit": 5}')
        completion = ask(provider, Plan)
        assert completion.parsed == Plan(tool="lakehouse", limit=5)
        assert completion.attempts == 2

    def test_the_retry_prompt_carries_the_fault_back(self):
        provider = scripted("nope", '{"tool": "lakehouse", "limit": 5}')
        ask(provider, Plan)
        retry = provider.seen[-1]
        assert [message.role for message in retry[-2:]] == [Role.ASSISTANT, Role.USER]
        assert "rejected" in retry[-1].content

    def test_the_budget_is_bounded_and_the_failure_is_explicit(self):
        provider = ScriptedProvider(responses=["bad", "worse", "worst"], max_attempts=3)
        with pytest.raises(SchemaViolation, match="after 2 attempt"):
            ask(provider, Plan)
        assert provider.responses == ["worst"]

    def test_without_a_schema_the_text_is_returned_unparsed(self):
        completion = ask(scripted("free prose"))
        assert completion.text == "free prose"
        assert completion.parsed is None
        assert completion.attempts == 1


class TestScriptedFailureModes:
    @pytest.mark.parametrize(
        "error",
        [
            TransportError("connection reset"),
            RateLimited("quota exceeded"),
            ModelUnavailable("no such model"),
            Refused("declined"),
        ],
    )
    def test_each_failure_reaches_the_caller_unchanged(self, error):
        with pytest.raises(type(error)):
            ask(scripted(error))

    def test_a_rate_limit_is_a_transport_error(self):
        # Callers retry transport faults; the taxonomy has to say which ones.
        assert issubclass(RateLimited, TransportError)
        assert not issubclass(ModelUnavailable, TransportError)

    def test_running_out_of_script_is_an_error_not_an_empty_answer(self):
        with pytest.raises(ProviderError, match="ran out of responses"):
            ask(ScriptedProvider())


class TestOptionalCapabilities:
    def test_embedding_distinguishes_queries_from_passages(self):
        provider = ScriptedProvider()
        text = "konut kredisi"
        assert provider.embed([text], kind="query") != provider.embed([text], kind="passage")

    def test_embedding_is_refused_when_unconfigured(self):
        with pytest.raises(CapabilityUnavailable, match="embedding"):
            ScriptedProvider(embedding_dimension=None).embed(["x"], kind="query")

    def test_vision_is_refused_when_unconfigured(self):
        with pytest.raises(CapabilityUnavailable, match="vision"):
            ScriptedProvider().vision(b"\x89PNG", "read this")

    def test_vision_returns_a_completion_when_configured(self):
        provider = ScriptedProvider(responses=["a table of gold prices"], supports_vision=True)
        assert provider.vision(b"\x89PNG", "read this").text == "a table of gold prices"

    def test_an_empty_image_is_refused(self):
        with pytest.raises(ProviderError, match="No image"):
            ScriptedProvider(supports_vision=True).vision(b"", "read this")


class TestTheBoundaryHoldsTheLine:
    def test_no_third_party_hosted_llm_is_named_in_the_package(self):
        # DEC-129 permits the openai SDK as a Kloudeks-only client, so an
        # import name proves nothing either way (M4-07, blocker F). Hosted
        # endpoints, their key variables and other vendors' SDKs do; where the
        # key actually goes is tested against the transport in
        # test_kloudeks_provider.py.
        from pathlib import Path

        package = Path(__file__).resolve().parents[2] / "src/kkb_agent"
        source = "\n".join(path.read_text(encoding="utf-8") for path in package.rglob("*.py"))
        for banned in (
            "api.openai.com",
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "anthropic",
            "google.generativeai",
            "generativelanguage.googleapis.com",
        ):
            assert banned not in source

    def test_only_the_kloudeks_module_builds_a_model_client(self):
        # DEC-002 stays checkable by inspection: one module holds the client
        # that carries the key, so a second route would have to add another.
        from pathlib import Path

        package = Path(__file__).resolve().parents[2] / "src/kkb_agent"
        clients = {
            path.relative_to(package).as_posix()
            for path in package.rglob("*.py")
            if "import httpx" in path.read_text(encoding="utf-8")
        }
        assert clients == {"llm/kloudeks.py"}

    def test_the_scripted_provider_satisfies_the_protocol(self):
        from kkb_agent.llm import LLMProvider

        assert isinstance(ScriptedProvider(), LLMProvider)


@pytest.mark.parametrize(
    "text",
    [
        '[{"tool":"lakehouse","limit":5}]',
        '{"tool":"lakehouse","limit":5} {',
    ],
)
def test_structural_damage_requires_replacement_not_silent_parser_repair(text):
    """An array or a second object is a different answer, not a mistyped one.

    A trailing comma is punctuation and is repaired; these are not, because guessing
    which object was meant would be the harness writing the plan.
    """
    with pytest.raises(SchemaViolation):
        parse_structured(text, Plan)
