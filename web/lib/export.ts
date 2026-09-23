import type { Cell, Dataset, Result } from "./contracts";
import { arrange, seriesLabel, unitLabel, type TableRow } from "./table";

/**
 * Exports of a published result, built from the cells the browser already
 * received and validated. No new server route, no recomputation: an export is
 * the same verified table in another shape, and its file name carries the
 * result version so it can be matched to its trace later.
 */
export type CsvDialect = "standard" | "excel-tr";

const EVIDENCE_SCHEMA = "kkb-datatrio-evidence-v1";
/** The UTF-8 byte-order mark, written by code point so it stays visible here. */
export const BOM = String.fromCharCode(0xfeff);

/** A text field Excel would evaluate as a formula is written as text. */
function neutralized(text: string) {
  return /^[=+\-@\t\r]/.test(text) ? `'${text}` : text;
}

function field(text: string, separator: string) {
  return /["\r\n]/.test(text) || text.includes(separator)
    ? `"${text.replaceAll('"', '""')}"`
    : text;
}

function number(value: number, dialect: CsvDialect) {
  // Full precision, never the rounded display string: an export is data.
  const written = String(value);
  return dialect === "excel-tr" ? written.replace(".", ",") : written;
}

function lines(rows: string[][], dialect: CsvDialect) {
  const separator = dialect === "excel-tr" ? ";" : ",";
  const body = rows
    .map((row) => row.map((item) => field(item, separator)).join(separator))
    .join("\r\n");
  // A byte-order mark is how Excel knows the file is UTF-8 (ş, ğ, İ).
  return (dialect === "excel-tr" ? BOM : "") + body + "\r\n";
}

function heading(
  cell: Pick<Cell, "label" | "unit" | "scale">,
  dataset: Dataset | null,
  names: Record<string, string>,
) {
  const unit = unitLabel(cell.unit, cell.scale);
  return neutralized(
    `${seriesLabel(cell.label, dataset, names)}${unit ? ` (${unit})` : ""}`,
  );
}

/**
 * One row per period, one column per measure — the table as shown. A result
 * with no period table (a single comparison) exports its values as rows.
 */
export function tableCsv(
  result: Result,
  dataset: Dataset | null,
  dialect: CsvDialect,
  /**
   * What the reader is looking at, when that is narrower than the whole table:
   * the rows a search left on screen. Omitted, the whole published table is
   * written. Columns and proof are never narrowed by this: a file always says
   * which series and which period each number belongs to.
   */
  view?: { rows: TableRow[] },
) {
  const arranged = arrange(result.cells);
  const { columns, metrics } = arranged;
  const rows = view?.rows ?? arranged.rows;
  if (columns.length === 0) {
    return lines(
      [
        ["Ölçü", "Dönem başı", "Dönem sonu", "Değer", "Birim"],
        ...metrics.map((cell) => [
          neutralized(seriesLabel(cell.label, dataset, result.series_names)),
          cell.period?.start ?? "",
          cell.period?.end ?? "",
          number(cell.value, dialect),
          unitLabel(cell.unit, cell.scale),
        ]),
      ],
      dialect,
    );
  }
  return lines(
    [
      [
        "Dönem başı",
        "Dönem sonu",
        ...columns.map((column) =>
          heading(column, dataset, result.series_names),
        ),
      ],
      ...rows.map((row) => [
        row.period?.start ?? "",
        row.period?.end ?? "",
        // An empty cell stays empty: nothing is filled on the way out either.
        ...columns.map((column) => {
          const cell = row.values[column.key];
          return cell ? number(cell.value, dialect) : "";
        }),
      ]),
    ],
    dialect,
  );
}

/** Everything needed to check the table elsewhere: values, units, periods and proof. */
export function evidencePackage(
  result: Result,
  context: { question?: string; answer?: string; exportedAt?: Date } = {},
) {
  return JSON.stringify(
    {
      schema: EVIDENCE_SCHEMA,
      exported_at: (context.exportedAt ?? new Date()).toISOString(),
      question: context.question ?? null,
      answer: context.answer ?? null,
      result_ref: result.result_ref,
      version: result.version,
      kind: result.kind,
      cells: result.cells,
      proof: result.proof,
    },
    null,
    2,
  );
}

export function exportName(
  result: Result,
  extension: "csv" | "json",
  suffix = "",
) {
  return `kkb-analiz-${result.version.slice(0, 12)}${suffix}.${extension}`;
}

export function download(content: string, name: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.rel = "noopener";
  document.body.append(link);
  link.click();
  link.remove();
  // Revoke after the click has been handled, not before the download starts.
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
