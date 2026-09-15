"""M10-08 result-level proof chain over real adapter lineage; injected sources, no network."""

import json
from datetime import date
from uuid import uuid4

import duckdb
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_api_boundary import verified  # noqa: F401 - shared gated fixture
from test_bddk_monthly_load import FakeSource, response, selector
from test_catalog_continuation import CATALOG, NOW, QUESTION, TOTAL, proposal
from test_prepared_api import BASE, responses, runner, wait_http
from test_series_inspection import CPI, SQL

from kkb_agent.agent import Workspace
from kkb_agent.api import proof as module
from kkb_agent.api.app import create_app
from kkb_agent.api.contracts import Proof, ProofInput, ProofStep, unavailable_proof
from kkb_agent.api.projection import OutputRefused, project_answer
from kkb_agent.api.proof import _host, build_proof
from kkb_agent.api.service import AnalysisService
from kkb_agent.catalog.mappings import load_reviewed_snapshot
from kkb_agent.core import ResultKind, SourceRef
from kkb_agent.ingest import bddk_monthly_load as load
from kkb_agent.ingest.bddk_monthly import MonthlyPeriod
from kkb_agent.ingest.bddk_monthly_request import MonthlyRange
from kkb_agent.ingest.safe_fetch import FetchSuccess
from kkb_agent.lakehouse import Observation, SeriesSemantics, open_lakehouse
from kkb_agent.llm import scripted

TOTALS = {4: 100, 5: 120, 6: 150}


class MonthlyTotals(FakeSource):
    """The real BDDK adapter's parser and lineage writer over injected responses."""

    def __call__(self, req):
        self.requests.append(req)
        total = TOTALS[req.period.month]
        return FetchSuccess(
            source_ref=req.fetch_request().source_ref,
            content=json.dumps(response(req, (total - 20, 20, total)), ensure_ascii=False).encode(),
            media_type="application/json",
            http_status=200,
        )


def prepare_pool(root):
    """Adapter-shaped BDDK pool plus a CPI series without raw-source lineage."""
    with open_lakehouse(root) as lake:
        window = MonthlyRange(
            start=MonthlyPeriod(year=2026, month=4), end=MonthlyPeriod(year=2026, month=6)
        )
        assert load.ingest_monthly(lake, selector(), window, retrieve=MonthlyTotals()).series_id
    return root


@pytest.fixture
def pool(tmp_path):
    return prepare_pool(tmp_path.resolve() / "prepared")


def add_cpi(root):
    """A prepared series with no recorded raw-source lineage."""
    record = next(
        s.record
        for s in load_reviewed_snapshot(CATALOG.read_bytes()).series
        if s.record.series_id == CPI
    )
    with open_lakehouse(root) as lake:
        artifact = lake.record_artifact(
            b"synthetic cpi 100 110 120",
            source=SourceRef(source_id="fixture", source_type="fixture", locator="opaque:fixture"),
            media_type="text/plain",
            recorded_at=NOW,
        )
        lake.register_series(
            CPI,
            title="Synthetic CPI",
            artifact_id=artifact.artifact_id,
            semantics=SeriesSemantics(
                unit=record.unit,
                scale=record.scale,
                frequency=record.frequency,
                observation=record.stock_flow,
                cumulative=record.cumulative,
                aggregation=record.aggregation.default,
                base_year=record.base_year,
            ),
        )
        lake.append_observations(
            CPI,
            [
                Observation(date(2026, m, 1), date(2026, m, last), value)
                for m, last, value in [(4, 30, 100.0), (5, 31, 110.0), (6, 30, 120.0)]
            ],
        )


def table_then_index(root, tmp_path):
    add_cpi(root)
    provider = scripted(
        proposal({"step_id": "a", "tool": "lakehouse", "arguments": {"sql": SQL}}),
        "Tablo hazır.",
        proposal(
            {
                "step_id": "b",
                "tool": "table_transform",
                "arguments": {"operation": "add_series", "source": "analiz_1", "series_id": CPI},
            }
        ),
        "Tabloya endeks eklendi.",
    )
    prepared = runner(root, tmp_path, provider)
    sid = uuid4().hex
    first = prepared(sid, uuid4().hex, "Konut kredisi tablosunu getir.")
    second = prepared(sid, uuid4().hex, "Önceki tabloyu koruyup TÜFE ekle.")
    assert first.status.value == second.status.value == "accepted", (first, second)
    return prepared, sid, first, second


def published(prepared, sid, name):
    with open_lakehouse(prepared.run_root / sid / "lake") as lake:
        return Workspace.open(lake.connection, sid).value_of(name)


