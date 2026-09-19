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
