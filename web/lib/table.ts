import type { Cell, Dataset } from "./contracts";
export type TableRow = {
  key: string;
  period: Cell["period"];
  values: Record<string, Cell>;
};
export type TableColumn = {
  key: string;
  label: string;
  unit: string | null;
  scale: Cell["scale"];
  measure: Cell["measure"];
};
export function arrange(cells: Cell[]) {
  const columns = new Map<string, TableColumn>();
  const rows: TableRow[] = [];
  const metrics: Cell[] = [];
  const columnKey = (cell: Cell) =>
    JSON.stringify([cell.label, cell.unit, cell.scale, cell.measure]);
  const periodsByColumn = new Map<string, Set<string>>();
  for (const cell of cells) {
    if (!cell.period) continue;
    const key = columnKey(cell);
    const periods = periodsByColumn.get(key) ?? new Set<string>();
    periods.add(JSON.stringify(cell.period));
    periodsByColumn.set(key, periods);
  }
  const timeline = new Set(
    [...periodsByColumn.values()]
      .filter((periods) => periods.size > 1)
      .flatMap((periods) => [...periods]),
  );
  for (const cell of cells) {
    // Single interval summaries stay separate from a repeated-period table.
    // This is layout by recorded intervals, never a financial classification.
    if (
      !cell.period ||
      (timeline.size > 0 &&
        periodsByColumn.get(columnKey(cell))?.size === 1 &&
        !timeline.has(JSON.stringify(cell.period)))
    ) {
      metrics.push(cell);
      continue;
    }
    const key = JSON.stringify([
      cell.label,
      cell.unit,
      cell.scale,
      cell.measure,
    ]);
    columns.set(key, {
      key,
      label: cell.label,
      unit: cell.unit,
      scale: cell.scale,
      measure: cell.measure,
    });
    const periodKey = JSON.stringify(cell.period);
    // Duplicate labels/periods occupy distinct rows; no cell is averaged or overwritten.
    let row = rows.find(
      (r) => r.key.startsWith(periodKey + "|") && !r.values[key],
    );
    if (!row) {
      row = {
        key: periodKey + "|" + rows.length,
        period: cell.period,
        values: {},
      };
      rows.push(row);
    }
    row.values[key] = cell;
  }
  return { columns: [...columns.values()], rows, metrics };
}
const scales: Record<string, string> = {
  unknown: "ölçek belirsiz",
  one: "",
  thousand: "bin",
  million: "milyon",
  billion: "milyar",
};
export function unitLabel(unit: string | null, scale: string) {
  const units: Record<string, string> = {
    TRY: "TL",
    percent: "%",
    "percentage point": "yüzde puan",
    dimensionless: "birimsiz",
    index: "endeks",
  };
  return [
    scales[scale] ?? "ölçek belirsiz",
    unit === null ? "birim belirsiz" : (units[unit] ?? unit),
  ]
    .filter(Boolean)
    .join(" ");
}
export function displayValue(cell: Cell) {
  // A unitless count needs no English suffix. Keep the canonical numeric value.
  if (cell.unit === "dimensionless" && cell.scale === "one")
    return String(cell.value);
  return cell.display ?? String(cell.value);
}
export function preparedTitle(title: string) {
  // Translate known presentation suffixes only; retain source scope verbatim.
  return title
    .replace(/; percent, weekly, rate$/, "; yüzde, haftalık faiz oranı")
    .replace(/; index, monthly, index$/, "; aylık endeks");
}
export function seriesLabel(
  label: string,
  dataset: Dataset | null,
  names: Record<string, string> = {},
) {
  let result = label;
  // The result's own names first: the startup dataset lists the seed pool only, so a
  // province series fetched during the turn, a series the reader saved, or a weekly
  // bulletin row reached the legend as "BDDK:selector:v1:001a584..." (live 2026-09-21).
  const known = [
    ...Object.entries(names).map(([id, title]) => ({ series_id: id, title })),
    ...(dataset?.series ?? []),
  ];
  for (const series of known.sort(
    (a, b) => b.series_id.length - a.series_id.length,
  ))
    result = result.replaceAll(series.series_id, preparedTitle(series.title));
  result = result
    .replace(
      / monthly (sum|average|first|last|min|max) \((by_end|by_majority)\)/g,
      (_, how: string, week: string) =>
        ` ${week === "by_end" ? "hafta bitişine" : "haftanın çoğunluğuna"} göre aylık ${
          {
            sum: "toplam",
            average: "ortalama",
            first: "ilk değer",
            last: "son değer",
            min: "en küçük",
            max: "en büyük",
          }[how]
        }`,
    )
    .replaceAll("month-over-month change", "aylık değişim")
    // table_transform change: "<column> % change (lag 1)" / "<column> change (lag 12)".
    .replace(
      / (% )?change \(lag (\d+)\)/g,
      (_, percent: string | undefined, lag: string) =>
        ` ${percent ? "yüzde " : ""}değişim (${lag === "1" ? "önceki döneme göre" : `${lag} dönem öncesine göre`})`,
    )
    .replace(/ real, (\d{4}-\d{2}) prices /g, " reel, $1 fiyatlarıyla ");
  const comparison = result.match(/^table comparison ([a-f0-9]{12}): (.+)$/);
  const comparisonLabels: Record<string, string> = {
    "complete monthly transitions": "Eksiksiz aylık geçişler",
    "transitions excluded for missing observations":
      "Eksik veri nedeniyle dışlanan geçişler",
    "transitions meeting the condition": "Koşulu sağlayan geçişler",
    "eligible transitions matching the driver direction":
      "Açıklayıcı serinin yönüne uyan geçişler",
    "eligible transitions matching the target direction":
      "Hedef serinin yönüne uyan geçişler",
    "eligible transitions matching both directions":
      "İki serinin yönüne de uyan geçişler",
  };
  if (comparison && comparisonLabels[comparison[2]])
    return `${comparisonLabels[comparison[2]]} · ${comparison[1]}`;
  if (result === "consecutive monthly transitions compared")
    return "Karşılaştırılan aylık geçişler";
  result = result
    .replace(
      /^transitions where (.+) fell and (.+) did not rise$/,
      "$1 azalırken $2 artmayan dönemler",
    )
    .replace(
      /^transitions where (.+) fell and (.+) rose$/,
      "$1 azalırken $2 artan dönemler",
    )
    .replace(/^transitions where (.+) fell$/, "$1 azalan dönemler");
  return result;
}
export function periodLabel(period: Cell["period"]) {
  if (!period) return "Dönem belirtilmedi";
  // Formatting only; preserve the full interval in detail and never infer frequency.
  if (
    period.frequency === "monthly" &&
    period.start.slice(0, 7) === period.end.slice(0, 7)
  )
    return new Intl.DateTimeFormat("tr-TR", {
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    }).format(new Date(period.end + "T00:00:00Z"));
  return period.start === period.end
    ? period.end
    : `${period.start} – ${period.end}`;
}
