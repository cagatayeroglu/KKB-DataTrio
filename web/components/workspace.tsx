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
  Archive,
  ArchiveRestore,
  BookOpen,
  MessagesSquare,
  Paperclip,
  Pencil,
  Plus,
  Search,
  RefreshCw,
  Send,
  Settings2,
  ShieldCheck,
  Sparkles,
  Square,
  Table2,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ResultTable } from "@/components/result-table";
import { Panel } from "@/components/panel";
import { TracePanel } from "@/components/trace-panel";
import { AnswerFeedback } from "@/components/answer-feedback";
import {
  KnowledgePanel,
  type ChatDocument,
} from "@/components/knowledge-panel";
import { preparedTitle } from "@/lib/table";
import { noticeText } from "@/lib/language";
import {
  api,
  ApiError,
  DOCUMENT_ACCEPT,
  admissionRejection,
  cancelTurn,
  draftRequest,
  publishedResult,
  restoredSelection,
  admit,
  clearSession,
  describeError,
  usableOwner,
  listConversations,
  listFeedback,
  loadSession,
  newSession,
  openConversation,
  updateConversation,
  readTurn,
  saveSession,
  uploadDocument,
  validQuestion,
  errorText,
} from "@/lib/client";
import {
  datasetSchema,
  healthSchema,
  type ConversationSummary,
  type Dataset,
  type Feedback,
  type DocumentAdmitted,
  type Health,
  type Saved,
  type StoredMessage,
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
    [panel, setPanel] = useState<"data" | "knowledge" | "settings" | null>(
      null,
    ),
    [pendingIndex, setPendingIndex] = useState<number | null>(null),
    [attachment, setAttachment] = useState<DocumentAdmitted | null>(null),
    [dragging, setDragging] = useState(false),
    [uploading, setUploading] = useState(false),
    [stopping, setStopping] = useState(false);
  // Conversations that outlive this tab: the browser's own key lists and reopens them.
  const [ownerToken, setOwnerToken] = useState<string | null>(null),
    [conversations, setConversations] = useState<ConversationSummary[]>([]),
    [conversationId, setConversationId] = useState<string | null>(null),
    [transcript, setTranscript] = useState<StoredMessage[]>([]),
    [restoredResult, setRestoredResult] = useState<string | null>(null),
    [chatSearch, setChatSearch] = useState(""),
    [showArchived, setShowArchived] = useState(false),
    [renaming, setRenaming] = useState<string | null>(null),
    [tracing, setTracing] = useState<{
      runId?: string;
      turnId?: string;
    } | null>(null),
    [ratings, setRatings] = useState<Record<string, Feedback>>({});
  const history =
    health?.capabilities.includes("conversation_history") ?? false;
  const pending = pendingIndex !== null;
  const uploads = health?.capabilities.includes("document_upload") ?? false;
  const ocr = health?.capabilities.includes("document_ocr") ?? false;
  const acquisition =
    health?.capabilities.includes("official_acquisition") ?? false;
  const webSearch = health?.capabilities.includes("web_search") ?? false;
  const knowledgeBase =
    health?.capabilities.includes("knowledge_base") ?? false;
  const saved = useRef<Saved | null>(null),
    busyRef = useRef(false),
    mounted = useRef(false),
    generation = useRef(0),
    recoveries = useRef<number[]>([]),
    chatEnd = useRef<HTMLDivElement>(null),
    input = useRef<HTMLTextAreaElement>(null),
    picker = useRef<HTMLInputElement>(null);
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
  async function refreshConversations(token = ownerToken) {
    if (!token) return;
    try {
      const listed = await listConversations(token, {
        archived: showArchived,
        search: chatSearch.trim() || undefined,
      });
      if (mounted.current) setConversations(listed.conversations);
    } catch (error) {
      if (mounted.current) setIssue(describeError(error));
    }
  }
  async function session(token = ownerToken) {
    // One conversation per chat; its id is also the session the turn routes use.
    const state = saved.current;
    if (state) return state;
    const created = await newSession(token ?? undefined);
    const next: Saved = {
      session: created,
      turns: [],
    };
    record(next);
    setConversationId(created.session_id);
    void refreshConversations(token);
    return next;
  }
  function startChat() {
    if (busyRef.current || pending || !ready) return;
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
    setTranscript([]);
    setRestoredResult(null);
    setConversationId(null);
    setRatings({});
    setPendingIndex(null);
    setSelected(-1);
    setAttachment(null);
    setQuestion("");
    setIssue("");
  }
  async function openChat(id: string) {
    if (busyRef.current || pending || !ready || !ownerToken) return;
    setIssue("");
    try {
      const detail = await openConversation(id, ownerToken);
      if (!mounted.current) return;
      generation.current++;
      recoveries.current = [];
      // The owner key opens this conversation's turn routes too; no second secret.
      record({
        session: {
          api_version: 1,
          session_id: id,
          token: ownerToken,
          survives_restart: true,
        },
        turns: [],
      });
      setConversationId(id);
      setTranscript(detail.messages);
      try {
        const rated = await listFeedback(id, ownerToken);
        if (mounted.current)
          setRatings(
            Object.fromEntries(
              rated.feedback.map((item) => [item.turn_id, item]),
            ),
          );
      } catch {
        // Ratings are supporting information; a chat still opens without them.
      }
      const answered = [...detail.messages]
        .reverse()
        .find((message) => message.result_ref);
      setRestoredResult(answered?.result_ref ?? null);
      setItems([]);
      setSelected(-1);
      setPendingIndex(null);
      setAttachment(null);
      setQuestion("");
    } catch (error) {
      if (mounted.current) setIssue(describeError(error));
    }
  }
  async function renameChat(id: string, title: string) {
    if (!ownerToken || !title.trim()) return setRenaming(null);
    try {
      await updateConversation(id, ownerToken, {
        title: title.trim().slice(0, 120),
      });
      await refreshConversations();
    } catch (error) {
      setIssue(describeError(error));
    }
    setRenaming(null);
  }
  async function archiveChat(id: string, archived: boolean) {
    if (!ownerToken) return;
    try {
      await updateConversation(id, ownerToken, { archived });
      if (id === conversationId && archived) startChat();
      await refreshConversations();
    } catch (error) {
      setIssue(describeError(error));
    }
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
            if (error instanceof ApiError && error.status === 404) {
              // The server no longer has this tab's session (restarted, or a new
              // state root). Broken turns would only mislead: start clean and say so.
              try {
                clearSession(sessionStorage);
              } catch {
                // Nothing stored to clear.
              }
              saved.current = null;
              setItems([]);
              setPendingIndex(null);
              setSelected(-1);
              setIssue(errorText.session_gone);
              setReady(true);
              return;
            }
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
    if (!history) return;
    let cancelled = false;
    void (async () => {
      try {
        // A key this server does not know (another state root) is replaced, not shown as an error.
        const token = await usableOwner(localStorage);
        if (cancelled || !mounted.current) return;
        setOwnerToken(token);
        await refreshConversations(token);
      } catch (error) {
        if (!cancelled && mounted.current) setIssue(describeError(error));
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [history, showArchived, chatSearch]);
  useEffect(() => {
    if (items.length) {
      const body = chatEnd.current?.parentElement;
      if (body) body.scrollTop = body.scrollHeight;
    }
  }, [items, busy]);
  async function attach(file: File | undefined) {
    if (!file || !uploads || busyRef.current || pending || !ready) return;
    busyRef.current = true;
    setUploading(true);
    setIssue("");
    try {
      const state = await session();
      setAttachment(await uploadDocument(state.session, file));
    } catch (error) {
      setIssue(describeError(error));
    } finally {
      busyRef.current = false;
      if (mounted.current) setUploading(false);
      if (picker.current) picker.current.value = "";
    }
  }
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
      const state = await session();
      if (!active()) return;
      if (state.turns.length >= 24) {
        setIssue(
          "Bu oturum 24 soruluk sınırına ulaştı. Yeni çalışma açabilirsin.",
        );
        return;
      }
      // No table is pinned from here: the planner is shown every table this
      // conversation published, and whether a message continues the previous
      // request is the agent's reading, not a control the person operates.
      const entry = draftRequest(
        question,
        undefined,
        undefined,
        attachment ?? undefined,
      );
      const next = { ...state, turns: [...state.turns, entry] };
      record(next);
      setItems((old) => [...old, entry]);
      setQuestion("");
      setAttachment(null);
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
  async function stop() {
    const state = saved.current;
    const turnId =
      pendingIndex === null ? undefined : items[pendingIndex]?.turn?.turn_id;
    if (!state || !turnId) return;
    setStopping(true);
    try {
      // Accepted, not immediate: the running turn is polled until it stops.
      await cancelTurn(state.session.session_id, state.session.token, turnId);
    } catch (error) {
      setIssue(describeError(error));
    } finally {
      setStopping(false);
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
    setIssue("");
    setQuestion("");
  }
  const versions = items.flatMap((item, index) =>
    publishedResult(item.turn) ? [{ index, item }] : [],
  );
  const result = publishedResult(items[selected]?.turn);
  // Tables this conversation published, this tab's turns and the reopened ones:
  // what the agent may reach for without being pointed at it.
  // Documents this conversation uploaded, offered to the knowledge-base form.
  const chatDocuments: ChatDocument[] = saved.current
    ? [
        ...new Set(
          items.flatMap((item) =>
            item.document_ref ? [item.document_ref] : [],
          ),
        ),
      ].map((ref, index) => ({
        sessionId: saved.current!.session.session_id,
        ref,
        label: `Belge ${index + 1}`,
      }))
    : [];
  const contextTables =
    versions.length + transcript.filter((message) => message.result_ref).length;
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
        {history && (
          <section className="chat-list" aria-label="Sohbetler">
            <Button
              variant="outline"
              className="new-chat"
              onClick={startChat}
              disabled={!ready || busy || pending}
            >
              <Plus size={15} /> Yeni sohbet
            </Button>
            <label className="chat-search">
              <Search size={13} />
              <input
                value={chatSearch}
                onChange={(event) => setChatSearch(event.target.value)}
                placeholder="Sohbetlerde ara"
                maxLength={120}
                aria-label="Sohbetlerde ara"
              />
            </label>
            <button
              type="button"
              className="chat-toggle"
              onClick={() => setShowArchived((value) => !value)}
            >
              {showArchived ? (
                <ArchiveRestore size={13} />
              ) : (
                <Archive size={13} />
              )}
              {showArchived ? "Arşivdekiler" : "Arşivi göster"}
            </button>
            <div className="chat-items">
              {conversations.length === 0 && (
                <p className="chat-empty">
                  {showArchived ? "Arşivde sohbet yok." : "Henüz sohbet yok."}
                </p>
              )}
              {conversations.map((item) => (
                <div
                  key={item.conversation_id}
                  className={`chat-item ${item.conversation_id === conversationId ? "active" : ""}`}
                >
                  {renaming === item.conversation_id ? (
                    <input
                      autoFocus
                      defaultValue={item.title}
                      maxLength={120}
                      aria-label="Sohbet adı"
                      onBlur={(event) =>
                        void renameChat(
                          item.conversation_id,
                          event.target.value,
                        )
                      }
                      onKeyDown={(event) => {
                        if (event.key === "Enter")
                          void renameChat(
                            item.conversation_id,
                            event.currentTarget.value,
                          );
                        if (event.key === "Escape") setRenaming(null);
                      }}
                    />
                  ) : (
                    <>
                      <button
                        type="button"
                        className="chat-open"
                        onClick={() => void openChat(item.conversation_id)}
                        disabled={busy || pending}
                      >
                        <MessagesSquare size={14} />
                        <span>
                          {item.title}
                          <small>
                            {new Date(item.updated_at).toLocaleDateString(
                              "tr-TR",
                            )}{" "}
                            · {item.turns} tur
                          </small>
                        </span>
                      </button>
                      <button
                        type="button"
                        aria-label="Sohbeti yeniden adlandır"
                        onClick={() => setRenaming(item.conversation_id)}
                      >
                        <Pencil size={12} />
                      </button>
                      <button
                        type="button"
                        aria-label={
                          item.archived ? "Arşivden çıkar" : "Sohbeti arşivle"
                        }
                        onClick={() =>
                          void archiveChat(item.conversation_id, !item.archived)
                        }
                      >
                        {item.archived ? (
                          <ArchiveRestore size={12} />
                        ) : (
                          <Archive size={12} />
                        )}
                      </button>
                    </>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}
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
        {knowledgeBase && ownerToken && (
          <button
            className={`nav-item ${panel === "knowledge" ? "chosen" : ""}`}
            onClick={() => setPanel("knowledge")}
          >
            <BookOpen size={18} /> Bilgi tabanı
          </button>
        )}
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
                  {transcript.map((message) => (
                    <div
                      key={`stored-${message.sequence}`}
                      className={`chat-row ${message.role === "user" ? "user" : "agent"} stored`}
                    >
                      <div className="bubble">
                        {message.role === "assistant" && (
                          <div className="answer-label">
                            <span className="small-brand">
                              <Layers3 size={13} />
                            </span>{" "}
                            DATATRIO{" "}
                            {message.status && (
                              <span className={`verdict ${message.status}`}>
                                {message.status === "accepted" &&
                                !message.result_ref
                                  ? "Yanıt"
                                  : {
                                      accepted: "Kontrolden geçti",
                                      qualified: "Sınırlı yanıt",
                                      abstained: "Netleştirme gerekli",
                                    }[message.status]}
                              </span>
                            )}
                          </div>
                        )}
                        <p
                          className={
                            message.role === "user" ? "" : "answer-text"
                          }
                        >
                          {message.text}
                        </p>
                        {message.result_ref && (
                          <p className="notice">
                            Bu turda yayımlanan tablo
                            {message.result_ref === restoredResult
                              ? " (sohbetin son tablosu)"
                              : ""}
                            .
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                  {items.map((item, index) => (
                    <article className="turn" key={item.request_id}>
                      <div className="question-label">
                        SEN <span>{String(index + 1).padStart(2, "0")}</span>
                      </div>
                      <p className="user-question">{item.question}</p>
                      {item.document_format && (
                        <p className="request-source">
                          <FileText size={12} /> Ekli belge:{" "}
                          {item.document_format.toUpperCase()}
                        </p>
                      )}
                      {item.selected_result_id && (
                        <p className="request-source">
                          {sourceLabel(item.selected_result_id)}
                        </p>
                      )}
                      <div className="answer-label">
                        <span className="small-brand">
                          <Layers3 size={13} />
                        </span>{" "}
                        DATATRIO{" "}
                        {item.turn?.answer && (
                          <span
                            className={`verdict ${item.turn.answer.status}`}
                          >
                            {item.turn.answer.status === "accepted" &&
                            !item.turn.answer.result
                              ? "Yanıt"
                              : {
                                  accepted: "Kontrolden geçti",
                                  qualified: "Sınırlı yanıt",
                                  abstained: "Netleştirme gerekli",
                                }[item.turn.answer.status]}
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
                          {history &&
                            conversationId &&
                            ownerToken &&
                            item.turn.turn_id &&
                            item.turn.state === "completed" && (
                              <AnswerFeedback
                                conversationId={conversationId}
                                token={ownerToken}
                                turnId={item.turn.turn_id}
                                saved={ratings[item.turn.turn_id]}
                                onSaved={(stored) =>
                                  setRatings((current) => ({
                                    ...current,
                                    [stored.turn_id]: stored,
                                  }))
                                }
                                onOpenTrace={(runId) => setTracing({ runId })}
                              />
                            )}
                          {history && conversationId && item.turn.turn_id && (
                            <button
                              type="button"
                              className="trace-link"
                              onClick={() =>
                                setTracing({ turnId: item.turn?.turn_id })
                              }
                            >
                              <Activity size={14} /> İşlem ayrıntıları
                            </button>
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
                          {history &&
                            conversationId &&
                            item.turn?.state === "running" && (
                              <button
                                type="button"
                                className="trace-link"
                                onClick={() =>
                                  setTracing({ turnId: item.turn?.turn_id })
                                }
                              >
                                <Activity size={14} /> Canlı izle
                              </button>
                            )}
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
              className={dragging ? "composer dragging" : "composer"}
              onSubmit={(e) => {
                e.preventDefault();
                void submit();
              }}
              onDragEnter={(e) => {
                if (!uploads || !e.dataTransfer.types.includes("Files")) return;
                e.preventDefault();
                setDragging(true);
              }}
              onDragOver={(e) => {
                if (!uploads || !e.dataTransfer.types.includes("Files")) return;
                e.preventDefault();
                e.dataTransfer.dropEffect =
                  !ready || busy || pending || uploading ? "none" : "copy";
              }}
              onDragLeave={(e) => {
                // Leaving for a child element is not leaving the drop zone.
                if (!e.currentTarget.contains(e.relatedTarget as Node | null))
                  setDragging(false);
              }}
              onDrop={(e) => {
                if (!uploads || !e.dataTransfer.types.includes("Files")) return;
                e.preventDefault();
                setDragging(false);
                // One document per question; the same admission checks as the picker.
                void attach(e.dataTransfer.files[0]);
              }}
            >
              {dragging && (
                <div className="composer-drop" aria-hidden="true">
                  <FileText size={16} /> Belgeyi buraya bırak · CSV, Excel, PDF,
                  HTML
                </div>
              )}
              {/* What this turn carries, stated rather than switched: the agent
                  reads the chat and its tables on its own. */}
              <div className="selection-context" aria-live="polite">
                <span>
                  {pending
                    ? "Bekleyen istek sürüyor."
                    : items.at(-1)?.turn?.answer?.status === "abstained"
                      ? "Son cevap netleştirme istedi: kısa bir yanıt yazarsan o isteğe eklenir, kendi başına bir soru yazarsan yeni soru sayılır."
                      : contextTables > 0
                        ? `Bu sohbetteki ${contextTables} tablo ve önceki sorular bağlamda; hangisini kullanacağını ajan seçer.`
                        : "Sorunu yaz; gereken veriyi ve tabloyu ajan kendisi seçer."}
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
              {attachment && (
                <div className="composer-attachment" aria-live="polite">
                  <FileText size={13} /> Ekli belge (sohbette sonraki sorularda
                  da kullanılabilir): {attachment.document_format.toUpperCase()}{" "}
                  · {Math.max(1, Math.round(attachment.bytes / 1024))} KB
                  <button
                    type="button"
                    aria-label="Ekli belgeyi kaldır"
                    disabled={busy || pending}
                    onClick={() => setAttachment(null)}
                  >
                    <X size={12} />
                  </button>
                </div>
              )}
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
                <div className="composer-buttons">
                  {!uploads && (
                    // The capability is off in this deployment: say so rather than
                    // quietly dropping the control.
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      aria-label="Belge ekleme kapalı"
                      title="Belge yükleme bu sunucuda kapatılmış (servis --no-uploads ile başlatılmış)."
                      disabled
                    >
                      <Paperclip size={17} />
                    </Button>
                  )}
                  {uploads && (
                    <>
                      <input
                        ref={picker}
                        type="file"
                        accept={DOCUMENT_ACCEPT}
                        hidden
                        onChange={(e) => void attach(e.target.files?.[0])}
                      />
                      <Button
                        type="button"
                        size="icon"
                        variant="ghost"
                        aria-label="Soruya belge ekle"
                        title={
                          "CSV, Excel, PDF veya HTML belge ekle ya da sürükleyip bırak " +
                          "(en fazla 10 MiB). Metin katmanlı PDF okunur; taranmış PDF " +
                          (ocr ? "OCR ile okunur." : "için OCR kapalı.")
                        }
                        disabled={!ready || busy || pending || uploading}
                        onClick={() => picker.current?.click()}
                      >
                        {uploading ? (
                          <LoaderCircle size={17} className="spin" />
                        ) : (
                          <Paperclip size={17} />
                        )}
                      </Button>
                    </>
                  )}
                  {pending && (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={stopping}
                      title="Çalışan model isteği bitince, bir sonraki adımdan önce durur."
                      onClick={() => void stop()}
                    >
                      {stopping ? (
                        <LoaderCircle size={14} className="spin" />
                      ) : (
                        <Square size={12} />
                      )}{" "}
                      Durdur
                    </Button>
                  )}
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
              </div>
            </form>
            {tracing && conversationId && ownerToken && (
              <TracePanel
                key={tracing.turnId ?? tracing.runId ?? "latest"}
                conversationId={conversationId}
                token={ownerToken}
                runId={tracing.runId}
                turnId={tracing.turnId}
                onClose={() => setTracing(null)}
              />
            )}
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
                  context={{
                    question: items[selected]?.question,
                    answer: items[selected]?.turn?.answer?.text,
                  }}
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
              {panel === "data"
                ? "Veri havuzu"
                : panel === "knowledge"
                  ? "Bilgi tabanı"
                  : "Çalışma ayarları"}
            </h2>
            {panel === "knowledge" && ownerToken ? (
              <KnowledgePanel owner={ownerToken} documents={chatDocuments} />
            ) : panel === "data" ? (
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
                  {acquisition &&
                    " Bir soru havuzda olmayan incelenmiş bir EVDS/BDDK serisine ihtiyaç duyarsa seri kaynaktan çekilir, saklanır ve işlem kaydında görünür; sonraki sohbetler yeniden çekmez."}
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
                    <dt>Sohbet geçmişi</dt>
                    <dd>
                      {history
                        ? "Kalıcı; bu tarayıcının anahtarına bağlı"
                        : "Bu sekmeye özel"}
                    </dd>
                  </div>
                  <div>
                    <dt>İşlem kayıtları</dt>
                    <dd>
                      {history
                        ? "Her tur kaydedilir; açmak yeni analiz başlatmaz"
                        : "Bu sürümde tutulmuyor"}
                    </dd>
                  </div>
                  <div>
                    <dt>Kayıtlı veri kopyası</dt>
                    <dd>Oturumlar arasında ayrılır</dd>
                  </div>
                  <div>
                    <dt>Belge yükleme</dt>
                    <dd>
                      {uploads ? "Açık · CSV, Excel, PDF, HTML" : "Kapalı"}
                    </dd>
                  </div>
                  <div>
                    <dt>Taranmış PDF (OCR)</dt>
                    <dd>
                      {ocr
                        ? "Açık · tablolar sütun toplamıyla doğrulanır"
                        : "Kapalı · OCR modeli tanımlı değil"}
                    </dd>
                  </div>
                  <div>
                    <dt>Web araması</dt>
                    <dd>
                      {webSearch
                        ? "Açık · sonuçlar doğrulanmamış aday listesi olarak gösterilir"
                        : "Kapalı · arama servisi tanımlı değil"}
                    </dd>
                  </div>
                  <div>
                    <dt>Resmî kaynaktan veri edinme</dt>
                    <dd>
                      {acquisition
                        ? "Açık · incelenmiş EVDS/BDDK serileri gerektiğinde çekilir ve saklanır"
                        : "Kapalı · yalnız hazır havuz kullanılır"}
                    </dd>
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
                  {history
                    ? "Sohbetler, mesajlar, yüklenen belgeler, yayımlanan tablolar ve işlem kayıtları yeniden başlatmadan sonra da açılır. Bu tarayıcının anahtarı silinirse eski sohbetlere ulaşılamaz. Arşivlemek veri silmez."
                    : "API yeniden başlatılınca tarayıcı oturumu geçersiz olur."}{" "}
                  Yeni sohbet açmak önceki hesap dosyalarını silmez. Gelişmiş
                  agent davranışı ayarları sonraki geliştirmedir.
                </p>
              </>
            )}
          </section>
        </Panel>
      )}
    </div>
  );
}
