import test from "node:test";
import assert from "node:assert/strict";
import {
  admit,
  admissionRejection,
  lostTurn,
  draftRequest,
  publishedResult,
  restoredSelection,
  readTurn,
  loadSession,
  saveSession,
  validQuestion,
  describeError,
  documentMediaType,
  uploadDocument,
  deleteConversation,
  deleteConversationRuns,
  listTraceConversations,
  ApiError,
} from "../lib/client";
import {
  cellSchema,
  conversationSummarySchema,
  traceConversationSummarySchema,
  turnSchema,
  type Saved,
} from "../lib/contracts";
import { arrange, displayValue, unitLabel, periodLabel } from "../lib/table";
import { noticeText } from "../lib/language";
const sid = "1".repeat(32),
  tid = "2".repeat(32),
  rid = "3".repeat(32);
const session = {
  api_version: 1 as const,
  session_id: sid,
  token: "t".repeat(43),
  survives_restart: false as const,
};
const saved: Saved = {
  session,
  turns: [{ question: "Konut kredileri", request_id: rid }],
};
const turn = {
  api_version: 1,
  turn_id: tid,
  request_id: rid,
  state: "running",
  answer: null,
  error: null,
  events: [
    { sequence: 1, state: "queued", elapsed_ms: 0 },
    { sequence: 2, state: "running", elapsed_ms: 0 },
  ],
};
const base = {
  cell_id: "4".repeat(32),
  slot: 0,
  label: "Kredi",
  value: 2,
  display: "2",
  unit: "TRY",
  scale: "million",
  measure: "stock",
  period: {
    start: "2025-01-01",
    end: "2025-01-31",
    frequency: "monthly",
    weekly_anchor: null,
  },
  samples: { used: 1, missing: 0, excluded: 0, minimum_required: null },
  lag: null,
};
test("ambiguous transport retry keeps the same identity and exact text", async () => {
  const old = globalThis.fetch;
  const requests: RequestInit[] = [];
  globalThis.fetch = async (_url, init) => {
    requests.push(init!);
    if (requests.length === 1) throw new Error("network");
    return Response.json(turn);
  };
  try {
    await assert.rejects(admit(saved, 0));
    const received = await admit(saved, 0);
    assert.equal(received.request_id, rid);
    assert.equal(requests[0].body, requests[1].body);
    assert.equal(JSON.parse(String(requests[1].body)).request_id, rid);
    assert.equal(
      new Headers(requests[1].headers).get("x-kkb-session-token"),
      session.token,
    );
  } finally {
    globalThis.fetch = old;
  }
});
test("an admitted turn is recovered by GET without another question submission", async () => {
  const old = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async (url, init) => {
    calls++;
    assert.equal(url, `/api/kkb/v1/sessions/${sid}/turns/${tid}`);
    assert.equal(init?.method, undefined);
    return Response.json(turn);
  };
  try {
    await admit({ ...saved, turns: [{ ...saved.turns[0], turn_id: tid }] }, 0);
    assert.equal(calls, 1);
  } finally {
    globalThis.fetch = old;
  }
});
test("deletion uses the owner key and keeps soft-delete separate from trace deletion", async () => {
  const old = globalThis.fetch;
  const seen: { url: string; method: string; headers: Headers }[] = [];
  globalThis.fetch = async (url, init) => {
    seen.push({
      url: String(url),
      method: init?.method ?? "GET",
      headers: new Headers(init?.headers),
    });
    return Response.json(
      seen.length === 1
        ? { api_version: 1, deleted: true }
        : { api_version: 1, deleted_runs: 2 },
    );
  };
  try {
    assert.equal((await deleteConversation(sid, session.token)).deleted, true);
    assert.equal(
      (await deleteConversationRuns(sid, session.token)).deleted_runs,
      2,
    );
  } finally {
    globalThis.fetch = old;
  }
  assert.deepEqual(
    seen.map((item) => item.url),
    [
      `/api/kkb/v1/conversations/${sid}`,
      `/api/kkb/v1/conversations/${sid}/runs`,
    ],
  );
  assert.ok(seen.every((item) => item.method === "DELETE"));
  assert.ok(
    seen.every(
      (item) => item.headers.get("x-kkb-owner-token") === session.token,
    ),
  );
  assert.ok(seen.every((item) => !item.headers.has("x-kkb-session-token")));
});
test("deleted chats have a trace-only owner index and never satisfy normal chat schema", async () => {
  const old = globalThis.fetch;
  const seen: { url: string; headers: Headers }[] = [];
  const entry = {
    conversation_id: sid,
    title: "Silinen test sohbeti",
    archived: false,
    created_at: "2026-09-19T10:00:00Z",
    updated_at: "2026-09-19T10:01:00Z",
    turns: 1,
    deleted: true,
  };
  globalThis.fetch = async (url, init) => {
    seen.push({ url: String(url), headers: new Headers(init?.headers) });
    return Response.json({ api_version: 1, conversations: [entry] });
  };
  try {
    const listed = await listTraceConversations(session.token, {
      search: "test",
    });
    assert.equal(listed.conversations[0].deleted, true);
  } finally {
    globalThis.fetch = old;
  }
  assert.equal(seen[0].url, "/api/kkb/v1/trace-conversations?search=test");
  assert.equal(seen[0].headers.get("x-kkb-owner-token"), session.token);
  assert.ok(traceConversationSummarySchema.safeParse(entry).success);
  assert.ok(!conversationSummarySchema.safeParse(entry).success);
});
test("session state is validated and storage failure is not ignored", () => {
  const memory = new Map<string, string>();
  const storage = {
    get length() {
      return memory.size;
    },
    clear: () => memory.clear(),
    key: (index: number) => [...memory.keys()][index] ?? null,
    getItem: (key: string) => memory.get(key) ?? null,
    setItem: (key: string, value: string) => memory.set(key, value),
    removeItem: (key: string) => memory.delete(key),
  } satisfies Storage;
  assert.equal(loadSession(storage), null);
  saveSession(storage, saved);
  assert.deepEqual(loadSession(storage), saved);
  memory.set("kkb.workspace.v1", '{"session":{"token":"invalid"}}');
  assert.equal(loadSession(storage), null);
  storage.setItem = () => {
    throw new Error("unavailable");
  };
  assert.throws(() => saveSession(storage, saved));
});
test("unknown scales, nullable sample minimum and full period survive validation", () => {
  const cell = cellSchema.parse({ ...base, unit: null, scale: "unknown" });
  assert.equal(cell.samples?.minimum_required, null);
  assert.equal(
    unitLabel(cell.unit, cell.scale),
    "ölçek belirsiz birim belirsiz",
  );
  assert.equal(displayValue(cell), "2");
  assert.equal(cellSchema.safeParse({ ...base, value: NaN }).success, false);
  assert.equal(
    cellSchema.safeParse({ ...base, value: Infinity }).success,
    false,
  );
  assert.equal(
    turnSchema.safeParse({ ...turn, secret: "hidden" }).success,
    false,
  );
});
test("duplicate cells and distinct units do not overwrite or aggregate", () => {
  const a = cellSchema.parse(base),
    b = cellSchema.parse({
      ...base,
      cell_id: "5".repeat(32),
      slot: 1,
      value: 3,
      display: "3",
    }),
    c = cellSchema.parse({
      ...base,
      cell_id: "6".repeat(32),
      slot: 2,
      unit: "USD",
    }),
    d = cellSchema.parse({
      ...base,
      cell_id: "7".repeat(32),
      slot: 3,
      period: null,
    });
  const table = arrange([a, b, c, d]);
  assert.equal(table.rows.length, 2);
  assert.equal(table.columns.length, 2);
  assert.deepEqual(table.metrics, [d]);
  const cells = table.rows.flatMap((row) => Object.values(row.values));
  assert.equal(cells.length, 3);
  assert.ok(cells.includes(a) && cells.includes(b) && cells.includes(c));
});
test("missing cells are absent, not fabricated zero or last-value copies", () => {
  const a = cellSchema.parse(base),
    b = cellSchema.parse({
      ...base,
      cell_id: "5".repeat(32),
      label: "Faiz",
      slot: 1,
      period: { ...base.period, start: "2025-02-01", end: "2025-02-28" },
    });
  const table = arrange([a, b]);
  assert.equal(table.rows.length, 2);
  assert.equal(Object.values(table.rows[0].values).length, 1);
  assert.equal(Object.values(table.rows[1].values).length, 1);
});
test("byte-aware question limits and safe errors", () => {
  assert.ok(validQuestion("Konut kredileri\n2025"));
  assert.ok(!validQuestion(" "));
  assert.ok(!validQuestion("x".repeat(4097)));
  assert.ok(!validQuestion("あ".repeat(3000)));
  assert.ok(!validQuestion("x\u0000y"));
  assert.ok(
    !describeError(new ApiError("private-token")).includes("private-token"),
  );
  assert.ok(!describeError(new Error("C:/private/key")).includes("private"));
});

