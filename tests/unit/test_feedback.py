"""Rating an answer: bound to the answer that was shown, and to its run."""

import json

from test_catalog_continuation import proposal
from test_conversation_persistence import launch, open_conversation, owner
from test_document_table import ask

__all__ = ["launch"]  # the fixture is imported for use here


def reply(text):
    return json.dumps({"question": "q", "steps": [], "clarification": None, "reply": text})


def rate(client, sid, headers, turn_id, rating, **extra):
    return client.post(
        f"/v1/conversations/{sid}/feedback",
        json={"turn_id": turn_id, "rating": rating, **extra},
        headers=headers,
    )


def test_a_rating_is_recorded_edited_and_reaches_the_runs_trace(launch):
    _, client = launch(reply("Merhaba, nasıl yardımcı olabilirim?"))
    owner_token = owner(client)
    sid, headers, _ = open_conversation(client, owner_token)
    answer = ask(client, sid, headers, "Merhaba")
    turn_id = answer["turn_id"]

    created = rate(client, sid, headers, turn_id, "down", comment="Eksik", reasons=["incomplete"])
    assert created.status_code == 201, created.text
    body = created.json()
    assert (body["rating"], body["comment"], body["reasons"]) == ("down", "Eksik", ["incomplete"])
    assert body["turn_id"] == turn_id and body["answer_digest"]

    # Changing one's mind edits the rating; it never becomes a second record.
    changed = rate(client, sid, headers, turn_id, "up", comment="Düzeldi").json()
    assert changed["rating"] == "up" and changed["comment"] == "Düzeldi"
    assert (
        changed["created_at"] == body["created_at"] and changed["updated_at"] >= body["updated_at"]
    )
    listed = client.get(f"/v1/conversations/{sid}/feedback", headers=headers).json()["feedback"]
    assert len(listed) == 1 and listed[0]["rating"] == "up"

    # The rating names the run, so a low rating leads straight to its trace.
    run = client.get(f"/v1/conversations/{sid}/runs", headers=headers).json()["runs"][0]
    assert listed[0]["run_id"] == run["run_id"]
    steps = client.get(f"/v1/conversations/{sid}/runs/{run['run_id']}", headers=headers).json()[
        "steps"
    ]
    assert [item for item in steps if item["stage"] == "planning"]


def test_a_new_answer_does_not_inherit_the_previous_rating(launch):
    _, client = launch(reply("İlk cevap."), reply("İkinci, farklı cevap."))
    owner_token = owner(client)
    sid, headers, _ = open_conversation(client, owner_token)
    first = ask(client, sid, headers, "Merhaba")
    rate(client, sid, headers, first["turn_id"], "up")
    second = ask(client, sid, headers, "Merhaba")

    listed = client.get(f"/v1/conversations/{sid}/feedback", headers=headers).json()["feedback"]
    assert [item["turn_id"] for item in listed] == [first["turn_id"]]
    assert second["turn_id"] not in [item["turn_id"] for item in listed]
    digests = {item["answer_digest"] for item in listed}
    rate(client, sid, headers, second["turn_id"], "down")
    after = client.get(f"/v1/conversations/{sid}/feedback", headers=headers).json()["feedback"]
    assert len(after) == 2 and {item["answer_digest"] for item in after} > digests


def test_ratings_survive_a_restart_and_stay_inside_their_conversation(launch):
    _, client = launch(reply("Merhaba!"), reply("Merhaba!"))
    owner_token = owner(client)
    sid, headers, _ = open_conversation(client, owner_token)
    other_id, other_headers, _ = open_conversation(client, owner_token)
    answer = ask(client, sid, headers, "Merhaba")
    ask(client, other_id, other_headers, "Selam")
    rate(client, sid, headers, answer["turn_id"], "down", comment="Yanlış kaynak")

    _, reopened = launch()
    listed = reopened.get(f"/v1/conversations/{sid}/feedback", headers=headers).json()["feedback"]
    assert [(item["rating"], item["comment"]) for item in listed] == [("down", "Yanlış kaynak")]
    assert (
        reopened.get(f"/v1/conversations/{other_id}/feedback", headers=other_headers).json()[
            "feedback"
        ]
        == []
    )
    # A turn of another conversation cannot be rated through this one.
    assert rate(reopened, other_id, other_headers, answer["turn_id"], "up").status_code == 404


def test_an_unanswered_turn_and_a_stranger_cannot_be_rated(launch):
    _, client = launch(proposal(clarification="unsupported_request"), "-")
    owner_token = owner(client)
    sid, headers, _ = open_conversation(client, owner_token)
    answer = ask(client, sid, headers, "Konut kredisini göster.")
    # An abstained turn still has an answer someone may rate.
    assert rate(client, sid, headers, answer["turn_id"], "down").status_code == 201
    assert rate(client, sid, headers, "0" * 32, "up").status_code == 404
    stranger = owner(client)
    assert (
        rate(client, sid, {"X-KKB-Session-Token": stranger}, answer["turn_id"], "up").status_code
        == 404
    )
    assert rate(client, sid, headers, answer["turn_id"], "maybe").status_code == 422


def test_a_score_from_one_to_five_is_kept_and_out_of_range_is_refused(launch):
    _, client = launch(reply("Merhaba."))
    owner_token = owner(client)
    sid, headers, _ = open_conversation(client, owner_token)
    turn_id = ask(client, sid, headers, "Merhaba")["turn_id"]

    scored = rate(client, sid, headers, turn_id, "up", score=4)
    assert scored.status_code == 201 and scored.json()["score"] == 4
    # Leaving it out is allowed and does not invent one.
    unscored = rate(client, sid, headers, turn_id, "down").json()
    assert unscored["score"] is None
    for bad in (0, 6, "5", 4.5):
        assert rate(client, sid, headers, turn_id, "up", score=bad).status_code == 422


def test_a_store_from_before_scores_opens_and_keeps_its_ratings(tmp_path):
    """The column is added in place; earlier ratings keep no score rather than a made-up one."""
    import sqlite3

    from kkb_agent.api.store import SCHEMA, ConversationStore

    path = tmp_path / "old.sqlite"
    legacy = SCHEMA.replace(
        "    score           INTEGER CHECK (score IS NULL OR score BETWEEN 1 AND 5),\n", ""
    )
    assert "score" not in legacy.split("CREATE TABLE IF NOT EXISTS feedback")[1].split(");")[0]
    with sqlite3.connect(path) as connection:
        connection.executescript(legacy)
        connection.execute("INSERT INTO owners VALUES ('o', 'd', '2026-09-18T00:00:00+00:00')")
        connection.execute(
            "INSERT INTO conversations (conversation_id, owner_id, token_digest, title, archived,"
            " created_at, updated_at) VALUES ('c', 'o', 'd', 't', 0,"
            " '2026-09-18T00:00:00+00:00', '2026-09-18T00:00:00+00:00')"
        )
        connection.execute(
            "INSERT INTO feedback VALUES ('c', 't', 'a', NULL, NULL, 'up', NULL, '[]',"
            " '2026-09-18T00:00:00+00:00', '2026-09-18T00:00:00+00:00')"
        )

    store = ConversationStore(path)
    try:
        (kept,) = store.ratings("c")
        assert kept.rating == "up" and kept.score is None
        rescored = store.rate("c", turn_id="t", answer_digest="a", rating="up", score=5)
        assert rescored.score == 5
    finally:
        store.close()
