"use client";
import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import { LineChart } from "lucide-react";
import type { Dataset, Result } from "@/lib/contracts";
import { chartModel, toggleGroup } from "@/lib/chart";

// Client-only: plotly touches the DOM on import. The minified bundle is bound
// through the factory so the full source build is never shipped.
const Plot = dynamic(
  async () => {
    const [{ default: createPlotlyComponent }, plotly] = await Promise.all([
      import("react-plotly.js/factory"),
      import("plotly.js"),
    ]);
    return createPlotlyComponent(plotly.default ?? plotly);
  },
  {
    ssr: false,
    loading: () => <p className="chart-loading">Grafik hazırlanıyor…</p>,
  },
);

const COLORS = ["#2f7a4b", "#3b6fb6", "#b7792f", "#8a4fa3", "#b04a4a"];

export function ResultChart({
  result,
  dataset,
}: {
  result: Result;
  dataset: Dataset | null;
}) {
  const model = useMemo(() => chartModel(result, dataset), [result, dataset]);
  const [active, setActive] = useState<string[]>(() =>
    (model?.groups ?? []).slice(0, 2).map((group) => group.key),
  );
  if (!model) return null;
  const shown = model.groups.filter((group) => active.includes(group.key));
  const axis = (key: string) =>
    shown.findIndex((group) => group.key === key) === 1 ? "y2" : "y";
  const data = model.series
    .filter((series) => active.includes(series.group))
    .map((series, index) => ({
      type: "scatter",
      mode: "lines+markers",
      name: series.legend,
      x: series.x,
      y: series.y,
      customdata: series.hover,
      // Full name on hover; a literal "%{" in a label must not become a template field.
      hovertemplate: `${series.name.replace(/%\{/g, "% {")}<br>%{customdata}<extra></extra>`,
      connectgaps: false,
      yaxis: axis(series.group),
      visible: series.hidden ? "legendonly" : true,
      line: { width: 2, color: COLORS[index % COLORS.length] },
      marker: { size: 4 },
    }));
  return (
    <section className="result-chart" aria-label="Sonuç grafiği">
      <div className="chart-heading">
        <span>
          <LineChart size={15} /> Dönemsel grafik
        </span>
        <div className="chart-groups" role="group" aria-label="Eksen grupları">
          {model.groups.map((group) => (
            <button
              key={group.key}
              type="button"
              className={active.includes(group.key) ? "active" : ""}
              aria-pressed={active.includes(group.key)}
              onClick={() => setActive((old) => toggleGroup(old, group.key))}
            >
              {group.label || "birimsiz"}
            </button>
          ))}
        </div>
      </div>
      {data.length ? (
        <Plot
          data={data}
          layout={{
            autosize: true,
            height: 320,
            margin: { l: 56, r: shown.length > 1 ? 56 : 16, t: 12, b: 40 },
            font: { family: "inherit", size: 11, color: "#4a6252" },
            separators: ",.",
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            showlegend: true,
            legend: { orientation: "h", y: -0.2 },
            // What the reader did to the chart - a zoom, a pan, a legend click -
            // survives a redraw while it keeps the same key. The studio replaces
            // `items` every second while a turn runs, and every one of those
            // renders used to throw the reader back to the full range.
            uirevision: `${result.result_ref}:${shown.map((group) => group.key).join("|")}`,
            xaxis: {
              type: "date",
              // The label follows the zoom: months at the usual scale, days once a
              // month or less is in view, years for a long range. A fixed "%Y-%m"
              // printed the same label on every tick when zoomed in (DN-6.6).
              tickformatstops: [
                { dtickrange: [null, 86400000 * 16], value: "%Y-%m-%d" },
                { dtickrange: [86400000 * 16, 86400000 * 400], value: "%Y-%m" },
                { dtickrange: [86400000 * 400, null], value: "%Y" },
              ],
              gridcolor: "#edf1ee",
            },
            yaxis: {
              title: { text: shown[0]?.label ?? "" },
              exponentformat: "none",
              separatethousands: true,
              automargin: true,
              gridcolor: "#edf1ee",
              zeroline: false,
            },
            // Declared only when a second unit group is on screen: an overlaying
            // axis with nothing on it still reserves its side and shifts the plot.
            ...(shown.length > 1
              ? {
                  yaxis2: {
                    title: { text: shown[1]?.label ?? "" },
                    exponentformat: "none",
                    separatethousands: true,
                    automargin: true,
                    overlaying: "y" as const,
                    side: "right" as const,
                    showgrid: false,
                    zeroline: false,
                  },
                }
              : {}),
          }}
          config={{
            displaylogo: false,
            responsive: true,
            // Box and lasso select do nothing on a line chart but leave the
            // cursor in a selecting mode the reader then has to undo; the image
            // download would leave a picture with no provenance beside it.
            modeBarButtonsToRemove: [
              "select2d",
              "lasso2d",
              "toImage",
              "toggleSpikelines",
            ],
            doubleClick: "reset+autosize",
            scrollZoom: false,
          }}
          style={{ width: "100%" }}
          useResizeHandler
        />
      ) : (
        <p className="chart-empty">
          Grafikte gösterilecek bir eksen grubu seç.
        </p>
      )}
      <p className="chart-note">
        Değerler yayımlanan sonuçtan aynen çizilir; tarayıcıda hesap yapılmaz.
        Farklı birimler aynı eksende gösterilmez, boş dönemler boş kalır.
      </p>
    </section>
  );
}
