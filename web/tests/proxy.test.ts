import test from "node:test";
import assert from "node:assert/strict";
import {
  backendOrigin,
  boundedRead,
  forward,
  proxyTimeoutMs,
  BODY_LIMIT,
  RESPONSE_LIMIT,
} from "../lib/proxy";
const sid = "1".repeat(32),
  tid = "2".repeat(32),
  token = "t".repeat(43);
test("proxy timeout has a bounded, validated per-request setting", () => {
  assert.equal(proxyTimeoutMs(undefined), 30000);
  assert.equal(proxyTimeoutMs("12000"), 12000);
  assert.equal(proxyTimeoutMs("900000"), 900000);
  for (const value of [
    "",
    "0",
    "-1",
    "NaN",
    "Infinity",
    "1.5",
    "900001",
    "1e6",
  ])
    assert.throws(() => proxyTimeoutMs(value));
});
test("invalid proxy timeout refuses dispatch before local transport", async () => {
  const prior = process.env.KKB_PROXY_TIMEOUT_MS;
  process.env.KKB_PROXY_TIMEOUT_MS = "Infinity";
  let calls = 0;
  try {
    const response = await forward(request(), ["v1", "health"], async () => {
      calls++;
      return Response.json({});
    });
    assert.equal(response.status, 503);
    assert.equal(calls, 0);
  } finally {
    if (prior === undefined) delete process.env.KKB_PROXY_TIMEOUT_MS;
    else process.env.KKB_PROXY_TIMEOUT_MS = prior;
  }
});
function request(
  path = "v1/health",
  method = "GET",
  headers: Record<string, string> = {},
  body?: string,
) {
  return new Request(`http://127.0.0.1:3000/api/kkb/${path}`, {
    method,
    headers: {
      host: "127.0.0.1:3000",
      origin: "http://127.0.0.1:3000",
      ...headers,
    },
    body,
  });
}
test("only literal uncredentialed loopback targets are accepted", () => {
  assert.equal(backendOrigin(), "http://127.0.0.1:8000");
  assert.equal(
    backendOrigin("http://localhost:8123/"),
    "http://localhost:8123",
  );
  for (const target of [
    "https://127.0.0.1:8000",
    "http://127.1:8000",
    "http://localhost:80",
    "http://localhost:99999",
    "http://example.com:8000",
    "http://localhost:8000@evil.test",
    "http://user:password@localhost:8000",
    "http://localhost:8000/path",
    "http://localhost:8000?key=x",
    "http://[::1]:8000",
  ]) {
    assert.throws(() => backendOrigin(target));
  }
});
test("foreign sites, null origins, duplicate hosts and query strings never dispatch", async () => {
  let calls = 0;
  const transport: typeof fetch = async () => {
    calls++;
    return Response.json({});
  };
  const cases: Record<string, string>[] = [
    { host: "evil.test:3000" },
    { host: "127.0.0.1:3000, evil.test" },
    { origin: "null" },
    { origin: "https://evil.test" },
    { "sec-fetch-site": "cross-site" },
    { "sec-fetch-site": "same-site" },
  ];
  for (const headers of cases)
    assert.equal(
      (
        await forward(
          request("v1/health", "GET", headers),
          ["v1", "health"],
          transport,
        )
      ).status,
      403,
    );
  assert.equal(
    (
      await forward(
        request("v1/health?token=secret"),
        ["v1", "health"],
        transport,
      )
    ).status,
    403,
  );
  const missingOrigin = request(
    "v1/sessions",
    "POST",
    { "content-type": "application/json" },
    "{}",
  );
  missingOrigin.headers.delete("origin");
  assert.equal(
    (await forward(missingOrigin, ["v1", "sessions"], transport)).status,
    403,
  );
  assert.equal(calls, 0);
});
test("route/method and token allowlists reject unauthorized proxy shapes", async () => {
  let calls = 0;
  const transport: typeof fetch = async () => {
    calls++;
    return Response.json({});
  };
  for (const path of [
    ["https:", "evil.test"],
    ["v1", "sessions", sid, "turns", tid, "events"],
    ["v1", "sessions", sid, "delete"],
    ["v1", "..", "health"],
    ["v1", "sessions", sid, "turns", tid + "x"],
  ])
    assert.equal((await forward(request(), path, transport)).status, 404);
  for (const value of ["", token + ", " + token, "../secret"])
    assert.equal(
      (
        await forward(
          request(`v1/sessions/${sid}/turns/${tid}`, "GET", {
            "x-kkb-session-token": value,
          }),
          ["v1", "sessions", sid, "turns", tid],
          transport,
        )
      ).status,
      404,
    );
  assert.equal(calls, 0);
});
test("only required token and content headers cross to the fixed backend", async () => {
  const path = `v1/sessions/${sid}/turns`;
  let calls = 0;
  const transport: typeof fetch = async (url, init) => {
    calls++;
    assert.equal(url, `http://127.0.0.1:8000/${path}`);
    assert.equal(init?.redirect, "error");
    assert.equal(init?.cache, "no-store");
    const headers = new Headers(init?.headers);
    assert.equal(headers.get("origin"), "http://127.0.0.1:8000");
    assert.equal(headers.get("x-kkb-session-token"), token);
    assert.equal(headers.get("authorization"), null);
    assert.equal(headers.get("cookie"), null);
    assert.equal(headers.get("x-forwarded-host"), null);
    assert.equal(init?.body, '{"question":"test"}');
    return Response.json({ state: "queued" }, { status: 202 });
  };
  const result = await forward(
    request(
      path,
      "POST",
      {
        "content-type": "application/json",
        "x-kkb-session-token": token,
        authorization: "never-forward",
        cookie: "never-forward",
        "x-forwarded-host": "evil.test",
      },
      '{"question":"test"}',
    ),
    path.split("/"),
    transport,
  );
  assert.equal(result.status, 202);
  assert.equal(result.headers.get("cache-control"), "no-store");
  assert.equal(calls, 1);
});
test("real byte limits reject bodies even without content-length", async () => {
  let calls = 0;
  const transport: typeof fetch = async () => {
    calls++;
    return Response.json({});
  };
  for (const body of ["x".repeat(BODY_LIMIT + 1), "ş".repeat(BODY_LIMIT)])
    assert.equal(
      (
        await forward(
          request(
            "v1/sessions",
            "POST",
            { "content-type": "application/json" },
            body,
          ),
          ["v1", "sessions"],
          transport,
        )
      ).status,
      413,
    );
  assert.equal(
    (
      await forward(
        request("v1/sessions", "POST", { "content-type": "text/plain" }, "{}"),
        ["v1", "sessions"],
        transport,
      )
    ).status,
    415,
  );
  assert.equal(calls, 0);
});
test("oversized response, wrong content and raw failures become fixed errors", async () => {
  const cases: [typeof fetch, number][] = [
    [
      async () =>
        new Response("secret", { headers: { "content-type": "text/html" } }),
      502,
    ],
    [
      async () =>
        new Response("x".repeat(RESPONSE_LIMIT + 1), {
          headers: { "content-type": "application/json" },
        }),
      503,
    ],
    [
      async () => {
        throw new Error("private-api-key");
      },
      503,
    ],
  ];
  for (const [transport, status] of cases) {
    const result = await forward(request(), ["v1", "health"], transport);
    assert.equal(result.status, status);
    assert.equal(
      await result.text(),
      '{"api_version":1,"error":"unavailable"}',
    );
  }
});
test("stream abort cancels blocked reads and preserves the exact limit", async () => {
  const controller = new AbortController();
  let cancelled = false;
  const stream = new ReadableStream<Uint8Array>({
    cancel() {
      cancelled = true;
    },
  });
  const pending = boundedRead(stream, 4, controller.signal);
  controller.abort();
  await assert.rejects(pending);
  assert.ok(cancelled);
  assert.deepEqual(
    await boundedRead(
      new Blob(["test"]).stream(),
      4,
      new AbortController().signal,
    ),
    new TextEncoder().encode("test"),
  );
});

test("selected source and request identity pass through the bounded local bridge unchanged", async () => {
  const body = JSON.stringify({
    request_id: "3".repeat(32),
    question: "TÜFE ekle",
    selected_result_id: "4".repeat(32),
  });
  let calls = 0;
  const transport: typeof fetch = async (_url, init) => {
    calls++;
    assert.equal(init?.body, body);
    return Response.json({ api_version: 1 }, { status: 202 });
  };
  const response = await forward(
    request(
      `v1/sessions/${sid}/turns`,
      "POST",
      {
        "content-type": "application/json",
        "x-kkb-session-token": token,
      },
      body,
    ),
    ["v1", "sessions", sid, "turns"],
    transport,
  );
  assert.equal(response.status, 202);
  assert.equal(calls, 1);
});
