import { z } from "zod";
import {
  sessionSchema,
  turnSchema,
  savedSchema,
  type Saved,
  type Session,
} from "./contracts";
const KEY = "kkb.workspace.v1";
export class ApiError extends Error {
  constructor(public code: string) {
    super(code);
  }
}
export async function api<T>(
  path: string,
  schema: z.ZodType<T>,
  options: RequestInit = {},
  token?: string,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.method === "POST")
    headers.set("Content-Type", "application/json");
  if (token) headers.set("X-KKB-Session-Token", token);
  let response: Response;
  try {
    response = await fetch(`/api/kkb/v1/${path}`, {
      ...options,
      headers,
      cache: "no-store",
      signal: AbortSignal.timeout(12000),
    });
  } catch {
    throw new ApiError("connection");
  }
  let data: unknown;
  try {
    const text = await response.text();
    if (text.length > 1024 * 1024) throw new Error();
    data = JSON.parse(text);
  } catch {
    throw new ApiError("invalid_response");
  }
  if (!response.ok) {
    const parsed = z
      .object({ api_version: z.literal(1), error: z.string() })
      .strict()
      .safeParse(data);
    throw new ApiError(parsed.success ? parsed.data.error : "unavailable");
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
export function newSession() {
  return api("sessions", sessionSchema, { method: "POST", body: "{}" });
}
export async function readTurn(session: Session, id: string) {
  const turn = await api(
    `sessions/${session.session_id}/turns/${id}`,
    turnSchema,
    {},
    session.token,
  );
  if (turn.turn_id !== id) throw new ApiError("invalid_response");
  return turn;
}
export async function admit(saved: Saved, index: number) {
  const entry = saved.turns[index];
  if (entry.turn_id) return readTurn(saved.session, entry.turn_id);
  const turn = await api(
    `sessions/${saved.session.session_id}/turns`,
    turnSchema,
    {
      method: "POST",
      body: JSON.stringify({
        request_id: entry.request_id,
        question: entry.question,
      }),
    },
    saved.session.token,
  );
  if (turn.request_id !== entry.request_id)
    throw new ApiError("invalid_response");
  return turn;
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
