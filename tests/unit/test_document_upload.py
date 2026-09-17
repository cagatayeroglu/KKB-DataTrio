"""M10-04 slice 1: uploads attached to one question; local HTTP boundary, no network."""

import hashlib
import json
import stat
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_catalog_continuation import CATALOG, seed_prepared
from test_prepared_api import BASE, set_config, wait_http

from kkb_agent.api import __main__ as cli
from kkb_agent.api.app import create_app
from kkb_agent.api.contracts import MAX_BODY_BYTES, MAX_DOCUMENT_BYTES, MAX_DOCUMENTS
from kkb_agent.api.prepared import PreparedRunner
from kkb_agent.api.service import AnalysisService
from kkb_agent.llm import scripted

CSV = "Ay;Kapanış (Puan)\n2026-04;9000\n2026-05;9100\n2026-06;9200\n".encode()
CSV_TYPE = "text/csv"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No live request in these tests")

    monkeypatch.setattr("socket.socket.connect", forbidden)


def runtime(tmp_path, provider=None, *, uploads=True):
    root = tmp_path.resolve() / "prepared"
    seed_prepared(root)
    runner = PreparedRunner(
        provider or scripted(),
        root,
        tmp_path.resolve() / "runtime",
        catalog_bytes=CATALOG.read_bytes(),
        document_uploads=uploads,
    )
    service = AnalysisService(
        runner,
        mode="scripted",
        selected_runner=runner.selected,
        document_store=runner.admit_document if uploads else None,
    )
    return runner, TestClient(create_app(service, prepared=runner.status), base_url=BASE)


def session(client):
    created = client.post("/v1/sessions", json={}).json()
    return created["session_id"], {"X-KKB-Session-Token": created["token"]}


def upload(client, sid, headers, content=CSV, media_type=CSV_TYPE):
    return client.post(
        f"/v1/sessions/{sid}/documents",
        content=content,
        headers={**headers, "Content-Type": media_type},
    )


def test_admitted_upload_is_stored_by_reference_without_its_name(tmp_path):
    runner, client = runtime(tmp_path)
    with client:
        assert "document_upload" in client.get("/v1/health").json()["capabilities"]
        sid, headers = session(client)
        response = upload(client, sid, headers)
        assert response.status_code == 201, response.text
        body = response.json()
        assert body == {
            "api_version": 1,
            "document_ref": body["document_ref"],
            "document_format": "csv",
            "bytes": len(CSV),
            "sha256": hashlib.sha256(CSV).hexdigest(),
        }
    (stored,) = (runner.run_root / sid / "documents").iterdir()
    assert stored.name == f"{body['document_ref']}.csv" and stored.read_bytes() == CSV
    assert stat.S_IMODE(stored.stat().st_mode) == 0o600


def test_without_the_switch_there_is_no_upload(tmp_path):
    _, client = runtime(tmp_path, uploads=False)
    with client:
        assert "document_upload" not in client.get("/v1/health").json()["capabilities"]
        sid, headers = session(client)
        response = upload(client, sid, headers)
        assert response.status_code == 503 and response.json()["error"] == "unavailable"


@pytest.mark.parametrize(
    ("content", "media_type", "status", "code"),
    [
        (CSV, "image/png", 415, "invalid_request"),
        (CSV, "application/json", 415, "invalid_request"),
        (CSV, "application/octet-stream", 415, "invalid_request"),
        (b"\x00\x01binary\x00", CSV_TYPE, 422, "document_rejected"),
        (b"not a pdf", "application/pdf", 422, "document_rejected"),
        (
            b"PK\x03\x04broken",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            422,
            "document_rejected",
        ),
        (b"plain text", "text/html", 422, "document_rejected"),
        (b"", CSV_TYPE, 422, "document_rejected"),
    ],
)
def test_types_and_contents_are_checked_before_storage(tmp_path, content, media_type, status, code):
    runner, client = runtime(tmp_path)
    with client:
        sid, headers = session(client)
        response = upload(client, sid, headers, content, media_type)
        assert (response.status_code, response.json()["error"]) == (status, code)
    assert not (runner.run_root / sid / "documents").exists() or not any(
        (runner.run_root / sid / "documents").iterdir()
    )


def test_size_limit_is_route_specific(tmp_path):
    _, client = runtime(tmp_path)
    with client:
        sid, headers = session(client)
        too_large = b"a" * (MAX_DOCUMENT_BYTES + 1)
        response = upload(client, sid, headers, too_large)
        assert (response.status_code, response.json()["error"]) == (413, "body_too_large")
        # A document-sized body elsewhere keeps the JSON limit and type.
        big_json = json.dumps({"request_id": uuid4().hex, "question": "x" * MAX_BODY_BYTES})
        response = client.post(
            f"/v1/sessions/{sid}/turns",
            content=big_json,
            headers={**headers, "Content-Type": "application/json"},
        )
        assert response.status_code == 413
        response = client.post(
            f"/v1/sessions/{sid}/turns", content=CSV, headers={**headers, "Content-Type": CSV_TYPE}
        )
        assert response.status_code == 415


