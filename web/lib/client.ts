import { z } from "zod";
import {
  conversationDetailSchema,
  conversationListSchema,
  conversationSummarySchema,
  documentAdmittedSchema,
  feedbackListSchema,
  feedbackSchema,
  knowledgeListSchema,
  datasetDetailSchema,
  noteHistorySchema,
  seriesValuesSchema,
  type DatasetRequest,
  ownerSchema,
  runDetailSchema,
  runtimeSettingsSchema,
  searchTrialSchema,
  traceStepFullSchema,
  runListSchema,
  sessionSchema,
  turnSchema,
  vectorIndexSchema,
  savedSchema,
  type DocumentAdmitted,
  type Saved,
  type Session,
  type Turn,
} from "./contracts";
const KEY = "kkb.workspace.v1";
/** The browser's own key for its conversations; without it, earlier chats stay closed. */
const OWNER_KEY = "kkb.owner.v1";
export class ApiError extends Error {
  constructor(
    public code: string,
    public status?: number,
  ) {
    super(code);
  }
}
export async function api<T>(
  path: string,
  schema: z.ZodType<T>,
  options: RequestInit = {},
  token?: string,
  ownerToken?: string,
  limits: { bytes?: number; timeoutMs?: number } = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (
    (options.method === "POST" || options.method === "PATCH") &&
    !headers.has("Content-Type")
  )
    headers.set("Content-Type", "application/json");
  if (token) headers.set("X-KKB-Session-Token", token);
  if (ownerToken) headers.set("X-KKB-Owner-Token", ownerToken);
  let response: Response;
  try {
    response = await fetch(`/api/kkb/v1/${path}`, {
      ...options,
      headers,
      cache: "no-store",
      signal: AbortSignal.timeout(limits.timeoutMs ?? 12000),
    });
  } catch {
    throw new ApiError("connection");
  }
  let data: unknown;
  try {
    const text = await response.text();
    if (text.length > (limits.bytes ?? 1024 * 1024)) throw new Error();
    data = JSON.parse(text);
  } catch {
    throw new ApiError("invalid_response");
  }
  if (!response.ok) {
    const parsed = z
      .object({ api_version: z.literal(1), error: z.string() })
      .strict()
      .safeParse(data);
    throw new ApiError(
      parsed.success ? parsed.data.error : "unavailable",
      response.status,
    );
  }
  const parsed = schema.safeParse(data);
  if (!parsed.success) throw new ApiError("invalid_response");
  return parsed.data;
}
export function loadSession(storage: Storage): Saved | null {
  try {
    const raw = storage.getItem(KEY);
    if (!raw || raw.length > 256 * 1024) return null;
    const parsed = savedSchema.safeParse(JSON.parse(raw));
    return parsed.success ? parsed.data : null;
  } catch {
    return null;
  }
}
export function saveSession(storage: Storage, value: Saved) {
  // Persist the request BEFORE sending it; failure must not silently create a second turn.
  storage.setItem(KEY, JSON.stringify(savedSchema.parse(value)));
}
export function clearSession(storage: Storage) {
  storage.removeItem(KEY);
}
export function loadOwner(storage: Storage) {
  try {
    const value = storage.getItem(OWNER_KEY);
    return value && /^[A-Za-z0-9_-]{43}$/.test(value) ? value : null;
  } catch {
    return null;
  }
}
export async function ensureOwner(storage: Storage) {
  const existing = loadOwner(storage);
  if (existing) return existing;
  const created = await api("owner", ownerSchema, {
    method: "POST",
    body: "{}",
  });
  try {
    storage.setItem(OWNER_KEY, created.owner_token);
  } catch {
    // A browser without storage still works for this session; history will not follow it.
  }
  return created.owner_token;
}
/**
 * The stored key if this server knows it, otherwise a fresh one. A key from another
 * state root opens nothing here, so keeping it would only turn every list into an error.
 */
