"""M10-18 admission slice; selected workspace execution is a later integration."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_api_boundary import BASE, finished, quiet_answer
from test_api_boundary import verified as verified

from kkb_agent.agent.verifier import AnswerStatus
from kkb_agent.api.app import create_app
from kkb_agent.api.contracts import Question
from kkb_agent.api.projection import project_answer
from kkb_agent.api.service import AnalysisService, ServiceError
from kkb_agent.llm.provider import TransportError


@pytest.fixture
def selection_service(verified):
    answered, published = verified
    ordinary, selected = [], []

    def run(sid, tid, text, *, is_continuation):
        ordinary.append((sid, tid, text))
        return project_answer(answered, turn_id=tid, published=published)

    def follow(sid, tid, text, selection, *, is_continuation):
        selected.append((sid, tid, text, selection))
        return quiet_answer()

    service = AnalysisService(run, mode="scripted", selected_runner=follow)
    try:
        yield service, ordinary, selected
    finally:
        service.close()


def submit(service, session, selected=None, request_id=None):
    request = Question(
        request_id=request_id or uuid4().hex,
        question="Bu tabloyu koru.",
        selected_result_id=selected,
    )
    return service.submit(session.session_id, session.token, request)


@pytest.mark.parametrize("bad", ["", "not-a-result", "a" * 64, 123, True, {}, []])
def test_selection_has_a_strict_public_reference_shape(bad):
    with pytest.raises(ValidationError):
        Question(request_id=uuid4().hex, question="Tablo", selected_result_id=bad)


def test_latest_and_older_publications_resolve_to_their_exact_turn_and_version(selection_service):
    service, ordinary, selected = selection_service
    session = service.create_session()
    first = finished(service, session, submit(service, session))
    second = finished(service, session, submit(service, session))
    before = [first.model_dump_json(), second.model_dump_json()]
    for source in (second, first):
        result = source.answer.result
        done = finished(service, session, submit(service, session, result.result_ref))
        assert done.state == "completed"
        resolved = selected[-1][-1]
        assert (resolved.turn_id, resolved.result_ref, resolved.version) == (
            source.turn_id,
            result.result_ref,
            result.version,
        )
        assert selected[-1][0] == session.session_id
    assert len(ordinary) == 2 and len(selected) == 2
    assert [
        service.get_turn(session.session_id, session.token, t.turn_id).model_dump_json()
        for t in (first, second)
    ] == before


def test_unknown_foreign_and_turn_references_fail_without_admission(selection_service):
    service, ordinary, selected = selection_service
    owner, stranger = service.create_session(), service.create_session()
    source = finished(service, owner, submit(service, owner))
    for session, ref in (
        (owner, uuid4().hex),
        (stranger, source.answer.result.result_ref),
        (owner, source.turn_id),
    ):
        count = len(service._sessions[session.session_id].turns)
        with pytest.raises(ServiceError, match="^invalid_result$") as error:
            submit(service, session, ref)
        assert error.value.status == 422
        assert len(service._sessions[session.session_id].turns) == count
    assert len(ordinary) == 1 and not selected


def test_selection_is_part_of_idempotency_and_failed_followup_preserves_history(selection_service):
    service, ordinary, selected = selection_service
    session = service.create_session()
    first = finished(service, session, submit(service, session))
    second = finished(service, session, submit(service, session))
    before = first.model_dump_json()
    request_id = uuid4().hex
    done = finished(
        service, session, submit(service, session, first.answer.result.result_ref, request_id)
    )
    assert (
        submit(service, session, first.answer.result.result_ref, request_id).turn_id == done.turn_id
    )
    for other in (second.answer.result.result_ref, None):
        with pytest.raises(ServiceError, match="request_conflict"):
            submit(service, session, other, request_id)
    assert len(selected) == 1

    def failed(sid, tid, text, selection, *, is_continuation):
        raise TransportError("sensitive details")

    service._selected_runner = failed
    failed_turn = finished(
        service, session, submit(service, session, first.answer.result.result_ref)
    )
    assert failed_turn.state == "failed" and failed_turn.error == "provider_failed"
    assert "sensitive" not in failed_turn.model_dump_json()
    assert (
        service.get_turn(session.session_id, session.token, first.turn_id).model_dump_json()
        == before
    )
    assert len(ordinary) == 2


def test_legacy_runner_cannot_silently_ignore_an_owned_selection(selection_service):
    service, ordinary, selected = selection_service
    session = service.create_session()
    first = finished(service, session, submit(service, session))
    service._selected_runner = None
    with pytest.raises(ServiceError, match="unavailable") as error:
        submit(service, session, first.answer.result.result_ref)
    assert error.value.status == 503
    assert len(service._sessions[session.session_id].turns) == 1
    assert len(ordinary) == 1 and not selected
    # An absent or explicit-null selection retains the original runner and retry behavior.
    q = Question(request_id=uuid4().hex, question="Yeni soru")
    done = finished(service, session, service.submit(session.session_id, session.token, q))
    assert (
        service.submit(session.session_id, session.token, Question(**q.model_dump())).turn_id
        == done.turn_id
    )
    assert len(ordinary) == 2


@pytest.mark.parametrize(
    "state,status",
    [
        ("failed", AnswerStatus.ACCEPTED),
        ("completed", AnswerStatus.QUALIFIED),
        ("completed", AnswerStatus.ABSTAINED),
    ],
)
def test_only_completed_accepted_publications_can_be_selected(selection_service, state, status):
    service, _, selected = selection_service
    session = service.create_session()
    source = finished(service, session, submit(service, session))
    # Defensive admission check even if an internal runner supplied inconsistent output.
    stored = service._sessions[session.session_id].turns[source.turn_id]
    stored.state = state
    stored.answer.status = status
    with pytest.raises(ServiceError, match="invalid_result"):
        submit(service, session, source.answer.result.result_ref)
    assert not selected


def test_http_selection_contract_ownership_and_authentication(selection_service):
    service, ordinary, selected = selection_service
    session = service.create_session()
    other = service.create_session()
    source = finished(service, session, submit(service, session))
    with TestClient(create_app(service), base_url=BASE) as client:
        assert (
            "selected_result_id"
            in client.get("/openapi.json").json()["components"]["schemas"]["Question"]["properties"]
        )
        body = {
            "request_id": uuid4().hex,
            "question": "Tablo",
            "selected_result_id": source.answer.result.result_ref,
        }
        path = f"/v1/sessions/{session.session_id}/turns"
        response = client.post(path, json=body, headers={"X-KKB-Session-Token": other.token})
        assert response.status_code == 404
        response = client.post(
            f"/v1/sessions/{other.session_id}/turns",
            json=body,
            headers={"X-KKB-Session-Token": other.token},
        )
        assert response.status_code == 422 and response.json()["error"] == "invalid_result"
        response = client.post(path, json=body, headers={"X-KKB-Session-Token": session.token})
        assert response.status_code == 202
        from kkb_agent.api.contracts import Turn

        assert finished(service, session, Turn.model_validate(response.json())).state == "completed"
        assert len(selected) == 1 and len(ordinary) == 1
