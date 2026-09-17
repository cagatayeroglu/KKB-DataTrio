"""A turn's trace: the context that went to the model, what it returned, what ran.

Nothing here is reconstructed. Every step is written where the work happened, so
these tests assert on facts the harness observed: prompts, the planner's own
output, tool arguments and results, the gate's decision and the publication.
"""

import json

import pytest
from test_catalog_continuation import TOTAL, proposal
from test_conversation_persistence import launch, open_conversation, owner, upload
from test_document_dataset import table_step
from test_document_table import ask, step

__all__ = ["launch"]  # the fixture is imported for use here


def reply(text):
    return json.dumps({"question": "q", "steps": [], "clarification": None, "reply": text})


def trace(client, sid, headers, run_id):
    return client.get(f"/v1/conversations/{sid}/runs/{run_id}", headers=headers).json()


def test_a_turn_records_its_context_the_model_output_and_every_tool_call(launch):
    runner, client = launch(
        table_step(),
        "Başvuru tablosu hazır.",
        step("a", "table_transform", operation="add_series", source="analiz_1", series_id=TOTAL),
        "Konut kredisi eklendi.",
    )
    owner_token = owner(client)
    sid, headers, _ = open_conversation(client, owner_token)
    document = upload(client, sid, headers)
    first = ask(client, sid, headers, "Belgeden aylık tablo yap.", document_ref=document)
    assert first["answer"]["status"] == "accepted", first

    listed = client.get(f"/v1/conversations/{sid}/runs", headers=headers).json()["runs"]
    assert len(listed) == 1
    assert listed[0]["status"] == "completed" and listed[0]["answer_status"] == "accepted"
    assert listed[0]["question"] == "Belgeden aylık tablo yap."
    assert listed[0]["duration_ms"] >= 0 and listed[0]["result_ref"]

    detail = trace(client, sid, headers, listed[0]["run_id"])
    steps = detail["steps"]
    stages = [item["stage"] for item in steps]
    names = [item["name"] for item in steps]
    assert stages[0] == "request" and stages[1] == "context"
    assert "planning" in stages and "tool" in stages
    assert "verification" in stages and "publication" in stages
    assert [item["sequence"] for item in steps] == sorted(item["sequence"] for item in steps)

    # The context that actually went to the model, verbatim, role by role.
    planning = next(item for item in steps if item["name"] == "planner.initial")
    assert planning["attributes"]["phase"] == "initial"
    assert planning["attributes"]["prompt_bytes"] > 0
    assert "[system]" in planning["detail"] and "[user]" in planning["detail"]
    assert "Belgeden aylık tablo yap." in planning["detail"]
    assert "Documents uploaded in this conversation" in planning["detail"]

    # What the model returned, as it returned it.
    output = next(item for item in steps if item["name"] == "planner.output")
    assert output["attributes"]["decision"] == "plan"
    assert output["attributes"]["tools"] == "web_url"
    assert json.loads(output["detail"])["steps"][0]["tool"] == "web_url"

    # The tool call: its arguments and a checkable preview of what came back.
    tool = next(item for item in steps if item["stage"] == "tool")
    assert tool["name"] == "web_url" and tool["attributes"]["step_id"] == "t"
    assert tool["attributes"]["status"] == "success"
    assert '"period_column": "Ay"' in tool["detail"]
    assert "columns: Başvuru Sayısı" in tool["detail"] and "values: 12" in tool["detail"]

    gate = next(item for item in steps if item["stage"] == "verification")
    assert gate["attributes"]["status"] == "accepted"
    published = next(item for item in steps if item["name"] == "workspace.published")
    assert published["attributes"]["workspace_name"] == "analiz_1"
    assert published["attributes"]["version"] == first["answer"]["result"]["version"]
    # The answer text came from somewhere visible: the harness or the model.
    assert "planner.initial" in names
    assert [name for name in names if name.startswith("draft.")] in (
        ["draft.deterministic"],
        ["draft.model"],
    )


def test_a_rejected_plan_and_its_repair_are_both_visible(launch):
    # The first proposal names a tool that does not exist; the harness rejects it.
    invalid = json.dumps(
        {
            "question": "q",
            "steps": [{"step_id": "s", "tool": "shell", "arguments": {}}],
            "clarification": None,
        }
    )
    _, client = launch(invalid, reply("Merhaba, nasıl yardımcı olabilirim?"))
    owner_token = owner(client)
    sid, headers, _ = open_conversation(client, owner_token)
    answer = ask(client, sid, headers, "Merhaba")
    assert answer["answer"]["status"] == "accepted", answer

    run = client.get(f"/v1/conversations/{sid}/runs", headers=headers).json()["runs"][0]
    steps = trace(client, sid, headers, run["run_id"])["steps"]
    rejected = next(item for item in steps if item["name"] == "plan.rejected")
    assert rejected["status"] == "rejected" and rejected["attributes"]["attempt"] == 1
    assert "shell" in rejected["attributes"]["reason"]
    attempts = [
        item["attributes"]["attempt"] for item in steps if item["name"] == "planner.initial"
    ]
    assert attempts == [1, 2]  # the repair is a second recorded call, not a silent retry
    decisions = [
        item["attributes"]["decision"] for item in steps if item["name"] == "planner.output"
    ]
    assert decisions[-1] == "reply"
    assert not [item for item in steps if item["stage"] == "tool"]
    assert next(item for item in steps if item["name"] == "workspace.not_published")


