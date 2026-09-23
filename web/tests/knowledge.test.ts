import test from "node:test";
import assert from "node:assert/strict";
import {
  ApiError,
  CONVERSATION_SAVE_LIMIT,
  datasetRequestFromExport,
  describeDatasetSource,
  describeKnowledgeError,
  parseMonthlyRows,
} from "../lib/client";
import {
  datasetDetailSchema,
  knowledgeListSchema,
  noteHistorySchema,
} from "../lib/contracts";
import { forward, KNOWLEDGE_LIMIT, BODY_LIMIT } from "../lib/proxy";

const SAVED_FROM_ADDRESS = {
  kind: "address" as const,
  url: "https://example.org/veri/gelir.csv",
  read_at: "2026-09-23T10:00:00+00:00",
  sha256: "b".repeat(64),
  document: "belge_1",
  page: null,
  table: 1,
  sheet: null,
  period_column: "Ay",
  value_column: "Gelir (milyon TL)",
};

test("a saved version carries its source; an older server and a typed-in version need not", () => {
  const version = {
    version: 1,
    status: "active",
    observations: 3,
    content_sha256: "a".repeat(64),
    created_at: "2026-09-23T10:00:01+00:00",
  };
  const detail = (extra: object, entry: object = version) =>
    datasetDetailSchema.safeParse({
      api_version: 1,
      series: {
        series_id: "USER:gelir.v1",
        title: "Gelir",
        provider: "USER",
        origin: "user",
        status: "active",
        prepared: false,
        fetchable: false,
        unit: "TRY",
        scale: "million",
        frequency: "monthly",
        stock_flow: "flow",
        cumulative: "none",
        base_year: null,
        coverage_start: null,
        coverage_end: null,
        observations: 3,
        aliases: [],
        note: null,
        version: 1,
        slug: "gelir",
        updated_at: null,
        acquired_at: null,
      },
      source_kind: "upload",
      description: null,
      aggregation: "sum",
      observations: [],
      history: [entry],
      ...extra,
    });
  assert.ok(
    detail(
      { source: SAVED_FROM_ADDRESS },
      { ...version, source: SAVED_FROM_ADDRESS },
    ).success,
  );
  assert.ok(detail({ source: null }, { ...version, source: null }).success);
  assert.ok(detail({}).success); // an older server sends neither
  // Still strict: nothing the page does not know is taken in.
  assert.equal(
    detail({ source: { ...SAVED_FROM_ADDRESS, token: "x" } }).success,
    false,
  );
});

test("a source is said in words, and only an http(s) address becomes a link", () => {
  const said = describeDatasetSource(SAVED_FROM_ADDRESS);
  assert.equal(said.href, "https://example.org/veri/gelir.csv");
  assert.equal(said.origin, "https://example.org/veri/gelir.csv");
  assert.match(said.when ?? "", /^erişim /);
  assert.match(
    said.place ?? "",
    /belge_1 · tablo 1 · sütun “Gelir \(milyon TL\)”/,
  );
  assert.equal(
    describeDatasetSource({ ...SAVED_FROM_ADDRESS, url: "javascript:alert(1)" })
      .href,
    null,
  );
  const upload = describeDatasetSource({
    kind: "upload",
    document: "belge_2",
    read_at: "2026-09-23T10:00:00+00:00",
  });
  assert.equal(upload.href, null);
  assert.equal(upload.origin, "sohbette yüklenen belge (belge_2)");
  assert.match(upload.when ?? "", /^yükleme /);
});

test("what a conversation can keep is said plainly", () => {
  assert.match(CONVERSATION_SAVE_LIMIT, /aylık/);
  assert.match(CONVERSATION_SAVE_LIMIT, /tek bir değer sütunu/);
});