test("whole-window summaries keep their period and do not create empty monthly columns", () => {
  const a = cellSchema.parse(base),
    b = cellSchema.parse({
      ...base,
      cell_id: "5".repeat(32),
      slot: 1,
      period: { ...base.period, start: "2025-02-01", end: "2025-02-28" },
    }),
    summary = cellSchema.parse({
      ...base,
      cell_id: "6".repeat(32),
      slot: 2,
      label: "total transitions",
      period: { ...base.period, end: "2025-02-28" },
    });
  const table = arrange([a, b, summary]);
  assert.equal(table.columns.length, 1);
  assert.equal(table.rows.length, 2);
  assert.deepEqual(table.metrics, [summary]);
  assert.equal(periodLabel(summary.period), "2025-01-01 – 2025-02-28");
});
test("diagnostic translation retains independent-verification limitations", () => {
  assert.equal(
    noticeText("No external cross-check was performed"),
    "Başka bir dış kaynakla bağımsız çapraz kontrol yapılmadı.",
  );
  assert.equal(noticeText("unknown diagnostic"), "unknown diagnostic");
});

function completed(reference = "a".repeat(32)) {
  return turnSchema.parse({
    ...turn,
    state: "completed",
    answer: {
      status: "accepted",
      text: "Tablo hazır",
      omitted_claims: 0,
      notices: [],
      result: {
        result_ref: reference,
        version: "b".repeat(64),
        kind: "table",
        claim_kind: "computed",
        published: true,
        cells: [base],
        proof: {
          scope: "result",
          availability: "unavailable",
          gate: "accepted",
          steps: [],
          sources: [],
          warnings: [],
          limitations: [],
          unresolved_semantics: [],
          gaps: [],
        },
      },
    },
  });
}
test("selected request persists its source across view changes and uncertain retry", async () => {
  const entry = draftRequest("  TÜFE ekle  ", completed());
  const state: Saved = {
    ...saved,
    view_result_id: "c".repeat(32),
    turns: [entry],
  };
  const old = globalThis.fetch;
  const bodies: string[] = [];
  globalThis.fetch = async (_url, init) => {
    bodies.push(String(init?.body));
    if (bodies.length === 1) throw new Error("lost after admission");
    return Response.json({ ...turn, request_id: entry.request_id });
  };
  try {
    await assert.rejects(admit(state, 0));
    state.follow_selected = false;
    state.view_result_id = "d".repeat(32);
    await admit(state, 0);
    assert.equal(bodies[0], bodies[1]);
    assert.deepEqual(JSON.parse(bodies[1]), {
      request_id: entry.request_id,
      question: "TÜFE ekle",
      selected_result_id: "a".repeat(32),
    });
  } finally {
    globalThis.fetch = old;
  }
});
test("reload restores an older exact selection and never substitutes a missing reference", () => {
  const first = completed(),
    second = completed("c".repeat(32));
  assert.equal(
    restoredSelection(
      { ...saved, view_result_id: first.answer!.result!.result_ref },
      [first, second],
    ),
    0,
  );
  assert.equal(
    restoredSelection({ ...saved, view_result_id: "d".repeat(32) }, [
      first,
      second,
    ]),
    -1,
  );
  assert.equal(restoredSelection(saved, [first, second]), 1);
  assert.equal(restoredSelection(saved, [undefined, second, undefined]), 1);
});
test("a finished turn that did not abstain can ground a new request", () => {
  const first = completed();
  for (const state of ["running", "failed"] as const) {
    assert.equal(turnSchema.safeParse({ ...first, state }).success, false);
    assert.equal(publishedResult({ ...first, state }), undefined);
    assert.throws(() => draftRequest("Devam", { ...first, state }));
  }
  const abstained = turnSchema.parse({
    ...first,
    answer: { ...first.answer, status: "abstained", result: null },
  });
  assert.throws(() => draftRequest("Devam", abstained));
  assert.equal(draftRequest("Serbest soru").selected_result_id, undefined);
  // A withheld sentence does not unpublish the table (DEC-186). The server attaches a
  // result to every status but abstained; rejecting it here froze the chat on a
  // qualified turn with "Yanıt beklenen veri biçimine uymuyor" (live 2026-09-21).
  const qualified = turnSchema.parse({
    ...first,
    answer: { ...first.answer, status: "qualified" },
  });
  const published = first.answer?.result?.result_ref;
  assert.ok(published);
  assert.equal(publishedResult(qualified)?.result_ref, published);
  assert.equal(draftRequest("Devam", qualified).selected_result_id, published);
});
test("legacy recovery does not inherit the current view's selected source", async () => {
  const old = globalThis.fetch;
  globalThis.fetch = async (_url, init) => {
    assert.deepEqual(JSON.parse(String(init?.body)), {
      request_id: rid,
      question: saved.turns[0].question,
    });
    return Response.json(turn);
  };
  try {
    await admit({ ...saved, view_result_id: "a".repeat(32) }, 0);
  } finally {
    globalThis.fetch = old;
  }
});
test("GET recovery checks both request and turn identity", async () => {
  const old = globalThis.fetch;
  globalThis.fetch = async () =>
    Response.json({ ...turn, request_id: "f".repeat(32) });
  try {
    await assert.rejects(readTurn(session, tid, rid), {
      code: "invalid_response",
    });
  } finally {
    globalThis.fetch = old;
  }
});
test("a forgotten turn is a 404 and nothing else", () => {
  // A restart is the one case where following the turn is pointless: the handle
  // is gone from the API process while the conversation stays in its store.
  assert.equal(lostTurn(new ApiError("not_found", 404)), true);
  for (const error of [
    new ApiError("busy", 409),
    new ApiError("capacity", 429),
    new ApiError("internal_error", 500),
    new ApiError("unavailable", 503),
    new ApiError("connection"),
    new Error("network"),
  ])
    assert.equal(lostTurn(error), false);
});
test("only explicit admission rejection ends recovery; transport and server errors do not", async () => {
  for (const code of [
    "invalid_result",
    "invalid_request",
    "request_conflict",
    "capacity",
  ])
    assert.equal(admissionRejection(new ApiError(code, 422)), code);
  for (const error of [
    new ApiError("invalid_result", 503),
    new ApiError("connection"),
    new ApiError("busy", 409),
    new Error("network"),
  ])
    assert.equal(admissionRejection(error), undefined);
  const old = globalThis.fetch;
  globalThis.fetch = async () => {
    assert.fail("Rejected admission must not be resubmitted");
  };
  try {
    await assert.rejects(
      admit(
        {
          ...saved,
          turns: [{ ...saved.turns[0], admission_error: "invalid_result" }],
        },
        0,
      ),
      { code: "invalid_result" },
    );
  } finally {
    globalThis.fetch = old;
  }
});

