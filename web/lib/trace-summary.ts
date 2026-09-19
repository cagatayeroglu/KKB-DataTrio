import type { RunSummary, TraceStep } from "./contracts";

/** A span is recorded when a provider call ends, not when it begins. */
export function modelCallLabel(
  status: RunSummary["status"],
  steps: Pick<TraceStep, "stage" | "name">[],
) {
  const completed = steps.filter(
    (step) =>
      (step.stage === "planning" &&
        step.name.startsWith("planner.") &&
        step.name !== "planner.output") ||
      step.name === "writer.call",
  ).length;
  if (status === "running" && completed === 0)
    return "Model çağrısı sürüyor veya bekleniyor; tamamlanan çağrı henüz yok";
  return `${completed} tamamlanan model çağrısı`;
}