def test_traces_survive_a_restart_and_opening_one_calls_no_model(launch):
    runner, client = launch(table_step(), "Tablo hazır.")
    owner_token = owner(client)
    sid, headers, _ = open_conversation(client, owner_token)
    document = upload(client, sid, headers)
    ask(client, sid, headers, "Belgeden aylık tablo yap.", document_ref=document)

    # --- restart with a provider that would fail if anything asked it for text.
    reopened_runner, reopened = launch()
    runs = reopened.get(f"/v1/conversations/{sid}/runs", headers=headers).json()["runs"]
    assert len(runs) == 1
    steps = trace(reopened, sid, headers, runs[0]["run_id"])["steps"]
    assert [item["name"] for item in steps if item["stage"] == "planning"] == [
        "planner.initial",
        "planner.output",
    ]
    assert any("Belgeden aylık tablo yap." in (item["detail"] or "") for item in steps)
    assert reopened_runner._provider.seen == []  # reading a trace runs nothing


def test_a_trace_belongs_to_its_conversation_and_carries_no_secret(launch):
    _, client = launch(reply("Merhaba!"), reply("Merhaba!"))
    owner_token = owner(client)
    first_id, first_headers, _ = open_conversation(client, owner_token)
    second_id, second_headers, _ = open_conversation(client, owner_token)
    ask(client, first_id, first_headers, "Merhaba")
    ask(client, second_id, second_headers, "Selam")

    first_run = client.get(f"/v1/conversations/{first_id}/runs", headers=first_headers).json()[
        "runs"
    ][0]
    # The other conversation cannot open this run, even with its own valid token.
    assert (
        client.get(
            f"/v1/conversations/{second_id}/runs/{first_run['run_id']}", headers=second_headers
        ).status_code
        == 404
    )
    stranger = owner(client)
    assert (
        client.get(
            f"/v1/conversations/{first_id}/runs",
            headers={"X-KKB-Session-Token": stranger},
        ).status_code
        == 404
    )
    body = json.dumps(trace(client, first_id, first_headers, first_run["run_id"]))
    assert owner_token not in body and first_headers["X-KKB-Session-Token"] not in body


@pytest.mark.parametrize("question", ["Merhaba", "Konut kredisini göster."])
def test_every_turn_leaves_a_run_even_when_it_answers_nothing(launch, question):
    _, client = launch(proposal(clarification="unsupported_request"), "-")
    owner_token = owner(client)
    sid, headers, _ = open_conversation(client, owner_token)
    answer = ask(client, sid, headers, question)
    assert answer["answer"]["status"] == "abstained"
    (run,) = client.get(f"/v1/conversations/{sid}/runs", headers=headers).json()["runs"]
    assert run["status"] == "completed" and run["answer_status"] == "abstained"
    steps = trace(client, sid, headers, run["run_id"])["steps"]
    assert (
        next(item for item in steps if item["name"] == "planner.output")["attributes"]["decision"]
        == "clarify"
    )


def test_events_are_readable_while_the_turn_is_still_running(launch):
    """A slow tool must not hide what already happened: events are stored as they occur."""
    seen: list[int] = []
    _, client = launch(table_step(), "Tablo hazır.")
    owner_token = owner(client)
    sid, headers, _ = open_conversation(client, owner_token)
    document = upload(client, sid, headers)

    import threading

    from kkb_agent.agent import executor

    original = executor._run_step
    released = threading.Event()

    def slow(*arguments, **keywords):
        # The planner has already been recorded by the time a tool runs.
        released.set()
        assert waiting.wait(5)
        return original(*arguments, **keywords)

    waiting = threading.Event()
    executor._run_step = slow
    try:
        path = f"/v1/sessions/{sid}/turns"
        body = {
            "request_id": "f" * 32,
            "question": "Belgeden aylık tablo yap.",
            "document_ref": document,
        }
        admitted = client.post(path, json=body, headers=headers)
        assert admitted.status_code == 202, admitted.text
        assert released.wait(5)
        running = client.get(f"/v1/conversations/{sid}/runs", headers=headers).json()["runs"][0]
        assert running["status"] == "running"
        mid = trace(client, sid, headers, running["run_id"])["steps"]
        seen = [item["name"] for item in mid]
        assert "turn.received" in seen and "planner.output" in seen
        assert not [item for item in mid if item["stage"] == "tool"]
    finally:
        waiting.set()
        executor._run_step = original
    from test_prepared_api import wait_http

    done = wait_http(client, f"{path}/{admitted.json()['turn_id']}", headers)
    assert done["answer"]["status"] == "accepted", done
    after = trace(client, sid, headers, running["run_id"])["steps"]
    assert [item["name"] for item in after][: len(seen)] == seen  # nothing was rewritten
    assert [item for item in after if item["stage"] == "tool"]
    assert (
        client.get(f"/v1/conversations/{sid}/runs", headers=headers).json()["runs"][0]["status"]
        == "completed"
    )
