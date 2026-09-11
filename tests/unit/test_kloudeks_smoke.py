"""M4-12: the live smoke reports what happened and nothing it should not.

Offline only. The smoke is driven through the real transport against a mock,
so its report is checked for the one property that matters before it is run
against the platform: it can be pasted into a record — no key, no model text.
"""

from __future__ import annotations

import json

import httpx
from pydantic import SecretStr

from kkb_agent.llm import KloudeksProvider, ProviderConfig, smoke
from kkb_agent.llm import config as env

CANARY = "zzz-canary-must-never-be-printed-zzz"
MODEL = "kkbhackathon2026/Qwen3.8-27B"
SECRET_REPLY_TEXT = "model-text-that-must-stay-out-of-the-report"


def provider(*responses: httpx.Response, embedding_model=MODEL + "-embed") -> KloudeksProvider:
    queue = list(responses)
    config = ProviderConfig(
        base_url="https://mia.csp.kloudeks.com/v1",
        credential=SecretStr(CANARY),
        planner_model=MODEL,
        router_model=MODEL,
        embedding_model=embedding_model,
    )
    return KloudeksProvider(config, transport=httpx.MockTransport(lambda request: queue.pop(0)))


def chat(text: str) -> httpx.Response:
    return httpx.Response(
        200, json={"choices": [{"message": {"content": text}, "finish_reason": "stop"}]}
    )


def embedding(dimension: int) -> httpx.Response:
    return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.1] * dimension}]})


def ticking():
    now = iter(range(0, 1000, 1))
    return lambda: float(next(now))


class TestTheReport:
    def test_a_good_run_reports_model_attempts_latency_and_dimension(self):
        reply = f'{{"status": "ok", "total": 5}} {SECRET_REPLY_TEXT}'
        report = smoke.run_smoke(provider(chat(reply), embedding(4096)), clock=ticking())

        assert report["passed"] is True
        assert report["chat"] == {
            "outcome": "ok",
            "model": MODEL,
            "attempts": 1,
            "finish_reason": "stop",
            "answer_correct": True,
            "latency_ms": 1000,
        }
        assert report["embedding"] == {
            "outcome": "ok",
            "vectors": 1,
            "dimension": 4096,
            "latency_ms": 1000,
        }

    def test_a_wrong_sum_is_reported_not_hidden(self):
        report = smoke.run_smoke(provider(chat('{"status": "ok", "total": 6}'), embedding(8)))
        assert report["chat"]["answer_correct"] is False

    def test_failures_are_reported_by_category(self):
        report = smoke.run_smoke(provider(httpx.Response(401), httpx.Response(429)))

        assert report["passed"] is False
        assert report["chat"]["outcome"] == "ConfigurationError"
        assert report["embedding"]["outcome"] == "RateLimited"

    def test_nothing_sensitive_reaches_the_report(self):
        for report in (
            smoke.run_smoke(
                provider(chat(f'{{"status":"ok","total":5}} {SECRET_REPLY_TEXT}'), embedding(8))
            ),
            smoke.run_smoke(provider(httpx.Response(401, text=CANARY), httpx.Response(500))),
        ):
            printed = json.dumps(report)
            assert CANARY not in printed
            assert SECRET_REPLY_TEXT not in printed

    def test_a_missing_embedding_model_is_a_reported_outcome(self):
        report = smoke.run_smoke(
            provider(chat('{"status": "ok", "total": 5}'), embedding_model=None)
        )
        assert report["embedding"]["outcome"] == "CapabilityUnavailable"
        assert report["passed"] is False


class TestTheEntryPoint:
    def test_missing_settings_are_named_and_exit_2(self, monkeypatch, capsys):
        for name in (env.BASE_URL, env.CREDENTIAL, env.PLANNER_MODEL, env.ROUTER_MODEL):
            monkeypatch.delenv(name, raising=False)

        assert smoke.main() == 2
        printed = json.loads(capsys.readouterr().out)
        assert printed["configuration"] == "ConfigurationError"
        assert env.CREDENTIAL in printed["detail"]

    def test_a_run_prints_the_report_and_exits_by_its_verdict(self, monkeypatch, capsys):
        built = provider(chat('{"status": "ok", "total": 5}'), embedding(16))
        monkeypatch.setattr(smoke.KloudeksProvider, "from_env", classmethod(lambda cls: built))

        assert smoke.main() == 0
        printed = json.loads(capsys.readouterr().out)
        assert printed["passed"] is True
        assert printed["embedding"]["dimension"] == 16
        assert CANARY not in json.dumps(printed)