def test_compare_proof_reaches_recorded_official_raw_responses_without_locators(pool, tmp_path):
    prepared = runner(pool, tmp_path, scripted(*responses()))
    answer = prepared(uuid4().hex, uuid4().hex, QUESTION)
    assert answer.status.value == "accepted", answer
    proof = answer.result.proof
    assert proof.availability == "available" and proof.gaps == () and proof.gate == "accepted"
    [step] = proof.steps
    assert (step.producer, step.operation, step.kind, step.execution) == (
        "change_detection",
        "change_detection_compare",
        ResultKind.COMPARISON,
        "verified",
    )
    assert step.result_version == answer.result.version and step.workspace_name is None
    assert step.inputs == (ProofInput(kind="series", index=0),)
    [source] = proof.sources
    assert source.series_id == TOTAL and source.binding == "execution_snapshot"
    assert (source.unit, source.scale, source.frequency, source.measure) == (
        "TRY",
        "million",
        "monthly",
        "stock",
    )
    assert source.dataset_source_type == "internal-dataset-manifest"
    assert source.parser == "bddk-monthly-json-v1" and source.normalization
    assert (source.observations, source.missing_values) == (3, 0)
    assert (source.first_period, source.last_period) == (date(2026, 4, 1), date(2026, 6, 30))
    assert source.raw_responses == 3 and source.raw_response_types == ("http-json",)
    assert source.hosts == ("www.bddk.org.tr",)
    assert source.first_retrieved is not None and source.first_retrieved <= source.last_retrieved
    assert proof.warnings  # Tool-owned qualification survives into the proof.
    text = answer.model_dump_json()
    for hidden in ("BultenAylik", "BasitRaporGetir", "locator", "source_id", "request", str(pool)):
        assert hidden not in text


def test_followup_proof_nests_published_table_and_marks_missing_lineage_partial(pool, tmp_path):
    prepared, sid, first, second = table_then_index(pool, tmp_path)
    table = first.result.proof
    assert table.availability == "available", table
    assert table.steps[0].producer == "lakehouse" and table.steps[0].operation == "lakehouse_query"
    assert table.sources[0].series_id == TOTAL and table.sources[0].observations == 3
    assert table.sources[0].catalog_status is not None  # Receipt annotates the projection.
    assert len(table.sources) == 1 and table.sources[0].hosts == ("www.bddk.org.tr",)

    proof = second.result.proof
    assert proof.availability == "partial" and proof.gaps == ("source_lineage_missing",)
    root, nested = proof.steps
    assert (root.producer, root.operation) == ("table_transform", "table_transform_add_series")
    assert (nested.producer, nested.workspace_name) == ("lakehouse", "analiz_1")
    assert nested.result_version == first.result.version
    assert ProofInput(kind="result", index=1) in root.inputs
    by_series = {s.series_id: s for s in proof.sources}
    assert by_series[CPI].raw_responses == 0 and by_series[CPI].dataset_source_type == "fixture"
    assert by_series[TOTAL].raw_responses == 3
    assert {i.index for i in nested.inputs if i.kind == "series"} == {
        proof.sources.index(by_series[TOTAL])
    }


def test_changed_result_or_unreadable_store_never_yields_a_chain(pool, tmp_path):
    prepared = runner(pool, tmp_path, scripted(*responses()))
    sid = uuid4().hex
    assert prepared(sid, uuid4().hex, QUESTION).status.value == "accepted"
    result = published(prepared, sid, "analiz_1")
    values = [v.model_copy(update={"value": v.value + 1}) for v in result.values]
    tampered = result.model_copy(update={"values": values})
    with open_lakehouse(prepared.run_root / sid / "lake") as lake:
        assert build_proof(lake.connection, result).availability == "available"
        rejected = build_proof(lake.connection, tampered)
    assert rejected == unavailable_proof("execution_not_verified")
    closed = duckdb.connect()
    closed.close()
    assert build_proof(closed, result) == unavailable_proof("proof_unreadable")


def test_unverified_nested_input_is_reported_not_followed(pool, tmp_path, monkeypatch):
    prepared, sid, _first, _second = table_then_index(pool, tmp_path)
    value = published(prepared, sid, "analiz_2")
    real = module.execution_proof
    monkeypatch.setattr(
        module, "execution_proof", lambda result, c: result.tool != "lakehouse" and real(result, c)
    )
    with open_lakehouse(prepared.run_root / sid / "lake") as lake:
        proof = build_proof(lake.connection, value)
    assert proof.availability == "partial" and len(proof.steps) == 1
    assert "input_result_not_verified" in proof.gaps
    assert all(item.kind == "series" for item in proof.steps[0].inputs)
    assert [s.series_id for s in proof.sources] == [CPI]


