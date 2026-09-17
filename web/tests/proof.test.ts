import test from "node:test";
import assert from "node:assert/strict";
import { proofSchema, resultSchema } from "../lib/contracts";
import {
  documentLocation,
  documentName,
  documentOrigin,
  gapText,
  orderedSteps,
  proofHeadline,
  sourceCoverage,
  sourceName,
  sourceOrigin,
  sourceSemantics,
  stepCheck,
  stepInputs,
  stepTitle,
} from "../lib/proof";

const version = "b".repeat(64);
const source = {
  series_id: "BDDK:selector:v1:" + "f".repeat(64),
  title: "Tüketici Kredileri - Konut",
  binding: "execution_snapshot",
  dataset_sha256: "d".repeat(64),
  dataset_source_type: "internal-dataset-manifest",
  unit: "TRY",
  scale: "million",
  frequency: "monthly",
  measure: "stock",
  cumulative: "none",
  aggregation: "last",
  catalog_status: "unknown",
  observations: 3,
  missing_values: 0,
  first_period: "2026-04-01",
  last_period: "2026-06-30",
  parser: "bddk-monthly-json-v1",
  normalization: "native-monthly;json-number-to-double",
  raw_responses: 3,
  raw_response_types: ["http-json"],
  hosts: ["www.bddk.org.tr"],
  first_retrieved: "2026-09-14T03:42:26.845711+03:00",
  last_retrieved: "2026-09-14T03:42:28.143727+03:00",
};
function step(overrides: Record<string, unknown> = {}) {
  return {
    producer: "table_transform",
    operation: "table_transform_add_series",
    kind: "series",
    method: null,
    execution: "verified",
    result_version: version,
    workspace_name: null,
    coverage: null,
    samples: null,
    inputs: [
      { kind: "result", index: 1 },
      { kind: "series", index: 0 },
    ],
    ...overrides,
  };
}
const proof = {
  scope: "result",
  availability: "partial",
  gate: "accepted",
  steps: [
    step(),
    step({
      producer: "lakehouse",
      operation: "lakehouse_query",
      result_version: "c".repeat(64),
      workspace_name: "analiz_1",
      inputs: [{ kind: "series", index: 0 }],
    }),
  ],
  sources: [source],
  warnings: ["No external cross-check was performed"],
  limitations: [],
  unresolved_semantics: [],
  gaps: ["source_lineage_missing"],
};

test("recorded proof chain reads from source to this result", () => {
  const parsed = proofSchema.parse(proof);
  const ordered = orderedSteps(parsed);
  assert.deepEqual(
    ordered.map((item) => item.index),
    [1, 0],
  );
  assert.equal(stepTitle(ordered[0].step), "Hazır veri tablosundan okuma");
  assert.deepEqual(stepInputs(parsed, parsed.steps[0]), [
    "analiz_1 tablosu",
    "Tüketici Kredileri - Konut",
  ]);
  assert.equal(
    sourceOrigin(parsed.sources[0]),
    "3 ham yanıt (www.bddk.org.tr), 2026-09-14 tarihinde alındı",
  );
  assert.equal(
    sourceCoverage(parsed.sources[0]),
    "2026-04-01 – 2026-06-30, 3 gözlem okundu, 0 boş",
  );
  assert.equal(
    sourceSemantics(parsed.sources[0]),
    "milyon TL · aylık · stok · kümülatif değil · katalog arşiv durumu bilinmiyor",
  );
  assert.equal(
    sourceName(parsed.sources[0], null),
    "Tüketici Kredileri - Konut",
  );
  assert.equal(proofHeadline(parsed), "Kaynaktan sonuca kayıtlı zincir kısmi");
  assert.match(gapText("source_lineage_missing"), /soy kaydı yok/);
  assert.equal(
    sourceOrigin({ ...parsed.sources[0], raw_responses: 0, hosts: [] }),
    "Ham kaynak yanıtlarına uzanan kayıt yok",
  );
});

