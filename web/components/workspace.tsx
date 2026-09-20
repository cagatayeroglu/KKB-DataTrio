"use client";
import { useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowRight,
  ArrowUp,
  Cpu,
  Share2,
  Trash2,
  Check,
  ChevronDown,
  Info,
  Database,
  ListTree,
  FileText,
  Image as ImageIcon,
  LoaderCircle,
  MessageSquare,
  Archive,
  ArchiveRestore,
  MessagesSquare,
  Pencil,
  Plus,
  Search,
  RefreshCw,
  Settings2,
  ShieldCheck,
  Square,
  Table2,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ResultTable } from "@/components/result-table";
import { TracesPage } from "@/components/traces-page";
import { AnswerFeedback } from "@/components/answer-feedback";
import { LiveActivity } from "@/components/live-activity";
import {
  KnowledgePanel,
  type ChatDocument,
} from "@/components/knowledge-panel";
import { preparedTitle } from "@/lib/table";
import { noticeText } from "@/lib/language";
import { clarificationPickText } from "@/lib/clarification";
import {
  hasUnrecordedRun,
  keepSubmittedPrompts,
  unreadTables,
} from "@/lib/chat-state";
import {
  api,
  ApiError,
  DOCUMENT_ACCEPT,
  admissionRejection,
  lostTurn,
  cancelTurn,
  deleteConversation,
  draftRequest,
  publishedResult,
  restoredSelection,
  admit,
  clearSession,
  describeError,
  usableOwner,
  listConversations,
  listRuns,
  readSettings,
  readPrompts,
  saveSettings,
  listFeedback,
  loadSession,
  newSession,
  openConversation,
  updateConversation,
  readTurn,
  storedResult,
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
  type Result,
  type RuntimeSettings,
  type PromptParts,
} from "@/lib/contracts";

// How close to the end of the conversation still counts as reading its end.
const END_TOLERANCE_PX = 80;

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
//: What the settings page may switch off, in the order the API reports them.
const capabilityRows = [
  {
    name: "document_upload",
    label: "Belge yükleme",
    on: "Açık · CSV, Excel, PDF, HTML",
    absent: "Operatör açmadı",
  },
  {
    name: "document_ocr",
    label: "Taranmış PDF (OCR)",
    on: "Açık · tablolar sütun toplamıyla doğrulanır",
    absent: "OCR modeli tanımlı değil",
  },
  {
    name: "official_acquisition",
    label: "Resmî kaynaktan veri edinme",
    on: "Açık · incelenmiş seriler gerektiğinde çekilir",
    absent: "Operatör açmadı",
  },
  {
    name: "web_search",
    label: "Web araması",
    on: "Açık · sonuçlar doğrulanmamış aday listesi",
    absent: "Arama servisi tanımlı değil",
  },
  {
    name: "web_url",
    label: "Sorudaki web adresini okuma",
    on: "Açık · yalnız soruda yazılan adres",
    absent: "Operatör açmadı",
  },
];

type Item = Saved["turns"][number] & { turn?: Turn };
type SeriesChoiceEntry = { series_id: string; title: string; detail: string };