def test_token_capacity_and_foreign_references(tmp_path):
    _, client = runtime(tmp_path)
    with client:
        sid, headers = session(client)
        other, other_headers = session(client)
        wrong = {"X-KKB-Session-Token": other_headers["X-KKB-Session-Token"]}
        assert upload(client, sid, wrong).status_code == 404
        refs = [upload(client, sid, headers).json()["document_ref"] for _ in range(MAX_DOCUMENTS)]
        extra = upload(client, sid, headers)
        assert (extra.status_code, extra.json()["error"]) == (429, "capacity")
        for reference in (uuid4().hex, refs[0]):
            target, owner = (sid, headers) if reference != refs[0] else (other, other_headers)
            response = client.post(
                f"/v1/sessions/{target}/turns",
                json={
                    "request_id": uuid4().hex,
                    "question": "Ekli belge?",
                    "document_ref": reference,
                },
                headers=owner,
            )
            assert (response.status_code, response.json()["error"]) == (422, "invalid_document")


def test_the_attachment_reaches_the_tools_only_when_its_bytes_still_match(tmp_path, monkeypatch):
    seen = []
    original = PreparedRunner._registry

    def registry(self, connection, workspace, lineage, attachment=None, library=None, fetch=None):
        seen.append(attachment)
        return original(self, connection, workspace, lineage, attachment, library, fetch)

    monkeypatch.setattr(PreparedRunner, "_registry", registry)
    provider = scripted('{"question": "q", "steps": [], "clarification": "unsupported_request"}')
    runner, client = runtime(tmp_path, provider)
    with client:
        sid, headers = session(client)
        admitted = upload(client, sid, headers).json()
        path = f"/v1/sessions/{sid}/turns"
        request = {
            "request_id": uuid4().hex,
            "question": "Ekli belgedeki Kapanış nedir?",
            "document_ref": admitted["document_ref"],
        }
        turn = client.post(path, json=request, headers=headers).json()
        done = wait_http(client, f"{path}/{turn['turn_id']}", headers)
        assert done["state"] == "completed", done
        (attachment,) = seen
        assert attachment.content == CSV and attachment.media_type == CSV_TYPE
        assert attachment.source.source_type == "upload"
        assert attachment.source.locator == f"upload:{admitted['document_ref']}"
        assert attachment.source.content_hash == f"sha256:{admitted['sha256']}"
        assert "Ekli" not in repr(attachment) and CSV.decode() not in repr(attachment)

        stored = runner.run_root / sid / "documents" / f"{admitted['document_ref']}.csv"
        stored.write_bytes(CSV.replace(b"9000", b"9999"))
        request = {**request, "request_id": uuid4().hex}
        turn = client.post(path, json=request, headers=headers).json()
        done = wait_http(client, f"{path}/{turn['turn_id']}", headers)
        assert (done["state"], done["error"]) == ("failed", "invalid_document")
        assert len(seen) == 1


@pytest.mark.parametrize("flag", [True, False])
def test_launcher_admits_documents_unless_they_are_refused(tmp_path, monkeypatch, capsys, flag):
    """Uploads are on by default; --no-uploads is the one way to refuse them."""
    set_config(monkeypatch)
    root = tmp_path.resolve() / "prepared"
    seed_prepared(root)
    seen = {}
    real = cli.AnalysisService

    def capture(*args, **kwargs):
        seen["store"] = kwargs.get("document_store")
        return real(*args, **kwargs)

    class Provider:
        def __enter__(self):
            return scripted()

        def __exit__(self, *args):
            return None

    monkeypatch.setattr(cli, "AnalysisService", capture)
    monkeypatch.setattr(cli, "KloudeksProvider", lambda *a: Provider())
    monkeypatch.setattr(cli.uvicorn, "run", lambda app, **kwargs: None)
    arguments = [
        "--serve",
        "--enable-model-requests",
        "--prepared-root",
        str(root),
        "--catalog",
        str(CATALOG),
        "--state-root",
        str(tmp_path.resolve() / "runtime"),
    ]
    assert cli.main(arguments if flag else [*arguments, "--no-uploads"]) == 0
    assert (seen["store"] is not None) is flag
    assert json.loads(capsys.readouterr().out.splitlines()[0])["uploads"] is flag


def ask(client, sid, headers, question, **extra):
    path = f"/v1/sessions/{sid}/turns"
    body = {"request_id": uuid4().hex, "question": question, **extra}
    admitted = client.post(path, json=body, headers=headers)
    assert admitted.status_code == 202, admitted.text
    return wait_http(client, f"{path}/{admitted.json()['turn_id']}", headers)


