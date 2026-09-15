"""Finite synthetic browser rehearsal; no external data or model calls."""

import json
import sys
import tempfile
import time
from pathlib import Path

import uvicorn
from starlette.responses import JSONResponse


def main() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
    from test_selected_runtime import add, proposal, runtime, table

    from kkb_agent.api.app import create_app
    from kkb_agent.api.service import AnalysisService

    with tempfile.TemporaryDirectory(prefix="kkb-selected-browser-") as directory:
        runner, provider = runtime(
            Path(directory),
            proposal(table()),
            "İlk tablo hazır.",
            proposal(add()),
            "Seçili tabloya endeks eklendi.",
            proposal(add()),
            "Eski tabloya endeks eklendi.",
            proposal(add(series="EVDS:TP.KFE.TR")),
            proposal(table()),
            "Serbest soru tablosu hazır.",
        )

        def selected(sid, tid, question, selection):
            time.sleep(2)
            return runner.selected(sid, tid, question, selection)

        app = create_app(
            AnalysisService(runner, mode="scripted", selected_runner=selected),
            port=8127,
            prepared=runner.status,
        )
        ledger = Path(__file__).resolve().parents[2] / "artifacts" / "selected-browser-ledger.jsonl"
        ledger.parent.mkdir(exist_ok=True)
        ledger.write_text("", encoding="utf-8")
        seen = set()

        @app.middleware("http")
        async def record(request, call_next):
            payload = None
            if request.method == "POST" and request.url.path.endswith("/turns"):
                payload = await request.json()
                if payload["question"] == "Reddedilen kaynak provası":
                    return JSONResponse(
                        {"api_version": 1, "error": "invalid_result"}, status_code=422
                    )
            response = await call_next(request)
            if payload:
                with ledger.open("a", encoding="utf-8") as file:
                    file.write(
                        json.dumps(
                            {
                                "request_id": payload["request_id"],
                                "selected_result_id": payload.get("selected_result_id"),
                                "status": response.status_code,
                                "provider_calls": len(provider.seen),
                            }
                        )
                        + "\n"
                    )
                if (
                    payload["question"] == "Eski tabloya TÜFE ekle; bağlantı provası"
                    and payload["request_id"] not in seen
                ):
                    seen.add(payload["request_id"])
                    return JSONResponse({"api_version": 1, "error": "unavailable"}, status_code=503)
            return response

        uvicorn.run(app, host="127.0.0.1", port=8127, access_log=False)


if __name__ == "__main__":
    main()