test("pasted monthly rows become month ends, and a bad line is named, not guessed", () => {
  const parsed = parseMonthlyRows(
    "2025-01;100\n2025-02-28, 110,5\n\n2024-02;\n2025-13;1\nOcak;5\n2025-03\t7",
  );
  assert.deepEqual(parsed.observations, [
    { period_end: "2025-01-31", value: 100 },
    { period_end: "2025-02-28", value: 110.5 },
    { period_end: "2024-02-29", value: null }, // leap year, and an empty value stays empty
    { period_end: "2025-03-31", value: 7 },
  ]);
  assert.deepEqual(parsed.rejected, [5, 6]);
});

const owner = "o".repeat(43);
function request(path: string, method = "GET", body?: string, headers = {}) {
  return new Request(`http://127.0.0.1:3000/api/kkb/${path}`, {
    method,
    headers: {
      host: "127.0.0.1:3000",
      origin: "http://127.0.0.1:3000",
      "content-type": "application/json",
      "x-kkb-owner-token": owner,
      ...headers,
    },
    body,
  });
}

test("knowledge routes pass only with the owner key and their own methods", async () => {
  const seen: string[] = [];
  const transport: typeof fetch = async (url, init) => {
    seen.push(
      `${init?.method} ${String(url).replace("http://127.0.0.1:8000/", "")}`,
    );
    assert.equal(new Headers(init?.headers).get("X-KKB-Owner-Token"), owner);
    return Response.json({ ok: true });
  };
  const allowed: [string, string][] = [
    ["v1/knowledge", "GET"],
    ["v1/knowledge/datasets/kart_harcamalari", "GET"],
    ["v1/knowledge/datasets", "POST"],
    ["v1/knowledge/datasets/kart_harcamalari/archive", "POST"],
    ["v1/knowledge/datasets/kart_harcamalari/restore", "POST"],
    ["v1/knowledge/series/EVDS:TP.KFE.TR/notes", "GET"],
    ["v1/knowledge/series/BDDK:selector:v1:abc/notes", "POST"],
    ["v1/knowledge/series/EVDS:TP.KFE.TR/values", "GET"],
  ];
  for (const [path, method] of allowed) {
    const response = await forward(
      request(path, method, method === "POST" ? "{}" : undefined),
      path.split("/"),
      transport,
    );
    assert.equal(response.status, 200, `${method} ${path}`);
  }
  assert.equal(seen.length, allowed.length);

  const refused: [string, string, Record<string, string>][] = [
    ["v1/knowledge", "POST", {}],
    ["v1/knowledge/datasets", "GET", {}],
    ["v1/knowledge/datasets/Kart", "GET", {}],
    ["v1/knowledge/datasets/kart_harcamalari/delete", "POST", {}],
    ["v1/knowledge/series/EVDS:TP.KFE.TR/values", "POST", {}],
    ["v1/knowledge/series/../notes", "GET", {}],
    ["v1/knowledge", "GET", { "x-kkb-owner-token": "" }],
  ];
  for (const [path, method, headers] of refused) {
    const response = await forward(
      request(path, method, method === "POST" ? "{}" : undefined, headers),
      path.split("/"),
      transport,
    );
    assert.equal(response.status, 404, `${method} ${path}`);
  }
  assert.equal(seen.length, allowed.length);
});

test("only the dataset route takes a body past the usual limit", async () => {
  const transport: typeof fetch = async () => Response.json({ ok: true });
  const large = JSON.stringify({ note: "a".repeat(BODY_LIMIT + 10) });
  const dataset = await forward(
    request("v1/knowledge/datasets", "POST", large),
    ["v1", "knowledge", "datasets"],
    transport,
  );
  assert.equal(dataset.status, 200);
  const note = await forward(
    request("v1/knowledge/series/EVDS:X/notes", "POST", large),
    ["v1", "knowledge", "series", "EVDS:X", "notes"],
    transport,
  );
  assert.equal(note.status, 413);
  const tooLarge = await forward(
    request(
      "v1/knowledge/datasets",
      "POST",
      JSON.stringify({ a: "a".repeat(KNOWLEDGE_LIMIT) }),
    ),
    ["v1", "knowledge", "datasets"],
    transport,
  );
  assert.equal(tooLarge.status, 413);
});

