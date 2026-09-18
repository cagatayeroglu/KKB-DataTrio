"use client";
import { useEffect, useState } from "react";
import { ChevronDown, LoaderCircle, X } from "lucide-react";
import { describeError, listRuns, openRun } from "@/lib/client";
import type { RunDetail, RunSummary, TraceStep } from "@/lib/contracts";

const stageNames: Record<string, string> = {
  request: "İstek",
  context: "Bağlam",
  planning: "Planlama",
  discovery: "Veri keşfi",
  tool: "Araç",
  verification: "Doğrulama",
  publication: "Yayın",
  answer: "Cevap",
};

function duration(ms: number) {
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)} sn` : `${ms} ms`;
}

function Step({ step }: { step: TraceStep }) {
  const [open, setOpen] = useState(false);
  const entries = Object.entries(step.attributes).filter(
    ([, value]) => value !== null && value !== "",
  );
  return (
    <li className={`trace-step ${step.status}`}>
      <button type="button" onClick={() => setOpen((value) => !value)}>
        <span className="trace-stage">
          {stageNames[step.stage] ?? step.stage}
        </span>
        <span className="trace-name">{step.name}</span>
        <span className="trace-time">
          +{duration(step.started_ms)} · {duration(step.duration_ms)}
        </span>
        {step.status !== "ok" && (
          <span className="trace-status">{step.status}</span>
        )}
        <ChevronDown size={13} className={open ? "open" : ""} />
      </button>
      {open && (
        <div className="trace-detail">
          {entries.length > 0 && (
            <dl>
              {entries.map(([key, value]) => (
                <div key={key}>
                  <dt>{key}</dt>
                  <dd>
                    {typeof value === "string" ? value : JSON.stringify(value)}
                  </dd>
                </div>
              ))}
            </dl>
          )}
          {step.detail && <pre>{step.detail}</pre>}
        </div>
      )}
    </li>
  );
}

export function TracePanel({
  conversationId,
  token,
  runId,
  onClose,
}: {
  conversationId: string;
  token: string;
  runId?: string;
  onClose: () => void;
}) {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [chosen, setChosen] = useState<string | undefined>(runId);
  const [loading, setLoading] = useState(true);
  const [issue, setIssue] = useState("");

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const listed = await listRuns(conversationId, token);
        if (cancelled) return;
        setRuns(listed.runs);
        setChosen((current) => current ?? listed.runs[0]?.run_id);
      } catch (error) {
        if (!cancelled) setIssue(describeError(error));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [conversationId, token]);

  useEffect(() => {
    if (!chosen) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    setLoading(true);
    const read = async () => {
      try {
        const opened = await openRun(conversationId, chosen, token);
        if (cancelled) return;
        setDetail(opened);
        // A running turn keeps writing events; follow it until it ends.
        if (opened.run.status === "running")
          timer = setTimeout(() => void read(), 1200);
      } catch (error) {
        if (!cancelled) setIssue(describeError(error));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void read();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [conversationId, chosen, token]);

  return (
    <section className="trace-panel" aria-label="İşlem ayrıntıları">
      <header>
        <strong>İşlem ayrıntıları</strong>
        <button type="button" aria-label="Kapat" onClick={onClose}>
          <X size={15} />
        </button>
      </header>
      <div className="trace-runs">
        {runs.map((run) => (
          <button
            key={run.run_id}
            type="button"
            className={run.run_id === chosen ? "chosen" : ""}
            onClick={() => setChosen(run.run_id)}
          >
            <span>{run.question}</span>
            <small>
              {new Date(run.started_at).toLocaleTimeString("tr-TR")} ·{" "}
              {duration(run.duration_ms)} · {run.answer_status ?? run.status}
            </small>
          </button>
        ))}
        {runs.length === 0 && !loading && (
          <p className="chat-empty">Kayıtlı işlem yok.</p>
        )}
      </div>
      {issue && <p className="notice">{issue}</p>}
      {loading && (
        <p className="working">
          <LoaderCircle size={14} className="spin" /> Yükleniyor
        </p>
      )}
      {detail && (
        <>
          <p className="trace-summary">
            {detail.steps.length} adım ·{" "}
            {detail.run.status === "running"
              ? "çalışıyor"
              : `toplam ${duration(detail.run.duration_ms)}`}{" "}
            · {detail.run.answer_status ?? detail.run.status}
          </p>
          <ol className="trace-steps">
            {detail.steps.map((step) => (
              <Step key={step.sequence} step={step} />
            ))}
          </ol>
        </>
      )}
    </section>
  );
}
