import test from "node:test";
import assert from "node:assert/strict";
import {
  backendOrigin,
  boundedRead,
  forward,
  proxyTimeoutMs,
  BODY_LIMIT,
  DOCUMENT_LIMIT,
  RESPONSE_LIMIT,
  TRACE_LIMIT,
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
test("a query is bounded by what was typed, not by its encoding", async () => {
  const seen: string[] = [];
  const transport: typeof fetch = async (input) => {
    seen.push(String(input));
    return Response.json({});
  };
  const key = "A".repeat(43);
  // 120 Turkish letters are 120 characters and 240 encoded ones; the old bound
  // refused them with 403 and said nothing about why (finding F4-vek-1).
  const typed = "ü".repeat(120);
  const query = new URLSearchParams({ search: typed }).toString();
  assert.equal(
    (
      await forward(
        request(`v1/conversations?${query}`, "GET", {
          "x-kkb-owner-token": key,
        }),
        ["v1", "conversations"],
        transport,
      )
    ).status,
    200,
  );
  assert.equal(seen.length, 1);
  // A space travels as "+" and is one character, so this is still within bounds.
  assert.equal(
    (
      await forward(
        request(
          `v1/conversations?${new URLSearchParams({
            search: "konut kredisi " + "a".repeat(106),
          }).toString()}`,
          "GET",
          { "x-kkb-owner-token": key },
        ),
        ["v1", "conversations"],
        transport,
      )
    ).status,
    200,
  );
  for (const query of [
    new URLSearchParams({ search: "ü".repeat(121) }).toString(),
    new URLSearchParams({ q: "x" }).toString(),
    "search=a&search=b",
    "archived=yes",
    "search=%E0%A4%A",
    "search=%00",
  ])
    assert.equal(
      (
        await forward(
          request(`v1/conversations?${query}`, "GET", {
            "x-kkb-owner-token": key,
          }),
          ["v1", "conversations"],
          transport,
        )
      ).status,
      403,
    );
  assert.equal(seen.length, 2);
});

test("a write without its own origin is refused whatever its method is", async () => {
  let calls = 0;
  const transport: typeof fetch = async () => {
    calls++;
    return Response.json({});
  };
  const key = "A".repeat(43);
  const sid = "a".repeat(32);
  const writes: [string, string, Record<string, string>, string?][] = [
    [
      `v1/conversations/${sid}`,
      "PATCH",
      {
        "x-kkb-session-token": "B".repeat(43),
        "content-type": "application/json",
      },
      '{"title":"x"}',
    ],
    [`v1/conversations/${sid}`, "DELETE", { "x-kkb-owner-token": key }],
    [`v1/conversations/${sid}/runs`, "DELETE", { "x-kkb-owner-token": key }],
  ];
  for (const [path, method, headers, body] of writes) {
    const bare = request(path, method, headers, body);
    bare.headers.delete("origin");
    assert.equal(
      (await forward(bare, path.split("/"), transport)).status,
      403,
      `${method} ${path}`,
    );
  }
  assert.equal(calls, 0);
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

function documentRequest(
  headers: Record<string, string>,
  body: BodyInit | null,
  method = "POST",
) {
  return new Request(
    `http://127.0.0.1:3000/api/kkb/v1/sessions/${sid}/documents`,
    {
      method,
      headers: {
        host: "127.0.0.1:3000",
        origin: "http://127.0.0.1:3000",
        ...headers,
      },
      body,
    },
  );
}
const documentPath = ["v1", "sessions", sid, "documents"];

test("a document upload crosses as exact bytes with only its type and token", async () => {
  const bytes = new TextEncoder().encode("Ay;Kapanış (Puan)\n2026-04;9000\n");
  let calls = 0;
  const transport: typeof fetch = async (url, init) => {
    calls++;
    assert.equal(url, `http://127.0.0.1:8000/v1/sessions/${sid}/documents`);
    const headers = new Headers(init?.headers);
    assert.equal(headers.get("content-type"), "text/csv");
    assert.equal(headers.get("x-kkb-session-token"), token);
    assert.equal(headers.get("cookie"), null);
    assert.deepEqual(new Uint8Array(init?.body as Uint8Array), bytes);
    return Response.json({ document_ref: "a".repeat(32) }, { status: 201 });
  };
  const result = await forward(
    documentRequest(
      {
        "content-type": "text/csv; charset=utf-8",
        "x-kkb-session-token": token,
        cookie: "never-forward",
      },
      bytes,
    ),
    documentPath,
    transport,
  );
  assert.equal(result.status, 201);
  assert.equal(calls, 1);
});

test("document uploads refuse other types, sizes, methods and missing tokens", async () => {
  let calls = 0;
  const transport: typeof fetch = async () => {
    calls++;
    return Response.json({}, { status: 201 });
  };
  const small = new Uint8Array([1, 2, 3]);
  const cases: [Request, number][] = [
    [
      documentRequest(
        { "content-type": "image/gif", "x-kkb-session-token": token },
        small,
      ),
      415,
    ],
    [
      documentRequest(
        { "content-type": "application/json", "x-kkb-session-token": token },
        small,
      ),
      415,
    ],
    [documentRequest({ "content-type": "text/csv" }, small), 404],
    [
      documentRequest(
        {
          "content-type": "text/csv",
          "x-kkb-session-token": token,
          "content-length": String(DOCUMENT_LIMIT + 1),
        },
        small,
      ),
      413,
    ],
    [
      documentRequest(
        { "content-type": "text/csv", "x-kkb-session-token": token },
        new Uint8Array(DOCUMENT_LIMIT + 1),
      ),
      413,
    ],
    [documentRequest({ "x-kkb-session-token": token }, null, "GET"), 404],
  ];
  for (const [item, status] of cases)
    assert.equal((await forward(item, documentPath, transport)).status, status);
  // A turn body is still JSON-only and 16 KiB, even with a document type.
  const turnPath = `v1/sessions/${sid}/turns`;
  assert.equal(
    (
      await forward(
        request(
          turnPath,
          "POST",
          { "content-type": "text/csv", "x-kkb-session-token": token },
          "a",
        ),
        turnPath.split("/"),
        transport,
      )
    ).status,
    415,
  );
  assert.equal(BODY_LIMIT < DOCUMENT_LIMIT, true);
  assert.equal(calls, 0);
});

test("conversation routes pass only with their key, method and bounded query", async () => {
  const seen: { url: string; headers: Headers }[] = [];
  const transport: typeof fetch = async (url, init) => {
    seen.push({ url: String(url), headers: new Headers(init?.headers) });
    return Response.json({ ok: true });
  };
  const owner = "o".repeat(43);

  // Listing needs the owner key and passes its filters through.
  const listed = await forward(
    request("v1/conversations?archived=true&search=konut", "GET", {
      "x-kkb-owner-token": owner,
    }),
    ["v1", "conversations"],
    transport,
  );
  assert.equal(listed.status, 200);
  assert.match(seen[0].url, /\/v1\/conversations\?archived=true&search=konut$/);
  assert.equal(seen[0].headers.get("X-KKB-Owner-Token"), owner);

  const traceListed = await forward(
    request("v1/trace-conversations?search=konut", "GET", {
      "x-kkb-owner-token": owner,
    }),
    ["v1", "trace-conversations"],
    transport,
  );
  assert.equal(traceListed.status, 200);
  assert.match(seen.at(-1)!.url, /\/v1\/trace-conversations\?search=konut$/);
  assert.equal(seen.at(-1)!.headers.get("X-KKB-Owner-Token"), owner);
  assert.equal(
    (
      await forward(
        request("v1/trace-conversations", "GET"),
        ["v1", "trace-conversations"],
        transport,
      )
    ).status,
    404,
  );
  assert.equal(
    (
      await forward(
        request("v1/trace-conversations", "DELETE", {
          "x-kkb-owner-token": owner,
        }),
        ["v1", "trace-conversations"],
        transport,
      )
    ).status,
    404,
  );

  // Without the key, and with a query nobody offered, nothing is forwarded.
  assert.equal(
    (
      await forward(
        request("v1/conversations", "GET"),
        ["v1", "conversations"],
        transport,
      )
    ).status,
    404,
  );
  for (const path of [
    `v1/conversations/${sid}`,
    `v1/conversations/${sid}/runs`,
  ]) {
    const removed = await forward(
      request(path, "DELETE", { "x-kkb-owner-token": owner }),
      path.split("/"),
      transport,
    );
    assert.equal(removed.status, 200);
    assert.equal(seen.at(-1)?.headers.get("X-KKB-Owner-Token"), owner);
    assert.equal(seen.at(-1)?.headers.get("X-KKB-Session-Token"), null);
    const denied = await forward(
      request(path, "DELETE", { "x-kkb-session-token": token }),
      path.split("/"),
      transport,
    );
    assert.equal(denied.status, 404);
  }
  assert.equal(
    (
      await forward(
        request("v1/conversations?limit=9999", "GET", {
          "x-kkb-owner-token": owner,
        }),
        ["v1", "conversations"],
        transport,
      )
    ).status,
    403,
  );
  assert.equal(
    (
      await forward(
        request(`v1/sessions/${sid}/turns?x=1`, "GET", {
          "x-kkb-session-token": token,
        }),
        ["v1", "sessions", sid, "turns"],
        transport,
      )
    ).status,
    403,
  );

  // Renaming is a PATCH with a JSON body and the conversation's own credential.
  const renamed = await forward(
    request(
      `v1/conversations/${sid}`,
      "PATCH",
      { "x-kkb-session-token": token, "content-type": "application/json" },
      JSON.stringify({ title: "Konut" }),
    ),
    ["v1", "conversations", sid],
    transport,
  );
  assert.equal(renamed.status, 200);
  assert.equal(seen.at(-1)?.headers.get("X-KKB-Session-Token"), token);
  assert.equal(
    (
      await forward(
        request(`v1/conversations/${sid}`, "DELETE", {
          "x-kkb-session-token": token,
        }),
        ["v1", "conversations", sid],
        transport,
      )
    ).status,
    404,
  );
});

test("a turn's cancel passes only as a keyed POST to that exact turn", async () => {
  const seen: { url: string; method: string; headers: Headers }[] = [];
  const transport: typeof fetch = async (url, init) => {
    seen.push({
      url: String(url),
      method: init?.method ?? "GET",
      headers: new Headers(init?.headers),
    });
    return Response.json({ ok: true }, { status: 202 });
  };
  const path = `v1/sessions/${sid}/turns/${"c".repeat(32)}/cancel`;
  const keyed = {
    "x-kkb-session-token": token,
    "content-type": "application/json",
  };

  const sent = await forward(
    request(path, "POST", keyed, "{}"),
    path.split("/"),
    transport,
  );
  assert.equal(sent.status, 202);
  assert.match(seen[0].url, new RegExp(`/${path}$`));
  assert.equal(seen[0].headers.get("X-KKB-Session-Token"), token);

  // Without the key, with another method, or under another name: nothing is forwarded.
  for (const [target, method, headers] of [
    [path, "POST", { "content-type": "application/json" }],
    [path, "GET", keyed],
    [`v1/sessions/${sid}/turns/${"c".repeat(32)}/stop`, "POST", keyed],
    [`v1/sessions/${sid}/turns/cancel`, "POST", keyed],
  ] as const) {
    const refused = await forward(
      request(target, method, headers, method === "POST" ? "{}" : undefined),
      target.split("/"),
      transport,
    );
    assert.equal(refused.status, 404, `${method} ${target}`);
  }
  assert.equal(seen.length, 1);
});

test("a stored trace and one whole step pass with the key, under the trace ceiling", async () => {
  const run = "3".repeat(32);
  const keyed = { "x-kkb-session-token": token };
  const big =
    (bytes: number): typeof fetch =>
    async () =>
      new Response("x".repeat(bytes), {
        headers: { "content-type": "application/json" },
      });
  for (const path of [
    `v1/conversations/${sid}/runs/${run}`,
    `v1/conversations/${sid}/runs/${run}/steps/12`,
  ]) {
    // A trace larger than an ordinary response still arrives whole.
    const passed = await forward(
      request(path, "GET", keyed),
      path.split("/"),
      big(RESPONSE_LIMIT + 1),
    );
    assert.equal(passed.status, 200);
    const beyond = await forward(
      request(path, "GET", keyed),
      path.split("/"),
      big(TRACE_LIMIT + 1),
    );
    assert.equal(beyond.status, 503);
    assert.equal(
      (await forward(request(path, "GET"), path.split("/"), big(2))).status,
      404,
    );
  }
  // The list keeps the ordinary ceiling; malformed steps never dispatch.
  const list = `v1/conversations/${sid}/runs`;
  assert.equal(
    (
      await forward(
        request(list, "GET", keyed),
        list.split("/"),
        big(RESPONSE_LIMIT + 1),
      )
    ).status,
    503,
  );
  for (const step of ["0", "01", "1234567", "x"]) {
    const path = `v1/conversations/${sid}/runs/${run}/steps/${step}`;
    assert.equal(
      (await forward(request(path, "GET", keyed), path.split("/"), big(2)))
        .status,
      404,
    );
  }
});

test("the catalogue trial passes with the browser key and only its own query", async () => {
  const seen: { url: string; headers: Headers }[] = [];
  const transport: typeof fetch = async (url, init) => {
    seen.push({ url: String(url), headers: new Headers(init?.headers) });
    return Response.json({ ok: true });
  };
  const key = "o".repeat(43);
  const path = ["v1", "knowledge", "search"];

  const passed = await forward(
    request("v1/knowledge/search?q=konut%20kredisi", "GET", {
      "x-kkb-owner-token": key,
    }),
    path,
    transport,
  );
  assert.equal(passed.status, 200);
  assert.match(seen[0].url, /\/v1\/knowledge\/search\?q=konut%20kredisi$/);
  assert.equal(seen[0].headers.get("X-KKB-Owner-Token"), key);

  // Without the key, with another parameter, or as a write: nothing is forwarded.
  for (const [target, method, headers] of [
    ["v1/knowledge/search?q=x", "GET", {}],
    ["v1/knowledge/search?limit=9", "GET", { "x-kkb-owner-token": key }],
    ["v1/knowledge/search?q=x", "POST", { "x-kkb-owner-token": key }],
  ] as [string, string, Record<string, string>][]) {
    const refused = await forward(
      request(target, method, headers),
      path,
      transport,
    );
    assert.ok([403, 404].includes(refused.status), `${target} ${method}`);
  }
});

test("the live progress route is allowed and the step route still is", async () => {
  const sid = "a".repeat(32);
  const run = "b".repeat(32);
  const keyed = { "x-kkb-session-token": "t".repeat(43) };
  for (const path of [
    `v1/conversations/${sid}/runs/${run}/progress`,
    `v1/conversations/${sid}/runs/${run}/steps/3`,
  ]) {
    const response = await forward(
      request(path, "GET", keyed),
      path.split("/"),
      async () =>
        new Response("{}", { headers: { "content-type": "application/json" } }),
    );
    assert.equal(response.status, 200, path);
  }
});
