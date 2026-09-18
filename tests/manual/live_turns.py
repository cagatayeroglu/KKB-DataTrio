"""Drive an owner-authorized live rehearsal over the local HTTP turn contract.

Talks only to a loopback `live_client.py` launcher. A JSON plan lists steps:
`{"upload": "path/to/file.csv"}` admits a document for the next question, and
`{"question": "...", "follow": true, "attach": true}` asks one question,
optionally selecting the previous publication and attaching the last upload.
The session token stays in memory. A turn that fails with `provider_failed` is
resent once in the same session (same selection and attachment, new request
identity); every other outcome is final, and the run stops at the first turn
that is not accepted. Each turn's JSON is written to `--out`; stdout gets one
content-free line per event.

    python tests/manual/live_turns.py --port 8128 --plan plan.json --out run-dir
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

MEDIA_TYPES = {
    ".csv": "text/csv",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pdf": "application/pdf",
    ".html": "text/html",
    ".htm": "text/html",
}
Call = Callable[[str, str, bytes | None, dict[str, str]], tuple[int, dict[str, Any]]]


def http_call(port: int) -> Call:
    base = f"http://127.0.0.1:{port}"

    def call(
        method: str, path: str, body: bytes | None, headers: dict[str, str]
    ) -> tuple[int, dict[str, Any]]:
        request = urllib.request.Request(base + path, data=body, method=method)
        request.add_header("Host", f"127.0.0.1:{port}")
        for name, value in headers.items():
            request.add_header(name, value)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read() or b"{}")

    return call


def run(
    plan: list[dict[str, Any]],
    call: Call,
    out: Path,
    *,
    log: Callable[[dict[str, Any]], None] = lambda entry: print(json.dumps(entry), flush=True),
    poll_seconds: float = 5.0,
    max_wait_seconds: float = 1900.0,
) -> bool:
    status, session = call("POST", "/v1/sessions", b"{}", {"Content-Type": "application/json"})
    if status != 201:
        log({"session": status})
        return False
    token = {"X-KKB-Session-Token": session["token"]}
    base = f"/v1/sessions/{session['session_id']}"
    selected: str | None = None
    document: str | None = None
    number = 0
    for step in plan:
        if "upload" in step:
            path = Path(step["upload"])
            media = MEDIA_TYPES.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0] or ""
            status, admitted = call(
                "POST", base + "/documents", path.read_bytes(), {**token, "Content-Type": media}
            )
            log(
                {
                    "upload": status,
                    "format": admitted.get("document_format"),
                    "error": admitted.get("error"),
                }
            )
            if status != 201:
                return False
            document = admitted["document_ref"]
            continue
        number += 1
        body: dict[str, Any] = {"question": step["question"]}
        if step.get("follow") and selected:
            body.update(selected_result_id=selected, is_continuation=True)
        if step.get("attach") and document:
            body["document_ref"] = document
        for attempt in (1, 2):
            turn, seconds = _ask(call, base, token, body, poll_seconds, max_wait_seconds)
            (out / f"turn{number}-attempt{attempt}.json").write_text(
                json.dumps(turn, ensure_ascii=False, indent=1), encoding="utf-8"
            )
            answer = turn.get("answer") or {}
            result = answer.get("result") or {}
            log(
                {
                    "turn": number,
                    "attempt": attempt,
                    "state": turn.get("state"),
                    "error": turn.get("error"),
                    "status": answer.get("status"),
                    "omitted": answer.get("omitted_claims"),
                    "cells": len(result.get("cells", [])),
                    "proof": (result.get("proof") or {}).get("availability"),
                    "seconds": seconds,
                }
            )
            if turn.get("error") != "provider_failed":
                break
        if answer.get("status") != "accepted" or not result:
            log({"stopped_at": number})
            return False
        selected = result["result_ref"]
    return True


def _ask(
    call: Call,
    base: str,
    token: dict[str, str],
    body: dict[str, Any],
    poll_seconds: float,
    max_wait_seconds: float,
) -> tuple[dict[str, Any], float]:
    start = time.monotonic()
    payload = json.dumps({**body, "request_id": uuid.uuid4().hex}).encode()
    status, turn = call(
        "POST", base + "/turns", payload, {**token, "Content-Type": "application/json"}
    )
    if status != 202:
        return {"state": "failed", "error": turn.get("error") or f"http_{status}"}, 0.0
    while turn.get("state") not in ("completed", "failed"):
        if time.monotonic() - start > max_wait_seconds:
            return {**turn, "error": "driver_wait_exceeded"}, round(time.monotonic() - start, 1)
        time.sleep(poll_seconds)
        status, turn = call("GET", f"{base}/turns/{turn['turn_id']}", None, token)
    return turn, round(time.monotonic() - start, 1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8128)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    return 0 if run(plan, http_call(args.port), args.out) else 1


if __name__ == "__main__":
    sys.exit(main())
