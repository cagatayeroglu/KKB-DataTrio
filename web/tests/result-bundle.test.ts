import test from "node:test";
import assert from "node:assert/strict";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ResultTable } from "../components/result-table";
import { resultSchema } from "../lib/contracts";

const proof = {
  scope: "result",
  availability: "unavailable",
  gate: "accepted",
  steps: [],
  sources: [],
  warnings: [],
  limitations: [],
  unresolved_semantics: [],
  gaps: [],
};
function cell(month: number, value: number, label = "Faiz") {
  return {
    cell_id: month.toString(16).padStart(32, "0"),
    slot: month - 1,
    label,
    value,
    display: `${value.toLocaleString("tr-TR", { maximumFractionDigits: 4 })} yüzde`,
    unit: "percent",
    scale: "one",
    measure: "rate",
    period: {
      start: `2024-${String(month).padStart(2, "0")}-01`,
      end: `2024-${String(month).padStart(2, "0")}-28`,
      frequency: "monthly",
      weekly_anchor: null,
    },
    samples: null,
    lag: null,
  };
}
const summary = {
  result_ref: "c".repeat(32),
  version: "d".repeat(64),
  kind: "level",
  claim_kind: "analytical_value",
  published: true,
  cells: [cell(12, 50.9667, "Faiz mean")],
  proof,
};
const payload = {
  result_ref: "a".repeat(32),
  version: "b".repeat(64),
  kind: "series",
  claim_kind: "analytical_value",
  published: true,
  cells: Array.from({ length: 12 }, (_, i) => cell(i + 1, 47.6 + i)),
  proof,
  related: [summary],
};
test("primary monthly table and independent summary both render with their own proof", () => {
  const result = resultSchema.parse(payload);
  const html = renderToStaticMarkup(
    createElement(ResultTable, { result, dataset: null }),
  );
  assert.match(html, /47,6/);
  assert.match(html, /Faiz mean/);
  assert.match(html, /50,9667/);
  assert.equal(result.cells.length, 12);
  assert.equal(result.related.length, 1);
  assert.match(html, /Ek sonuç/);
  assert.equal((html.match(/Kanıt paketi/g) ?? []).length, 2);
});
test("nested bundles and malformed companion versions are rejected", () => {
  assert.equal(
    resultSchema.safeParse({
      ...payload,
      related: [{ ...summary, related: [summary] }],
    }).success,
    false,
  );
  assert.equal(
    resultSchema.safeParse({
      ...payload,
      related: [{ ...summary, version: "invalid" }],
    }).success,
    false,
  );
});
