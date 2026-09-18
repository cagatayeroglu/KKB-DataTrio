"use client";
import { useEffect, useMemo, useState } from "react";
import {
  ChevronDown,
  Download,
  LoaderCircle,
  Search,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  describeError,
  listConversations,
  listFeedback,
  listRuns,
  openConversation,
  openRun,
  openRunStep,
} from "@/lib/client";
import type {
  ConversationSummary,
  Feedback,
  RunDetail,
  RunSummary,
  TraceStep,
} from "@/lib/contracts";

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
const reasonNames: Record<string, string> = {
  accuracy: "Doğruluk",
  incomplete: "Eksik",
  wrong_source: "Yanlış kaynak",
  slow: "Yavaş",
  lost_context: "Bağlam kaybı",
  unclear: "Anlaşılmaz",
  other: "Diğer",
};

function duration(ms: number) {
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)} sn` : `${ms} ms`;
}
function size(chars: number) {
  return chars >= 1024
    ? `${(chars / 1024).toLocaleString("tr-TR", { maximumFractionDigits: 1 })} KB`
    : `${chars} karakter`;
}

/** Full text of every step whose stored detail was sent as a preview. */
type FullDetails = Record<number, string | null>;

function Step({
  step,
  open,
  full,
  onToggle,
}: {
  step: TraceStep;
  open: boolean;
  full: string | null | undefined;
  onToggle: () => void;
}) {
  const entries = Object.entries(step.attributes).filter(
    ([, value]) => value !== null && value !== "",
  );
  const text = full !== undefined ? full : step.detail;
  const chars = step.detail_chars ?? step.detail?.length ?? 0;
  const clipped = step.detail_complete === false && full === undefined;
  return (
    <li className={`trace-step ${step.status}`}>
      <button type="button" onClick={onToggle} aria-expanded={open}>
        <span className="trace-seq">{step.sequence}</span>
        <span className="trace-stage">
          {stageNames[step.stage] ?? step.stage}
        </span>
        <span className="trace-name">{step.name}</span>
        {chars > 0 && <span className="trace-size">{size(chars)}</span>}
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
                    {typeof value === "string"
                      ? value
                      : JSON.stringify(value, null, 1)}
                  </dd>
                </div>
              ))}
            </dl>
          )}
          {clipped && (
            <p className="helper">
              <LoaderCircle size={12} className="spin" />{" "}
              {`Tam metin yükleniyor (${size(chars)})`}
            </p>
          )}
          {text && <pre>{text}</pre>}
        </div>
      )}
    </li>
  );
}

function RunView({
  conversationId,
  token,
  run,
  answer,
  feedback,
}: {
  conversationId: string;
  token: string;
  run: RunSummary;
  answer?: string;
  feedback: Feedback[];
}) {
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [open, setOpen] = useState<Set<number>>(new Set());
  const [full, setFull] = useState<FullDetails>({});
  const [issue, setIssue] = useState("");
  const [filter, setFilter] = useState("");

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    setDetail(null);
    setOpen(new Set());
    setFull({});
    setIssue("");
    const read = async () => {
      try {
        const opened = await openRun(conversationId, run.run_id, token);
        if (cancelled) return;
        setDetail(opened);
        if (opened.run.status === "running")
          timer = setTimeout(() => void read(), 1500);
      } catch (error) {
        if (!cancelled) setIssue(describeError(error));
      }
    };
    void read();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [conversationId, run.run_id, token]);

  async function loadFull(steps: TraceStep[]) {
    const missing = steps.filter(
      (step) =>
        step.detail_complete === false && full[step.sequence] === undefined,
    );
    for (const step of missing) {
      try {
        const whole = await openRunStep(
          conversationId,
          run.run_id,
          step.sequence,
          token,
        );
        setFull((current) => ({ ...current, [step.sequence]: whole.detail }));
      } catch (error) {
        setIssue(describeError(error));
        return;
      }
    }
  }

  function toggle(step: TraceStep) {
    setOpen((current) => {
      const next = new Set(current);
      if (next.has(step.sequence)) next.delete(step.sequence);
      else {
        next.add(step.sequence);
        void loadFull([step]);
      }
      return next;
    });
  }

  const shown = useMemo(() => {
    const needle = filter.trim().toLocaleLowerCase("tr");
    if (!detail) return [];
    if (!needle) return detail.steps;
    return detail.steps.filter((step) =>
      [step.stage, step.name, step.status, JSON.stringify(step.attributes)]
        .join(" ")
        .toLocaleLowerCase("tr")
        .includes(needle),
    );
  }, [detail, filter]);

  async function download() {
    if (!detail) return;
    // Every clipped step is read whole for the file, whether or not it is open.
    const steps = await Promise.all(
      detail.steps.map(async (step) =>
        step.detail_complete === false
          ? {
              ...step,
              detail: (
                await openRunStep(
                  conversationId,
                  run.run_id,
                  step.sequence,
                  token,
                )
              ).detail,
              detail_complete: true,
            }
          : step,
      ),
    );
    const blob = new Blob(
      [JSON.stringify({ run: detail.run, answer, feedback, steps }, null, 2)],
      { type: "application/json" },
    );
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `trace-${run.run_id.slice(0, 8)}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  const model = detail?.steps.filter(
    (step) =>
      (step.stage === "planning" && step.name !== "planner.output") ||
      step.name === "draft.model",
  ).length;
  const tools = detail?.steps.filter((step) => step.stage === "tool").length;

  return (
    <div className="trace-run">
      <header className="trace-run-head">
        <h3>{run.question}</h3>
        <p>
          {new Date(run.started_at).toLocaleString("tr-TR")} ·{" "}
          {run.status === "running"
            ? "çalışıyor"
            : `toplam ${duration(run.duration_ms)}`}{" "}
          · {run.answer_status ?? run.status}
          {run.error ? ` · hata: ${run.error}` : ""}
          {detail &&
            ` · ${detail.steps.length} adım · ${model} model çağrısı · ${tools} araç adımı`}
        </p>
      </header>
      {answer && (
        <div className="trace-answer">
          <span className="eyebrow">YANIT</span>
          <p>{answer}</p>
        </div>
      )}
      {feedback.map((item) => (
        <div
          key={item.answer_digest}
          className={`trace-feedback ${item.rating}`}
        >
          {item.rating === "up" ? (
            <ThumbsUp size={14} />
          ) : (
            <ThumbsDown size={14} />
          )}
          <div>
            <strong>
              Geri bildirim{item.score ? ` · ${item.score}/5` : ""}
            </strong>
            {item.reasons.length > 0 && (
              <span>
                {" "}
                · {item.reasons.map((r) => reasonNames[r] ?? r).join(", ")}
              </span>
            )}
            {item.comment && <p>{item.comment}</p>}
            <small>{new Date(item.updated_at).toLocaleString("tr-TR")}</small>
          </div>
        </div>
      ))}
      <div className="trace-tools">
        <label className="table-search">
          <Search size={13} />
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Adım, araç veya özellik ara"
            aria-label="Adımlarda ara"
          />
        </label>
        <Button
          variant="outline"
          size="sm"
          disabled={!detail}
          onClick={() => {
            if (!detail) return;
            setOpen(new Set(shown.map((step) => step.sequence)));
            void loadFull(shown);
          }}
        >
          Tümünü aç
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={!detail}
          onClick={() => setOpen(new Set())}
        >
          Tümünü kapat
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={!detail}
          onClick={() => void download()}
        >
          <Download size={13} /> JSON indir
        </Button>
      </div>
      {issue && <p className="notice">{issue}</p>}
      {!detail && !issue && (
        <p className="working">
          <LoaderCircle size={14} className="spin" /> Yükleniyor
        </p>
      )}
      <ol className="trace-steps">
        {shown.map((step) => (
          <Step
            key={step.sequence}
            step={step}
            open={open.has(step.sequence)}
            full={full[step.sequence]}
            onToggle={() => toggle(step)}
          />
        ))}
      </ol>
    </div>
  );
}