export async function usableOwner(storage: Storage) {
  const stored = loadOwner(storage);
  if (stored) {
    try {
      await listConversations(stored);
      return stored;
    } catch (error) {
      if (!(error instanceof ApiError && error.status === 403)) throw error;
      try {
        storage.removeItem(OWNER_KEY);
      } catch {
        // Storage refused: a new key is still issued for this page.
      }
    }
  }
  return ensureOwner(storage);
}
export function newSession(ownerToken?: string) {
  return api(
    "sessions",
    sessionSchema,
    { method: "POST", body: "{}" },
    undefined,
    ownerToken,
  );
}
export function listConversations(
  ownerToken: string,
  options: { archived?: boolean; search?: string } = {},
) {
  const query = new URLSearchParams();
  if (options.archived) query.set("archived", "true");
  if (options.search) query.set("search", options.search.slice(0, 120));
  const suffix = query.toString();
  return api(
    `conversations${suffix ? `?${suffix}` : ""}`,
    conversationListSchema,
    {},
    undefined,
    ownerToken,
  );
}
export function openConversation(conversationId: string, token: string) {
  return api(
    `conversations/${conversationId}`,
    conversationDetailSchema,
    {},
    token,
  );
}
export function rateAnswer(
  conversationId: string,
  token: string,
  rating: {
    turn_id: string;
    rating: "up" | "down";
    comment?: string;
    reasons?: readonly string[];
    score?: number;
  },
) {
  return api(
    `conversations/${conversationId}/feedback`,
    feedbackSchema,
    { method: "POST", body: JSON.stringify(rating) },
    token,
  );
}
// -- Settings (DEC-162): a browser narrows its own runtime, never widens it.
export function readSettings(owner: string) {
  return api("settings", runtimeSettingsSchema, {}, undefined, owner);
}
export function saveSettings(
  owner: string,
  change: { disabled?: string[]; history_turns?: number },
) {
  return api(
    "settings",
    runtimeSettingsSchema,
    { method: "PATCH", body: JSON.stringify(change) },
    undefined,
    owner,
  );
}

// -- Knowledge base (DEC-157): every read and edit carries the browser's key.
export function listKnowledge(owner: string) {
  return api("knowledge", knowledgeListSchema, {}, undefined, owner);
}
export function trySearch(owner: string, query: string) {
  // Reading what discovery would find starts no analysis and stores nothing.
  return api(
    `knowledge/search?q=${encodeURIComponent(query.slice(0, 512))}`,
    searchTrialSchema,
    {},
    undefined,
    owner,
  );
}
export function readIndex(owner: string) {
  return api("knowledge/index", vectorIndexSchema, {}, undefined, owner);
}
export function rebuildIndex(owner: string) {
  // Accepted, not finished: the build embeds every catalogue entry again.
  return api(
    "knowledge/index",
    vectorIndexSchema,
    { method: "POST", body: "{}" },
    undefined,
    owner,
  );
}
export function openDataset(owner: string, slug: string) {
  return api(
    `knowledge/datasets/${slug}`,
    datasetDetailSchema,
    {},
    undefined,
    owner,
  );
}
export function saveDataset(owner: string, request: DatasetRequest) {
  return api(
    "knowledge/datasets",
    datasetDetailSchema,
    { method: "POST", body: JSON.stringify(request) },
    undefined,
    owner,
  );
}
export function setDatasetArchived(
  owner: string,
  slug: string,
  archived: boolean,
) {
  return api(
    `knowledge/datasets/${slug}/${archived ? "archive" : "restore"}`,
    datasetDetailSchema,
    { method: "POST", body: "{}" },
    undefined,
    owner,
  );
}
/**
 * "2025-01-03;100" lines, the period end written as a full date (weekly data).
 * The date is kept as written; the server checks it falls on the declared weekday.
 */
export function parseDatedRows(text: string) {
  const observations: { period_end: string; value: number | null }[] = [];
  const rejected: number[] = [];
  text.split(/\r?\n/).forEach((line, index) => {
    const trimmed = line.trim();
    if (!trimmed) return;
    const match = trimmed.match(
      /^(\d{4}-\d{2}-\d{2})\s*[;,\t]\s*(-?\d+(?:[.,]\d+)?)?\s*$/,
    );
    const day = match ? new Date(`${match[1]}T00:00:00Z`) : null;
    if (
      !match ||
      !day ||
      Number.isNaN(day.getTime()) ||
      day.toISOString().slice(0, 10) !== match[1]
    ) {
      rejected.push(index + 1);
      return;
    }
    observations.push({
      period_end: match[1],
      value: match[2] === undefined ? null : Number(match[2].replace(",", ".")),
    });
  });
  return { observations, rejected };
}
export function seriesValues(owner: string, seriesId: string) {
  return api(
    `knowledge/series/${seriesId}/values`,
    seriesValuesSchema,
    {},
    undefined,
    owner,
  );
}
export function seriesNotes(owner: string, seriesId: string) {
  return api(
    `knowledge/series/${seriesId}/notes`,
    noteHistorySchema,
    {},
    undefined,
    owner,
  );
}
export function annotateSeries(
  owner: string,
  seriesId: string,
  note: { archived: boolean; aliases: string[]; note?: string },
) {
  return api(
    `knowledge/series/${seriesId}/notes`,
    noteHistorySchema,
    { method: "POST", body: JSON.stringify(note) },
    undefined,
    owner,
  );
}
/**
 * "2025-01;100" or "2025-01-31,100" lines into month-end observations; an empty
 * value stays empty. Returns the line numbers it could not read instead of guessing.
 */