test("a workspace question pins no table and states no continuation", async () => {
  // The composer sends the question alone: which earlier table serves it, and
  // whether it continues a pending clarification, is the agent's reading.
  const entry = draftRequest("Bu tabloya TÜFE ekle", undefined, undefined);
  assert.equal(entry.selected_result_id, undefined);
  assert.equal(entry.is_continuation, undefined);
  const old = globalThis.fetch;
  const bodies: Record<string, unknown>[] = [];
  globalThis.fetch = async (_url, init) => {
    bodies.push(JSON.parse(String(init?.body)));
    return Response.json({ ...turn, request_id: bodies.at(-1)?.request_id });
  };
  try {
    await admit({ ...saved, turns: [entry] }, 0);
  } finally {
    globalThis.fetch = old;
  }
  assert.deepEqual(bodies[0], {
    request_id: entry.request_id,
    question: entry.question,
  });
  // An API caller may still pin one explicitly; the contract keeps that field.
  const pinned = draftRequest("Bu tabloya TÜFE ekle", completed(), true);
  assert.equal(pinned.selected_result_id, "a".repeat(32));
  assert.equal(pinned.is_continuation, true);
});

test("abstained or error turns leave client UI state clean and selectable", () => {
  const failedTurn = turnSchema.parse({
    ...turn,
    state: "failed",
    error: "temporary_failure",
    answer: null,
  });

  // Failed turn produces no published selection
  assert.equal(publishedResult(failedTurn), undefined);

  // Fresh question submission after failure succeeds without stuck state
  const retryReq = draftRequest("Konut kredilerini göster");
  assert.equal(retryReq.question, "Konut kredilerini göster");
  assert.equal(retryReq.selected_result_id, undefined);
});

