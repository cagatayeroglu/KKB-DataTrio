"""Does this deployment stream a chat completion, and with structured output?

One live call, on purpose: D6-2 (abort on silence instead of a 900 s total
deadline, and a Stop that ends the request rather than waiting for it) is only
possible if the served model honours `stream: true`, and it is only useful for a
plan if it honours it together with `response_format: json_object`. Nothing else
can answer that; the provider's own documentation does not say.

Run it from the repository root with the same environment the API uses:

    python tests/manual/probe_streaming.py            # free text
    python tests/manual/probe_streaming.py --json     # with response_format

It prints timings and whether chunks arrived progressively. It never prints the
credential, the endpoint's host or the model's text beyond a short head."""

from __future__ import annotations

import argparse
import json
import time

import httpx

from kkb_agent.llm.config import ProviderConfig
from kkb_agent.llm.kloudeks import CHAT_PATH, approved_base_url


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="ask for response_format")
    parser.add_argument("--max-tokens", type=int, default=256)
    args = parser.parse_args()

    config = ProviderConfig.from_env()
    body: dict[str, object] = {
        "model": config.planner_model,
        "messages": [
            {"role": "system", "content": 'Answer with a JSON object: {"ok": true}.'},
            {"role": "user", "content": "Say ok."},
        ],
        "temperature": 0.0,
        "max_tokens": args.max_tokens,
        "stream": True,
    }
    if args.json:
        body["response_format"] = {"type": "json_object"}

    started = time.monotonic()
    first: float | None = None
    chunks = 0
    text = []
    with httpx.Client(
        base_url=approved_base_url(config.base_url),
        timeout=httpx.Timeout(120.0),
        trust_env=False,
        follow_redirects=False,
    ) as client:
        request = client.build_request(
            "POST",
            CHAT_PATH,
            json=body,
            headers={
                "Authorization": f"Bearer {config.credential.get_secret_value()}",
            },
        )
        with client.send(request, stream=True) as response:
            print(f"status {response.status_code}")
            print(f"content-type {response.headers.get('content-type', '-')}")
            if response.status_code >= 400:
                response.read()
                print("body head:", response.text[:300])
                return 1
            for line in response.iter_lines():
                if not line:
                    continue
                if first is None:
                    first = time.monotonic() - started
                chunks += 1
                if line.startswith("data: "):
                    payload = line[6:]
                    if payload.strip() == "[DONE]":
                        continue
                    try:
                        event = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    choices = event.get("choices") or [{}]
                    delta = choices[0].get("delta") or {}
                    piece = delta.get("content")
                    if isinstance(piece, str):
                        text.append(piece)
    total = time.monotonic() - started
    joined = "".join(text)
    print(
        json.dumps(
            {
                "chunks": chunks,
                "seconds_to_first_chunk": round(first, 2) if first else None,
                "seconds_total": round(total, 2),
                "streamed_progressively": bool(first and total - first > 0.2),
                "content_chars": len(joined),
                "content_parses_as_json": _parses(joined),
                "content_head": joined[:80],
            },
            ensure_ascii=False,
        )
    )
    return 0


def _parses(text: str) -> bool:
    try:
        json.loads(text)
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