export function parseMonthlyRows(text: string) {
  const observations: { period_end: string; value: number | null }[] = [];
  const rejected: number[] = [];
  text.split(/\r?\n/).forEach((line, index) => {
    const trimmed = line.trim();
    if (!trimmed) return;
    const match = trimmed.match(
      /^(\d{4})-(\d{2})(?:-\d{2})?\s*[;,\t]\s*(-?\d+(?:[.,]\d+)?)?\s*$/,
    );
    const month = match ? Number(match[2]) : 0;
    if (!match || month < 1 || month > 12) {
      rejected.push(index + 1);
      return;
    }
    const end = new Date(Date.UTC(Number(match[1]), month, 0));
    observations.push({
      period_end: end.toISOString().slice(0, 10),
      value: match[3] === undefined ? null : Number(match[3].replace(",", ".")),
    });
  });
  return { observations, rejected };
}
/** Ask a running turn to stop at its next checkpoint; the turn is then polled as usual. */
export function cancelTurn(sessionId: string, token: string, turnId: string) {
  return api(
    `sessions/${sessionId}/turns/${turnId}/cancel`,
    turnSchema,
    { method: "POST", body: "{}" },
    token,
  );
}
export function listFeedback(conversationId: string, token: string) {
  return api(
    `conversations/${conversationId}/feedback`,
    feedbackListSchema,
    {},
    token,
  );
}
export function listRuns(conversationId: string, token: string) {
  return api(`conversations/${conversationId}/runs`, runListSchema, {}, token);
}
/** A trace carries every prompt and tool output; it is read with a larger ceiling. */
export const TRACE_BYTES = 8 * 1024 * 1024;
export function openRun(conversationId: string, runId: string, token: string) {
  // Reading a trace is a stored record: it starts no model or tool call.
  return api(
    `conversations/${conversationId}/runs/${runId}`,
    runDetailSchema,
    {},
    token,
    undefined,
    { bytes: TRACE_BYTES, timeoutMs: 30000 },
  );
}
/** One step's whole detail: every prompt byte and every tool output, never clipped. */
export function openRunStep(
  conversationId: string,
  runId: string,
  sequence: number,
  token: string,
) {
  return api(
    `conversations/${conversationId}/runs/${runId}/steps/${sequence}`,
    traceStepFullSchema,
    {},
    token,
    undefined,
    { bytes: TRACE_BYTES, timeoutMs: 30000 },
  );
}
export function updateConversation(
  conversationId: string,
  token: string,
  change: { title?: string; archived?: boolean },
) {
  return api(
    `conversations/${conversationId}`,
    conversationSummarySchema,
    { method: "PATCH", body: JSON.stringify(change) },
    token,
  );
}
export async function readTurn(
  session: Session,
  id: string,
  requestId?: string,
) {
  const turn = await api(
    `sessions/${session.session_id}/turns/${id}`,
    turnSchema,
    {},
    session.token,
  );
  if (turn.turn_id !== id || (requestId && turn.request_id !== requestId))
    throw new ApiError("invalid_response");
  return turn;
}
export async function admit(saved: Saved, index: number) {
  const entry = saved.turns[index];
  if (entry.admission_error) throw new ApiError(entry.admission_error, 400);
  if (entry.turn_id)
    return readTurn(saved.session, entry.turn_id, entry.request_id);
  const turn = await api(
    `sessions/${saved.session.session_id}/turns`,
    turnSchema,
    {
      method: "POST",
      body: JSON.stringify({
        request_id: entry.request_id,
        question: entry.question,
        selected_result_id: entry.selected_result_id,
        ...(entry.is_continuation !== undefined
          ? { is_continuation: entry.is_continuation }
          : {}),
        ...(entry.document_ref ? { document_ref: entry.document_ref } : {}),
      }),
    },
    saved.session.token,
  );
  if (turn.request_id !== entry.request_id)
    throw new ApiError("invalid_response");
  return turn;
}
const documentTypes: Record<string, string> = {
  csv: "text/csv",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  pdf: "application/pdf",
  html: "text/html",
  htm: "text/html",
};
export const DOCUMENT_ACCEPT = ".csv,.xlsx,.pdf,.html,.htm";