test("an attached document travels with exactly one question", async () => {
  assert.equal(documentMediaType("veri.CSV"), "text/csv");
  assert.equal(
    documentMediaType("tablo.xlsx"),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  );
  assert.equal(documentMediaType("rapor.pdf"), "application/pdf");
  assert.equal(documentMediaType("sayfa.htm"), "text/html");
  // A picture is read as a one-page scanned document (DEC-179).
  assert.equal(documentMediaType("ekran.png"), "image/png");
  assert.equal(documentMediaType("Tarama.JPG"), "image/jpeg");
  assert.equal(documentMediaType("foto.jpeg"), "image/jpeg");
  for (const name of ["makro.xlsm", "resim.gif", "csv", "arsiv.csv.zip"])
    assert.equal(documentMediaType(name), undefined);

  const admitted = {
    api_version: 1 as const,
    document_ref: "d".repeat(32),
    document_format: "csv" as const,
    bytes: 42,
    sha256: "e".repeat(64),
  };
  const old = globalThis.fetch;
  const seen: { url: string; type: string | null; body: unknown }[] = [];
  globalThis.fetch = async (url, init) => {
    seen.push({
      url: String(url),
      type: new Headers(init?.headers).get("content-type"),
      body: init?.body,
    });
    if (String(url).endsWith("/documents"))
      return Response.json(admitted, { status: 201 });
    const body = JSON.parse(String(init?.body));
    return Response.json({ ...turn, request_id: body.request_id });
  };
  try {
    const file = new File(["Ay;Kapanış (Puan)\n"], "veri.csv");
    assert.deepEqual(await uploadDocument(session, file), admitted);
    await assert.rejects(
      uploadDocument(session, new File(["x"], "makro.xlsm")),
      (error: unknown) =>
        error instanceof ApiError && error.code === "document_rejected",
    );
    const attached = draftRequest(
      "Ekli belgede Kapanış nedir?",
      undefined,
      undefined,
      admitted,
    );
    const plain = draftRequest("Belge olmadan soru");
    await admit({ ...saved, turns: [attached] }, 0);
    await admit({ ...saved, turns: [plain] }, 0);
  } finally {
    globalThis.fetch = old;
  }
  assert.equal(seen[0].url, `/api/kkb/v1/sessions/${sid}/documents`);
  assert.equal(seen[0].type, "text/csv");
  assert.equal(seen.length, 3); // the refused .xlsm never reached fetch
  assert.equal(JSON.parse(String(seen[1].body)).document_ref, "d".repeat(32));
  assert.equal("document_ref" in JSON.parse(String(seen[2].body)), false);
  assert.equal(
    describeError(new ApiError("invalid_document", 422)).includes(
      "yeniden yükle",
    ),
    true,
  );
});

