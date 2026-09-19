import test from "node:test";
import assert from "node:assert/strict";
import { DELETE, PATCH } from "../app/api/kkb/[...path]/route";

const session = "1".repeat(32);
const token = "t".repeat(43);

function browserRequest(
  path: string[],
  method: "PATCH" | "DELETE",
  body?: object,
  origin = "http://127.0.0.1:3000",
) {
  return new Request(`http://127.0.0.1:3000/api/kkb/${path.join("/")}`, {
    method,
    headers: {
      host: "127.0.0.1:3000",
      origin,
      "x-kkb-owner-token": token,
      "x-kkb-session-token": token,
      ...(body ? { "content-type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
}

test("actual Next route exports forward PATCH and DELETE without bypassing guards", async () => {
  const originalFetch = globalThis.fetch;
  const sent: { path: string; method: string; body: string | undefined }[] = [];
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    sent.push({
      path: new URL(String(input)).pathname,
      method: init?.method ?? "",
      body: typeof init?.body === "string" ? init.body : undefined,
    });
    return Response.json({ ok: true });
  }) as typeof fetch;
  try {
    const conversation = ["v1", "conversations", session];
    const settings = ["v1", "settings"];
    const runs = [...conversation, "runs"];
    const patches: { path: string[]; body: object }[] = [
      { path: conversation, body: { title: "Yeni ad" } },
      { path: conversation, body: { archived: true } },
      { path: conversation, body: { archived: false } },
      { path: settings, body: { language: "tr" } },
    ];
    for (const { path, body } of patches) {
      const response = await PATCH(browserRequest(path, "PATCH", body), {
        params: Promise.resolve({ path }),
      });
      assert.equal(response.status, 200);
    }
    for (const path of [conversation, runs]) {
      const response = await DELETE(browserRequest(path, "DELETE"), {
        params: Promise.resolve({ path }),
      });
      assert.equal(response.status, 200);
    }
    assert.deepEqual(
      sent.map(({ path, method }) => [path, method]),
      [
        [`/${conversation.join("/")}`, "PATCH"],
        [`/${conversation.join("/")}`, "PATCH"],
        [`/${conversation.join("/")}`, "PATCH"],
        ["/v1/settings", "PATCH"],
        [`/${conversation.join("/")}`, "DELETE"],
        [`/${runs.join("/")}`, "DELETE"],
      ],
    );
    assert.deepEqual(
      sent.slice(0, 4).map(({ body }) => JSON.parse(body ?? "")),
      patches.map(({ body }) => body),
    );

    const beforeDenied = sent.length;
    assert.equal(
      (
        await PATCH(
          browserRequest(
            conversation,
            "PATCH",
            { title: "bad" },
            "http://evil.test",
          ),
          {
            params: Promise.resolve({ path: conversation }),
          },
        )
      ).status,
      403,
    );
    assert.equal(
      (
        await DELETE(browserRequest(["v1", "unlisted"], "DELETE"), {
          params: Promise.resolve({ path: ["v1", "unlisted"] }),
        })
      ).status,
      404,
    );
    assert.equal(sent.length, beforeDenied);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
