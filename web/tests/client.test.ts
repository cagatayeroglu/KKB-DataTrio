import test from "node:test";
import assert from "node:assert/strict";
import {
  admit,
  admissionRejection,
  draftRequest,
  draftWorkspaceRequest,
  publishedResult,
  restoredSelection,
  readTurn,
  loadSession,
  saveSession,
  validQuestion,
  describeError,
  documentMediaType,
  uploadDocument,
  ApiError,
} from "../lib/client";
import { cellSchema, turnSchema, type Saved } from "../lib/contracts";
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
test("only accepted completed publications can ground a new request", () => {
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

test("workspace continuation intent reaches the browser request body", async () => {
  const abstainedTurn = turnSchema.parse({
    ...turn,
    state: "completed",
    answer: {
      status: "abstained",
      text: "Seri seçimi net değil.",
      omitted_claims: 0,
      notices: [],
      result: null,
    },
  });

  assert.equal(publishedResult(abstainedTurn), undefined);
  const cases = [
    {
      entry: draftWorkspaceRequest("BDDK verisini kullan", true, abstainedTurn),
      expected: { is_continuation: true, selected_result_id: undefined },
    },
    {
      entry: draftWorkspaceRequest(
        "Yeni soru: 2026 yılı enflasyonu",
        false,
        abstainedTurn,
      ),
      expected: { is_continuation: false, selected_result_id: undefined },
    },
    {
      entry: draftWorkspaceRequest("Bu tabloya TÜFE ekle", true, completed()),
      expected: { is_continuation: true, selected_result_id: "a".repeat(32) },
    },
    {
      entry: draftWorkspaceRequest("Bağımsız soru", false, completed()),
      expected: { is_continuation: false, selected_result_id: undefined },
    },
    {
      entry: draftWorkspaceRequest("İlk bağımsız soru", true),
      expected: { is_continuation: false, selected_result_id: undefined },
    },
  ];
  const old = globalThis.fetch;
  const bodies: Record<string, unknown>[] = [];
  globalThis.fetch = async (_url, init) => {
    bodies.push(JSON.parse(String(init?.body)));
    return Response.json({ ...turn, request_id: bodies.at(-1)?.request_id });
  };
  try {
    for (const { entry } of cases) await admit({ ...saved, turns: [entry] }, 0);
  } finally {
    globalThis.fetch = old;
  }
  cases.forEach(({ expected }, index) => {
    assert.equal(bodies[index].is_continuation, expected.is_continuation);
    assert.equal(bodies[index].selected_result_id, expected.selected_result_id);
  });
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
  for (const name of ["makro.xlsm", "resim.png", "csv", "arsiv.csv.zip"])
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
