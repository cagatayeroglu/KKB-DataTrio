import type { Dataset, Proof } from "./contracts";
import { documentName, sourceName, stepTitle } from "./proof";

/**
 * The proof as a graph: where each number came from, left to right.
 *
 * Sources and documents sit in the first column, steps to the right of every
 * step they read, and step 0 — this result — last. Edges are exactly the
 * recorded `inputs`; nothing is inferred, so an input the proof does not name
 * draws no edge, and an unreferenced source still appears on its own.
 */
export type GraphNode = {
  id: string;
  kind: "source" | "document" | "step";
  label: string;
  detail: string;
  column: number;
  row: number;
  verified: boolean | null;
};
export type GraphEdge = { from: string; to: string };
export type EvidenceGraph = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  columns: number;
  rows: number;
};

export function evidenceGraph(
  proof: Proof,
  dataset: Dataset | null,
): EvidenceGraph {
  // Distance from this result: step 0 is 0, a step it reads is 1, and so on.
  const depth = new Map<number, number>();
  const queue: number[] = proof.steps.length ? [0] : [];
  depth.set(0, 0);
  while (queue.length) {
    const index = queue.shift()!;
    for (const input of proof.steps[index]?.inputs ?? []) {
      if (input.kind !== "result" || depth.has(input.index)) continue;
      if (!proof.steps[input.index]) continue;
      depth.set(input.index, (depth.get(index) ?? 0) + 1);
      queue.push(input.index);
    }
  }
  const deepest = Math.max(0, ...depth.values());
  const columns = proof.steps.length ? deepest + 2 : 1;
  const nodes: GraphNode[] = [];
  const rowsIn = new Map<number, number>();
  const place = (column: number) => {
    const row = rowsIn.get(column) ?? 0;
    rowsIn.set(column, row + 1);
    return row;
  };
  proof.sources.forEach((source, index) =>
    nodes.push({
      id: `source-${index}`,
      kind: "source",
      label: sourceName(source, dataset),
      detail: source.series_id,
      column: 0,
      row: place(0),
      verified: null,
    }),
  );
  proof.documents.forEach((document, index) =>
    nodes.push({
      id: `document-${index}`,
      kind: "document",
      label: documentName(document),
      detail: `sha256 ${document.content_sha256.slice(0, 12)}`,
      column: 0,
      row: place(0),
      verified: null,
    }),
  );
  // Steps no path from this result reaches are still shown, beside the sources.
  proof.steps
    .map((step, index) => ({ step, index }))
    .sort(
      (a, b) =>
        (depth.get(b.index) ?? deepest) - (depth.get(a.index) ?? deepest) ||
        a.index - b.index,
    )
    .forEach(({ step, index }) => {
      const column = 1 + deepest - (depth.get(index) ?? deepest);
      nodes.push({
        id: `step-${index}`,
        kind: "step",
        label: stepTitle(step),
        detail:
          index === 0
            ? "bu sonuç"
            : (step.workspace_name ?? `ara sonuç ${index}`),
        column,
        row: place(column),
        verified: step.execution === "verified",
      });
    });
  const known = new Set(nodes.map((node) => node.id));
  const edges: GraphEdge[] = [];
  proof.steps.forEach((step, index) => {
    for (const input of step.inputs) {
      const from =
        input.kind === "series"
          ? `source-${input.index}`
          : input.kind === "document"
            ? `document-${input.index}`
            : `step-${input.index}`;
      if (known.has(from) && from !== `step-${index}`)
        edges.push({ from, to: `step-${index}` });
    }
  });
  return {
    nodes,
    edges,
    columns,
    rows: Math.max(1, ...rowsIn.values()),
  };
}
