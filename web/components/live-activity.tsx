"use client";
import { useEffect, useState } from "react";
import { listRuns, openRun } from "@/lib/client";
import { liveActivityLabel } from "@/lib/trace-summary";

/** What the newest recorded step means, in one line a person can read. */
const stageWords: Record<string, string> = {
  "knowledge.applied": "Bilgi tabanı uygulanıyor",
  "turn.received": "Soru alındı",
  "context.assembled": "Bağlam toplanıyor",
  "planner.initial": "Plan hazırlanıyor",
  "planner.continuation": "Bulunan serilerle plan kuruluyor",
  "planner.output": "Plan hazır",
  "catalog.feedback": "Katalog sonuçları okunuyor",
  "writer.call": "Yanıt yazılıyor",
  "draft.model": "Yanıt yazıldı",
  "draft.deterministic": "Yanıt hazırlanıyor",
  "answer.gate": "Yanıt doğrulanıyor",
  "workspace.published": "Tablo yayımlanıyor",
  "workspace.not_published": "Yayımlanacak tablo yok",
  "gold.materialized": "Tablo kaydediliyor",
  "gold.skipped": "Tablo kaydı atlandı",
  "model.reasoning": "Model düşünüyor",
};
const toolWords: Record<string, string> = {
  catalog_search: "Katalogda seri aranıyor",
  lakehouse: "Veri okunuyor",
  change_detection: "Değişim hesaplanıyor",
  table_transform: "Tablo dönüştürülüyor",
  anomaly: "Sapmalar inceleniyor",
  causality: "İlişki sınanıyor",
  web_url: "Adresteki belge okunuyor",
  web_search: "Web'de aranıyor",
};

function phrase(step: { stage: string; name: string }): string {
  if (step.stage === "tool")
    return toolWords[step.name] ?? `${step.name} çalışıyor`;
  if (step.stage === "acquisition") return "Resmî kaynaktan seri çekiliyor";
  return stageWords[step.name] ?? "Analiz sürüyor";
}

/**
 * The newest step of the running turn, refreshed while it runs. Reading a trace
 * starts no work: it is the record the turn is already writing.
 */
export function LiveActivity({
  conversationId,
  token,
  turnId,
}: {
  conversationId: string;
  token: string;
  turnId: string;
}) {
  const [line, setLine] = useState("");
  const [readFailed, setReadFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const read = async () => {
      try {
        const runs = await listRuns(conversationId, token);
        if (!cancelled) setReadFailed(false);
        const run = runs.runs.find((item) => item.turn_id === turnId);
        if (run) {
          const detail = await openRun(conversationId, run.run_id, token);
          const last = detail.steps.at(-1);
          if (!cancelled && last) setLine(phrase(last));
          if (!cancelled && detail.run.status !== "running") return;
        }
      } catch {
        // One stable state per outage, while the bounded polling retry continues.
        if (!cancelled) setReadFailed(true);
      }
      if (!cancelled) timer = setTimeout(() => void read(), 2000);
    };
    void read();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [conversationId, token, turnId]);

  return (
    <span className="live-activity">
      {liveActivityLabel(line, readFailed)}…
    </span>
  );
}