/** The upload media type follows the file extension only; the server checks the content. */
export function documentMediaType(name: string) {
  const extension = name.toLowerCase().match(/\.([a-z]+)$/)?.[1];
  return extension ? documentTypes[extension] : undefined;
}
export async function uploadDocument(
  session: Session,
  file: File,
): Promise<DocumentAdmitted> {
  const type = documentMediaType(file.name);
  if (!type) throw new ApiError("document_rejected", 415);
  if (file.size < 1 || file.size > 10 * 1024 * 1024)
    throw new ApiError("body_too_large", 413);
  return api(
    `sessions/${session.session_id}/documents`,
    documentAdmittedSchema,
    { method: "POST", body: file, headers: { "Content-Type": type } },
    session.token,
  );
}
export function publishedResult(turn?: Turn) {
  return turn?.state === "completed" && turn.answer?.status === "accepted"
    ? (turn.answer.result ?? undefined)
    : undefined;
}
export function restoredSelection(saved: Saved, turns: (Turn | undefined)[]) {
  if (saved.view_result_id)
    return turns.findIndex(
      (turn) => publishedResult(turn)?.result_ref === saved.view_result_id,
    );
  return turns.findLastIndex((turn) => Boolean(publishedResult(turn)));
}
export function draftRequest(
  question: string,
  source?: Turn,
  isContinuation?: boolean,
  document?: DocumentAdmitted,
): Saved["turns"][number] {
  if (!validQuestion(question)) throw new ApiError("invalid_request");
  const result = publishedResult(source);
  if (source && !result) throw new ApiError("invalid_result");
  return {
    request_id: crypto.randomUUID().replaceAll("-", ""),
    question: question.trim(),
    ...(result ? { selected_result_id: result.result_ref } : {}),
    ...(isContinuation !== undefined
      ? { is_continuation: isContinuation }
      : {}),
    ...(document
      ? {
          document_ref: document.document_ref,
          document_format: document.document_format,
        }
      : {}),
  };
}
export function admissionRejection(
  error: unknown,
): Saved["turns"][number]["admission_error"] {
  if (
    !(error instanceof ApiError) ||
    !error.status ||
    error.status < 400 ||
    error.status >= 500
  )
    return undefined;
  switch (error.code) {
    case "invalid_result":
    case "invalid_request":
    case "request_conflict":
    case "capacity":
    case "invalid_document":
      return error.code;
    default:
      return undefined;
  }
}
export function validQuestion(value: string) {
  return (
    value.trim().length > 0 &&
    value.length <= 4096 &&
    new TextEncoder().encode(value).length <= 8192 &&
    !/[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(value)
  );
}
export const errorText: Record<string, string> = {
  document_rejected:
    "Belge kabul edilmedi. CSV, Excel (.xlsx), PDF veya HTML olmalı ve içerik kontrollerinden geçmeli.",
  invalid_document:
    "Ekli belge bu oturumda bulunamadı ya da değişmiş. Belgeyi yeniden yükle.",
  body_too_large:
    "İstek veya belge boyut sınırını aşıyor (belgeler için 10 MiB).",
  connection:
    "Bağlantı kesildi. İstek korunuyor; aynı işlemin durumunu yeniden alabilirsin.",
  unavailable:
    "Yerel analiz servisine ulaşılamıyor. API’nin çalıştığını kontrol et.",
  busy: "Başka bir analiz devam ediyor. Bitince aynı isteği yeniden gönderebilirsin.",
  capacity: "Bu oturumun veya servisin işlem sınırına ulaşıldı.",
  not_found:
    "Oturum bulunamadı. API yeniden başlamış olabilir; yeni oturum açmalısın.",
  forbidden:
    "Yerel bağlantı doğrulanamadı. Arayüzü 127.0.0.1:3000 adresinden aç.",
  planning_failed:
    "Model uygulanabilir bir plan üretemedi. Soruyu daha açık bir dönem ve ölçüyle yeniden kur.",
  provider_failed: "Model isteği tamamlanamadı. Önceki tablolar korunuyor.",
  invalid_result:
    "Kaynak tablo bu oturumda kullanılamıyor. Geçerli bir sonuç seçip yeni soru gönderebilirsin.",
  session_gone:
    "Bu sekmedeki oturum sunucuda artık yok (sunucu yeniden başlatılmış olabilir). Yeni bir sohbet açıldı; kayıtlı sohbetler soldaki listede.",
  selection_unavailable:
    "Kayıtlı kaynak tablo yüklenemedi. Yeni bir soru gönderebilirsin; ajan kullanılabilir tabloları kendisi seçer.",
  cancelled:
    "İstek durduruldu. O ana kadar yapılanlar işlem kaydında duruyor; tablo yayımlanmadı.",
  invalid_request:
    "İstek kabul edilmedi. Soruyu ve metin uzunluğunu kontrol et.",
  invalid_response: "Yanıt beklenen veri biçimine uymuyor; sonuç gösterilmedi.",
  output_limit:
    "Sonuç gösterim sınırını aştı. Daha dar bir dönem veya kapsam iste.",
  request_conflict:
    "Bu istek kimliği farklı bir soruya ait. Mevcut isteği tamamla.",
  internal_error: "Analiz tamamlanamadı. Önceki sonuçlar korunuyor.",
};
export function describeError(error: unknown) {
  return error instanceof ApiError
    ? (errorText[error.code] ??
        "İşlem tamamlanamadı. Önceki sonuçlar korunuyor.")
    : "Tarayıcı oturum kaydını tutamadı. Depolama izinlerini kontrol et.";
}
