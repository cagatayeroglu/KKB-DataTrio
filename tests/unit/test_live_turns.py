"""Manual live-turn driver: token stays in memory, one resend after a provider failure."""

import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "manual_live_turns", Path(__file__).parents[1] / "manual/live_turns.py"
)
assert spec and spec.loader
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)

SID, TOKEN = "s" * 32, "t" * 43


class Server:
    """Scripted turn outcomes per submission; records every request."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.requests = []
        self.turns = {}

    def __call__(self, method, path, body, headers):
        self.requests.append(
            (method, path, json.loads(body) if body and path.endswith("turns") else body, headers)
        )
        if path == "/v1/sessions":
            return 201, {"session_id": SID, "token": TOKEN}
        if path.endswith("/documents"):
            return 201, {"document_ref": "d" * 32, "document_format": "csv"}
        if method == "POST":
            turn_id = f"{len(self.turns):032d}"
            outcome = self.outcomes.pop(0)
            self.turns[turn_id] = outcome
            return 202, {"turn_id": turn_id, "state": "queued"}
        turn_id = path.rsplit("/", 1)[1]
        return 200, {"turn_id": turn_id, **self.turns[turn_id]}


def accepted(ref):
    return {
        "state": "completed",
        "answer": {"status": "accepted", "result": {"result_ref": ref, "cells": [1]}},
    }


FAILED = {"state": "failed", "error": "provider_failed", "answer": None}


def test_follow_attach_and_one_resend_in_the_same_session(tmp_path):
    upload = tmp_path / "table.csv"
    upload.write_text("Ay;Faiz (%)\n2026-01;4\n")
    server = Server([accepted("a" * 32), FAILED, accepted("b" * 32)])
    logged = []
    plan = [
        {"upload": str(upload)},
        {"question": "one", "attach": True},
        {"question": "two", "follow": True},
    ]
    assert driver.run(plan, server, tmp_path, log=logged.append, poll_seconds=0)
    turns = [
        body
        for method, path, body, _ in server.requests
        if method == "POST" and path.endswith("/turns")
    ]
    assert turns[0]["document_ref"] == "d" * 32 and "selected_result_id" not in turns[0]
    assert turns[1]["selected_result_id"] == "a" * 32 and turns[1]["is_continuation"] is True
    assert (
        turns[2]["selected_result_id"] == "a" * 32
        and turns[2]["request_id"] != turns[1]["request_id"]
    )
    assert [(e.get("turn"), e.get("attempt")) for e in logged if "turn" in e] == [
        (1, 1),
        (2, 1),
        (2, 2),
    ]
    assert all(
        h.get("X-KKB-Session-Token") == TOKEN
        for m, p, _, h in server.requests
        if p != "/v1/sessions"
    )
    assert TOKEN not in json.dumps(logged)
    assert (tmp_path / "turn2-attempt2.json").exists()


def test_a_second_failure_or_a_refusal_stops_the_run(tmp_path):
    server = Server([FAILED, FAILED])
    logged = []
    plan = [{"question": "one"}, {"question": "never sent"}]
    assert not driver.run(plan, server, tmp_path, log=logged.append, poll_seconds=0)
    assert logged[-1] == {"stopped_at": 1}
    assert len([r for r in server.requests if r[0] == "POST" and r[1].endswith("/turns")]) == 2
