import test from "node:test";
import assert from "node:assert/strict";
import { cellSchema, resultSchema, type Result } from "../lib/contracts";
import { chartModel, legendName, toggleGroup } from "../lib/chart";

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
  month: number,
  value: number,
  unit = "TRY",
  scale = "million",
) {
  const end = new Date(Date.UTC(2021, month, 0)).toISOString().slice(0, 10);
  return cellSchema.parse({
    cell_id: (slot + 1).toString(16).padStart(32, "0"),
    slot: slot++,
    label,
    value,
    display: `${value} gösterim`,
    unit,
    scale,
    measure: unit === "percent" ? "rate" : "stock",
    period: {
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

test("chart plots canonical values per period with gaps and separate unit groups", () => {
  const model = chartModel(
    result([
      cell("balance", 3, 300.5),
      cell("balance", 1, 100.25),
      cell("rate", 1, 18.39, "percent", "one"),
      cell("rate", 2, 17.99, "percent", "one"),
      cell("rate", 3, 17.5, "percent", "one"),
      cell("balance month-over-month change", 2, -1.5),
      cell("balance month-over-month change", 3, 200.25),
    ]),
    null,
  )!;
  const balance = model.series.find((s) => s.name === "balance")!;
  assert.deepEqual(balance.x, ["2021-01-31", "2021-02-28", "2021-03-31"]);
  assert.deepEqual(balance.y, [100.25, null, 300.5]);
  // The tooltip names the whole period, not only the point's own day.
  assert.deepEqual(balance.hover, [
    "2021-01-01 – 2021-01-31 · 100.25 gösterim",
    "2021-02-01 – 2021-02-28 · değer yok",
    "2021-03-01 – 2021-03-31 · 300.5 gösterim",
  ]);
  assert.equal(model.groups.length, 2);
  assert.notEqual(
    balance.group,
    model.series.find((s) => s.name === "rate")!.group,
  );
  assert.equal(
    model.series.find((s) => s.name === "balance aylık değişim")!.hidden,
    true,
  );
  assert.equal(balance.hidden, false);
});

test("no chart for a single period or summary-only result, and labels stay plain", () => {
  assert.equal(chartModel(result([cell("balance", 1, 1)]), null), null);
  const model = chartModel(
    result([cell("<b>x</b>", 1, 1), cell("<b>x</b>", 2, 2)]),
    null,
  )!;
  assert.equal(model.series[0].name.includes("<"), false);
  const long = chartModel(
    result([cell("x".repeat(80), 1, 1), cell("x".repeat(80), 2, 2)]),
    null,
  )!.series[0];
  assert.equal(long.legend.length, 72);
  assert.equal(long.name.length, 80);
});

test("at most two unit groups are active and toggling is reversible", () => {
  assert.deepEqual(toggleGroup(["a", "b"], "c"), ["b", "c"]);
  assert.deepEqual(toggleGroup(["a", "b"], "a"), ["b"]);
  assert.deepEqual(toggleGroup([], "a"), ["a"]);
});

test("derived columns keep a distinguishing legend suffix", () => {
  const base =
    "BDDK Aylık Bülten konut kredisi bakiyesi, sektör, toplam (TP ve YP birlikte), milyon TL";
  const names = [
    base,
    `${base} aylık değişim`,
    `${base} reel, 2025-12 fiyatlarıyla (TÜFE genel endeksi)`,
  ];
  const legends = names.map((name) => legendName(name, names));
  assert.equal(new Set(legends).size, 3);
  assert.match(legends[1], /aylık değişim$/);
  assert.match(legends[2], /reel, 2025-12/);
  assert.ok(legends.every((legend) => legend.length <= 72));
});

test("a change column's suffix is read in Turkish, percent and lag included", async () => {
  const { seriesLabel } = await import("../lib/table");
  assert.equal(
    seriesLabel("balance % change (lag 1)", null),
    "balance yüzde değişim (önceki döneme göre)",
  );
  assert.equal(
    seriesLabel("balance change (lag 12)", null),
    "balance değişim (12 dönem öncesine göre)",
  );
});
