"""M4-15: one question through the whole product, reported stage by stage.

Offline only. The command is driven with a scripted provider and with the real
Kloudeks transport over a mock, so what is checked is the report: that it shows
the plan, each tool, the results and the gated answer, that failures surface
as categories, and that the key never reaches it.
"""

from __future__ import annotations

import json

import httpx
from pydantic import SecretStr

from kkb_agent import live_check
from kkb_agent.llm import KloudeksProvider, ProviderConfig, RateLimited, scripted
from kkb_agent.llm import config as env

CANARY = "zzz-canary-must-never-be-printed-zzz"
MODEL = "kkbhackathon2026/Qwen3.8-27B"

PLAN = json.dumps(
    {
        "question": "konut kredisi ne kadar değişti",
        "steps": [
            {
                "step_id": "s1",
                "tool": "change_detection",
                "arguments": {
                    "operation": "compare",
                    "series_id": "bddk:konut",
                    "start": "2026-04-30",
                    "end": "2026-06-30",
                },
            }
        ],
    }
)
#: 801438 - 767314, written the way a Turkish answer writes it.
DRAFT = "Nisan'dan Haziran 2026'ya konut kredisi stoğu 34.124 milyon TL arttı."


def test_a_question_runs_through_every_stage(tmp_path):
    report = live_check.run_live_check(scripted(PLAN, DRAFT), tmp_path / "lake")

    assert report["passed"] is True
    assert report["completions"] == [1, 1]
    assert report["plan"]["attempts"] == 1
    assert report["plan"]["steps"] == [
        {
            "tool": "change_detection",
            "arguments": {
                "operation": "compare",
                "series_id": "bddk:konut",
                "start": "2026-04-30",
                "end": "2026-06-30",
            },
        }
    ]
    assert report["tools"] == [{"tool": "change_detection", "status": "success", "error": None}]
    assert report["results"][0]["status"] == "computed"
    assert report["answer"]["status"] == "accepted"
    assert "34.124" in report["answer"]["text"]


def test_an_invented_figure_is_withheld_and_the_reason_reported(tmp_path):
    draft = DRAFT + " Temmuz'da 50.000 milyon TL daha artacak."
    report = live_check.run_live_check(scripted(PLAN, draft), tmp_path / "lake")

    assert report["answer"]["status"] == "qualified"
    assert "50.000" not in report["answer"]["text"]
    assert report["answer"]["withheld"]


def test_a_plan_that_never_parses_is_reported_as_a_planning_failure(tmp_path):
    report = live_check.run_live_check(
        scripted("plan yok", "hâlâ yok", "yine yok"), tmp_path / "lake"
    )

    assert report["passed"] is False
    assert report["failed"] == "PlanningFailed"


def test_a_provider_failure_is_reported_by_category(tmp_path):
    report = live_check.run_live_check(scripted(RateLimited("429")), tmp_path / "lake")

    assert report["failed"] == "RateLimited"
    assert report["passed"] is False


def test_the_real_transport_carries_the_question_and_the_key_stays_out(tmp_path):
    replies = [
        httpx.Response(200, json={"choices": [{"message": {"content": text}}]})
        for text in (PLAN, DRAFT)
    ]
    seen: list[httpx.Request] = []

    def server(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return replies.pop(0)

    config = ProviderConfig(
        base_url="https://mia.csp.kloudeks.com/v1",
        credential=SecretStr(CANARY),
        planner_model=MODEL,
        router_model=MODEL,
    )
    with KloudeksProvider(config, transport=httpx.MockTransport(server)) as provider:
        report = live_check.run_live_check(provider, tmp_path / "lake")

    assert report["passed"] is True
    assert [request.url.path for request in seen] == ["/v1/chat/completions"] * 2
    planning, drafting = (json.loads(request.content)["messages"] for request in seen)
    assert live_check.QUESTION in planning[-1]["content"]
    # Both calls carry two system turns in the product; the platform takes one.
    assert [message["role"] for message in planning] == ["system", "user"]
    assert [message["role"] for message in drafting] == ["system", "user"]
    assert CANARY not in json.dumps(report, ensure_ascii=False)


def test_missing_settings_are_named_and_exit_2(monkeypatch, capsys):
    for name in (env.BASE_URL, env.CREDENTIAL, env.PLANNER_MODEL, env.ROUTER_MODEL):
        monkeypatch.delenv(name, raising=False)

    assert live_check.main() == 2
    assert json.loads(capsys.readouterr().out)["configuration"] == "ConfigurationError"


def test_prepared_copy_failure_is_safe_and_never_calls_the_model(tmp_path, monkeypatch):
    import shutil

    prepared = tmp_path / "prepared"
    prepared.mkdir()
    (prepared / "kkb.duckdb").write_bytes(b"synthetic; copy is mocked")
    provider = scripted()

    def fail_copy(*args, **kwargs):
        raise shutil.Error([("private-source", "private-target", CANARY)])

    monkeypatch.setattr(live_check.shutil, "copytree", fail_copy)
    report = live_check.run_prepared_check(provider, prepared, tmp_path / "work", turns=2)
    assert report == {"passed": False, "configuration": "prepared_copy_failed"}
    assert provider.seen == []
    assert CANARY not in json.dumps(report)