test("proof schema refuses fabricated, inconsistent or leaking chains", () => {
  const invalid = [
    { ...proof, availability: "available" },
    { ...proof, availability: "unavailable" },
    { ...proof, steps: [step({ execution: "not_verified" })] },
    { ...proof, steps: [step({ inputs: [{ kind: "result", index: 5 }] })] },
    { ...proof, sources: [{ ...source, locator: "https://x/y?key=1" }] },
    { ...proof, sources: [{ ...source, parser: "<script>" }] },
    { ...proof, gaps: ["made_up"] },
    { ...proof, extra: true },
  ];
  for (const item of invalid) {
    assert.equal(
      proofSchema.safeParse(item).success,
      false,
      JSON.stringify(item).slice(0, 80),
    );
  }
});

test("a result cannot carry a proof for another version", () => {
  const result = {
    result_ref: "a".repeat(32),
    version,
    kind: "series",
    claim_kind: "analytical_value",
    published: true,
    cells: [],
    proof,
  };
  assert.equal(resultSchema.safeParse(result).success, true);
  assert.equal(
    resultSchema.safeParse({ ...result, version: "e".repeat(64) }).success,
    false,
  );
  assert.equal(
    resultSchema.safeParse({ ...result, proof_graph: "unavailable" }).success,
    false,
  );
});

const document = {
  source_type: "web_url",
  document_format: "pdf",
  host: "www.borsaistanbul.com",
  content_sha256: "e".repeat(64),
  retrieved_at: "2026-09-17T10:15:00+03:00",
  page: 2,
  table: 1,
  row: 3,
  column: 4,
  sheet_selected: false,
};
const documentProof = {
  ...proof,
  availability: "available",
  steps: [
    step({
      producer: "web_url",
      operation: null,
      kind: "level",
      method: "document_cell",
      inputs: [{ kind: "document", index: 0 }],
    }),
  ],
  sources: [],
  documents: [document],
  gaps: [],
};

test("a literal cell proof names its document without the address path", () => {
  const parsed = proofSchema.parse(documentProof);
  assert.equal(
    stepTitle(parsed.steps[0]),
    "Sorudaki adresteki belgeden hücre okuma",
  );
  assert.deepEqual(stepInputs(parsed, parsed.steps[0]), [
    "PDF belgesi (www.borsaistanbul.com)",
  ]);
  assert.match(stepCheck(parsed.steps[0]), /hücre/);
  assert.equal(
    documentOrigin(parsed.documents[0]),
    "Sorudaki adresten güvenli indirme, 2026-09-17 tarihinde okundu",
  );
  assert.equal(
    documentLocation(parsed.documents[0]),
    "sayfa 2 · tablo 1 · satır 3 · sütun 4",
  );
  assert.equal(
    documentName({
      ...parsed.documents[0],
      host: null,
      document_format: "xlsx",
    }),
    "Excel belgesi",
  );
  assert.equal(proofSchema.parse(proof).documents.length, 0);
  assert.equal(
    documentLocation({
      ...parsed.documents[0],
      document_format: "csv",
      page: null,
      row: null,
      column: 2,
      values_read: 3,
    }),
    "tablo 1 · sütun 2 · 3 değer okundu",
  );
  const uploaded = {
    ...parsed.documents[0],
    source_type: "upload" as const,
    host: null,
  };
  assert.equal(documentName(uploaded), "Yüklenen PDF belgesi");
  assert.equal(
    documentOrigin(uploaded),
    "Bu soruya eklenen yükleme, 2026-09-17 tarihinde kabul edildi",
  );
});

test("document proof schema refuses dangling, leaking or foreign documents", () => {
  const invalid = [
    { ...documentProof, documents: [] },
    { ...documentProof, availability: "unavailable", steps: [] },
    {
      ...documentProof,
      documents: [{ ...document, url: "https://x/y?token=1" }],
    },
    { ...documentProof, documents: [{ ...document, cell_text: "1.234,56" }] },
    {
      ...documentProof,
      documents: [{ ...document, source_type: "lakehouse" }],
    },
    { ...documentProof, documents: Array(5).fill(document) },
    { ...documentProof, documents: [{ ...document, values_read: -1 }] },
  ];
  for (const item of invalid) {
    assert.equal(
      proofSchema.safeParse(item).success,
      false,
      JSON.stringify(item).slice(0, 80),
    );
  }
});
