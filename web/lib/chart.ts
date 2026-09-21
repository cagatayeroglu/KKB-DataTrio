import type { Dataset, Result } from "./contracts";
import { arrange, displayValue, seriesLabel, unitLabel } from "./table";

/** One plotted column: canonical values only, never recomputed in the browser. */
export type ChartSeries = {
  key: string;
  name: string;
  legend: string;
  group: string;
  x: string[];
  y: (number | null)[];
  hover: string[];
  hidden: boolean;
};
export type ChartModel = {
  groups: { key: string; label: string }[];
  series: ChartSeries[];
};

const LEGEND = 72;

// Plotly interprets a small HTML subset in trace names; labels stay plain text.
function plain(text: string) {
  return text.replace(/[<>]/g, (c) => (c === "<" ? "‹" : "›"));
}

/**
 * Timeline columns of a published result, grouped by unit and scale so that
 * amounts, rates and indices never share an axis. Missing periods stay null
 * (a visible gap); month-over-month change columns start hidden in the legend.
 */
export function chartModel(
  result: Result,
  dataset: Dataset | null,
): ChartModel | null {
  const table = arrange(result.cells);
  const rows = [...table.rows]
    .filter((row) => row.period)
    .sort(
      (a, b) =>
        a.period!.start.localeCompare(b.period!.start) ||
        a.period!.end.localeCompare(b.period!.end),
    );
  if (rows.length < 2 || !table.columns.length) return null;
  // A column holding one value is a point, not a line, and a result made only of such
  // columns is not a chart: a breakpoint result is "breakpoints found = 2" and one shift
  // per break, each at a period of its own, and it was drawn as three lone markers while
  // the series the reader wanted to see the breaks in was not in that result at all
  // (live 2026-09-21). Beside a real column a single value still shows; alone, nothing is
  // drawn, because a chart of three unrelated points says something untrue.
  if (
    !table.columns.some(
      (column) =>
        rows.filter((row) => row.values[column.key] !== undefined).length > 1,
    )
  )
    return null;
  const groups = new Map<string, string>();
  const series: ChartSeries[] = table.columns.map((column) => {
    const group = JSON.stringify([column.unit, column.scale]);
    if (!groups.has(group))
      groups.set(group, plain(unitLabel(column.unit, column.scale)));
    const name = plain(seriesLabel(column.label, dataset, result.series_names));
    return {
      key: column.key,
      name,
      legend: name,
      group,
      x: rows.map((row) => row.period!.end),
      y: rows.map((row) => row.values[column.key]?.value ?? null),
      // The whole period, then the value: a point sits at the period's end, so a
      // monthly point read as "2021-03" alone and a daily one said nothing about
      // the range it stands for (finding DN-6.6).
      hover: rows.map((row) => {
        const cell = row.values[column.key];
        const shown = cell ? plain(displayValue(cell)) : "değer yok";
        const period = row.period!;
        return period.start === period.end
          ? `${period.end} · ${shown}`
          : `${period.start} – ${period.end} · ${shown}`;
      }),
      hidden: column.label.includes("month-over-month change"),
    };
  });
  const names = series.map((item) => item.name);
  for (const item of series) item.legend = legendName(item.name, names);
  return {
    groups: [...groups].map(([key, label]) => ({ key, label })),
    series,
  };
}

function clip(text: string, length: number) {
  return text.length > length ? `${text.slice(0, length - 1)}…` : text;
}

/**
 * Short legend text. A derived column (a base name plus a suffix such as
 * "aylık değişim" or "reel, 2025-12 fiyatlarıyla") keeps its distinguishing
 * suffix; the full name is always shown on hover.
 */
export function legendName(name: string, names: string[]) {
  const base = names
    .filter((other) => other !== name && name.startsWith(other))
    .sort((a, b) => b.length - a.length)[0];
  if (!base) return clip(name, LEGEND);
  return `${clip(base, 36)} ${clip(name.slice(base.length).trim(), LEGEND - 37)}`;
}

/** At most two unit groups share a chart: the first on the left axis, the second on the right. */
export function toggleGroup(active: string[], group: string) {
  if (active.includes(group)) return active.filter((key) => key !== group);
  return [...active, group].slice(-2);
}
