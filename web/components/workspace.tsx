"use client";
import { useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronDown,
  CircleHelp,
  Database,
  FileText,
  Layers3,
  LoaderCircle,
  MessageSquare,
  Plus,
  RefreshCw,
  Send,
  Settings2,
  ShieldCheck,
  Sparkles,
  Table2,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ResultTable } from "@/components/result-table";
import { Panel } from "@/components/panel";
import { preparedTitle } from "@/lib/table";
import { noticeText } from "@/lib/language";
import {
  api,
  ApiError,
  admissionRejection,
  draftRequest,
  publishedResult,
  restoredSelection,
  admit,
  clearSession,
  describeError,
  loadSession,
  newSession,
  readTurn,
  saveSession,
  validQuestion,
  errorText,
} from "@/lib/client";
import {
  datasetSchema,
  healthSchema,
  type Dataset,
  type Health,
  type Saved,
  type Turn,
} from "@/lib/contracts";

const examples = [
  {
    tag: "KARŞILAŞTIR",
    title: "Kredi ile faiz aynı yönde mi?",
    question:
      "2021–2025 konut kredisi bakiyesi ile konut kredisi faizlerini aylık tabloda karşılaştır. Faiz düşerken kredinin artmadığı dönemleri göster.",
  },
  {
    tag: "DÖNÜŞTÜR",
    title: "Nominal artış mı, reel artış mı?",
    question:
      "2021–2025 konut kredisi bakiyesini aylık getir, TÜFE ile Aralık 2025 fiyatlarına göre enflasyondan arındır.",
  },
  {
    tag: "KEŞFET",
    title: "Hangi verilerle çalışabilirim?",
    question:
      "Hazır veri havuzunda konut kredileri ve fiyat endeksleri için hangi seriler var?",
  },
];
type Item = Saved["turns"][number] & { turn?: Turn };
export function Workspace() {
  const [health, setHealth] = useState<Health | null>(null),
    [dataset, setDataset] = useState<Dataset | null>(null);
  const [ready, setReady] = useState(false),
    [loading, setLoading] = useState(true),
    [connectionError, setConnectionError] = useState("");
  const [question, setQuestion] = useState(""),
    [items, setItems] = useState<Item[]>([]),
    [busy, setBusy] = useState(false),
    [issue, setIssue] = useState("");
  const [selected, setSelected] = useState<number>(-1),
    [panel, setPanel] = useState<"data" | "settings" | null>(null),
    [followSelected, setFollowSelected] = useState(true),
    [pendingIndex, setPendingIndex] = useState<number | null>(null);
  const pending = pendingIndex !== null;
  const saved = useRef<Saved | null>(null),
    busyRef = useRef(false),
    mounted = useRef(false),
    generation = useRef(0),
    recoveries = useRef<number[]>([]),
    chatEnd = useRef<HTMLDivElement>(null),
    input = useRef<HTMLTextAreaElement>(null);
  async function refresh() {
    setLoading(true);
    setConnectionError("");
    const results = await Promise.allSettled([
      api("health", healthSchema),
      api("dataset", datasetSchema),
    ]);
    if (!mounted.current) return;
    if (results[0].status === "fulfilled") setHealth(results[0].value);
    else {
      setHealth(null);
      setConnectionError(describeError(results[0].reason));
    }
    if (results[1].status === "fulfilled") setDataset(results[1].value);
    else {
      setDataset(null);
      setConnectionError(describeError(results[1].reason));
    }
    setLoading(false);
  }
  function record(value: Saved) {
    saveSession(sessionStorage, value);
    saved.current = value;
  }
  function chooseResult(index: number) {
    const result = publishedResult(items[index]?.turn);
    if (!ready || busyRef.current || pending || !result || !saved.current)
      return;
    try {
      record({ ...saved.current, view_result_id: result.result_ref });
      setSelected(index);
      setIssue("");
    } catch (error) {
      setIssue(describeError(error));
    }
  }
  function chooseMode(follow: boolean) {
    if (!ready || busyRef.current || pending) return;
    try {
      if (saved.current) record({ ...saved.current, follow_selected: follow });
      setFollowSelected(follow);
      setIssue("");
    } catch (error) {
      setIssue(describeError(error));
    }
  }
  function update(index: number, turn: Turn, selectResult = false) {
    const result = publishedResult(turn);
    if (selectResult && result && saved.current) {
      record({ ...saved.current, view_result_id: result.result_ref });
      setSelected(index);
    }
    setItems((old) =>
      old.map((item, i) => (i === index ? { ...item, turn } : item)),
    );
  }
  function recovered(index: number) {
    recoveries.current = recoveries.current.filter(
      (pending) => pending !== index,
    );
    setPendingIndex(recoveries.current[0] ?? null);
  }
  async function watch(index: number, canAdmit: boolean) {
    const state = saved.current;
    if (!state || !state.turns[index] || busyRef.current) return;
    const epoch = generation.current;
    const active = () => mounted.current && generation.current === epoch;
    const entry = state.turns[index];
    busyRef.current = true;
    setBusy(true);
    setPendingIndex(index);
    setIssue("");
    try {
      let turn = canAdmit
        ? await admit(state, index)
        : await readTurn(state.session, entry.turn_id!, entry.request_id);
      if (!active()) return;
      const next = {
        ...state,
        turns: state.turns.map((entry, i) =>
          i === index ? { ...entry, turn_id: turn.turn_id } : entry,
        ),
      };
      record(next);
      update(index, turn, true);
      const deadline = Date.now() + 10 * 60 * 1000;
      while (turn.state !== "completed" && turn.state !== "failed") {
        if (Date.now() > deadline) {
          setIssue(
            "İşlem hâlâ devam ediyor olabilir. Aynı işlemin durumunu yeniden alabilirsin; yeni analiz başlatılmadı.",
          );
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, 1000));
        if (!active()) return;
        turn = await readTurn(next.session, turn.turn_id, entry.request_id);
        if (!active()) return;
        update(index, turn, true);
      }
      recovered(index);
    } catch (error) {
      if (!active()) return;
      const rejection = admissionRejection(error);
      if (rejection && !saved.current?.turns[index].turn_id) {
        try {
          record({
            ...saved.current!,
            turns: saved.current!.turns.map((entry, i) =>
              i === index ? { ...entry, admission_error: rejection } : entry,
            ),
          });
          setItems((old) =>
            old.map((item, i) =>
              i === index ? { ...item, admission_error: rejection } : item,
            ),
          );
          recovered(index);
        } catch (storageError) {
          setIssue(describeError(storageError));
          return;
        }
      }
      setIssue(describeError(error));
    } finally {
      if (active()) {
        busyRef.current = false;
        setBusy(false);
      }
    }
  }
  useEffect(() => {
    mounted.current = true;
    const epoch = ++generation.current;
    const active = () => mounted.current && generation.current === epoch;
    void refresh();
    const stored = loadSession(sessionStorage);
    saved.current = stored;
    if (stored) {
      setFollowSelected(stored.follow_selected ?? true);
      setItems(stored.turns.map((entry) => ({ ...entry })));
      void (async () => {
        const resume: number[] = [];
        const restored: (Turn | undefined)[] = [];
        for (let i = 0; i < stored.turns.length; i++) {
          const entry = stored.turns[i];
          if (entry.admission_error) continue;
          if (!entry.turn_id) {
            resume.push(i);
            continue;
          }
          try {
            const turn = await readTurn(
              stored.session,
              entry.turn_id,
              entry.request_id,
            );
            if (!active()) return;
            restored[i] = turn;
            update(i, turn);
            if (!["completed", "failed"].includes(turn.state)) resume.push(i);
          } catch (error) {
            if (!active()) return;
            setIssue(describeError(error));
            resume.push(i);
          }
        }
        if (!active()) return;
        const index = restoredSelection(stored, restored);
        try {
          if (index >= 0)
            record({
              ...stored,
              view_result_id: publishedResult(restored[index])!.result_ref,
            });
          else if (stored.view_result_id && resume.length === 0)
            setIssue(errorText.selection_unavailable);
          setSelected(index);
        } catch (error) {
          setIssue(describeError(error));
        }
        recoveries.current = resume;
        setPendingIndex(resume[0] ?? null);
        setReady(true);
      })();
    } else setReady(true);
    return () => {
      mounted.current = false;
      generation.current++;
    };
  }, []);
  useEffect(() => {
    if (items.length) {
      const body = chatEnd.current?.parentElement;
      if (body) body.scrollTop = body.scrollHeight;
    }
  }, [items, busy]);
  async function submit() {
    if (
      busyRef.current ||
      pending ||
      !validQuestion(question) ||
      !health ||
      !dataset ||
      !ready
    )
      return;
    const epoch = generation.current;
    const active = () => mounted.current && generation.current === epoch;
    busyRef.current = true;
    setBusy(true);
    setIssue("");
    try {
      let state = saved.current;
      if (!state) {
        const session = await newSession();
        if (!active()) return;
        state = { session, turns: [], follow_selected: followSelected };
        record(state);
      }
      if (state.turns.length >= 24) {
        setIssue(
          "Bu oturum 24 soruluk sınırına ulaştı. Yeni çalışma açabilirsin.",
        );
        return;
      }
      const source = items[selected]?.turn;
      if (followSelected && state.view_result_id && !publishedResult(source))
        throw new ApiError("selection_unavailable");
      const entry = draftRequest(question, followSelected ? source : undefined);
      const next = { ...state, turns: [...state.turns, entry] };
      record(next);
      setItems((old) => [...old, entry]);
      setQuestion("");
      recoveries.current = [next.turns.length - 1];
      setPendingIndex(next.turns.length - 1);
      busyRef.current = false;
      await watch(next.turns.length - 1, true);
    } catch (error) {
      if (active()) setIssue(describeError(error));
    } finally {
      if (active()) {
        busyRef.current = false;
        setBusy(false);
      }
    }
  }
  function resetView() {
    if (busyRef.current || !ready) return;
    if (
      pending &&
      !window.confirm(
        "Bekleyen isteğin kurtarma kaydı bu sekmeden kaldırılacak. Sunucudaki işlem iptal edilmez. Yeni çalışma açılsın mı?",
      )
    )
      return;
    try {
      clearSession(sessionStorage);
    } catch (error) {
      setIssue(describeError(error));
      return;
    }
    generation.current++;
    saved.current = null;
    recoveries.current = [];
    setItems([]);
    setPendingIndex(null);
    setSelected(-1);
    setFollowSelected(true);
    setIssue("");
    setQuestion("");
  }
  const versions = items.flatMap((item, index) =>
    publishedResult(item.turn) ? [{ index, item }] : [],
  );
  const result = publishedResult(items[selected]?.turn);
  function sourceLabel(reference?: string) {
    if (!reference) return "Serbest soru";
    const index = items.findIndex(
      (item) => publishedResult(item.turn)?.result_ref === reference,
    );
    return index >= 0
      ? `Kaynak tablo: Analiz ${index + 1}`
      : "Kaynak tablo yüklenemedi";
  }
  const current = items.at(-1)?.turn;
  const number = (value: number) => value.toLocaleString("tr-TR");
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="/" aria-label="DataTrio çalışma alanı">
          <span className="brand-mark">
            <i />
            <i />
            <i />
          </span>
          <span>
            DataTrio<span className="brand-sub">FINANCIAL INTELLIGENCE</span>
          </span>
        </a>
        <div className="workspace-label">ÇALIŞMA ALANI</div>
        <button className="nav-item active" onClick={() => setPanel(null)}>
          <MessageSquare size={18} /> Analiz stüdyosu{" "}
          <span className="nav-dot" />
        </button>
        <button
          className={`nav-item ${panel === "data" ? "chosen" : ""}`}
          onClick={() => setPanel("data")}
        >
          <Database size={18} /> Veri havuzu{" "}
          <span className="nav-count">
            {dataset?.prepared_identities ?? "—"}
          </span>
        </button>
        <button
          className={`nav-item ${panel === "settings" ? "chosen" : ""}`}
          onClick={() => setPanel("settings")}
        >
          <Settings2 size={18} /> Çalışma ayarları
        </button>
        <div className="sidebar-bottom">
          <div className="trust-icon">
            <ShieldCheck size={20} />
          </div>
          <strong>Her sayının bir izi var.</strong>
          <p>
            Kontrollü araçlar.
            <br />
            İzlenebilir hesaplamalar.
          </p>
          <div className="sidebar-event">
            KKB HACKATHON <span>2026</span>
          </div>
        </div>
      </aside>
      <main className="main-shell">
        <header className="topbar">
          <div>
            <span className="breadcrumb">Çalışma alanı</span>
            <span className="slash">/</span>
            <strong>Analiz stüdyosu</strong>
          </div>
          <div className="topbar-right">
            <span className={`connection ${health ? "online" : "offline"}`}>
              <i />
              {loading
                ? "Bağlanıyor"
                : health
                  ? "Yerel servis hazır"
                  : "Servis kapalı"}
            </span>
            <span className="avatar">A</span>
          </div>
        </header>
        {health?.execution_mode === "scripted" && (
          <div className="rehearsal">
            <FileText size={15} />
            <strong>Çevrimdışı prova</strong>
            <span>
              Yanıt planları test senaryosundan gelir. Canlı Qwen kullanılmıyor.
            </span>
          </div>
        )}
        <section className="page-heading">
          <div>
            <div className="eyebrow">
              <span /> FİNANSAL ANALİZ ÇALIŞMA ALANI
            </div>
            <h1>
              İyi sorular. <span>İzlenebilir cevaplar.</span>
            </h1>
            <p>
              Hazır verileri keşfet, karşılaştır ve aynı tablo üzerinde analizi
              derinleştir.
            </p>
          </div>
          <Button
            variant="outline"
            onClick={resetView}
            disabled={busy || !ready}
          >
            <Plus size={16} /> Yeni çalışma
          </Button>
        </section>
        <section className="data-bar" aria-label="Hazır veri durumu">
          <div className="data-bar-title">
            <span className="data-icon">
              <Database size={20} />
            </span>
            <span>
              <strong>Hazır veri havuzu</strong>
              <small>
                {dataset
                  ? "BDDK & TCMB EVDS · Yerel kopya"
                  : "Bağlantı bekleniyor"}
              </small>
            </span>
          </div>
          <div className="data-stat">
            <strong>
              {dataset ? number(dataset.prepared_identities) : "—"}
            </strong>
            <span>hazır seri</span>
          </div>
          <div className="data-stat">
            <strong>{dataset ? number(dataset.observation_rows) : "—"}</strong>
            <span>gözlem</span>
          </div>
          <div className="data-stat">
            <strong>
              {dataset ? number(dataset.catalog_identities) : "—"}
            </strong>
            <span>katalog kaydı</span>
          </div>
          <button className="text-action" onClick={() => setPanel("data")}>
            Kapsamı incele <ArrowUpRight size={16} />
          </button>
        </section>
        {connectionError && (
          <div className="connection-alert" role="status">
            <span>{connectionError}</span>
            <Button
              size="sm"
              variant="outline"
              disabled={loading}
              onClick={() => void refresh()}
            >
              <RefreshCw size={14} /> Yeniden bağlan
            </Button>
          </div>
        )}
        <div className="analysis-grid">
          <section className="conversation-card">
            <div className="card-heading">
              <span>
                <Sparkles size={17} /> Analist
              </span>
              <span className="mini-tag">
                {health?.execution_mode === "scripted" ? "PROVA" : "KLOUDEKS"}
              </span>
            </div>
            <div className="conversation-body">
              {!items.length ? (
                <div className="welcome">
                  <div className="welcome-symbol">
                    <Layers3 size={27} />
                  </div>
                  <h2>Neyi inceleyelim?</h2>
                  <p>
                    Bir dönem, bir ölçü, bir soru.
                    <br />
                    Analizin buradan başlasın.
                  </p>
                  <div className="suggestions">
                    {examples.map((example) => (
                      <button
                        key={example.tag}
                        onClick={() => {
                          setQuestion(example.question);
                          input.current?.focus();
                        }}
                      >
                        <small>{example.tag}</small>
                        <span>
                          {example.title}
                          <ArrowRight size={15} />
                        </span>
                      </button>
                    ))}
                  </div>
                  <div className="welcome-tip">
                    <CircleHelp size={15} />
                    <span>
                      Sorunda dönemi ve ölçüyü belirtmen doğru veriyi seçmeye
                      yardımcı olur.
                    </span>
                  </div>
                </div>
              ) : (
                <div className="messages">
                  {items.map((item, index) => (
                    <article className="turn" key={item.request_id}>
                      <div className="question-label">
                        SEN <span>{String(index + 1).padStart(2, "0")}</span>
                      </div>
                      <p className="user-question">{item.question}</p>
                      <p className="request-source">
                        {sourceLabel(item.selected_result_id)}
                      </p>
                      <div className="answer-label">
                        <span className="small-brand">
                          <Layers3 size={13} />
                        </span>{" "}
                        DATATRIO{" "}
                        {item.turn?.answer && (
                          <span
                            className={`verdict ${item.turn.answer.status}`}
                          >
                            {
                              {
                                accepted: "Kontrolden geçti",
                                qualified: "Sınırlı yanıt",
                                abstained: "Netleştirme gerekli",
                              }[item.turn.answer.status]
                            }
                          </span>
                        )}
                      </div>
                      {item.turn?.answer ? (
                        <>
                          <p className="answer-text">{item.turn.answer.text}</p>
                          {item.turn.answer.notices.length > 0 && (
                            <details
                              className="notice-details"
                              open={item.turn.answer.status !== "accepted"}
                            >
                              <summary>
                                Kapsam ve kontrol notları (
                                {item.turn.answer.notices.length})
                              </summary>
                              {item.turn.answer.notices.map((notice, i) => (
                                <p key={i} className="notice">
                                  {noticeText(notice)}
                                </p>
                              ))}
                            </details>
                          )}
                          {item.turn.answer.omitted_claims > 0 && (
                            <p className="notice">
                              {item.turn.answer.omitted_claims} desteklenmeyen
                              ifade yanıta alınmadı.
                            </p>
                          )}
                          {item.turn.answer.result && (
                            <button
                              className={`result-link ${selected === index ? "selected" : ""}`}
                              onClick={() => chooseResult(index)}
                              disabled={!ready || busy || pending}
                            >
                              <Table2 size={17} />
                              <span>
                                Analiz {index + 1}
                                <small>
                                  {item.turn.answer.result.cells.length} kayıtlı
                                  değer
                                </small>
                              </span>
                              <ArrowUpRight size={16} />
                            </button>
                          )}
                        </>
                      ) : item.turn?.state === "failed" ||
                        item.admission_error ? (
                        <p className="notice">
                          {errorText[
                            item.admission_error ??
                              item.turn?.error ??
                              "internal_error"
                          ] ?? errorText.internal_error}
                        </p>
                      ) : (
                        <p className="working">
                          <LoaderCircle
                            size={15}
                            className={busy ? "spin" : ""}
                          />
                          {busy
                            ? item.turn?.state === "running"
                              ? "Analiz çalışıyor…"
                              : "İstek iletiliyor…"
                            : "Durum yeniden alınabilir."}
                        </p>
                      )}
                    </article>
                  ))}
                </div>
              )}
              <div ref={chatEnd} />
            </div>
            {issue && (
              <div className="request-issue" role="alert">
                <p>{issue}</p>
                {pending && (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busy}
                    onClick={() => void watch(pendingIndex ?? 0, true)}
                  >
                    <RefreshCw size={14} /> Aynı isteğin durumunu al
                  </Button>
                )}
              </div>
            )}
            {pending && !busy && !issue && (
              <div className="request-issue">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => void watch(pendingIndex ?? 0, true)}
                >
                  Bekleyen isteğe devam et
                </Button>
              </div>
            )}
            <form
              className="composer"
              onSubmit={(e) => {
                e.preventDefault();
                void submit();
              }}
            >
              <div className="selection-context" aria-live="polite">
                <label>
                  <input
                    type="checkbox"
                    checked={followSelected}
                    disabled={!ready || busy || pending}
                    onChange={(e) => chooseMode(e.target.checked)}
                  />
                  Seçili tabloyla devam et
                </label>
                <span>
                  {pending
                    ? sourceLabel(items[pendingIndex!]?.selected_result_id)
                    : followSelected && result
                      ? `Kaynak tablo: Analiz ${selected + 1}`
                      : followSelected && saved.current?.view_result_id
                        ? "Devam etmek için kaynak tabloyu seç"
                        : "Serbest soru · belirli bir tabloya sabitlenmez"}
                </span>
              </div>
              <textarea
                ref={input}
                aria-label="Finansal sorunuz"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder={
                  items.length
                    ? "Bu analizi nasıl derinleştirelim?"
                    : "Finansal sorunu yaz…"
                }
                maxLength={4096}
                disabled={busy || pending}
                onKeyDown={(e) => {
                  if (
                    e.key === "Enter" &&
                    !e.shiftKey &&
                    !e.nativeEvent.isComposing
                  ) {
                    e.preventDefault();
                    void submit();
                  }
                }}
              />
              <div className="composer-actions">
                <span>
                  {busy ? (
                    <>
                      <LoaderCircle size={13} className="spin" /> Çalışıyor
                    </>
                  ) : (
                    <>
                      Enter gönderir <span>·</span> Shift + Enter yeni satır
                    </>
                  )}
                </span>
                <Button
                  type="submit"
                  size="icon"
                  aria-label="Soruyu gönder"
                  disabled={
                    !ready ||
                    !health ||
                    !dataset ||
                    busy ||
                    pending ||
                    !validQuestion(question)
                  }
                >
                  <Send size={17} />
                </Button>
              </div>
            </form>
            <div className="composer-footnote">
              <ShieldCheck size={12} /> Hesaplar araçlarla yapılır, cevaplar
              kontrol edilir.
            </div>
          </section>
          <section className="results-card">
            <div className="card-heading">
              <span>
                <Table2 size={17} /> Analiz sonuçları
              </span>
              {versions.length > 0 ? (
                <label className="version-select">
                  <select
                    aria-label="Sonuç sürümü"
                    value={selected}
                    onChange={(e) => chooseResult(Number(e.target.value))}
                    disabled={!ready || busy || pending}
                  >
                    {selected < 0 && <option value={-1}>Sonuç seç</option>}
                    {versions.map(({ index }) => (
                      <option key={index} value={index}>
                        Analiz {index + 1}
                        {index === versions.at(-1)?.index
                          ? " · son sonuç"
                          : " · önceki sonuç"}
                      </option>
                    ))}
                  </select>
                  <ChevronDown size={14} />
                </label>
              ) : (
                <span className="mini-tag subtle">ÇALIŞMA TABLOSU</span>
              )}
            </div>
            {result ? (
              <>
                <div className="result-intro">
                  <div>
                    <span className="result-kicker">YAYIMLANAN SONUÇ</span>
                    <h2>Analiz {selected + 1}</h2>
                  </div>
                  <span className="verified-pill">
                    <Check size={14} /> Kayıtlı tablo
                  </span>
                </div>
                <ResultTable
                  key={result.result_ref}
                  result={result}
                  dataset={dataset}
                />
              </>
            ) : (
              <div className="result-empty">
                <div className="empty-visual">
                  <div className="visual-top">
                    <span />
                    <span />
                    <span />
                  </div>
                  <div className="visual-grid">
                    {Array.from({ length: 15 }, (_, i) => (
                      <i key={i} />
                    ))}
                  </div>
                  <div className="visual-badge">
                    <ShieldCheck size={23} />
                  </div>
                </div>
                <h2>
                  Sorudan tabloya,
                  <br />
                  her adım izlenebilir.
                </h2>
                <p>
                  Analizin tamamlandığında kayıtlı değerler burada görünür.
                  Sonraki sorularınla aynı tabloyu geliştirebilirsin.
                </p>
                <div className="empty-steps">
                  <span>
                    <Database size={16} /> Veriyi bul
                  </span>
                  <ArrowRight size={12} />
                  <span>
                    <Activity size={16} /> Hesapla
                  </span>
                  <ArrowRight size={12} />
                  <span>
                    <ShieldCheck size={16} /> Kontrol et
                  </span>
                </div>
              </div>
            )}
            <div className="results-bottom">
              <span>
                <span className="tiny-dot" />{" "}
                {result
                  ? "Değerler yayımlanmış sonuçtan gösteriliyor"
                  : "Henüz yayımlanmış sonuç yok"}
              </span>
              <span>DataTrio / 2026</span>
            </div>
          </section>
        </div>
        <footer className="page-footer">
          <span>Model yorumlar. Araçlar hesaplar. Harness kontrol eder.</span>
          <span>
            {current?.events.length
              ? `Son işlem: ${(current.events.at(-1)!.elapsed_ms / 1000).toLocaleString("tr-TR")} sn`
              : "Yerel çalışma alanı"}
          </span>
        </footer>
      </main>
      {panel && (
        <Panel onClose={() => setPanel(null)}>
          <section
            className="info-panel"
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => {
              if (e.key === "Escape") setPanel(null);
            }}
          >
            <div className="panel-header">
              <span className="eyebrow">ÇALIŞMA ALANI</span>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Paneli kapat"
                autoFocus
                onClick={() => setPanel(null)}
              >
                <X size={19} />
              </Button>
            </div>
            <h2 id="panel-title">
              {panel === "data" ? "Veri havuzu" : "Çalışma ayarları"}
            </h2>
            {panel === "data" ? (
              <>
                <p className="panel-description">
                  Bu oturumun başlangıçta hazırlanan veri kopyası. Katalogda
                  bulunan her seri bu havuza indirilmiş olmayabilir.
                </p>
                <div className="panel-stat">
                  <strong>
                    {dataset?.prepared_identities ?? "—"} /{" "}
                    {dataset?.catalog_identities ?? "—"}
                  </strong>
                  <span>hazır seri / katalog kaydı</span>
                  <small>
                    {dataset
                      ? `${(dataset.pool_bytes / 1024 / 1024).toLocaleString("tr-TR", { maximumFractionDigits: 2 })} MiB · ${dataset.files} dosya`
                      : "Veri bilgisi alınamadı"}
                  </small>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={loading}
                  onClick={() => void refresh()}
                >
                  <RefreshCw size={14} /> Durumu yeniden al
                </Button>
                <p className="helper">
                  Bu düğme BDDK / EVDS’den yeni veri çekmez.
                </p>
                <div className="series-list">
                  {dataset?.series.map((series) => (
                    <article key={series.series_id}>
                      <span className="series-source">
                        {series.series_id.startsWith("EVDS:")
                          ? "TCMB EVDS"
                          : "BDDK"}
                      </span>
                      <h3>{preparedTitle(series.title)}</h3>
                      <p>
                        {series.first_period ?? "?"} <ArrowRight size={12} />{" "}
                        {series.last_period ?? "?"}
                      </p>
                      <small>
                        {series.nonnull_observations} dolu gözlem /{" "}
                        {series.observations} kayıt
                      </small>
                      <details>
                        <summary>Seri kimliği</summary>
                        <code>{series.series_id}</code>
                      </details>
                    </article>
                  ))}
                </div>
                <p className="helper">
                  Başlangıç ve bitiş tarihi, aradaki tüm dönemlerin eksiksiz
                  olduğu anlamına gelmez. Uygunluk analiz sırasında ayrıca
                  kontrol edilir.
                </p>
              </>
            ) : (
              <>
                <p className="panel-description">
                  Bu sürümde ayarlar bilgi amaçlıdır. Model, araç ve doğrulama
                  kuralları uygulamanın yapılandırmasında yönetilir.
                </p>
                <dl className="settings-list">
                  <div>
                    <dt>Model yolu</dt>
                    <dd>
                      {health?.execution_mode === "scripted"
                        ? "Çevrimdışı test senaryosu"
                        : "Yalnız Kloudeks"}
                    </dd>
                  </div>
                  <div>
                    <dt>Canlı model testi</dt>
                    <dd>Bu ekranda doğrulanmadı</dd>
                  </div>
                  <div>
                    <dt>Aynı anda çalışan analiz</dt>
                    <dd>{health?.max_running_turns ?? "—"}</dd>
                  </div>
                  <div>
                    <dt>Oturum başına soru</dt>
                    <dd>{health?.max_turns_per_session ?? "—"}</dd>
                  </div>
                  <div>
                    <dt>Tarayıcı oturumu</dt>
                    <dd>Bu sekmeye özel</dd>
                  </div>
                  <div>
                    <dt>Kayıtlı veri kopyası</dt>
                    <dd>Oturumlar arasında ayrılır</dd>
                  </div>
                </dl>
                <div className="panel-callout">
                  <ShieldCheck size={20} />
                  <p>
                    Doğrulama ve güvenlik kontrolleri model tercihine bağlı
                    değildir.
                  </p>
                </div>
                <p className="helper">
                  API yeniden başlatılınca tarayıcı oturumu geçersiz olur. Yeni
                  çalışma açmak önceki hesap dosyalarını silmez. Gelişmiş agent
                  davranışı ayarları sonraki geliştirmedir.
                </p>
              </>
            )}
          </section>
        </Panel>
      )}
    </div>
  );
}
