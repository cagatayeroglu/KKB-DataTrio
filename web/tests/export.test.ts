import test from "node:test";
import assert from "node:assert/strict";
import { cellSchema, resultSchema, type Result } from "../lib/contracts";
import { BOM, evidencePackage, exportName, tableCsv } from "../lib/export";

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
let slot = 0;
function cell(
  label: string,
  month: number | null,
  value: number,
  unit = "TRY",
) {
  const end =
    month === null
      ? null
      : new Date(Date.UTC(2021, month, 0)).toISOString().slice(0, 10);
  return cellSchema.parse({
    cell_id: (slot + 1).toString(16).padStart(32, "0"),
    slot: slot++,
    label,
    value,
    display: `${value} gösterim`,
    unit,
    scale: unit === "TRY" ? "million" : "one",
    measure: unit === "percent" ? "rate" : "stock",
    period:
      month === null
        ? null
        : {
            start: `2021-${String(month).padStart(2, "0")}-01`,
            end,
            frequency: "monthly",
            weekly_anchor: null,
          },
    samples: null,
    lag: null,
  });
}
function result(cells: ReturnType<typeof cell>[]): Result {
  return resultSchema.parse({
    result_ref: "a".repeat(32),
    version: "b".repeat(64),
    kind: "series",
    claim_kind: "analytical_value",
    published: true,
    cells,
    proof,
  });
}

const table = () =>
  result([
    cell("balance", 1, 100.25),
    cell("balance", 3, 300.5),
    cell("rate", 1, 18.39, "percent"),
    cell("rate", 2, 17.99, "percent"),
    cell("rate", 3, 17.5, "percent"),
  ]);

test("standard CSV is the table as shown, full precision, gaps left empty", () => {
  const csv = tableCsv(table(), null, "standard");
  assert.equal(
    csv,
    [
      "Dönem başı,Dönem sonu,balance (milyon TL),rate (%)",
      "2021-01-01,2021-01-31,100.25,18.39",
      "2021-03-01,2021-03-31,300.5,17.5",
      "2021-02-01,2021-02-28,,17.99",
      "",
    ].join("\r\n"),
  );
  assert.ok(!csv.startsWith(BOM));
});

test("the Turkish Excel dialect uses semicolons, decimal commas and a UTF-8 mark", () => {
  const csv = tableCsv(table(), null, "excel-tr");
  assert.ok(
    csv.startsWith(
      BOM + "Dönem başı;Dönem sonu;balance (milyon TL);rate (%)\r\n",
    ),
  );
  assert.ok(csv.includes("2021-01-01;2021-01-31;100,25;18,39\r\n"));
});

test("a label that would run as a spreadsheet formula is written as text", () => {
  const csv = tableCsv(
    result([cell('=HYPERLINK("x")', 1, 1), cell('=HYPERLINK("x")', 2, 2)]),
    null,
    "standard",
  );
  const header = csv.split("\r\n")[0];
  assert.equal(
    header,
    'Dönem başı,Dönem sonu,"\'=HYPERLINK(""x"") (milyon TL)"',
  );
  // A negative number is data, not a formula, and is not altered.
  const negative = tableCsv(
    result([cell("x", 1, -5), cell("x", 2, -6)]),
    null,
    "standard",
  );
  assert.ok(negative.includes(",-5\r\n"));
});

test("a result without a period table exports its values as rows", () => {
  const csv = tableCsv(result([cell("change", null, 50)]), null, "standard");
  assert.equal(
    csv,
    [
      "Ölçü,Dönem başı,Dönem sonu,Değer,Birim",
      "change,,,50,milyon TL",
      "",
    ].join("\r\n"),
  );
});

test("the evidence package carries the version, every cell and the proof", () => {
  const published = table();
  const exported = JSON.parse(
    evidencePackage(published, {
      question: "Soru",
      answer: "Cevap",
      exportedAt: new Date("2026-09-18T00:00:00Z"),
    }),
  );
  assert.equal(exported.schema, "kkb-datatrio-evidence-v1");
  assert.equal(exported.version, "b".repeat(64));
  assert.equal(exported.cells.length, 5);
  assert.deepEqual(exported.proof, published.proof);
  assert.equal(exported.question, "Soru");
  assert.equal(exported.exported_at, "2026-09-18T00:00:00.000Z");
});

test("file names carry the result version so an export can be matched to its trace", () => {
  assert.equal(
    exportName(table(), "csv", "-excel"),
    "kkb-analiz-bbbbbbbbbbbb-excel.csv",
  );
});
