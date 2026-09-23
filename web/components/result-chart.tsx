"use client";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
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
// The page's own font, by name: plotly measures text before it draws it, and "inherit"
// measured in one font and drew in another, so legend entries ran into each other.
const FONT = 'Inter, "Segoe UI", Arial, sans-serif';
const PLOT_HEIGHT = 280;
const LEGEND_ROW = 22;

export function ResultChart({
  result,
  dataset,
}: {
  result: Result;
  dataset: Dataset | null;
}) {
  const model = useMemo(() => chartModel(result, dataset), [result, dataset]);
  // What the reader chose, for this result only. The default used to be computed once,
  // when the component first mounted: mounted before the result's cells were there, it
  // stayed empty for good, and the chart drew nothing until the chat was opened again.
  const [chosen, setChosen] = useState<{ ref: string; keys: string[] } | null>(
    null,
  );
  // The plot is given its container's measured width. Drawn into a container that is
  // still hidden or animating, plotly kept a zero-width layout: axes and a legend, no
  // lines. A window resize fixed it; nothing else did.
  const holder = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const drawable = model !== null;
  useEffect(() => {
    const node = holder.current;
    if (!node || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) =>
      setWidth(Math.round(entry.contentRect.width)),
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [drawable]);
  if (!model) return null;
  const groupKeys = model.groups.map((group) => group.key);
  const active =
    chosen && chosen.ref === result.result_ref
      ? chosen.keys.filter((key) => groupKeys.includes(key))
      : groupKeys.slice(0, 2);
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
              onClick={() =>
                setChosen({
                  ref: result.result_ref,
                  keys: toggleGroup(active, group.key),
                })
              }
            >
              {group.label || "birimsiz"}
            </button>
          ))}
        </div>
      </div>
      <div ref={holder} className="chart-holder">
        {data.length && width > 0 ? (
          <Plot
            data={data}
            revision={width}
            layout={{
              autosize: false,
              width,
              // One legend row per series, under the plot: side by side, long names
              // were cut short and still overlapped.
              height: PLOT_HEIGHT + 64 + LEGEND_ROW * data.length,
              margin: {
                l: 64,
                r: shown.length > 1 ? 64 : 16,
                t: 28,
                b: 48 + LEGEND_ROW * data.length,
              },
              font: { family: FONT, size: 11, color: "#4a6252" },
              separators: ",.",
              paper_bgcolor: "rgba(0,0,0,0)",
              plot_bgcolor: "rgba(0,0,0,0)",
              showlegend: true,
              legend: {
                orientation: "v",
                x: 0,
                xanchor: "left",
                y: -0.16,
                yanchor: "top",
                font: { family: FONT, size: 12 },
              },
              // The unit of each axis, written level above it. A rotated axis title sat
              // on top of the tick labels whenever they were wide ("1.000.000").
              annotations: shown.slice(0, 2).map((group, index) => ({
                xref: "paper" as const,
                yref: "paper" as const,
                x: index === 0 ? 0 : 1,
                xanchor: index === 0 ? ("left" as const) : ("right" as const),
                y: 1,
                yanchor: "bottom" as const,
                yshift: 6,
                text: group.label || "birimsiz",
                showarrow: false,
                font: { family: FONT, size: 11, color: "#4a6252" },
              })),
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
                  {
                    dtickrange: [86400000 * 16, 86400000 * 400],
                    value: "%Y-%m",
                  },
                  { dtickrange: [86400000 * 400, null], value: "%Y" },
                ],
                ...model.monthlyTicks,
                gridcolor: "#edf1ee",
              },
              yaxis: {
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
          />
        ) : data.length ? (
          <p className="chart-loading">Grafik hazırlanıyor…</p>
        ) : (
          <p className="chart-empty">
            Grafikte gösterilecek bir eksen grubu seç.
          </p>
        )}
      </div>
      <p className="chart-note">
        Değerler yayımlanan sonuçtan aynen çizilir; tarayıcıda hesap yapılmaz.
        Farklı birimler aynı eksende gösterilmez, boş dönemler boş kalır.
      </p>
    </section>
  );
}
