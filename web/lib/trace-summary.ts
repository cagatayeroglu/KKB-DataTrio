import type { RunSummary, TraceStep } from "./contracts";

export type RunReadState = "loading" | "ready" | "error";

/** An unreadable run list is never described as an empty one. */
export function runReadMessage(state: RunReadState, count: number) {
  if (state === "error") return "Kayıtlar okunamadı — yeniden dene";
  if (state === "loading") return "Kayıtlar yükleniyor…";
  return count === 0 ? "Bu sohbette kayıtlı işlem yok." : null;
}

export function liveActivityLabel(line: string, readFailed: boolean) {
  return readFailed
    ? "İşlem kayıtları okunamadı; yeniden deneniyor"
    : line || "Analiz başlıyor";
}

/**
 * How many provider calls this run has made, and whether one is out right now.
 *
 * A span is recorded when the call ends; "model.started" is written when the
 * request leaves, so a call in flight can be counted honestly instead of being
 * reported as nothing at all.
 */
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
  const started = steps.filter((step) => step.name === "model.started").length;
  const running = status === "running" && started > completed;
  if (running)
    return completed === 0
      ? "1. model çağrısı sürüyor"
      : `${completed} tamamlanan model çağrısı · ${started}. çağrı sürüyor`;
  if (status === "running" && completed === 0)
    return "Model çağrısı sürüyor veya bekleniyor; tamamlanan çağrı henüz yok";
  return `${completed} tamamlanan model çağrısı`;
}