test("weekly rows keep the date as written and refuse one that is not a date", async () => {
  const { parseDatedRows } = await import("../lib/client");
  const parsed = parseDatedRows(
    "2026-09-04;10\n2026-09-11, 11,5\n2026-02-30;1\n2026-09;4\n2026-09-18;",
  );
  assert.deepEqual(parsed.observations, [
    { period_end: "2026-09-04", value: 10 },
    { period_end: "2026-09-11", value: 11.5 },
    { period_end: "2026-09-18", value: null },
  ]);
  assert.deepEqual(parsed.rejected, [3, 4]);
});

test("an exported dataset detail rebuilds the exact versioned save request", () => {
  const detail = {
    api_version: 1 as const,
    series: {
      series_id: "USER:haftalik.v2",
      title: "Haftalık seri",
      provider: "USER",
      origin: "user" as const,
      status: "active" as const,
      prepared: false,
      fetchable: false,
      unit: "TRY",
      scale: "million",
      frequency: "weekly",
      stock_flow: "flow",
      cumulative: "none",
      base_year: null,
      coverage_start: null,
      coverage_end: null,
      observations: 1,
      aliases: ["haftalık"],
      note: null,
      version: 2,
      slug: "haftalik",
      updated_at: null,
      acquired_at: null,
    },
    source_kind: "manual" as const,
    description: "Açıklama",
    aggregation: "sum",
    weekly_anchor: "monday",
    observations: [
      { period_start: "2026-01-05", period_end: "2026-01-11", value: 4 },
    ],
    history: [],
  };
  const request = datasetRequestFromExport(detail);
  assert.equal(request.slug, "haftalik");
  assert.equal(request.weekly_anchor, "monday");
  assert.equal(request.aggregation, "sum");
  assert.deepEqual(request.observations, [
    { period_end: "2026-01-11", value: 4 },
  ]);

  // A meaning this build does not know is refused by name, never coerced.
  assert.throws(
    () =>
      datasetRequestFromExport({
        ...detail,
        aggregation: "median",
      }),
    /aggregation_not_importable/,
  );
  assert.throws(
    () => datasetRequestFromExport({ ...detail, weekly_anchor: null }),
    /weekly_anchor_not_importable/,
  );
});

test("the listing says whether catalogue notes are open here; an older server need not", () => {
  const digest = "a".repeat(64);
  const listing = {
    api_version: 1,
    catalog_digest: digest,
    reviewed_digest: digest,
    series: [],
  };
  for (const catalog_editable of [true, false])
    assert.equal(
      knowledgeListSchema.parse({ ...listing, catalog_editable })
        .catalog_editable,
      catalog_editable,
    );
  // Absent on an older server; the page reads that as not editable.
  assert.equal(knowledgeListSchema.parse(listing).catalog_editable, undefined);
  assert.equal(
    knowledgeListSchema.safeParse({ ...listing, catalog_editable: "yes" })
      .success,
    false,
  );
});

test("a note version says whether this key wrote it, and never who did", () => {
  const version = {
    version: 1,
    archived: true,
    aliases: [],
    note: null,
    created_at: "2026-09-22T08:00:00+00:00",
  };
  const history = (entry: object) =>
    noteHistorySchema.safeParse({
      api_version: 1,
      series_id: "EVDS:TP.KFE.TR",
      history: [entry],
    }).success;
  for (const by_you of [true, false, null])
    assert.ok(history({ ...version, by_you }), String(by_you));
  assert.ok(history(version)); // an older server
  // Still strict: an author's owner id is nothing this page takes in.
  assert.equal(history({ ...version, author: "0".repeat(32) }), false);
});

test("a read-only catalogue is said as such, not as a refused local origin", () => {
  const text = describeKnowledgeError(new ApiError("catalog_read_only", 403));
  assert.match(text, /salt okunur/);
  assert.match(text, /--allow-catalog-edits/);
  assert.notEqual(text, describeKnowledgeError(new ApiError("forbidden", 403)));
});