test("a key the server does not know is replaced; a known key and a network error are kept", async () => {
  const { usableOwner } = await import("../lib/client");
  const store = new Map<string, string>();
  const storage = {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
  } as unknown as Storage;
  const old = "o".repeat(43);
  const fresh = "n".repeat(43);
  const original = globalThis.fetch;
  const calls: string[] = [];
  try {
    // Unknown here (another state root): listing is refused, a new key is issued.
    store.set("kkb.owner.v1", old);
    globalThis.fetch = async (url, init) => {
      calls.push(`${init?.method ?? "GET"} ${String(url)}`);
      if (String(url).endsWith("/conversations"))
        return Response.json(
          { api_version: 1, error: "forbidden" },
          { status: 403 },
        );
      return Response.json(
        { api_version: 1, owner_token: fresh },
        { status: 201 },
      );
    };
    assert.equal(await usableOwner(storage), fresh);
    assert.equal(store.get("kkb.owner.v1"), fresh);
    assert.deepEqual(calls, [
      "GET /api/kkb/v1/conversations",
      "POST /api/kkb/v1/owner",
    ]);

    // Known: kept, nothing created.
    calls.length = 0;
    globalThis.fetch = async (url, init) => {
      calls.push(`${init?.method ?? "GET"} ${String(url)}`);
      return Response.json({ api_version: 1, conversations: [] });
    };
    assert.equal(await usableOwner(storage), fresh);
    assert.deepEqual(calls, ["GET /api/kkb/v1/conversations"]);

    // A server that cannot be reached says nothing about the key: it is kept.
    globalThis.fetch = async () => {
      throw new TypeError("offline");
    };
    await assert.rejects(usableOwner(storage));
    assert.equal(store.get("kkb.owner.v1"), fresh);
  } finally {
    globalThis.fetch = original;
  }
});
