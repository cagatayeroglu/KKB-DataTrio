"""Persisted USER + reviewed official composition, through the served offline path."""

import json
from datetime import date, timedelta

from fastapi.testclient import TestClient
from test_catalog_continuation import CATALOG
from test_conversation_persistence import open_conversation, owner
from test_document_dataset import BASE, month_end, seed
from test_document_table import ask
from test_evds_load import encoded, envelope, row
from test_knowledge_api import manual

from kkb_agent.api.app import create_app
from kkb_agent.api.knowledge_service import KnowledgeService
from kkb_agent.api.prepared import PreparedRunner
from kkb_agent.api.service import AnalysisService
from kkb_agent.api.store import DATABASE_NAME, ConversationStore
from kkb_agent.catalog.mappings import load_reviewed_snapshot
from kkb_agent.catalog.search import CatalogSearchArguments, search_catalog
from kkb_agent.ingest.evds_load import ingest_series
from kkb_agent.ingest.evds_request import EvdsWindow
from kkb_agent.ingest.safe_fetch import FetchSuccess
from kkb_agent.knowledge import KnowledgeStore
from kkb_agent.lakehouse import open_lakehouse
from kkb_agent.llm import scripted

QUESTION = (
    "Bu seriyi 2025 konut kredisi faiziyle aylık tek tabloda birleştir "
    "ve ikisinin yıl içindeki seyrini karşılaştır."
)


