"use client";
import { useMemo, useState } from "react";
import {
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";
import {
  ChevronLeft,
  ChevronRight,
  Search,
  X,
  Fingerprint,
  Table2,
  CircleHelp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ProofChain } from "@/components/proof-chain";
import {
  arrange,
  displayValue,
  periodLabel,
  seriesLabel,
  unitLabel,
  type TableRow,
} from "@/lib/table";
import type { Cell, Dataset, Result } from "@/lib/contracts";

export function ResultTable({
  result,
  dataset,
}: {
  result: Result;
  dataset: Dataset | null;
}) {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Cell | null>(null);
  const arranged = useMemo(() => arrange(result.cells), [result]);
  const columns = useMemo<ColumnDef<TableRow>[]>(
    () => [
      {
        id: "period",
        header: "Dönem",
        cell: ({ row }) => (
          <span
            className="period-cell"
            title={`${row.original.period?.start} – ${row.original.period?.end}`}
          >
            {periodLabel(row.original.period)}
          </span>
        ),
      },
      ...arranged.columns.map((column) => ({
        id: column.key,
        header: () => (
          <div className="column-title">
            <span title={seriesLabel(column.label, dataset)}>
              {seriesLabel(column.label, dataset)}
            </span>
            <small>{unitLabel(column.unit, column.scale)}</small>
          </div>
        ),
        cell: ({ row }: { row: { original: TableRow } }) => {
          const cell = row.original.values[column.key];
          return cell ? (
            <button
              className={`value-cell ${selected?.cell_id === cell.cell_id ? "selected" : ""}`}
              onClick={() => setSelected(cell)}
              title="Hücrenin kayıtlı ayrıntısını incele"
            >
              {displayValue(cell)}
            </button>
          ) : (
            <span
              className="missing-cell"
              title="Bu dönemde bu ölçü için yayımlanmış hücre yok"
            >
              —
            </span>
          );
        },
      })),
    ],
    [arranged.columns, dataset, selected],
  );
  const filtered = useMemo(
    () =>
      arranged.rows.filter(
        (row) =>
          !query ||
          [
            periodLabel(row.period),
            row.period?.start,
            row.period?.end,
            ...Object.values(row.values).map(displayValue),
          ]
            .join(" ")
            .toLocaleLowerCase("tr")
            .includes(query.toLocaleLowerCase("tr")),
      ),
    [arranged.rows, query],
  );
  const table = useReactTable({
    data: filtered,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 12 } },
  });
  return (
    <>
      <div className="table-tools">
        <span>
          <Table2 size={15} />
          {result.cells.length} kayıtlı değer
        </span>
        <label className="table-search">
          <Search size={15} />
          <input
            aria-label="Tabloda ara"
            value={query}
            placeholder="Dönem veya değer ara"
            onChange={(e) => {
              setQuery(e.target.value);
              table.setPageIndex(0);
            }}
          />
        </label>
      </div>
      {arranged.metrics.length > 0 && (
        <div className="metric-strip">
          {arranged.metrics.map((cell) => (
            <button
              key={cell.cell_id}
              onClick={() => setSelected(cell)}
              className="metric-item"
            >
              <span title={seriesLabel(cell.label, dataset)}>
                {seriesLabel(cell.label, dataset)}
              </span>
              <strong>{displayValue(cell)}</strong>
              <small>{unitLabel(cell.unit, cell.scale)}</small>
              {cell.period && (
                <small className="metric-period">
                  {periodLabel(cell.period)}
                </small>
              )}
            </button>
          ))}
        </div>
      )}
      {arranged.rows.length > 0 && (
        <>
          <div className="table-scroll">
            <table className="analysis-table">
              <thead>
                {table.getHeaderGroups().map((group) => (
                  <tr key={group.id}>
                    {group.headers.map((header) => (
                      <th key={header.id}>
                        {flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody>
                {table.getRowModel().rows.map((row) => (
                  <tr key={row.id}>
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id}>
                        {flexRender(
                          cell.column.columnDef.cell,
                          cell.getContext(),
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {!filtered.length && (
              <p className="no-match">Bu aramayla eşleşen satır bulunamadı.</p>
            )}
          </div>
          <div className="table-footer">
            <span>
              {filtered.length} satır · {arranged.columns.length} ölçü{" "}
              <span className="muted">/ sayfada 12 satır</span>
            </span>
            <div>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Önceki sayfa"
                disabled={!table.getCanPreviousPage()}
                onClick={() => table.previousPage()}
              >
                <ChevronLeft size={17} />
              </Button>
              <span>
                {table.getState().pagination.pageIndex + 1} /{" "}
                {Math.max(1, table.getPageCount())}
              </span>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Sonraki sayfa"
                disabled={!table.getCanNextPage()}
                onClick={() => table.nextPage()}
              >
                <ChevronRight size={17} />
              </Button>
            </div>
          </div>
        </>
      )}
      <div className="evidence-note">
        <CircleHelp size={16} />
        <span>
          Bir değere tıklayarak birimini, dönemini ve kaynaktan bu sonuca uzanan
          kayıtlı kanıt zincirini incele.
        </span>
      </div>
      {selected && (
        <section className="cell-detail" aria-label="Hücre ayrıntısı">
          <div className="detail-heading">
            <span>
              <Fingerprint size={17} /> Kayıtlı hücre
            </span>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Hücre ayrıntısını kapat"
              onClick={() => setSelected(null)}
            >
              <X size={17} />
            </Button>
          </div>
          <h3>{seriesLabel(selected.label, dataset)}</h3>
          <dl>
            <div>
              <dt>Değer</dt>
              <dd>{displayValue(selected)}</dd>
            </div>
            <div>
              <dt>Birim / ölçek</dt>
              <dd>{unitLabel(selected.unit, selected.scale)}</dd>
            </div>
            <div>
              <dt>Dönem</dt>
              <dd>
                {selected.period
                  ? `${selected.period.start} → ${selected.period.end}`
                  : "Belirtilmedi"}
              </dd>
            </div>
            <div>
              <dt>Ölçü türü</dt>
              <dd>
                {
                  {
                    unknown: "Belirsiz",
                    stock: "Stok",
                    flow: "Akım",
                    rate: "Oran",
                    index: "Endeks",
                  }[selected.measure]
                }
              </dd>
            </div>
            {selected.samples && (
              <div>
                <dt>Gözlemler</dt>
                <dd>
                  {selected.samples.used} kullanılan ·{" "}
                  {selected.samples.missing} eksik · {selected.samples.excluded}{" "}
                  dışlanan
                </dd>
              </div>
            )}
            <div>
              <dt>Gecikme</dt>
              <dd>{selected.lag ?? "Belirtilmedi"}</dd>
            </div>
            <div>
              <dt>Hücre kimliği</dt>
              <dd className="mono">{selected.cell_id}</dd>
            </div>
            <div>
              <dt>Sonuç sürümü</dt>
              <dd className="mono">{result.version}</dd>
            </div>
          </dl>
          <ProofChain proof={result.proof} dataset={dataset} />
        </section>
      )}
    </>
  );
}