def table_plan():
    from test_catalog_continuation import proposal
    from test_series_inspection import SQL

    return proposal({"step_id": "a", "tool": "lakehouse", "arguments": {"sql": SQL}})


def add_attached(**overrides):
    from test_catalog_continuation import proposal

    arguments = {
        "operation": "add_document_column",
        "source": "analiz_1",
        "attached": True,
        "delimiter": ";",
        "period_column": "Ay",
        "value_column": "Kapanış",
        **overrides,
    }
    return proposal({"step_id": "b", "tool": "table_transform", "arguments": arguments})


def test_an_uploaded_column_joins_the_selected_table_with_an_upload_proof(tmp_path):
    provider = scripted(table_plan(), "Tablo hazır.", add_attached(), "Kapanış eklendi.")
    _, client = runtime(tmp_path, provider)
    with client:
        sid, headers = session(client)
        first = ask(client, sid, headers, "Konut kredisi tablosunu getir.")
        assert first["answer"]["status"] == "accepted", first
        admitted = upload(client, sid, headers).json()
        second = ask(
            client,
            sid,
            headers,
            "Ekli belgedeki Kapanış sütununu tabloya ekle.",
            selected_result_id=first["answer"]["result"]["result_ref"],
            document_ref=admitted["document_ref"],
        )
    assert second["answer"]["status"] == "accepted", second
    cells = second["answer"]["result"]["cells"]
    assert [c["value"] for c in cells if c["label"] == "Kapanış"] == [9000.0, 9100.0, 9200.0]
    assert {c["measure"] for c in cells if c["label"] == "Kapanış"} == {"index"}
    (document,) = second["answer"]["result"]["proof"]["documents"]
    assert document["source_type"] == "upload" and document["host"] is None
    assert document["content_sha256"] == admitted["sha256"] and document["values_read"] == 3
    assert admitted["document_ref"] not in json.dumps(second)


def test_an_uploaded_cell_is_quoted_with_its_proof(tmp_path):
    from test_document_check import CSV as TABLE
    from test_document_check import DRAFT

    read = json.dumps(
        {
            "question": "q",
            "steps": [
                {
                    "step_id": "s1",
                    "tool": "web_url",
                    "arguments": {
                        "attached": True,
                        "delimiter": ",",
                        "column": "Tutar",
                        "row": "2026-01-31",
                    },
                }
            ],
        }
    )
    _, client = runtime(tmp_path, scripted(read, DRAFT))
    with client:
        sid, headers = session(client)
        admitted = upload(client, sid, headers, TABLE).json()
        done = ask(
            client,
            sid,
            headers,
            "Ekli belgede 2026-01-31 Tutar nedir?",
            document_ref=admitted["document_ref"],
        )
    assert done["answer"]["status"] == "accepted", done
    (document,) = done["answer"]["result"]["proof"]["documents"]
    assert (document["source_type"], document["row"], document["column"]) == ("upload", 1, 2)
    assert "RAW-CONTENT" not in json.dumps(done)


def test_without_an_attachment_or_fetch_no_document_tool_exists(tmp_path):
    provider = scripted(add_attached(source="analiz_1"), add_attached(source="analiz_1"))
    _, client = runtime(tmp_path, provider)
    with client:
        sid, headers = session(client)
        done = ask(client, sid, headers, "Ekli belgedeki Kapanış sütununu ekle.")
    assert (done["state"], done["error"]) == ("failed", "planning_failed")
    prompt = json.dumps([m.content for m in provider.seen[0]], ensure_ascii=False)
    assert "attached=true" not in prompt and '"web_url"' not in prompt


@pytest.mark.parametrize("arguments", [{"url": "https://data.example.test/x.csv"}, {}])
def test_an_attachment_never_enables_reading_an_address(tmp_path, arguments):
    from test_catalog_continuation import proposal

    step = {"step_id": "s1", "tool": "web_url", "arguments": {"delimiter": ";", **arguments}}
    if not arguments:
        step["arguments"].update(url="https://data.example.test/x.csv", attached=True)
    provider = scripted(proposal(step), proposal(step), "Okundu.")
    _, client = runtime(tmp_path, provider)
    with client:
        sid, headers = session(client)
        admitted = upload(client, sid, headers).json()
        done = ask(
            client,
            sid,
            headers,
            "https://data.example.test/x.csv adresini oku.",
            document_ref=admitted["document_ref"],
        )
    if arguments:
        assert done["answer"]["status"] == "abstained" and done["answer"]["result"] is None
    else:
        assert (done["state"], done["error"]) == ("failed", "planning_failed")
