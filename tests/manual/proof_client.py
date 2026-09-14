"""Finite synthetic proof-chain browser rehearsal; no external data or model calls."""

import sys
import tempfile
from pathlib import Path

import uvicorn


def main() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
    from test_api_proof import add_cpi, prepare_pool
    from test_catalog_continuation import CATALOG, proposal
    from test_series_inspection import CPI, SQL

    from kkb_agent.api.app import create_app
    from kkb_agent.api.prepared import PreparedRunner
    from kkb_agent.api.service import AnalysisService
    from kkb_agent.llm import scripted

    with tempfile.TemporaryDirectory(prefix="kkb-proof-browser-") as directory:
        root = Path(directory).resolve()
        pool = prepare_pool(root / "prepared")
        add_cpi(pool)
        provider = scripted(
            proposal({"step_id": "a", "tool": "lakehouse", "arguments": {"sql": SQL}}),
            "Konut kredisi tablosu hazır.",
            proposal(
                {
                    "step_id": "b",
                    "tool": "table_transform",
                    "arguments": {
                        "operation": "add_series",
                        "source": "analiz_1",
                        "series_id": CPI,
                    },
                }
            ),
            "Tabloya TÜFE eklendi.",
        )
        runner = PreparedRunner(
            provider, pool, root / "runtime", catalog_bytes=CATALOG.read_bytes()
        )
        app = create_app(
            AnalysisService(runner, mode="scripted", selected_runner=runner.selected),
            port=8127,
            prepared=runner.status,
        )
        uvicorn.run(app, host="127.0.0.1", port=8127, access_log=False)


if __name__ == "__main__":
    main()