/** Every stored run of every conversation this browser owns, each step in full. */
export function TracesPage({
  owner,
  initialConversation,
  initialTurn,
}: {
  owner: string;
  initialConversation?: string | null;
  /** Open this turn's own run: the studio's "İşlem ayrıntıları" and "Canlı izle". */
  initialTurn?: string | null;
}) {
  const [archived, setArchived] = useState(false);
  const [search, setSearch] = useState("");
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [chosen, setChosen] = useState<string | null>(
    initialConversation ?? null,
  );
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [run, setRun] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [ratings, setRatings] = useState<Feedback[]>([]);
  const [issue, setIssue] = useState("");

  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const listed = await listConversations(owner, {
          archived,
          search: search.trim() || undefined,
        });
        if (cancelled) return;
        setConversations(listed.conversations);
        setChosen(
          (current) =>
            current ?? listed.conversations[0]?.conversation_id ?? null,
        );
      } catch (error) {
        if (!cancelled) setIssue(describeError(error));
      }
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [owner, archived, search]);

  useEffect(() => {
    if (!chosen) return;
    let cancelled = false;
    setRuns([]);
    setRun(null);
    setAnswers({});
    setRatings([]);
    void (async () => {
      try {
        // The browser's key opens its own conversations' records; no second secret.
        const [listed, detail, feedback] = await Promise.all([
          listRuns(chosen, owner),
          openConversation(chosen, owner),
          listFeedback(chosen, owner).catch(() => ({ feedback: [] })),
        ]);
        if (cancelled) return;
        setRuns(listed.runs);
        setRun(
          (initialTurn
            ? listed.runs.find((item) => item.turn_id === initialTurn)?.run_id
            : undefined) ??
            listed.runs[0]?.run_id ??
            null,
        );
        setAnswers(
          Object.fromEntries(
            detail.messages
              .filter((message) => message.role === "assistant")
              .map((message) => [message.turn_id, message.text]),
          ),
        );
        setRatings(feedback.feedback);
        setIssue("");
      } catch (error) {
        if (!cancelled) setIssue(describeError(error));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [chosen, owner, initialTurn]);

  const current = runs.find((item) => item.run_id === run);
  return (
    <section
      className="traces-page"
      aria-labelledby="panel-title"
      onClick={(e) => e.stopPropagation()}
    >
      <header className="traces-head">
        <h2 id="panel-title">İşlem kayıtları</h2>
        <p>
          Her turda modele giden istemler, araç çağrıları ve dönen çıktıların
          tamamı. Açmak yeni analiz başlatmaz.
        </p>
      </header>
      {issue && <p className="notice">{issue}</p>}
      <div className="traces-body">
        <nav className="traces-column" aria-label="Sohbetler">
          <label className="table-search">
            <Search size={13} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Sohbet ara"
              aria-label="Sohbet ara"
            />
          </label>
          <label className="traces-archived">
            <input
              type="checkbox"
              checked={archived}
              onChange={(e) => setArchived(e.target.checked)}
            />{" "}
            Arşivdekiler
          </label>
          {conversations.map((item) => (
            <button
              key={item.conversation_id}
              type="button"
              className={item.conversation_id === chosen ? "chosen" : ""}
              onClick={() => setChosen(item.conversation_id)}
            >
              <span>{item.title}</span>
              <small>
                {new Date(item.updated_at).toLocaleString("tr-TR")} ·{" "}
                {item.turns} soru
              </small>
            </button>
          ))}
          {conversations.length === 0 && (
            <p className="chat-empty">Sohbet yok.</p>
          )}
        </nav>
        <nav className="traces-column" aria-label="Turlar">
          {runs.map((item) => {
            const rated = ratings.filter((r) => r.turn_id === item.turn_id);
            return (
              <button
                key={item.run_id}
                type="button"
                className={item.run_id === run ? "chosen" : ""}
                onClick={() => setRun(item.run_id)}
              >
                <span>{item.question}</span>
                <small>
                  {new Date(item.started_at).toLocaleTimeString("tr-TR")} ·{" "}
                  {duration(item.duration_ms)} ·{" "}
                  {item.answer_status ?? item.status} · {item.events} adım
                  {rated.some((r) => r.rating === "up") && " · 👍"}
                  {rated.some((r) => r.rating === "down") && " · 👎"}
                </small>
              </button>
            );
          })}
          {chosen && runs.length === 0 && (
            <p className="chat-empty">Bu sohbette kayıtlı işlem yok.</p>
          )}
        </nav>
        <div className="traces-main">
          {current && chosen ? (
            <RunView
              key={current.run_id}
              conversationId={chosen}
              token={owner}
              run={current}
              answer={answers[current.turn_id]}
              feedback={ratings.filter((r) => r.turn_id === current.turn_id)}
            />
          ) : (
            <p className="chat-empty">Bir sohbet ve tur seçin.</p>
          )}
        </div>
      </div>
    </section>
  );
}
