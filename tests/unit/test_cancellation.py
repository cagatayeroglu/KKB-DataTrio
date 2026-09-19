"""Cancelling a turn: it stops at the next checkpoint, publishes nothing, and says so.

The provider here holds its first call open until the test has sent the cancel,
which is exactly the case that matters: a model request already in flight is
not taken back, and the turn stops as soon as that request returns.
"""

import threading
import time

import pytest
from test_catalog_continuation import proposal
from test_conversation_persistence import launch, open_conversation, owner
from test_document_table import ask

from kkb_agent.agent.cancellation import CancelToken, TurnCancelled, cancellable, checkpoint
from kkb_agent.llm import scripted

__all__ = ["launch"]


class HeldProvider:
    """The scripted provider, with its first call held until released."""

    def __init__(self, *responses):
        self.inner = scripted(*responses)
        self.entered = threading.Event()
        self.release = threading.Event()
        self.calls = 0

    def complete(self, *args, **kwargs):
        self.calls += 1
        if self.calls == 1:
            self.entered.set()
            assert self.release.wait(10), "the test never released the held call"
        return self.inner.complete(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.inner, name)


def wait_for(client, path, headers, done=("completed", "failed")):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        body = client.get(path, headers=headers).json()
        if body["state"] in done:
            return body
        time.sleep(0.02)
    raise AssertionError("turn did not finish")


def discover():
    return {"step_id": "d", "tool": "catalog_search", "arguments": {"query": "konut kredisi"}}


def test_a_running_turn_stops_at_its_next_checkpoint(launch, monkeypatch):
    held = HeldProvider(proposal(discover()), "never reached")
    monkeypatch.setattr("test_conversation_persistence.scripted", lambda *r: held)
    _, client = launch()
    token = owner(client)
    sid, headers, _ = open_conversation(client, token)

    path = f"/v1/sessions/{sid}/turns"
    admitted = client.post(
        path, json={"request_id": "a" * 32, "question": "Kredi"}, headers=headers
    )
    assert admitted.status_code == 202
    turn_id = admitted.json()["turn_id"]
    assert held.entered.wait(10)

    cancelled = client.post(f"{path}/{turn_id}/cancel", json={}, headers=headers)
    assert cancelled.status_code == 202 and cancelled.json()["state"] == "running"
    held.release.set()

    finished = wait_for(client, f"{path}/{turn_id}", headers)
    assert (finished["state"], finished["error"]) == ("failed", "cancelled")
    assert finished["answer"] is None
    assert held.calls == 1  # the planned tool step never ran and nothing was written

    run = client.get(f"/v1/conversations/{sid}/runs", headers=headers).json()["runs"][0]
    assert run["status"] == "cancelled"
    steps = client.get(f"/v1/conversations/{sid}/runs/{run['run_id']}", headers=headers).json()[
        "steps"
    ]
    stopped = [step for step in steps if step["name"] == "turn.cancelled"]
    assert stopped and stopped[0]["attributes"]["at"] == "tool.catalog_search"
    # The service is free again: a new question is admitted.
    again = client.post(path, json={"request_id": "b" * 32, "question": "x"}, headers=headers)
    assert again.status_code == 202


def test_cancelling_a_finished_turn_changes_nothing(launch):
    import json

    reply = json.dumps({"question": "q", "steps": [], "clarification": None, "reply": "Merhaba."})
    _, client = launch(reply)
    token = owner(client)
    sid, headers, _ = open_conversation(client, token)
    answered = ask(client, sid, headers, "Merhaba")

    again = client.post(
        f"/v1/sessions/{sid}/turns/{answered['turn_id']}/cancel", json={}, headers=headers
    )
    assert again.status_code == 202
    assert again.json()["state"] == "completed" and again.json()["answer"] is not None


def test_deleting_a_running_chat_cancels_then_cleans_without_losing_trace(launch, monkeypatch):
    held = HeldProvider(proposal(discover()), "never reached")
    monkeypatch.setattr("test_conversation_persistence.scripted", lambda *r: held)
    runner, client = launch()
    owner_token = owner(client)
    sid, headers, _ = open_conversation(client, owner_token)
    admitted = client.post(
        f"/v1/sessions/{sid}/turns",
        json={"request_id": "e" * 32, "question": "Kredi"},
        headers=headers,
    )
    assert admitted.status_code == 202 and held.entered.wait(10)
    owner_headers = {"X-KKB-Owner-Token": owner_token}
    assert client.delete(f"/v1/conversations/{sid}", headers=owner_headers).status_code == 200
    assert client.get(f"/v1/conversations/{sid}", headers=headers).status_code == 404
    turn_id = admitted.json()["turn_id"]
    assert client.get(f"/v1/sessions/{sid}/turns/{turn_id}", headers=headers).status_code == 404
    assert client.delete(f"/v1/conversations/{sid}/runs", headers=owner_headers).status_code == 409
    held.release.set()

    deadline = time.monotonic() + 10
    while (runner.run_root / sid).exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert not (runner.run_root / sid).exists()
    runs = client.get(f"/v1/conversations/{sid}/runs", headers=headers).json()["runs"]
    assert len(runs) == 1 and runs[0]["status"] == "cancelled"
    assert held.calls == 1


def test_a_stranger_or_an_unknown_turn_cannot_be_cancelled(launch):
    import json

    reply = json.dumps({"question": "q", "steps": [], "clarification": None, "reply": "Merhaba."})
    _, client = launch(reply)
    sid, headers, _ = open_conversation(client, owner(client))
    _, stranger, _ = open_conversation(client, owner(client))
    real = ask(client, sid, headers, "Merhaba")["turn_id"]
    base = f"/v1/sessions/{sid}/turns"

    assert client.post(f"{base}/{'c' * 32}/cancel", json={}, headers=headers).status_code == 404
    # Another conversation's key cannot reach this conversation's real turn.
    foreign = client.post(f"{base}/{real}/cancel", json={}, headers=stranger)
    assert foreign.status_code in (403, 404)
    assert client.get(f"{base}/{real}", headers=headers).json()["state"] == "completed"


def test_checkpoints_do_nothing_outside_a_turn_and_stop_inside_a_cancelled_one():
    checkpoint("anywhere")  # no flag in this context
    token = CancelToken()
    with cancellable(token):
        checkpoint("before")
        token.cancel()
        with pytest.raises(TurnCancelled, match="after"):
            checkpoint("after")
    assert token.where == "after"
    checkpoint("outside again")
