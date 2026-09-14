import test from "node:test";
import assert from "node:assert/strict";
import { proofSchema, resultSchema } from "../lib/contracts";
import {
  gapText,
  orderedSteps,
  proofHeadline,
  sourceCoverage,
  sourceOrigin,
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
  catalog_status: "consistent",
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
