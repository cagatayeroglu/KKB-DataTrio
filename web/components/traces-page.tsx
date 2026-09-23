"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  ChevronDown,
  Maximize2,
  Download,
  LoaderCircle,
  Search,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  ApiError,
  deleteConversationRuns,
  describeError,
  listConversations,
  listTraceConversations,
  listFeedback,
  listRuns,
  openConversation,
  openRun,
  openRunStep,
} from "@/lib/client";
import {
  modelCallLabel,
  runReadMessage,
  type RunReadState,
} from "@/lib/trace-summary";
import type {
  TraceConversationSummary,
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
//: What an event recorded under a model call is, in the reader's words.
const childNames: Record<string, string> = {
  "prompt.system": "Sistem mesajı",
  "prompt.user": "Kullanıcı mesajı",
  "prompt.assistant": "Model mesajı",
  "model.reasoning": "Modelin akıl yürütmesi",
  "planner.output": "Modelin verdiği plan",
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

function Content({
  step,
  full,
  failed = false,
  onRetry,
  onExpand,
}: {
  step: TraceStep;
  full: string | null | undefined;
  //: The full text could not be read. Without this the spinner turned forever
  //: and the preview below it looked like the whole step (finding F4-iz-5).
  failed?: boolean;
  onRetry?: () => void;
  onExpand: (step: TraceStep, text: string) => void;
}) {
  const text = full !== undefined ? full : step.detail;
  const chars = step.detail_chars ?? step.detail?.length ?? 0;
  const clipped =
    step.detail_complete === false && full === undefined && !failed;
  const entries = Object.entries(step.attributes).filter(
    ([, value]) => value !== null && value !== "",
  );
  return (
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
      {failed && (
        <p className="helper">
          {`Tam metin okunamadı (${size(chars)}); aşağıdaki ilk bölüm kayıttan geliyor.`}
          {onRetry && (
            <button type="button" className="trace-retry" onClick={onRetry}>
              Yeniden dene
            </button>
          )}
        </p>
      )}
      {text && (
        <>
          <button
            type="button"
            className="trace-expand"
            onClick={() => onExpand(step, text)}
          >
            <Maximize2 size={12} /> Tam ekran
          </button>
          <pre>{text}</pre>
        </>
      )}
    </div>
  );
}

function Step({
  step,
  records,
  open,
  full,
  onToggle,
  onExpand,
  fullOf,
  failedOf,
  onRetry,
}: {
  step: TraceStep;
  records: TraceStep[];
  open: boolean;
  full: string | null | undefined;
  onToggle: () => void;
  onExpand: (step: TraceStep, text: string) => void;
  fullOf: (step: TraceStep) => string | null | undefined;
  failedOf: (step: TraceStep) => boolean;
  onRetry: (step: TraceStep) => void;
}) {
  const own = (step.detail_chars ?? step.detail?.length ?? 0) as number;
  const chars =
    own +
    records.reduce(
      (total, child) =>
        total + (child.detail_chars ?? child.detail?.length ?? 0),
      0,
    );
  return (
    <li className={`trace-step ${step.status}`}>
      <button type="button" onClick={onToggle} aria-expanded={open}>
        <span className="trace-seq">{step.sequence}</span>
        <span className="trace-stage">
          {stageNames[step.stage] ?? step.stage}
        </span>
        <span className="trace-name">{step.name}</span>
        {records.length > 0 && (
          <span className="trace-children">{records.length} kayıt</span>
        )}
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
        <div className="trace-nested">
          <Content
            step={step}
            full={full}
            failed={failedOf(step)}
            onRetry={() => onRetry(step)}
            onExpand={onExpand}
          />
          {records.map((child) => (
            <section key={child.sequence} className="trace-child">
              <h4>
                {childNames[child.name] ?? child.name}
                {typeof child.attributes.position === "number" && (
                  <span> · {String(child.attributes.position)}</span>
                )}
              </h4>
              <Content
                step={child}
                full={fullOf(child)}
                failed={failedOf(child)}
                onRetry={() => onRetry(child)}
                onExpand={onExpand}
              />
            </section>
          ))}
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
  //: Steps whose full text could not be read, and whether a file is being built.
  const [failed, setFailed] = useState<Set<number>>(new Set());
  const [downloading, setDownloading] = useState(false);
  const [issue, setIssue] = useState("");
  const [filter, setFilter] = useState("");
  //: One record read on its own, filling the page until it is closed.
  const [expanded, setExpanded] = useState<{
    step: TraceStep;
    text: string;
  } | null>(null);

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
      setFailed((current) => {
        if (!current.has(step.sequence)) return current;
        const next = new Set(current);
        next.delete(step.sequence);
        return next;
      });
      try {
        const whole = await openRunStep(
          conversationId,
          run.run_id,
          step.sequence,
          token,
        );
        setFull((current) => ({ ...current, [step.sequence]: whole.detail }));
      } catch (error) {
        // One unreadable step is not the end of the list: it says so in place and
        // the others still open (finding F4-iz-5).
        setFailed((current) => new Set(current).add(step.sequence));
        setIssue(describeError(error));
      }
    }
  }

  function toggle(step: TraceStep, children: TraceStep[] = []) {
    setOpen((current) => {
      const next = new Set(current);
      if (next.has(step.sequence)) next.delete(step.sequence);
      else {
        next.add(step.sequence);
        void loadFull([step, ...children]);
      }
      return next;
    });
  }

  // A model call records its prompts and its reasoning as its own events; they
  // belong under it, not as thirty sibling rows.
  const grouped = useMemo(() => {
    const steps = detail?.steps ?? [];
    const children = new Map<number, TraceStep[]>();
    for (const step of steps) {
      if (step.parent == null) continue;
      children.set(step.parent, [...(children.get(step.parent) ?? []), step]);
    }
    return steps
      .filter((step) => step.parent == null)
      .map((step) => ({ step, children: children.get(step.sequence) ?? [] }));
  }, [detail]);

  const shown = useMemo(() => {
    const needle = filter.trim().toLocaleLowerCase("tr");
    if (!needle) return grouped;
    const matches = (step: TraceStep) =>
      [step.stage, step.name, step.status, JSON.stringify(step.attributes)]
        .join(" ")
        .toLocaleLowerCase("tr")
        .includes(needle);
    return grouped.filter(
      (item) => matches(item.step) || item.children.some(matches),
    );
  }, [grouped, filter]);

  async function download() {
    if (!detail || downloading) return;
    setDownloading(true);
    setIssue("");
    try {
      // Every clipped step is read whole for the file, whether or not it is open.
      // One at a time: a long run is hundreds of steps, and asking for all of
      // them at once used to flood the bridge and fail without a word (F4-iz-5).
      const steps: TraceStep[] = [];
      for (const step of detail.steps) {
        if (step.detail_complete === false) {
          const whole = await openRunStep(
            conversationId,
            run.run_id,
            step.sequence,
            token,
          );
          steps.push({ ...step, detail: whole.detail, detail_complete: true });
        } else steps.push(step);
      }
      const blob = new Blob(
        [JSON.stringify({ run: detail.run, answer, feedback, steps }, null, 2)],
        { type: "application/json" },
      );
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `trace-${run.run_id.slice(0, 8)}.json`;
      link.click();
      URL.revokeObjectURL(link.href);
    } catch (error) {
      setIssue(describeError(error));
    } finally {
      setDownloading(false);
    }
  }

  // Call spans appear only after completion. Never label a running first call
  // "0 model calls" merely because the provider has not returned yet.
  const summary = detail?.run ?? run;
  const model = detail ? modelCallLabel(summary.status, detail.steps) : "";
  const tools = detail?.steps.filter((step) => step.stage === "tool").length;

  return (
    <div className="trace-run">
      <header className="trace-run-head">
        <h3>{summary.question}</h3>
        <p>
          {new Date(summary.started_at).toLocaleString("tr-TR")} ·{" "}
          {summary.status === "running"
            ? "çalışıyor"
            : `toplam ${duration(summary.duration_ms)}`}{" "}
          · {summary.answer_status ?? summary.status}
          {summary.error ? ` · hata: ${summary.error}` : ""}
          {detail &&
            ` · ${detail.steps.length} adım · ${model} · ${tools} araç adımı`}
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
            setOpen(new Set(shown.map((item) => item.step.sequence)));
            void loadFull(
              shown.flatMap((item) => [item.step, ...item.children]),
            );
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
          disabled={!detail || downloading}
          onClick={() => void download()}
        >
          <Download size={13} /> {downloading ? "Hazırlanıyor…" : "JSON indir"}
        </Button>
      </div>
      {issue && <p className="notice">{issue}</p>}
      {!detail && !issue && (
        <p className="working">
          <LoaderCircle size={14} className="spin" /> Yükleniyor
        </p>
      )}
      {expanded && (
        <div className="trace-full" role="dialog" aria-label="Kayıt">
          <header>
            <strong>
              {childNames[expanded.step.name] ?? expanded.step.name}
            </strong>
            <span>{size(expanded.text.length)}</span>
            <button type="button" onClick={() => setExpanded(null)}>
              Kapat
            </button>
          </header>
          <pre>{expanded.text}</pre>
        </div>
      )}
      <ol className="trace-steps">
        {shown.map((item) => (
          <Step
            key={item.step.sequence}
            step={item.step}
            records={item.children}
            open={open.has(item.step.sequence)}
            full={full[item.step.sequence]}
            onToggle={() => toggle(item.step, item.children)}
            onExpand={(step, text) => setExpanded({ step, text })}
            fullOf={(child) => full[child.sequence]}
            failedOf={(child) => failed.has(child.sequence)}
            onRetry={(child) => void loadFull([child])}
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
  const [conversations, setConversations] = useState<
    TraceConversationSummary[]
  >([]);
  const [chosen, setChosen] = useState<string | null>(
    initialConversation ?? null,
  );
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [run, setRun] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [ratings, setRatings] = useState<Feedback[]>([]);
  const [issue, setIssue] = useState("");
  const [runsState, setRunsState] = useState<RunReadState>("loading");
  const [retry, setRetry] = useState(0);
  const [listRevision, setListRevision] = useState(0);
  const [listError, setListError] = useState(false);
  //: This API has no retained-trace index, so the list came from the ordinary
  //: conversation list and deleted conversations are not in it.
  const [plainList, setPlainList] = useState(false);
  //: How many times the watched turn's record has been looked for. A turn runs
  //: for minutes and each look is three requests, so the wait is slow and ends.
  const waited = useRef(0);
  const chosenDeleted =
    conversations.find((item) => item.conversation_id === chosen)?.deleted ??
    false;

  async function removeRuns() {
    if (
      !chosen ||
      !window.confirm(
        "Bu sohbetin tüm işlem kayıtları kalıcı olarak silinsin mi? Bu işlem geri alınamaz; sohbet ve tablolar korunur.",
      )
    )
      return;
    try {
      await deleteConversationRuns(chosen, owner);
      setRuns([]);
      setRun(null);
      setConversations((old) =>
        old.filter((item) => item.conversation_id !== chosen),
      );
      setChosen(null);
      setListRevision((old) => old + 1);
      setIssue("");
    } catch (error) {
      setIssue(describeError(error));
    }
  }

  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const filters = { archived, search: search.trim() || undefined };
        let listed;
        let retained = true;
        try {
          listed = await listTraceConversations(owner, filters);
        } catch (error) {
          // An API older than this page has no trace index, and its 404 read as
          // "Oturum bulunamadı. API yeniden başlamış olabilir" - which is about
          // a session, not about a route that does not exist. The ordinary list
          // exists in every version; only deleted conversations are missing from
          // it, and the page says so. A 404 because the key is unknown fails
          // here too, and is reported as before.
          if (!(error instanceof ApiError && error.status === 404)) throw error;
          const plain = await listConversations(owner, filters);
          listed = {
            conversations: plain.conversations.map((item) => ({
              ...item,
              deleted: false,
            })),
          };
          retained = false;
        }
        if (cancelled) return;
        setListError(false);
        setPlainList(!retained);
        setIssue("");
        setConversations(listed.conversations);
        setChosen((current) =>
          listed.conversations.some((item) => item.conversation_id === current)
            ? current
            : (listed.conversations[0]?.conversation_id ?? null),
        );
      } catch (error) {
        if (!cancelled) {
          setListError(true);
          setIssue(describeError(error));
        }
      }
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [owner, archived, search, listRevision]);

  useEffect(() => {
    waited.current = 0;
  }, [initialTurn, chosen]);
  useEffect(() => {
    if (!chosen) {
      setRuns([]);
      setRun(null);
      setRunsState("ready");
      return;
    }
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    setRuns([]);
    setRun(null);
    setRunsState("loading");
    setAnswers({});
    setRatings([]);
    void (async () => {
      try {
        // The trace index can contain deleted chats: their normal GET is still
        // forbidden, but their retained runs remain owner-readable.
        const listed = await listRuns(chosen, owner);
        if (cancelled) return;
        setRuns(listed.runs);
        const wanted = initialTurn
          ? listed.runs.find((item) => item.turn_id === initialTurn)?.run_id
          : undefined;
        if (initialTurn && !wanted && waited.current < 40) {
          // Asked for one turn and its record is not written yet: wait for it
          // rather than open a different one (finding F4-iz-3). Older servers
          // write the row only when the turn ends, so the wait is bounded and
          // then the page says so instead of polling all afternoon.
          waited.current += 1;
          setRunsState("waiting");
          timer = setTimeout(() => {
            if (!cancelled) setRetry((old) => old + 1);
          }, 3000);
          return;
        }
        setRun(
          wanted ?? (initialTurn ? null : (listed.runs[0]?.run_id ?? null)),
        );
        setRunsState("ready");
        setIssue("");
        if (!chosenDeleted) {
          const [detail, feedback] = await Promise.all([
            openConversation(chosen, owner).catch(() => null),
            listFeedback(chosen, owner).catch(() => ({ feedback: [] })),
          ]);
          if (cancelled) return;
          if (detail)
            setAnswers(
              Object.fromEntries(
                detail.messages
                  .filter((message) => message.role === "assistant")
                  .map((message) => [message.turn_id, message.text]),
              ),
            );
          setRatings(feedback.feedback);
        }
      } catch {
        if (!cancelled) setRunsState("error");
      }
    })();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [chosen, owner, initialTurn, retry, chosenDeleted]);

  const current = runs.find((item) => item.run_id === run);
  //: Asked to watch one turn whose record never appeared: the list is this
  //: conversation's earlier runs, and none of them is that turn.
  const missedTurn = Boolean(initialTurn && !current && runsState === "ready");
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
              {item.deleted && (
                <small className="trace-deleted">Silinmiş sohbet</small>
              )}
              <small>
                {new Date(item.updated_at).toLocaleString("tr-TR")} ·{" "}
                {item.turns} soru
              </small>
            </button>
          ))}
          {listError && (
            <div className="chat-empty">
              Sohbetler okunamadı — yeniden dene
              <button
                type="button"
                className="trace-retry"
                onClick={() => setListRevision((old) => old + 1)}
              >
                Yeniden dene
              </button>
            </div>
          )}
          {conversations.length === 0 && !listError && (
            <p className="chat-empty">Sohbet yok.</p>
          )}
          {plainList && (
            <p className="helper">
              Bu sunucu sürümü silinmiş sohbetlerin izlerini listelemiyor; liste
              sohbetlerden okundu. Güncel koddan yeniden başlatınca silinmiş
              sohbetlerin izleri de burada görünür.
            </p>
          )}
        </nav>
        <nav className="traces-column" aria-label="Turlar">
          {chosen && runs.length > 0 && (
            <button
              type="button"
              className="trace-delete"
              onClick={() => void removeRuns()}
            >
              Bu sohbetin işlem kayıtlarını kalıcı sil
            </button>
          )}
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
          {chosen && runsState === "error" && (
            <div className="chat-empty">
              {runReadMessage(runsState, runs.length)}
              <button
                type="button"
                className="trace-retry"
                onClick={() => {
                  setRetry((old) => old + 1);
                  setListRevision((old) => old + 1);
                }}
              >
                Yeniden dene
              </button>
            </div>
          )}
          {chosen && (runsState === "loading" || runsState === "waiting") && (
            <p className="chat-empty">
              {runReadMessage(runsState, runs.length)}
            </p>
          )}
          {chosen && runsState === "ready" && runs.length === 0 && (
            <p className="chat-empty">
              {runReadMessage(runsState, runs.length)}
            </p>
          )}
        </nav>
        <div className="traces-main">
          {runsState === "waiting" ? (
            <p className="chat-empty">
              Bu turun kaydı henüz açılmadı. Tur çalışmaya başlayınca kaydı
              burada kendiliğinden açılacak; aşağıdaki liste bu sohbetin daha
              önceki turları.
            </p>
          ) : missedTurn ? (
            <p className="chat-empty">
              Bu turun kaydı hâlâ açılmadı. Tur bitince listede görünür;
              listeden bir tur seçebilirsin.
            </p>
          ) : current && chosen ? (
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
