"""Print an overview of every stored run and write each run's full trace to a text file.

    python tests/manual/dump_traces.py --state-root <dir> [--out <dir>]

Reads a copy of <state-root>/conversations.sqlite (never the live file), prints one
line per event (start, duration, stage, name, status, detail size, attributes) and
writes <out>/<NN>_<run>.txt with every event's attributes and complete detail:
prompts, model reasoning, plans, tool arguments and full tool outputs.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import tempfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    out = args.out or args.state_root / "trace-dump"
    out.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as scratch:
        source = args.state_root / "conversations.sqlite"
        copy = Path(scratch) / "conversations.sqlite"
        for suffix in ("", "-wal", "-shm"):
            if (source.parent / (source.name + suffix)).exists():
                shutil.copy(source.parent / (source.name + suffix), Path(str(copy) + suffix))
        connection = sqlite3.connect(copy)
        runs = connection.execute(
            "SELECT run_id, question, status, answer_status, error, duration_ms FROM runs "
            "ORDER BY started_at"
        ).fetchall()
        for number, (run_id, question, status, answer, error, ms) in enumerate(runs, 1):
            print(
                f"\n#{number} {run_id[:8]} {status}/{answer} error={error} "
                f"{ms / 1000:.1f}s :: {question[:90]}"
            )
            lines = [f"QUESTION: {question}\nSTATUS: {status}/{answer} error={error} {ms} ms\n"]
            for seq, stage, name, state, start, dur, attrs, detail in connection.execute(
                "SELECT sequence, stage, name, status, started_ms, duration_ms, attributes, "
                "detail FROM trace_events WHERE run_id = ? ORDER BY sequence",
                (run_id,),
            ):
                size = len(detail or "")
                if not name.startswith("prompt."):
                    print(
                        f"  {seq:>3} {start / 1000:7.1f}s +{dur / 1000:6.1f}s {stage:<11} "
                        f"{name:<26} {state:<8} {size:>7}c {attrs[:150]}"
                    )
                lines.append(
                    f"\n===== {seq} {stage} {name} {state} start={start} dur={dur}\n"
                    f"ATTR {attrs}\n{detail or ''}"
                )
            (out / f"{number:02d}_{run_id[:8]}.txt").write_text("\n".join(lines), encoding="utf-8")
        connection.close()
    print(f"\nFull traces: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
