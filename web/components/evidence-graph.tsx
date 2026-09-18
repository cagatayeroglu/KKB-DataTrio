"use client";
import type { Dataset, Proof } from "@/lib/contracts";
import { evidenceGraph, type GraphNode } from "@/lib/evidence-graph";

const WIDTH = 168;
const HEIGHT = 46;
const GAP_X = 56;
const GAP_Y = 14;

function clip(text: string, limit: number) {
  return text.length > limit ? `${text.slice(0, limit - 1)}…` : text;
}

/** The recorded proof drawn as boxes and arrows; text nodes only, no HTML from data. */
export function EvidenceGraph({
  proof,
  dataset,
}: {
  proof: Proof;
  dataset: Dataset | null;
}) {
  const graph = evidenceGraph(proof, dataset);
  if (!graph.nodes.length) return null;
  const x = (node: GraphNode) => node.column * (WIDTH + GAP_X);
  const y = (node: GraphNode) => node.row * (HEIGHT + GAP_Y);
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  const width = graph.columns * (WIDTH + GAP_X) - GAP_X;
  const height = graph.rows * (HEIGHT + GAP_Y) - GAP_Y;
  return (
    <figure className="evidence-graph">
      <svg
        viewBox={`-2 -2 ${width + 4} ${height + 4}`}
        width="100%"
        role="img"
        aria-label="Kanıt grafiği: kaynaklardan bu sonuca uzanan kayıtlı adımlar"
      >
        <defs>
          <marker
            id="evidence-arrow"
            viewBox="0 0 8 8"
            refX="7"
            refY="4"
            markerWidth="6"
            markerHeight="6"
            orient="auto"
          >
            <path d="M0,0 L8,4 L0,8 z" className="evidence-arrow" />
          </marker>
        </defs>
        {graph.edges.map((edge) => {
          const from = byId.get(edge.from)!;
          const to = byId.get(edge.to)!;
          const x1 = x(from) + WIDTH;
          const y1 = y(from) + HEIGHT / 2;
          const x2 = x(to);
          const y2 = y(to) + HEIGHT / 2;
          const bend = (x2 - x1) / 2;
          return (
            <path
              key={`${edge.from}-${edge.to}`}
              className="evidence-edge"
              d={`M${x1},${y1} C${x1 + bend},${y1} ${x2 - bend},${y2} ${x2},${y2}`}
              markerEnd="url(#evidence-arrow)"
            />
          );
        })}
        {graph.nodes.map((node) => (
          <g
            key={node.id}
            transform={`translate(${x(node)},${y(node)})`}
            className={`evidence-node ${node.kind} ${
              node.verified === false ? "unverified" : ""
            }`}
          >
            <title>{`${node.label} — ${node.detail}`}</title>
            <rect width={WIDTH} height={HEIGHT} rx={8} />
            <text x={10} y={19} className="evidence-label">
              {clip(node.label, 24)}
            </text>
            <text x={10} y={35} className="evidence-detail">
              {clip(
                node.kind === "step" && node.verified === false
                  ? `${node.detail} · yürütme doğrulanmadı`
                  : node.detail,
                28,
              )}
            </text>
          </g>
        ))}
      </svg>
      <figcaption>
        Soldan sağa: kaynak ve belgeler, onları okuyan adımlar, en sağda bu
        sonuç. Oklar yalnızca kayıtlı girdileri gösterir.
      </figcaption>
    </figure>
  );
}