/** Which catalogue entry an answer used, or which ones a clarification offers (DEC-177). */
function SeriesChoiceCard({
  selection,
  onPick,
  resolved = false,
}: {
  selection: { chosen: SeriesChoiceEntry[]; others: SeriesChoiceEntry[] };
  onPick: (text: string) => void;
  //: A later turn answered this clarification, so its choices are history: they
  //: are shown, not offered. Picking one used to send an answer to a question
  //: nobody was waiting on any more (finding F2-kart).
  resolved?: boolean;
}) {
  const asking = selection.chosen.length === 0;
  const settled = asking && resolved;
  return (
    <div className="series-choice">
      {!asking && (
        <>
          <p className="series-choice-head">
            Kullanılan seri
            <span> · hazır eşleşme yoktu, arama sonuçlarından seçildi</span>
          </p>
          <ul>
            {selection.chosen.map((entry) => (
              <li key={entry.series_id}>
                <strong>{entry.title}</strong>
                <span>{entry.detail}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      {selection.others.length > 0 && (
        <details open={asking && !settled}>
          <summary>
            {settled
              ? `Bu netleştirmede sunulan kayıtlar (${selection.others.length}) — yanıtlandı`
              : asking
                ? "Birini seçin: soru kutusuna yazılır, gönderdiğinizde istek o kayıtla sürer"
                : `Aramada çıkan diğer yakın kayıtlar (${selection.others.length}) — başka birini kastettiyseniz seçin`}
          </summary>
          <ul>
            {selection.others.map((entry) => (
              <li key={entry.series_id}>
                <button
                  type="button"
                  disabled={settled}
                  title={
                    settled
                      ? "Bu netleştirme yanıtlandı; yeni bir soru gönderebilirsin"
                      : "Soru kutusuna bu kaydı kullanan bir istek yazar"
                  }
                  onClick={() => onPick(clarificationPickText(entry, asking))}
                >
                  {entry.title}
                </button>
                <span>{entry.detail}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

export function Workspace() {
  const [health, setHealth] = useState<Health | null>(null),
    [dataset, setDataset] = useState<Dataset | null>(null);
  const [ready, setReady] = useState(false),
    [loading, setLoading] = useState(true),
    [connectionError, setConnectionError] = useState("");
  const [modelMenu, setModelMenu] = useState(false);
  const [modelMenuAt, setModelMenuAt] = useState({ left: 0, bottom: 0 });
  const [question, setQuestion] = useState(""),
    [items, setItems] = useState<Item[]>([]),
    [busy, setBusy] = useState(false),
    [issue, setIssue] = useState("");
  // The published table on screen, named by its own reference: a reopened
  // conversation's tables and this tab's turns are one list.
  const [selected, setSelected] = useState<string | null>(null),
    [panel, setPanel] = useState<"data" | "traces" | "settings" | null>(null),
    [pendingIndex, setPendingIndex] = useState<number | null>(null),
    [attachment, setAttachment] = useState<DocumentAdmitted | null>(null),
    //: Bumped when something happened that the sidebar should show: a finished
    //: turn names a new chat and counts its questions (finding F2-yan-1).
    [listVersion, setListVersion] = useState(0),
    //: The name of the file the person chose. The server keeps none (it names
    //: documents belge_1, belge_2), and an image is admitted as a one-page PDF,
    //: so without this the badge said "PDF" about a screenshot.
    [attachedName, setAttachedName] = useState<string | null>(null),
    [dragging, setDragging] = useState(false),
    [uploading, setUploading] = useState(false),
    //: The turn a stop was asked for. It stays until that turn reaches a terminal
    //: state, because the turn stops only after the model call that is out returns.
    [stopRequestedFor, setStopRequestedFor] = useState<string | null>(null);
  // Conversations that outlive this tab: the browser's own key lists and reopens them.
  const [prompts, setPrompts] = useState<PromptParts | null>(null),
    //: Why the prompt parts are not on screen: not read yet, this server has no
    //: route for them, or the read failed and can be tried again.
    [promptsState, setPromptsState] = useState<
      "loading" | "ready" | "unsupported" | "error"
    >("loading"),
    [openPrompt, setOpenPrompt] = useState<string | null>(null);
  // Header chrome for the open chat: its menu, an inline rename, the copy flash.
  const [chatMenu, setChatMenu] = useState(false),
    [headerRenaming, setHeaderRenaming] = useState(false),
    [copied, setCopied] = useState(false);
  const [ownerToken, setOwnerToken] = useState<string | null>(null),
    [conversations, setConversations] = useState<ConversationSummary[]>([]),
    [conversationId, setConversationId] = useState<string | null>(null),
    [transcript, setTranscript] = useState<StoredMessage[]>([]),
    //: Receipts this process answered for, and the ones it truly cannot serve.
    [lostTables, setLostTables] = useState<string[]>([]),
    //: Send the next message as its own question instead of an answer to the
    //: pending clarification; the harness decides when this is off.
    [asNewQuestion, setAsNewQuestion] = useState(false),
    //: What the clarification this conversation is waiting on offered, for a reopened tab.
    [pendingOffered, setPendingOffered] = useState<string[]>([]),
    [restoredTables, setRestoredTables] = useState<
      { turnId: string; result: Result }[]
    >([]),
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
  const [settings, setSettings] = useState<RuntimeSettings | null>(null),
    [savingSetting, setSavingSetting] = useState(""),
    //: What the slider shows while it is being dragged; saved on release.
    [historyDraft, setHistoryDraft] = useState<number | null>(null);
  const uploads = health?.capabilities.includes("document_upload") ?? false;
  const ocr = health?.capabilities.includes("document_ocr") ?? false;
  const knowledgeBase =
    health?.capabilities.includes("knowledge_base") ?? false;
  const saved = useRef<Saved | null>(null),
    busyRef = useRef(false),
    //: A chat is being opened. `busyRef` guards a running turn, this guards the
    //: awaits inside `openChat`: without it a prompt sent meanwhile was dropped by
    //: the `setItems([])` that follows them, and `busy` stayed on (finding F1-3).
    opening = useRef(false),
    mounted = useRef(false),
    generation = useRef(0),
    recoveries = useRef<number[]>([]),
    chatEnd = useRef<HTMLDivElement>(null),
    atEnd = useRef(true),
    transcriptFor = useRef<string | null>(null),
    hiddenDeleted = useRef<Set<string>>(new Set()),
    pickedClarification = useRef<string | null>(null),
    input = useRef<HTMLTextAreaElement>(null),
    picker = useRef<HTMLInputElement>(null),
    imagePicker = useRef<HTMLInputElement>(null);
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
  function openTrace(turnId?: string, runId?: string) {
    setTracing({ turnId, runId });
    setPanel("traces");
  }
  async function refreshSettings(token = ownerToken) {
    if (!token) return;
    try {
      setSettings(await readSettings(token));
    } catch (error) {
      setIssue(describeError(error));
    }
    try {
      setPrompts(await readPrompts(token));
      setPromptsState("ready");
    } catch (error) {
      // Only a route this server does not have means "older server"; a timeout
      // or a dropped connection is a retry, not a missing feature (F4-istem).
      setPrompts(null);
      setPromptsState(
        error instanceof ApiError && error.code === "not_found"
          ? "unsupported"
          : "error",
      );
    }
  }
  async function changeSetting(change: {
    disabled?: string[];
    history_turns?: number;
  }) {
    if (!ownerToken) return;
    setSavingSetting(Object.keys(change)[0] ?? "");
    try {
      setSettings(await saveSettings(ownerToken, change));
    } catch (error) {
      setIssue(describeError(error));
    } finally {
      setSavingSetting("");
    }
  }
  function commitHistoryTurns() {
    if (historyDraft === null || historyDraft === settings?.history_turns) {
      setHistoryDraft(null);
      return;
    }
    const chosen = historyDraft;
    setHistoryDraft(null);
    void changeSetting({ history_turns: chosen });
  }
  async function refreshConversations(token = ownerToken) {
    if (!token) return;
    try {
      const listed = await listConversations(token, {
        archived: showArchived,
        search: chatSearch.trim() || undefined,
      });
      if (mounted.current)
        setConversations(
          listed.conversations.filter(
            (item) => !hiddenDeleted.current.has(item.conversation_id),
          ),
        );
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
    if (busyRef.current || opening.current || pending || !ready) return;
    resetChat();
  }
  function resetChat() {
    // Starting or opening a chat is a move to the studio: the page follows the
    // choice instead of leaving the person on a page that does not show it.
    setPanel(null);
    let storageIssue = "";
    try {
      clearSession(sessionStorage);
    } catch (error) {
      storageIssue = describeError(error);
    }
    generation.current++;
    saved.current = null;
    recoveries.current = [];
    transcriptFor.current = null;
    setItems([]);
    setTranscript([]);
    setPendingOffered([]);
    setRestoredTables([]);
    setLostTables([]);
    setConversationId(null);
    setRatings({});
    setPendingIndex(null);
    busyRef.current = false;
    setBusy(false);
    setStopRequestedFor(null);
    setSelected(null);
    setAttachment(null);
    setAttachedName(null);
    setQuestion("");
    pickedClarification.current = null;
    setIssue(storageIssue);
    setChatMenu(false);
    atEnd.current = true;
  }
  /** The tables a stored conversation published, read back from their receipts. */
  async function restoreTables(
    id: string,
    messages: StoredMessage[],
    token: string,
  ) {
    const published = messages.filter((message) => message.result_ref);
    const restored = await Promise.all(
      published.map(async (message) => {
        try {
          return {
            turnId: message.turn_id,
            result: await storedResult(id, message.turn_id, token),
          };
        } catch {
          // Busy (a turn is running) or gone: the message says so in place.
          return undefined;
        }
      }),
    );
    return restored.filter(
      (entry): entry is { turnId: string; result: Result } => Boolean(entry),
    );
  }
  // A table published while a turn is running cannot be read back yet: the runner
  // answers "busy" and `restoreTables` returns nothing for it. Ask again as soon as
  // the runner is free, so a table that exists is never explained away as a restart
  // (reported live 2026-09-20: the answer was accepted and the table was materialised,
  // but the chat said the server had restarted).
  useEffect(() => {
    if (!ownerToken || !conversationId || busy) return;
    const missing = unreadTables(transcript, restoredTables, lostTables);
    if (!missing.length) return;
    let cancelled = false;
    void (async () => {
      const found = await restoreTables(conversationId, missing, ownerToken);
      if (cancelled || !mounted.current) return;
      if (found.length) setRestoredTables((old) => [...old, ...found]);
      const arrived = new Set(found.map((entry) => entry.result.result_ref));
      const gone = missing
        .map((message) => message.result_ref as string)
        .filter((ref) => !arrived.has(ref));
      // Only a failure with the runner free means the receipt is really gone.
      if (gone.length) setLostTables((old) => [...old, ...gone]);
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    transcript,
    restoredTables,
    lostTables,
    busy,
    conversationId,
    ownerToken,
  ]);
  // Leaving the studio for another page and coming back remounts this component: the turns
  // of this tab come back from sessionStorage, but the conversation's EARLIER messages live
  // on the server. Without this they vanished, and with them the clarification being
  // answered (reported 2026-09-19). Messages of this tab's own turns are left to `items`.
  useEffect(() => {
    if (!ownerToken || !conversationId) return;
    if (transcriptFor.current === conversationId) return;
    transcriptFor.current = conversationId;
    let cancelled = false;
    void (async () => {
      try {
        const detail = await openConversation(conversationId, ownerToken);
        if (cancelled || !mounted.current) return;
        const local = new Set(
          (saved.current?.turns ?? [])
            .map((entry) => entry.turn_id)
            .filter(Boolean),
        );
        const earlier = detail.messages.filter(
          (message) => !local.has(message.turn_id),
        );
        setTranscript(earlier);
        setPendingOffered(detail.pending_offered);
        const kept = await restoreTables(conversationId, earlier, ownerToken);
        if (!cancelled && mounted.current) setRestoredTables(kept);
      } catch {
        // A chat still works without its earlier messages; the sidebar can reopen it.
        transcriptFor.current = null;
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ownerToken, conversationId]);
  async function openChat(id: string, options?: { force?: boolean }) {
    if (!ownerToken) return;
    // `force` is the restart recovery re-adopting this same conversation: it has
    // already dropped the turn it was waiting on, so the guards below would only
    // read their own stale state.
    if (
      !options?.force &&
      (busyRef.current || opening.current || pending || !ready)
    )
      return;
    opening.current = true;
    const beforeOpen = generation.current;
    setPanel(null);
    setIssue("");
    try {
      const detail = await openConversation(id, ownerToken);
      if (!mounted.current || generation.current !== beforeOpen) return;
      generation.current++;
      const epoch = generation.current;
      const active = () => mounted.current && generation.current === epoch;
      recoveries.current = [];
      transcriptFor.current = id;
      atEnd.current = true;
      // The owner key opens this conversation's turn routes too; no second secret.
      const reopened: Saved = {
        session: {
          api_version: 1,
          session_id: id,
          token: ownerToken,
          survives_restart: true,
        },
        turns: [],
      };
      record(reopened);
      setConversationId(id);
      setTranscript(detail.messages);
      setPendingOffered(detail.pending_offered);
      try {
        const rated = await listFeedback(id, ownerToken);
        if (active())
          setRatings(
            Object.fromEntries(
              rated.feedback.map((item) => [item.turn_id, item]),
            ),
          );
      } catch {
        // Ratings are supporting information; a chat still opens without them.
      }
      if (!active()) return;
      setItems([]);
      setSelected(null);
      setPendingIndex(null);
      setAttachment(null);
      setAttachedName(null);
      setQuestion("");
      setAsNewQuestion(false);
      pickedClarification.current = null;
      // A reopened conversation keeps its tables: each published one is read
      // back from its receipt on the server, so it comes with the same reference
      // and version the messages recorded - whichever process produced it.
      const published = detail.messages.filter((message) => message.result_ref);
      const restored = await Promise.all(
        published.map(async (message) => {
          try {
            return {
              turnId: message.turn_id,
              result: await storedResult(id, message.turn_id, ownerToken),
            };
          } catch {
            // Busy (a turn is running) or gone: the message says so in place.
            return undefined;
          }
        }),
      );
      if (active()) {
        const kept = restored.filter(
          (entry): entry is { turnId: string; result: Result } =>
            Boolean(entry),
        );
        setRestoredTables(kept);
        // The newest table opens with the conversation; nobody re-selects what
        // they were already looking at when they left.
        const newest = kept.at(-1)?.result.result_ref;
        if (newest) setSelected(newest);
      }
      // An in-flight turn is not yet a stored message. A reopened chat still
      // needs its server-issued turn identity for polling and cancellation.
      const listed = await listRuns(id, ownerToken).catch(() => null);
      if (!active()) return;
      const running = listed?.runs.find((run) => run.status === "running");
      // Completion may race the first conversation read. Re-read only if a run
      // finished after that snapshot, so its prompt and answer never disappear.
      if (
        !running &&
        listed &&
        hasUnrecordedRun(listed.runs, detail.messages)
      ) {
        const fresh = await openConversation(id, ownerToken);
        if (!active()) return;
        setTranscript(fresh.messages);
        setPendingOffered(fresh.pending_offered);
        const freshTables = await restoreTables(id, fresh.messages, ownerToken);
        if (!active()) return;
        setRestoredTables(freshTables);
        setSelected(freshTables.at(-1)?.result.result_ref ?? null);
      }
      if (running) {
        const turn = await readTurn(reopened.session, running.turn_id).catch(
          () => null,
        );
        if (active() && turn && ["queued", "running"].includes(turn.state)) {
          const entry = {
            request_id: turn.request_id,
            turn_id: turn.turn_id,
            question: running.question,
            turn,
          };
          record({ ...reopened, turns: [entry] });
          setItems([entry]);
          recoveries.current = [0];
          void watch(0, false);
        }
      }
    } catch (error) {
      if (mounted.current) setIssue(describeError(error));
    } finally {
      opening.current = false;
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
  async function deleteChat(id: string) {
    if (!ownerToken) return;
    if (
      !window.confirm(
        "Bu sohbet silinsin mi? Sohbet ve yüklenen belgeler kaldırılır; işlem kayıtları korunur.",
      )
    )
      return;
    try {
      await deleteConversation(id, ownerToken);
      hiddenDeleted.current.add(id);
      setConversations((old) =>
        old.filter((item) => item.conversation_id !== id),
      );
      if (id === conversationId) resetChat();
      await refreshConversations();
    } catch (error) {
      setIssue(describeError(error));
    }
  }
  function update(index: number, turn: Turn, selectResult = false) {
    const result = publishedResult(turn);
    if (selectResult && result && saved.current) {
      record({ ...saved.current, view_result_id: result.result_ref });
      setSelected(result.result_ref);
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
    // The finished turn gave this chat its title and one more question.
    setListVersion((old) => old + 1);
  }
  // A file dropped anywhere but the composer used to be opened by the browser,
  // which navigated away from the chat and lost the turn in flight. The window
  // refuses every drop it is not meant to handle (finding F2-upl-4).
  useEffect(() => {
    const swallow = (event: DragEvent) => {
      if (!event.dataTransfer?.types.includes("Files")) return;
      if ((event.target as HTMLElement | null)?.closest?.(".composer")) return;
      event.preventDefault();
      if (event.type === "drop") event.dataTransfer.dropEffect = "none";
    };
    window.addEventListener("dragover", swallow);
    window.addEventListener("drop", swallow);
    return () => {
      window.removeEventListener("dragover", swallow);
      window.removeEventListener("drop", swallow);
    };
  }, []);
  /**
   * Drop a request the server never admitted, so the composer is usable again.
   *
   * A 409 "busy", a connection error or a 5xx left `pending` set with no turn to
   * cancel, and that blocked sending, opening and starting a chat across reloads
   * with no way out (finding F2-vazgeç).
   */
  function discardPending() {
    const index = pendingIndex;
    const state = saved.current;
    if (index === null || !state || state.turns[index]?.turn_id) return;
    const turns = state.turns.filter((_, at) => at !== index);
    record({ ...state, turns });
    setItems((old) => old.filter((_, at) => at !== index));
    recoveries.current = [];
    setPendingIndex(null);
    busyRef.current = false;
    setBusy(false);
    setStopRequestedFor(null);
    setIssue("");
  }
  /**
   * The server forgot this turn: re-adopt the conversation instead of a dead end.
   *
   * A turn handle lives in the API process, a conversation lives in its store. A
   * restart therefore answers 404 for the turn being polled while the chat itself
   * is still readable with this browser's own key. Before this, `pending` stayed
   * set with nothing to cancel and nothing to open: sending, opening and starting
   * a chat were all refused until the tab was reloaded (finding F2-restart).
   */
  async function recoverFromRestart(index: number) {
    const id = saved.current?.session.session_id ?? conversationId;
    const unanswered = saved.current?.turns[index]?.question ?? "";
    try {
      clearSession(sessionStorage);
    } catch {
      // Nothing stored to clear.
    }
    saved.current = null;
    recoveries.current = [];
    setPendingIndex(null);
    busyRef.current = false;
    setBusy(false);
    setStopRequestedFor(null);
    if (!id || !ownerToken) {
      // Nothing stored to go back to: the prompts stay on screen, marked as lost.
      setItems((old) => keepSubmittedPrompts(old));
      setConversationId(null);
      setTranscript([]);
      setPendingOffered([]);
      setRestoredTables([]);
      setLostTables([]);
      transcriptFor.current = null;
      setSelected(null);
      setIssue(errorText.session_gone);
      return;
    }
    transcriptFor.current = null;
    await openChat(id, { force: true });
    if (!mounted.current) return;
    // The question the lost turn was carrying comes back in the composer, so
    // asking it again is one key rather than retyping it.
    if (unanswered) setQuestion((old) => old || unanswered);
    setIssue(errorText.session_restored);
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
      const deadline = Date.now() + 60 * 60 * 1000;
      let turn: Turn;
      for (;;) {
        try {
          turn = canAdmit
            ? await admit(state, index)
            : await readTurn(state.session, entry.turn_id!, entry.request_id);
          break;
        } catch (error) {
          if (
            !(error instanceof ApiError) ||
            !["connection", "unavailable"].includes(error.code) ||
            Date.now() > deadline
          )
            throw error;
          if (active()) setIssue((old) => old || describeError(error));
          await new Promise((resolve) => setTimeout(resolve, 1000));
          if (!active()) return;
        }
      }
      if (!active()) return;
      setIssue("");
      const next = {
        ...state,
        turns: state.turns.map((entry, i) =>
          i === index ? { ...entry, turn_id: turn.turn_id } : entry,
        ),
      };
      record(next);
      update(index, turn, true);
      // A turn is several model calls and one call may run for its whole request
      // timeout; the turn keeps running server-side either way, so keep watching it.
      while (turn.state !== "completed" && turn.state !== "failed") {
        if (Date.now() > deadline) {
          setIssue(
            "İşlem hâlâ devam ediyor olabilir. Aynı işlemin durumunu yeniden alabilirsin; yeni analiz başlatılmadı.",
          );
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, 1000));
        if (!active()) return;
        try {
          turn = await readTurn(next.session, turn.turn_id, entry.request_id);
        } catch (error) {
          if (
            error instanceof ApiError &&
            ["connection", "unavailable"].includes(error.code)
          ) {
            if (active()) setIssue((old) => old || describeError(error));
            continue;
          }
          throw error;
        }
        if (!active()) return;
        setIssue("");
        update(index, turn, true);
      }
      recovered(index);
    } catch (error) {
      if (!active()) return;
      if (lostTurn(error)) {
        await recoverFromRestart(index);
        return;
      }
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
    // Every `if (!active()) return` in `watch` skips the reset in its `finally`, so
    // a remount used to start with a `busy` nothing could clear: the send button,
    // "new chat" and the chat list were all dead (finding F1-3).
    busyRef.current = false;
    opening.current = false;
    setBusy(false);
    setStopRequestedFor(null);
    const epoch = ++generation.current;
    const active = () => mounted.current && generation.current === epoch;
    void refresh();
    const stored = loadSession(sessionStorage);
    saved.current = stored;
    if (stored) {
      // A session is its conversation, so a reloaded tab keeps the sidebar, the
      // rename and archive actions and the trace page pointing at this chat.
      setConversationId(stored.session.session_id);
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
            if (lostTurn(error)) {
              // Keep the exact submitted prompt visible even when the server lost
              // this turn, and leave no stale conversation behind: the id used to
              // stay, so the next question opened a new session whose empty
              // transcript wiped the chat on screen mid-send (finding F2-restart).
              await recoverFromRestart(i);
              if (!active()) return;
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
          setSelected(
            index >= 0 ? publishedResult(restored[index])!.result_ref : null,
          );
        } catch (error) {
          setIssue(describeError(error));
        }
        recoveries.current = resume;
        setPendingIndex(resume[0] ?? null);
        setReady(true);
        // A refresh/navigation return must resume observing the same request,
        // never silently leave a live turn behind a manual recovery button.
        if (resume.length > 0)
          void watch(resume[0], !stored.turns[resume[0]].turn_id);
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
        await refreshSettings(token);
      } catch (error) {
        if (!cancelled && mounted.current) setIssue(describeError(error));
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [history]);
  // The list is its own effect: typing in the search box used to re-read the owner
  // key, the settings and the prompt parts on every keystroke, and a slow earlier
  // answer could overwrite a newer one (finding F2-yan-2).
  useEffect(() => {
    if (!history || !ownerToken) return;
    let cancelled = false;
    const timer = setTimeout(
      () => {
        if (!cancelled) void refreshConversations(ownerToken);
      },
      chatSearch.trim() ? 250 : 0,
    );
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [history, ownerToken, showArchived, chatSearch, listVersion]);
  // The conversation follows new content only while the reader is at its end. Every poll
  // replaces `items`, and jumping to the end each time threw a reader who had scrolled up
  // to an earlier table back down while the agent was still working.
  useEffect(() => {
    const body = chatEnd.current?.parentElement;
    if (!body) return;
    const onScroll = () => {
      atEnd.current =
        body.scrollHeight - body.scrollTop - body.clientHeight <
        END_TOLERANCE_PX;
    };
    body.addEventListener("scroll", onScroll, { passive: true });
    return () => body.removeEventListener("scroll", onScroll);
  });
  useEffect(() => {
    const body = chatEnd.current?.parentElement;
    if (body && atEnd.current) body.scrollTop = body.scrollHeight;
  }, [items, transcript, restoredTables, busy, conversationId]);
  useEffect(() => {
    const body = chatEnd.current?.parentElement;
    const content = body?.querySelector(".messages");
    if (!body || !content || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => {
      if (atEnd.current) body.scrollTop = body.scrollHeight;
    });
    observer.observe(content);
    return () => observer.disconnect();
  }, [items.length, transcript.length, conversationId]);
  async function attach(file: File | undefined) {
    if (
      !file ||
      !uploads ||
      busyRef.current ||
      opening.current ||
      pending ||
      !ready
    )
      return;
    busyRef.current = true;
    setUploading(true);
    setIssue("");
    try {
      const state = await session();
      setAttachment(await uploadDocument(state.session, file));
      setAttachedName(file.name);
    } catch (error) {
      setIssue(describeError(error));
    } finally {
      busyRef.current = false;
      if (mounted.current) setUploading(false);
      if (picker.current) picker.current.value = "";
    }
  }
  async function submit(text = question) {
    if (uploading) {
      setIssue("Belge yükleniyor; bitince gönderebilirsin.");
      return;
    }
    if (
      busyRef.current ||
      opening.current ||
      pending ||
      !validQuestion(text) ||
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
      const turnCap = health?.max_turns_per_session ?? 24;
      if (state.turns.length >= turnCap) {
        setIssue(
          `Bu sohbet ${turnCap} soruluk sınırına ulaştı. Yeni bir sohbet aç: bu sohbetin geçmişi ve tabloları duruyor.`,
        );
        return;
      }
      // An offered card is an explicit continuation. Free text remains the
      // harness's decision unless the person changed the card's drafted text.
      const entry = draftRequest(
        text,
        undefined,
        pickedClarification.current === text.trim()
          ? true
          : asNewQuestion
            ? false
            : undefined,
        attachment ?? undefined,
      );
      const next = { ...state, turns: [...state.turns, entry] };
      record(next);
      setItems((old) => [...old, entry]);
      setQuestion("");
      pickedClarification.current = null;
      setAttachment(null);
      setAttachedName(null);
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
      pendingIndex === null ? undefined : state?.turns[pendingIndex]?.turn_id;
    if (!state || !turnId) return;
    setStopRequestedFor(turnId);
    try {
      // Accepted, not immediate: the running turn is polled until it stops.
      await cancelTurn(state.session.session_id, state.session.token, turnId);
    } catch (error) {
      // The turn keeps running; let the person ask again.
      setStopRequestedFor(null);
      setIssue(describeError(error));
    }
  }
  /**
   * Every table this conversation has published, oldest first: the ones read
   * back when it was reopened, then this tab's own turns. One list, so a
   * reopened conversation shows its results and follow-ups can cite them.
   */
  const analyses = [
    ...restoredTables.map(({ turnId, result }) => ({
      ref: result.result_ref,
      result,
      question: transcript.find(
        (message) => message.turn_id === turnId && message.role === "user",
      )?.text,
      answer: transcript.find(
        (message) => message.turn_id === turnId && message.role === "assistant",
      )?.text,
    })),
    ...items.flatMap((item) => {
      const published = publishedResult(item.turn);
      return published
        ? [
            {
              ref: published.result_ref,
              result: published,
              question: item.question,
              answer: item.turn?.answer?.text,
            },
          ]
        : [];
    }),
  ];
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
  function sourceLabel(reference?: string) {
    if (!reference) return "Serbest soru";
    const index = analyses.findIndex((entry) => entry.ref === reference);
    return index >= 0
      ? `Kaynak tablo: Analiz ${index + 1}`
      : "Kaynak tablo yüklenemedi";
  }
  const activeChat = conversations.find(
    (item) => item.conversation_id === conversationId,
  );
  const currentTitle =
    activeChat?.title ??
    (items[0]?.question ? items[0].question.slice(0, 60) : "Yeni sohbet");
  function formatWhen(iso?: string) {
    if (!iso) return "";
    const date = new Date(iso);
    const time = date.toLocaleTimeString("tr-TR", {
      hour: "2-digit",
      minute: "2-digit",
    });
    return date.toDateString() === new Date().toDateString()
      ? `Bugün ${time}`
      : `${date.toLocaleDateString("tr-TR", { day: "numeric", month: "long" })} ${time}`;
  }
  const currentWhen = formatWhen(activeChat?.updated_at);
  const modelLabel = loading
    ? "Bağlanıyor"
    : !health
      ? "Servis kapalı"
      : (health.model ??
        (health.execution_mode === "scripted" ? "Prova modeli" : "Kloudeks"));
  const modelShort = modelLabel.split("/").pop() ?? modelLabel;
  //: A turn of this tab is out: the button is the way to stop it.
  const pendingTurnId =
    pendingIndex === null
      ? undefined
      : (saved.current?.turns[pendingIndex]?.turn_id ??
        items[pendingIndex]?.turn?.turn_id);
  const running = Boolean(pending) || busy;
  const canStop = Boolean(pendingTurnId);
  const stopRequested = Boolean(
    stopRequestedFor && stopRequestedFor === pendingTurnId,
  );
  /** The table a stored message published, when this process still serves it. */
  const restoredTable = (ref: string | null | undefined) =>
    ref
      ? restoredTables.find((t) => t.result.result_ref === ref)?.result
      : undefined;
  async function shareConversation() {
    const lines: string[] = [];
    for (const message of transcript)
      lines.push(
        `${message.role === "user" ? "Soru" : "Cevap"}: ${message.text}`,
      );
    for (const item of items) {
      lines.push(`Soru: ${item.question}`);
      if (item.turn?.answer) lines.push(`Cevap: ${item.turn.answer.text}`);
    }
    try {
      await navigator.clipboard.writeText(lines.join("\n\n"));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setIssue("Panoya kopyalanamadı; tarayıcı izin vermedi.");
    }
  }
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
            <div className="chat-section">
              <span>Sohbetler</span>
              <button
                type="button"
                className={`chat-toggle ${showArchived ? "on" : ""}`}
                aria-pressed={showArchived}
                onClick={() => setShowArchived((value) => !value)}
              >
                <Archive size={13} />
                {showArchived ? "Arşiv · açık" : "Arşiv"}
              </button>
            </div>
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
                      <button
                        type="button"
                        className="chat-delete"
                        aria-label="Sohbeti sil"
                        title="Sohbeti sil; işlem kayıtlarını koru"
                        onClick={() => void deleteChat(item.conversation_id)}
                      >
                        <Trash2 size={12} />
                      </button>
                    </>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}
        <button
          className={`nav-item ${panel === null ? "chosen" : ""}`}
          onClick={() => setPanel(null)}
        >
          <MessageSquare size={18} /> Analiz stüdyosu
        </button>
        <button
          className={`nav-item ${panel === "data" ? "chosen" : ""}`}
          onClick={() => setPanel("data")}
        >
          <Database size={18} /> Veri ve bilgi tabanı{" "}
          <span className="nav-count">
            {dataset?.prepared_identities ?? "—"}
          </span>
        </button>
        {history && ownerToken && (
          <button
            className={`nav-item ${panel === "traces" ? "chosen" : ""}`}
            onClick={() => setPanel("traces")}
          >
            <ListTree size={18} /> İşlem kayıtları
          </button>
        )}
        <button
          className={`nav-item ${panel === "settings" ? "chosen" : ""}`}
          onClick={() => setPanel("settings")}
        >
          <Settings2 size={18} /> Çalışma ayarları
        </button>
        <div className="sidebar-bottom">
          <span>KKB Hackathon 2026</span>
        </div>
      </aside>
      <main className="main-shell">
        <header className="topbar">
          <div className="topbar-left">
            {panel === null ? (
              <div className="chat-heading-wrap">
                {headerRenaming && conversationId ? (
                  <input
                    autoFocus
                    className="chat-rename"
                    defaultValue={currentTitle}
                    maxLength={120}
                    aria-label="Sohbet adı"
                    onBlur={(event) => {
                      setHeaderRenaming(false);
                      void renameChat(conversationId, event.target.value);
                    }}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        setHeaderRenaming(false);
                        void renameChat(
                          conversationId,
                          event.currentTarget.value,
                        );
                      }
                      if (event.key === "Escape") setHeaderRenaming(false);
                    }}
                  />
                ) : (
                  <button
                    type="button"
                    className="chat-heading"
                    aria-haspopup="menu"
                    aria-expanded={chatMenu}
                    disabled={!conversationId}
                    onClick={() => setChatMenu((value) => !value)}
                  >
                    <strong>{currentTitle}</strong>
                    {currentWhen && (
                      <small title="Son etkinlik">{currentWhen}</small>
                    )}
                    {conversationId && <ChevronDown size={14} />}
                  </button>
                )}
                {chatMenu && conversationId && (
                  <div className="chat-menu" role="menu">
                    <button
                      type="button"
                      role="menuitem"
                      onClick={() => {
                        setChatMenu(false);
                        setHeaderRenaming(true);
                      }}
                    >
                      <Pencil size={13} /> Yeniden adlandır
                    </button>
                    <button
                      type="button"
                      role="menuitem"
                      onClick={() => {
                        setChatMenu(false);
                        void archiveChat(conversationId, true);
                      }}
                    >
                      <Archive size={13} /> Sohbeti arşivle
                    </button>
                    <button
                      type="button"
                      role="menuitem"
                      className="danger"
                      onClick={() => {
                        setChatMenu(false);
                        void deleteChat(conversationId);
                      }}
                    >
                      <Trash2 size={13} /> Sohbeti sil
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <strong>
                {panel === "data"
                  ? "Veri ve bilgi tabanı"
                  : panel === "traces"
                    ? "İşlem kayıtları"
                    : "Çalışma ayarları"}
              </strong>
            )}
          </div>
          <div className="topbar-right">
            {panel === null && (transcript.length > 0 || items.length > 0) && (
              <button
                type="button"
                className="chip-button"
                title="Sohbeti soru-cevap metni olarak panoya kopyala"
                onClick={() => void shareConversation()}
              >
                {copied ? <Check size={14} /> : <Share2 size={14} />}{" "}
                {copied ? "Kopyalandı" : "Paylaş"}
              </button>
            )}
            <span
              className={`connection ${health ? "online" : "offline"}`}
              title={
                health
                  ? "Bağlı model; hesaplar araçlarla yapılır, cevaplar kontrol edilir."
                  : "Yerel servise ulaşılamıyor."
              }
            >
              <i />
              {modelLabel}
            </span>
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
        {panel === null ? (
          <section className="studio" aria-label="Sohbet">
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
            <div className="thread">
              {!items.length && !transcript.length ? (
                <div className="hero">
                  <div className="hero-mark" aria-hidden="true">
                    <i />
                    <i />
                    <i />
                  </div>
                  <h1>Ne öğrenmek istersin?</h1>
                  <p>
                    Resmî serilerden, araçlarla hesaplanmış ve her sayısı
                    kanıtlı cevaplar.
                  </p>
                </div>
              ) : (
                <div className="messages">
                  {transcript.map((message) => {
                    const table = restoredTable(message.result_ref);
                    return (
                      <div
                        key={`stored-${message.sequence}`}
                        className={`msg ${message.role === "user" ? "user" : "agent"}`}
                      >
                        {message.role === "user" ? (
                          <div className="bubble">{message.text}</div>
                        ) : (
                          <div className="bubble">
                            {message.status && (
                              <div className="answer-meta">
                                <span className={`verdict ${message.status}`}>
                                  {message.status === "accepted" &&
                                  !message.result_ref
                                    ? "Yanıt"
                                    : {
                                        accepted: "Kontrolden geçti",
                                        qualified: "Sınırlı yanıt",
                                        abstained: "Netleştirme gerekli",
                                        queued: "Bekliyor",
                                        running: "Çalışıyor",
                                        completed: "Tamamlandı",
                                        failed: "Başarısız",
                                      }[message.status]}
                                </span>
                              </div>
                            )}
                            <p className="answer-text">{message.text}</p>
                            {table ? (
                              <div
                                className={`inline-result ${table.result_ref === selected ? "newest" : ""}`}
                              >
                                <div className="inline-result-head">
                                  <Table2 size={14} /> Tablo ·{" "}
                                  {table.cells.length} kayıtlı değer
                                  {table.result_ref === selected && (
                                    <span className="pill">son tablo</span>
                                  )}
                                </div>
                                <ResultTable
                                  key={table.result_ref}
                                  result={table}
                                  dataset={dataset}
                                  context={{
                                    question: transcript.find(
                                      (m) =>
                                        m.turn_id === message.turn_id &&
                                        m.role === "user",
                                    )?.text,
                                    answer: message.text,
                                  }}
                                />
                              </div>
                            ) : (
                              message.result_ref &&
                              (lostTables.includes(message.result_ref) ? (
                                <p className="notice">
                                  Bu turda bir tablo yayımlandı; bu sunucu artık
                                  onu sunmuyor (yeniden başlatılmış olabilir).
                                </p>
                              ) : (
                                <p className="notice">Tablo yükleniyor…</p>
                              ))
                            )}
                            {history && conversationId && ownerToken && (
                              <div className="answer-actions">
                                <AnswerFeedback
                                  conversationId={conversationId}
                                  token={ownerToken}
                                  turnId={message.turn_id}
                                  saved={ratings[message.turn_id]}
                                  onSaved={(stored) =>
                                    setRatings((current) => ({
                                      ...current,
                                      [stored.turn_id]: stored,
                                    }))
                                  }
                                  onOpenTrace={(runId) =>
                                    openTrace(message.turn_id, runId)
                                  }
                                />
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                  {pendingOffered.length > 0 && items.length === 0 && (
                    // Reopened in another tab or after a restart: the question the
                    // agent is waiting on is stored, so its choices are shown again
                    // instead of leaving the person to retype one (finding F2-netl).
                    <div className="msg agent">
                      <div className="bubble">
                        <div className="series-choice">
                          <p className="series-choice-head">
                            Bekleyen netleştirme
                            <span>
                              {" "}
                              · birini seç: soru kutusuna yazılır, gönderince
                              istek o kayıtla sürer
                            </span>
                          </p>
                          <ul>
                            {pendingOffered.map((title) => (
                              <li key={title}>
                                <button
                                  type="button"
                                  onClick={() => {
                                    const picked = clarificationPickText(
                                      { title, detail: "" },
                                      true,
                                    );
                                    // The pick answers the clarification this
                                    // conversation is waiting on; without this it
                                    // was sent as a brand-new question and the
                                    // agent started over (finding F2-kart).
                                    pickedClarification.current = picked;
                                    setQuestion(picked);
                                    setAsNewQuestion(false);
                                    input.current?.focus();
                                  }}
                                >
                                  {title}
                                </button>
                              </li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    </div>
                  )}
                  {items.map((item, itemIndex) => (
                    <div className="turn-pair" key={item.request_id}>
                      <div className="msg user">
                        <div className="bubble">{item.question}</div>
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
                      </div>
                      <div className="msg agent">
                        <div className="bubble">
                          {item.turn?.answer ? (
                            <>
                              <div className="answer-meta">
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
                              </div>
                              <p className="answer-text">
                                {item.turn.answer.text}
                              </p>
                              {item.turn.answer.selection && (
                                <SeriesChoiceCard
                                  selection={item.turn.answer.selection}
                                  resolved={itemIndex < items.length - 1}
                                  onPick={(picked) => {
                                    pickedClarification.current = picked;
                                    setQuestion(picked);
                                    setAsNewQuestion(false);
                                    input.current?.focus();
                                  }}
                                />
                              )}
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
                                  {item.turn.answer.omitted_claims}{" "}
                                  desteklenmeyen ifade yanıta alınmadı.
                                </p>
                              )}
                              {item.turn.answer.result && (
                                <div
                                  className={`inline-result ${item.turn.answer.result.result_ref === selected ? "newest" : ""}`}
                                >
                                  <div className="inline-result-head">
                                    <Table2 size={14} /> Tablo ·{" "}
                                    {item.turn.answer.result.cells.length}{" "}
                                    kayıtlı değer
                                    {item.turn.answer.result.result_ref ===
                                      selected && (
                                      <span className="pill">son tablo</span>
                                    )}
                                  </div>
                                  <ResultTable
                                    key={item.turn.answer.result.result_ref}
                                    result={item.turn.answer.result}
                                    dataset={dataset}
                                    context={{
                                      question: item.question,
                                      answer: item.turn.answer.text,
                                    }}
                                  />
                                </div>
                              )}
                              {history &&
                                conversationId &&
                                ownerToken &&
                                item.turn.turn_id &&
                                item.turn.state === "completed" && (
                                  <div className="answer-actions">
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
                                      onOpenTrace={(runId) =>
                                        openTrace(item.turn?.turn_id, runId)
                                      }
                                    />
                                  </div>
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
                            <div className="thinking" aria-live="polite">
                              <span className="pulse" aria-hidden="true">
                                <i />
                                <i />
                                <i />
                              </span>
                              {busy ? (
                                item.turn?.state === "running" ? (
                                  history &&
                                  conversationId &&
                                  ownerToken &&
                                  item.turn.turn_id ? (
                                    <LiveActivity
                                      conversationId={conversationId}
                                      token={ownerToken}
                                      turnId={item.turn.turn_id}
                                    />
                                  ) : (
                                    "Analiz çalışıyor…"
                                  )
                                ) : (
                                  "İstek iletiliyor…"
                                )
                              ) : (
                                "Durum yeniden alınabilir."
                              )}
                              {history &&
                                conversationId &&
                                item.turn?.state === "running" && (
                                  <button
                                    type="button"
                                    className="trace-link"
                                    onClick={() =>
                                      openTrace(item.turn?.turn_id)
                                    }
                                  >
                                    <Activity size={14} /> Canlı izle
                                  </button>
                                )}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              <div ref={chatEnd} />
            </div>
            <div className="composer-wrap">
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
              {!items.length && !transcript.length && (
                <div className="chips" role="list">
                  {examples.map((example) => (
                    <button
                      key={example.tag}
                      type="button"
                      role="listitem"
                      className="chip"
                      title={example.question}
                      onClick={() => {
                        pickedClarification.current = null;
                        setQuestion(example.question);
                        input.current?.focus();
                      }}
                    >
                      {example.title}
                    </button>
                  ))}
                </div>
              )}
              <form
                className={dragging ? "composer dragging" : "composer"}
                onSubmit={(e) => {
                  e.preventDefault();
                  void submit();
                }}
                onDragEnter={(e) => {
                  if (!uploads || !e.dataTransfer.types.includes("Files"))
                    return;
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragOver={(e) => {
                  if (!uploads || !e.dataTransfer.types.includes("Files"))
                    return;
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
                  if (!uploads || !e.dataTransfer.types.includes("Files"))
                    return;
                  e.preventDefault();
                  setDragging(false);
                  // One document per question; the same admission checks as the picker.
                  void attach(e.dataTransfer.files[0]);
                }}
              >
                {dragging && (
                  <div className="composer-drop" aria-hidden="true">
                    <FileText size={16} /> Belgeyi ya da görseli buraya bırak ·
                    CSV, Excel, PDF, HTML, PNG, JPG
                  </div>
                )}
                <textarea
                  ref={input}
                  rows={1}
                  aria-label="Finansal sorunuz"
                  onPaste={(e) => {
                    // A pasted screenshot is attached like a dropped file; pasted text is text.
                    const file = Array.from(e.clipboardData.files).find(
                      (item) => item.type.startsWith("image/"),
                    );
                    if (!uploads || !file) return;
                    e.preventDefault();
                    // Only the two formats the server reads; webp or gif pasted from a
                    // browser used to be renamed .jpg and refused without a word.
                    const extension =
                      file.type === "image/png"
                        ? "png"
                        : file.type === "image/jpeg"
                          ? "jpg"
                          : null;
                    if (!extension) {
                      setIssue(
                        "Yapıştırılan görsel PNG ya da JPG olmalı. Ekran görüntüsünü PNG olarak kaydedip yükleyebilirsin.",
                      );
                      return;
                    }
                    if (busyRef.current || pending || uploading) {
                      setIssue(
                        "Analiz sürerken belge eklenemiyor; tur bitince yeniden yapıştır.",
                      );
                      return;
                    }
                    void attach(
                      new File([file], `pano.${extension}`, {
                        type: file.type,
                      }),
                    );
                  }}
                  value={question}
                  onChange={(e) => {
                    pickedClarification.current = null;
                    setQuestion(e.target.value);
                  }}
                  placeholder={
                    pending
                      ? "Analiz sürüyor; bitince devam edebilirsin"
                      : items.length || transcript.length
                        ? items.at(-1)?.turn?.answer?.status === "abstained"
                          ? "Kısa bir cevap netleştirmeye eklenir; soru yazarsan yeni soru sayılır"
                          : "Devam et…"
                        : "Finansal sorunu yaz…"
                  }
                  maxLength={4096}
                  // Drafting is always allowed; only sending waits for the running
                  // turn (one turn at a time - the server refuses a second with 409).
                  onKeyDown={(e) => {
                    if (e.key === "Escape" && running && !stopRequested) {
                      e.preventDefault();
                      if (canStop) void stop();
                      else discardPending();
                      return;
                    }
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
                    <FileText size={13} /> Ekli belge:{" "}
                    {attachedName ?? attachment.document_format.toUpperCase()} ·{" "}
                    {/^.+\.(png|jpe?g)$/i.test(attachedName ?? "")
                      ? "görsel, tek sayfalık PDF olarak okunuyor"
                      : attachment.document_format.toUpperCase()}{" "}
                    · {Math.max(1, Math.round(attachment.bytes / 1024))} KB
                    <button
                      type="button"
                      aria-label="Ekli belgeyi kaldır"
                      disabled={busy || pending}
                      onClick={() => {
                        setAttachment(null);
                        setAttachedName(null);
                      }}
                    >
                      <X size={12} />
                    </button>
                  </div>
                )}
                {(pendingOffered.length > 0 ||
                  items.at(-1)?.turn?.answer?.status === "abstained") && (
                  <label className="composer-escape">
                    <input
                      type="checkbox"
                      checked={asNewQuestion}
                      disabled={busy || pending}
                      onChange={(event) =>
                        setAsNewQuestion(event.target.checked)
                      }
                    />
                    Bekleyen netleştirmeyi bırak, bunu yeni soru olarak gönder
                  </label>
                )}
                <div className="composer-bar">
                  <div className="composer-left">
                    {uploads ? (
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
                          aria-label="Belge ekle"
                          title={
                            "CSV, Excel, PDF, HTML ya da görsel (PNG, JPG) ekle; " +
                            "sürükleyip bırakabilir ya da ekran görüntüsünü " +
                            "yapıştırabilirsin (en fazla 10 MiB). Taranmış PDF ve görseller " +
                            (ocr ? "OCR ile okunur." : "için OCR kapalı.")
                          }
                          disabled={!ready || busy || pending || uploading}
                          onClick={() => picker.current?.click()}
                        >
                          {uploading ? (
                            <LoaderCircle size={18} className="spin" />
                          ) : (
                            <Plus size={18} />
                          )}
                        </Button>
                        <input
                          ref={imagePicker}
                          type="file"
                          accept=".png,.jpg,.jpeg,image/png,image/jpeg"
                          hidden
                          onChange={(e) => {
                            void attach(e.target.files?.[0]);
                            e.target.value = "";
                          }}
                        />
                        <Button
                          type="button"
                          size="icon"
                          variant="ghost"
                          aria-label="Görsel ekle"
                          title={
                            "Görsel ekle (PNG, JPG): tablo ekran görüntüsü, taranmış sayfa. " +
                            (ocr
                              ? "Metni ve tabloları OCR ile okunur; yalnız bu sohbette tutulur."
                              : "Bu sunucuda OCR kapalı olduğu için okunamaz.")
                          }
                          disabled={!ready || busy || pending || uploading}
                          onClick={() => imagePicker.current?.click()}
                        >
                          <ImageIcon size={18} />
                        </Button>
                      </>
                    ) : (
                      <Button
                        type="button"
                        size="icon"
                        variant="ghost"
                        aria-label="Belge ekleme kapalı"
                        title="Belge yükleme bu sunucuda kapatılmış."
                        disabled
                      >
                        <Plus size={18} />
                      </Button>
                    )}
                    <div className="model-menu">
                      <button
                        type="button"
                        className="model-pick"
                        aria-haspopup="dialog"
                        aria-expanded={modelMenu}
                        // It never chose anything: the deployment serves one model
                        // and the contract has no model field. It says which models
                        // are in use instead of pretending to be a chooser (F4-model).
                        title="Bu dağıtımın kullandığı modeller"
                        onClick={(e) => {
                          // The composer clips its children, so the menu is placed on the
                          // viewport from the button's own box instead of inside it.
                          const box = e.currentTarget.getBoundingClientRect();
                          setModelMenuAt({
                            left: box.left,
                            bottom: window.innerHeight - box.top + 8,
                          });
                          setModelMenu((open) => !open);
                        }}
                        onBlur={(e) => {
                          if (
                            !e.currentTarget.parentElement?.contains(
                              e.relatedTarget as Node | null,
                            )
                          )
                            setModelMenu(false);
                        }}
                      >
                        <Cpu size={14} /> {modelShort}
                        <Info size={12} />
                      </button>
                      {modelMenu && (
                        <ul
                          className="model-options"
                          aria-label="Kullanılan modeller"
                          style={{
                            left: modelMenuAt.left,
                            bottom: modelMenuAt.bottom,
                          }}
                        >
                          <li className="model-current">
                            <Check size={13} /> {modelLabel}
                          </li>
                          <li className="model-note">
                            Yarışma platformundaki en güçlü sohbet modeli.
                            Anlamsal arama Qwen3-Embedding-8B, belge ve görsel
                            okuma Unlimited-OCR ile yapılır.
                          </li>
                        </ul>
                      )}
                    </div>
                  </div>
                  <div className="composer-right">
                    {/* One round button: an arrow while idle, a running ring while a
                        turn is out, and pressing it again asks that turn to stop. The
                        separate "Durdur" button was a second control for the same
                        moment, and it went back to normal the instant the request was
                        accepted, although the turn stops only after the model call
                        that is out returns. */}
                    <Button
                      type={running ? "button" : "submit"}
                      size="icon"
                      className={
                        running
                          ? stopRequested
                            ? "send stopping"
                            : "send running"
                          : "send"
                      }
                      aria-label={
                        running
                          ? stopRequested
                            ? "Durduruluyor"
                            : canStop
                              ? "Durdur"
                              : "Bekleyen isteği bırak"
                          : "Gönder"
                      }
                      title={
                        running
                          ? stopRequested
                            ? "Durduruluyor: çalışan model isteği bitince duracak."
                            : canStop
                              ? "Çalışan model isteği bitince, bir sonraki adımdan önce durur."
                              : "Bu istek sunucuya iletilemedi; bırakıp yeniden yazabilirsin."
                          : undefined
                      }
                      disabled={
                        running
                          ? stopRequested
                          : !ready ||
                            !health ||
                            !dataset ||
                            uploading ||
                            !validQuestion(question)
                      }
                      onClick={
                        running
                          ? canStop
                            ? () => void stop()
                            : discardPending
                          : undefined
                      }
                    >
                      {running ? <Square size={13} /> : <ArrowUp size={17} />}
                    </Button>
                  </div>
                </div>
              </form>
              <p className="ai-note">
                DataTrio bir yapay zekâ analistidir: hesaplar araçlarla yapılır
                ve cevaplar kontrol edilir; önemli kararlarda kaynağı yine de
                doğrula.
              </p>
            </div>
          </section>
        ) : (
          <>
            {panel === "traces" && ownerToken && (
              <TracesPage
                owner={ownerToken}
                initialConversation={conversationId}
                initialTurn={tracing?.turnId ?? null}
              />
            )}
            {panel && panel !== "traces" && (
              <section className="page-view">
                <h2 id="panel-title">
                  {panel === "data"
                    ? "Veri ve bilgi tabanı"
                    : "Çalışma ayarları"}
                </h2>
                {/* Settings and sidebar failures set the same notice as the chat,
                    but it was drawn only inside the studio: a switch that did not
                    save snapped back with no word at all (finding F4-2). */}
                {issue && (
                  <div className="request-issue" role="alert">
                    <p>{issue}</p>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setIssue("")}
                    >
                      Kapat
                    </Button>
                  </div>
                )}
                {panel === "data" ? (
                  <>
                    <div className="page-stats">
                      <span>
                        <strong>{dataset?.prepared_identities ?? "—"}</strong>{" "}
                        hazır seri
                      </span>
                      <span>
                        <strong>{dataset?.catalog_identities ?? "—"}</strong>{" "}
                        katalog kaydı
                      </span>
                      {dataset && (
                        <span>
                          {(dataset.pool_bytes / 1024 / 1024).toLocaleString(
                            "tr-TR",
                            { maximumFractionDigits: 1 },
                          )}{" "}
                          MiB · {dataset.files} dosya
                        </span>
                      )}
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={loading}
                        onClick={() => void refresh()}
                      >
                        <RefreshCw size={14} /> Yenile
                      </Button>
                    </div>
                    {knowledgeBase && ownerToken ? (
                      <KnowledgePanel
                        owner={ownerToken}
                        documents={chatDocuments}
                        pool={dataset}
                        onOpenConversation={(id) => void openChat(id)}
                        session={
                          saved.current
                            ? {
                                id: saved.current.session.session_id,
                                token: saved.current.session.token,
                              }
                            : null
                        }
                      />
                    ) : (
                      <>
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
                                {series.first_period ?? "?"}{" "}
                                <ArrowRight size={12} />{" "}
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
                          Başlangıç ve bitiş tarihi, aradaki tüm dönemlerin
                          eksiksiz olduğu anlamına gelmez. Uygunluk analiz
                          sırasında ayrıca kontrol edilir.
                        </p>
                      </>
                    )}
                  </>
                ) : (
                  <>
                    <p className="panel-description">
                      Yetenekleri operatör servisi başlatırken açar; bu sayfa
                      neyin açık olduğunu gösterir. Doğrulama ve güvenlik
                      kontrolleri hiçbir ayara bağlı değildir.
                    </p>
                    <h3 className="settings-group">Yetenekler</h3>
                    <dl className="settings-list">
                      {capabilityRows.map((row) => {
                        const offered = settings?.available.includes(row.name);
                        const off =
                          settings?.disabled.includes(row.name) ?? false;
                        return (
                          <div key={row.name}>
                            <dt>{row.label}</dt>
                            <dd>
                              {!settings ? (
                                <span className="setting-off">—</span>
                              ) : !offered ? (
                                <span className="setting-off">
                                  {row.absent}
                                </span>
                              ) : (
                                <label className="setting-switch">
                                  <input
                                    type="checkbox"
                                    checked={!off}
                                    disabled={savingSetting !== ""}
                                    onChange={(event) =>
                                      void changeSetting({
                                        disabled: event.target.checked
                                          ? (settings?.disabled ?? []).filter(
                                              (item) => item !== row.name,
                                            )
                                          : [
                                              ...(settings?.disabled ?? []),
                                              row.name,
                                            ],
                                      })
                                    }
                                  />
                                  <span>{off ? "Kapalı" : row.on}</span>
                                </label>
                              )}
                            </dd>
                          </div>
                        );
                      })}
                    </dl>
                    <p className="helper">
                      Operatörün açmadığı bir yetenek buradan açılamaz; açık
                      olanı kendi sohbetlerin için kapatabilirsin.
                    </p>
                    <h3 className="settings-group">Bu tarayıcı</h3>
                    <dl className="settings-list">
                      <div>
                        <dt>Sohbet geçmişi</dt>
                        <dd>
                          {history
                            ? "Kalıcı; bu tarayıcının anahtarına bağlı"
                            : "Bu sekmeye özel"}
                        </dd>
                      </div>
                      <div>
                        <dt>Ajana gösterilen önceki tur</dt>
                        <dd>
                          {settings ? (
                            <label className="setting-switch">
                              <input
                                type="range"
                                min={0}
                                max={settings.max_history_turns}
                                value={historyDraft ?? settings.history_turns}
                                // Saving on every step sent one request per pixel and
                                // disabled the slider mid-drag, which broke the drag
                                // itself; the value is committed on release (F4-kaydırıcı).
                                onChange={(event) =>
                                  setHistoryDraft(Number(event.target.value))
                                }
                                onPointerUp={() => commitHistoryTurns()}
                                onKeyUp={() => commitHistoryTurns()}
                                onBlur={() => commitHistoryTurns()}
                              />
                              <span>
                                {(historyDraft ?? settings.history_turns) === 0
                                  ? "Yok"
                                  : `${historyDraft ?? settings.history_turns} tur`}
                                {savingSetting === "history_turns"
                                  ? " · kaydediliyor"
                                  : ""}
                              </span>
                            </label>
                          ) : (
                            "—"
                          )}
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
                        <dd>Her sohbet kendi kopyasında çalışır</dd>
                      </div>
                    </dl>
                    <h3 className="settings-group">Model ve sınırlar</h3>
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
                        <dt>Aynı anda çalışan analiz</dt>
                        <dd>{health?.max_running_turns ?? "—"}</dd>
                      </div>
                      <div>
                        <dt>Oturum başına soru</dt>
                        <dd>{health?.max_turns_per_session ?? "—"}</dd>
                      </div>
                    </dl>
                    <div className="panel-callout">
                      <ShieldCheck size={20} />
                      <p>
                        Doğrulama ve güvenlik kontrolleri model tercihine bağlı
                        değildir.
                      </p>
                    </div>
                    <h3 className="settings-group">Sistem istemi</h3>
                    <p className="helper">
                      Modele giden mesajların kaynak parçaları, içerik
                      özetleriyle. Her model çağrısının gönderilmiş tam istemi
                      işlem kayıtlarında; buradaki parçalar koddan okunur ve
                      tarayıcıdan değiştirilemez — bir oturum kendini denetleyen
                      kuralları yumuşatamaz.
                    </p>
                    {prompts === null ? (
                      <p className="helper">
                        {promptsState === "loading"
                          ? "İstem parçaları yükleniyor…"
                          : promptsState === "unsupported"
                            ? "Bu sunucu istem parçalarını sunmuyor (eski sürüm)."
                            : "İstem parçaları okunamadı; sayfayı yenilemeyi dene."}
                      </p>
                    ) : (
                      <ul className="prompt-parts">
                        {prompts.parts.map((part) => (
                          <li key={part.part_id}>
                            <button
                              type="button"
                              onClick={() =>
                                setOpenPrompt(
                                  openPrompt === part.part_id
                                    ? null
                                    : part.part_id,
                                )
                              }
                            >
                              <span>
                                {part.title}
                                <small>{part.sent_when}</small>
                              </span>
                              <code>{part.content_sha256.slice(0, 8)}</code>
                            </button>
                            {openPrompt === part.part_id && (
                              <pre>{part.content}</pre>
                            )}
                          </li>
                        ))}
                      </ul>
                    )}
                    <p className="helper">
                      {history
                        ? "Sohbetler, mesajlar, yüklenen belgeler, yayımlanan tablolar ve işlem kayıtları yeniden başlatmadan sonra da açılır. Bu tarayıcının anahtarı silinirse eski sohbetlere ulaşılamaz. Arşivlemek veri silmez."
                        : "API yeniden başlatılınca tarayıcı oturumu geçersiz olur."}{" "}
                      Yeni sohbet açmak önceki hesap dosyalarını silmez.
                      Gelişmiş agent davranışı ayarları sonraki geliştirmedir.
                    </p>
                  </>
                )}
              </section>
            )}
          </>
        )}
      </main>
    </div>
  );
}