def test_persisted_user_and_reviewed_official_rate_align_join_and_compare(tmp_path, monkeypatch):
    def offline(*args, **kwargs):
        raise AssertionError("No external model, embedding or acquisition")

    monkeypatch.setattr("socket.socket.connect", offline)
    snapshot = load_reviewed_snapshot(CATALOG.read_bytes())
    chosen = search_catalog(snapshot, CatalogSearchArguments(query="2025 konut kredisi faizi"))
    reviewed = chosen.candidates[0].series
    assert reviewed.rate_basis == "new_credit"
    rate = reviewed.record
    user_id = "USER:aylik_basvurular.v1"
    monthly_rate = f"{rate.series_id} monthly average (by_end)"
    values = [100, 110, 105, 120, 125, 115, 130, 128, 140, 145, 142, 150]
    rates = [48, 47, 47.5, 46, 45, 46, 44, 44.5, 43, 42, 42.5, 41]
    root = tmp_path / "prepared"
    seed(root)

    def weekly_source(request):
        fridays = [date(2025, 1, 3) + timedelta(days=7 * n) for n in range(52)]
        return FetchSuccess(
            source_ref=request.fetch_request().source_ref,
            content=encoded(
                envelope([row(request.code, end, str(rates[end.month - 1])) for end in fridays])
            ),
            media_type="application/json",
            http_status=200,
        )

    with open_lakehouse(root) as lake:
        ingest_series(
            lake,
            rate.source_series_id,
            EvdsWindow(start=date(2025, 1, 1), end=date(2025, 12, 31)),
            retrieve=weekly_source,
        )

    def step(sid, tool, *, dependencies=(), present=False, **arguments):
        return dict(
            step_id=sid,
            tool=tool,
            arguments=arguments,
            depends_on=list(dependencies),
            present=present,
        )

    def plan(*steps):
        return json.dumps(dict(question=QUESTION, steps=steps), ensure_ascii=False)

    provider = scripted(
        plan(step("find_user", "catalog_search", query="aylık başvuru sayısı")),
        plan(step("user_read", "lakehouse", series=[user_id])),
        "Başvuru tablosu hazır.",
        plan(step("find_rate", "catalog_search", query="2025 konut kredisi faizi")),
        plan(
            step(
                "rate_read",
                "lakehouse",
                series=[rate.series_id],
                start="2025-01-01",
                end="2025-12-31",
            ),
            step(
                "monthly",
                "table_transform",
                dependencies=("rate_read",),
                operation="resample",
                source="rate_read",
                column=rate.series_id,
                week_assignment="by_end",
            ),
            step(
                "joined",
                "table_transform",
                dependencies=("monthly",),
                operation="join_table",
                source="analiz_1",
                other="monthly",
                columns=[monthly_rate],
            ),
            step(
                "aligned",
                "table_transform",
                dependencies=("joined",),
                present=True,
                operation="align",
                source="joined",
                columns=[user_id, monthly_rate],
                join="inner",
            ),
            step(
                "compared",
                "change_detection",
                dependencies=("aligned",),
                operation="table_co_movement",
                source="aligned",
                driver_column=monthly_rate,
                target_column=user_id,
                driver_direction="down",
                target_direction="up",
            ),
        ),
        "Aylık tablo ve karşılaştırma hazır.",
    )
    store = ConversationStore(tmp_path / "state" / DATABASE_NAME)
    knowledge = KnowledgeStore(tmp_path / "state" / "knowledge.sqlite")
    runner = PreparedRunner(
        provider,
        root,
        tmp_path / "runtime",
        catalog_bytes=CATALOG.read_bytes(),
        store=store,
        knowledge=knowledge,
    )
    service = AnalysisService(
        runner, mode="scripted", store=store, knowledge=True, selected_runner=runner.selected
    )
    ks = KnowledgeService(
        knowledge,
        store,
        runner.catalog,
        prepared=frozenset(item.series_id for item in runner.status.series),
        series_values=runner.series_values,
    )
    try:
        with TestClient(
            create_app(service, prepared=runner.status, knowledge=ks), base_url=BASE
        ) as client:
            token = owner(client)
            key = {"X-KKB-Owner-Token": token}
            saved = client.post(
                "/v1/knowledge/datasets",
                headers=key,
                json=manual(
                    slug="aylik_basvurular",
                    title="Aylık başvuru sayısı",
                    aliases=["aylık başvuru sayısı"],
                    unit="count",
                    scale="one",
                    observations=[
                        dict(period_end=month_end(date(2025, m, 1)).isoformat(), value=float(v))
                        for m, v in enumerate(values, 1)
                    ],
                ),
            )
            assert saved.status_code == 201, saved.text
            assert saved.json()["series"]["series_id"] == user_id
            # New conversation after persistence: discover/read from KB, not uploaded bytes.
            sid, headers, _ = open_conversation(client, token)
            first = ask(client, sid, headers, "Aylık başvuru sayısı serisini getir.")
            assert first["answer"]["status"] == "accepted", first
            result = first["answer"]["result"]
            assert [c["value"] for c in result["cells"]] == values
            second = ask(client, sid, headers, QUESTION)
            assert second["answer"] is not None, second
            assert second["answer"]["status"] == "accepted", second
            table = second["answer"]["result"]
            dated = [c for c in table["cells"] if c["label"] in {user_id, monthly_rate}]
            assert len(table["cells"]) == 30
            assert len(dated) == 24
            assert {c["label"] for c in dated} == {user_id, monthly_rate}
            assert [c["value"] for c in table["cells"] if c["label"] == monthly_rate] == rates
            # Analytics retains the exact table cells, so no duplicate table is published.
            assert table["related"] == []
            for artifact in (table, *table["related"]):
                proof = artifact["proof"]
                # Manual KB observations have a dataset snapshot, but no imported
                # raw-source lineage. Execution and both input identities still verify.
                assert proof["availability"] == "partial"
                assert proof["gaps"] == ["source_lineage_missing"]
                assert proof["steps"][0]["execution"] == "verified"
                assert {s["series_id"] for s in proof["sources"]} >= {user_id, rate.series_id}
                official_source = next(
                    s for s in proof["sources"] if s["series_id"] == rate.series_id
                )
                assert official_source["raw_responses"] == 1
            comparison = table
            counts = {
                c["label"].split(": ", 1)[-1]: c["value"]
                for c in comparison["cells"]
                if c["label"].startswith("table comparison ")
            }
            assert counts["complete monthly transitions"] == 11
            assert counts["eligible transitions matching both directions"] == 7
            # The real continuation receives the rank/semantic distinction, not an ID route.
            feedback = "\n".join(m.content for m in provider.seen[4])
            assert feedback.index(rate.series_id) < feedback.index("EVDS:TP.BKR.TRY.18")
            assert "unresolved_read_fields" in feedback
            assert not provider.responses
    finally:
        store.close()
        knowledge.close()