@pytest.mark.parametrize(
    ("limit", "value", "gap"),
    [("MAX_RAW_RESPONSES", 2, "raw_response_limit"), ("MAX_PROOF_STEPS", 1, "step_limit")],
)
def test_budgets_stop_as_partial_never_complete(pool, tmp_path, monkeypatch, limit, value, gap):
    prepared, sid, _first, _second = table_then_index(pool, tmp_path)
    monkeypatch.setattr(module, limit, value)
    with open_lakehouse(prepared.run_root / sid / "lake") as lake:
        proof = build_proof(lake.connection, published(prepared, sid, "analiz_2"))
    assert proof.availability == "partial" and gap in proof.gaps
    assert len(proof.steps) <= (1 if gap == "step_limit" else 2)
    assert all(source.raw_responses <= 2 for source in proof.sources) or gap == "step_limit"


def test_titles_are_scrubbed_and_redacted(pool, tmp_path):
    with open_lakehouse(pool) as lake:
        lake.connection.execute(
            "UPDATE silver_series SET title = ? WHERE series_id = ?",
            ["Konut https://evil.example/x?token=abc operator-secret", TOTAL],
        )
    prepared = runner(pool, tmp_path, scripted(*responses()))
    prepared._redactions = ("operator-secret",)
    answer = prepared(uuid4().hex, uuid4().hex, QUESTION)
    title = answer.result.proof.sources[0].title
    assert title is not None and "evil.example" not in title and "operator-secret" not in title


@pytest.mark.parametrize(
    ("locator", "host"),
    [
        ("https://www.bddk.org.tr/BultenAylik/tr/Home/BasitRaporGetir", "www.bddk.org.tr"),
        ("https://evds3.tcmb.gov.tr/igmevdsms-dis/fe?key=secret", "evds3.tcmb.gov.tr"),
        ("http://www.bddk.org.tr/", None),
        ("https://user:pw@www.bddk.org.tr/", None),
        ("https://www.bddk.org.tr:99999/", None),
        ("https://10.0.0.1/", None),
        ("https://[::1]/", None),
        ("https://localhost/", None),
        ("file:///etc/passwd", None),
        ("internal:bddk-monthly-batch-v1", None),
        (None, None),
    ],
)
def test_only_https_dns_hosts_are_shown(locator, host):
    assert _host(locator) == host


MISSING_RESULT = [{"kind": "result", "index": 1}]
MISSING_SOURCE = [{"kind": "series", "index": 0}]


def step_data(**updates):
    base = {
        "producer": "lakehouse",
        "operation": None,
        "kind": "series",
        "method": None,
        "execution": "verified",
        "result_version": "a" * 64,
        "workspace_name": None,
        "coverage": None,
        "samples": None,
        "inputs": (),
    }
    return {**base, **updates}


def step(**updates):
    return ProofStep.model_validate(step_data(**updates))


@pytest.mark.parametrize(
    "payload",
    [
        {"availability": "unavailable", "steps": [step_data()]},
        {"availability": "available"},
        {"availability": "available", "steps": [step_data()], "gaps": ["step_limit"]},
        {"availability": "partial", "steps": [step_data(execution="not_verified")]},
        {"availability": "available", "steps": [step_data(inputs=MISSING_RESULT)]},
        {"availability": "available", "steps": [step_data(inputs=MISSING_SOURCE)]},
        {"availability": "available", "steps": [step_data(producer="bad name")]},
        {"availability": "available", "steps": [step_data()], "unexpected": True},
    ],
)
def test_proof_contract_refuses_inconsistent_or_fabricated_chains(payload):
    with pytest.raises(ValidationError):
        Proof.model_validate(payload)


def test_projection_refuses_a_proof_for_another_version(verified):  # noqa: F811
    answered, result = verified
    own = Proof(availability="available", steps=(step(result_version=result.digest()),))
    output = project_answer(answered, turn_id=uuid4().hex, published=result, proof=own)
    assert output.result.proof == own
    foreign = Proof(availability="available", steps=(step(result_version="b" * 64),))
    with pytest.raises(OutputRefused):
        project_answer(answered, turn_id=uuid4().hex, published=result, proof=foreign)


def test_http_turn_carries_proof_only_to_its_session(pool, tmp_path):
    prepared = runner(pool, tmp_path, scripted(*responses()))
    service = AnalysisService(prepared, mode="scripted")
    with TestClient(create_app(service, prepared=prepared.status), base_url=BASE) as client:
        owner = client.post("/v1/sessions", json={}).json()
        other = client.post("/v1/sessions", json={}).json()
        headers = {"X-KKB-Session-Token": owner["token"]}
        path = f"/v1/sessions/{owner['session_id']}/turns"
        admitted = client.post(
            path, json={"request_id": uuid4().hex, "question": QUESTION}, headers=headers
        ).json()
        done = wait_http(client, f"{path}/{admitted['turn_id']}", headers)
        assert done["answer"]["result"]["proof"]["availability"] == "available"
        foreign = client.get(
            f"{path}/{admitted['turn_id']}", headers={"X-KKB-Session-Token": other["token"]}
        )
        assert foreign.status_code == 404 and "proof" not in foreign.text
