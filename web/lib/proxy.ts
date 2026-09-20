/** Fixed loopback bridge. Browser input never chooses a destination or capability. */
export const BODY_LIMIT = 16 * 1024;
/** M10-04: the one non-JSON body, a document upload, has its own byte and type limits. */
export const DOCUMENT_LIMIT = 10 * 1024 * 1024;
export const DOCUMENT_TYPES = new Set([
  "text/csv",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/pdf",
  "text/html",
  "image/png",
  "image/jpeg",
]);
export const RESPONSE_LIMIT = 1024 * 1024;
/** DEC-157: the one JSON body allowed past 16 KiB, a knowledge-base dataset. */
export const KNOWLEDGE_LIMIT = 1024 * 1024;
const REF = "[a-f0-9]{32}";
const route = new RegExp(`^v1/sessions/${REF}/turns(?:/${REF})?$`);
const documentRoute = new RegExp(`^v1/sessions/${REF}/documents$`);
const documentUrlRoute = new RegExp(`^v1/sessions/${REF}/documents/from-url$`);
const conversationRoute = new RegExp(`^v1/conversations/${REF}$`);
const runRoute = new RegExp(
  `^v1/conversations/${REF}/runs(?:/${REF}(?:/progress|/steps/[1-9][0-9]{0,5})?)?$`,
);
/** A stored trace holds every prompt and tool output, so it may exceed the usual ceiling. */
export const TRACE_LIMIT = 8 * 1024 * 1024;
/** A published table read back from its receipt, after any restart. */
const resultRoute = new RegExp(`^v1/conversations/${REF}/results/${REF}$`);
const feedbackRoute = new RegExp(`^v1/conversations/${REF}/feedback$`);
const cancelRoute = new RegExp(`^v1/sessions/${REF}/turns/${REF}/cancel$`);
const SLUG = "[a-z][a-z0-9_]{2,39}";
const datasetRoute = new RegExp(`^v1/knowledge/datasets/${SLUG}$`);
const datasetStatusRoute = new RegExp(
  `^v1/knowledge/datasets/${SLUG}/(?:archive|restore)$`,
);
const notesRoute =
  /^v1\/knowledge\/series\/[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}\/notes$/;
const valuesRoute =
  /^v1\/knowledge\/series\/[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}\/values$/;
const usesRoute =
  /^v1\/knowledge\/series\/[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}\/uses$/;
/** The filters the conversation list accepts, measured after decoding. */
export const LIST_FILTERS = {
  archived: /^(?:true|false)$/,
  search: /^[\s\S]{0,120}$/,
};
/** The one filter the knowledge search accepts, measured after decoding. */
export const SEARCH_FILTERS = { q: /^[\s\S]{1,512}$/ };
/**
 * A query string carrying only the named filters, each within its own bound.
 *
 * The bounds are on the characters the person typed, not on their percent-encoded
 * form: one Turkish letter encodes to six characters there, so a 20-letter search
 * was refused with 403 and no explanation (finding F4-vek-1). Anything else about
 * the query is still refused: an unknown key, a repeated key, a malformed escape,
 * a control character.
 */
export function queryWithin(
  search: string,
  filters: Record<string, RegExp>,
): boolean {
  if (!search) return false;
  const seen = new Set<string>();
  for (const part of search.split("&")) {
    const at = part.indexOf("=");
    if (at <= 0) return false;
    const key = part.slice(0, at);
    const filter = filters[key];
    if (!filter || seen.has(key)) return false;
    seen.add(key);
    let value: string;
    try {
      value = decodeURIComponent(part.slice(at + 1).replace(/\+/g, " "));
    } catch {
      return false;
    }
    if (CONTROL.test(value) || !filter.test(value)) return false;
  }
  return true;
}
const CONTROL = /[\u0000-\u001f\u007f]/;
const hosts = new Set(["127.0.0.1:3000", "localhost:3000"]);
const tokenPattern = /^[A-Za-z0-9_-]{43}$/;
const responseHeaders = {
  "Content-Type": "application/json",
  "Cache-Control": "no-store",
  "X-Content-Type-Options": "nosniff",
};
export function error(code: string, status: number) {
  return new Response(JSON.stringify({ api_version: 1, error: code }), {
    status,
    headers: responseHeaders,
  });
}
export function backendOrigin(value = "http://127.0.0.1:8000") {
  const url = new URL(value);
  if (
    !/^http:\/\/(127\.0\.0\.1|localhost):[0-9]{4,5}\/?$/.test(value) ||
    Number(url.port) < 1024 ||
    Number(url.port) > 65535
  )
    throw new Error("invalid_backend");
  return url.origin;
}
export function proxyTimeoutMs(value: string | undefined) {
  if (value === undefined) return 30000;
  if (!/^[1-9]\d*$/.test(value)) throw new Error("invalid_proxy_timeout");
  const timeout = Number(value);
  if (!Number.isSafeInteger(timeout) || timeout > 900000)
    throw new Error("invalid_proxy_timeout");
  return timeout;
}
export async function boundedRead(
  stream: ReadableStream<Uint8Array> | null,
  limit: number,
  signal: AbortSignal,
) {
  if (!stream) return new Uint8Array();
  const reader = stream.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  const abort = () => {
    void reader.cancel().catch(() => {});
  };
  signal.addEventListener("abort", abort, { once: true });
  try {
    while (true) {
      if (signal.aborted) throw new Error("timeout");
      const { done, value } = await reader.read();
      if (signal.aborted) throw new Error("timeout");
      if (done) break;
      size += value.byteLength;
      if (size > limit) throw new Error("body_limit");
      chunks.push(value);
    }
    const result = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) {
      result.set(chunk, offset);
      offset += chunk.byteLength;
    }
    return result;
  } finally {
    signal.removeEventListener("abort", abort);
    void reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
export async function forward(
  request: Request,
  path: string[],
  transport: typeof fetch = fetch,
  target?: string,
) {
  const host = request.headers.get("host");
  const origin = request.headers.get("origin");
  const site = request.headers.get("sec-fetch-site");
  if (
    !host ||
    !hosts.has(host) ||
    (origin !== null && origin !== `http://${host}`) ||
    (site !== null && !["same-origin", "none"].includes(site))
  )
    return error("forbidden", 403);
  // Every write states its origin, not only POST: a page from elsewhere must not
  // be able to rename, archive or delete through this bridge (finding F4-vek-3).
  if (request.method !== "GET" && origin !== `http://${host}`)
    return error("forbidden", 403);
  const name = path.join("/");
  const publicGet = ["v1/health", "v1/dataset"].includes(name);
  const creation = name === "v1/sessions";
  const owner = name === "v1/owner";
  const list = name === "v1/conversations";
  const traceList = name === "v1/trace-conversations";
  const conversation = conversationRoute.test(name);
  const runs = runRoute.test(name);
  const deleteConversation = conversation && request.method === "DELETE";
  const deleteRuns = runs && path.length === 4 && request.method === "DELETE";
  const feedback = feedbackRoute.test(name);
  const results = resultRoute.test(name);
  const turns = route.test(name);
  const documents = documentRoute.test(name);
  const cancel = cancelRoute.test(name);
  const documentFromUrl = documentUrlRoute.test(name);
  const settings = name === "v1/settings";
  const prompts = name === "v1/prompts";
  const knowledgeList = name === "v1/knowledge";
  const knowledgeSearch = name === "v1/knowledge/search";
  const vectorIndex = name === "v1/knowledge/index";
  const directoryRefresh = name === "v1/knowledge/directory";
  const datasetSave = name === "v1/knowledge/datasets";
  const dataset = datasetRoute.test(name);
  const datasetStatus = datasetStatusRoute.test(name);
  const notes = notesRoute.test(name);
  const values = valuesRoute.test(name);
  const uses = usesRoute.test(name);
  const knowledge =
    knowledgeList ||
    knowledgeSearch ||
    vectorIndex ||
    directoryRefresh ||
    datasetSave ||
    dataset ||
    datasetStatus ||
    notes ||
    values ||
    uses ||
    settings ||
    prompts;
  const getTurn = turns && path.length === 5;
  const search = new URL(request.url).search.replace(/^\?/, "");
  if (
    search &&
    !((list || traceList) && queryWithin(search, LIST_FILTERS)) &&
    !(knowledgeSearch && queryWithin(search, SEARCH_FILTERS))
  )
    return error("forbidden", 403);
  if (
    !(
      request.method === "GET" &&
      (publicGet ||
        getTurn ||
        list ||
        traceList ||
        settings ||
        prompts ||
        conversation ||
        runs ||
        results ||
        feedback ||
        knowledgeList ||
        knowledgeSearch ||
        vectorIndex ||
        dataset ||
        notes ||
        values ||
        uses)
    ) &&
    !(
      request.method === "POST" &&
      (creation ||
        owner ||
        documents ||
        feedback ||
        cancel ||
        documentFromUrl ||
        datasetSave ||
        datasetStatus ||
        notes ||
        vectorIndex ||
        directoryRefresh ||
        (turns && path.length === 4))
    ) &&
    !(request.method === "PATCH" && (conversation || settings)) &&
    !(deleteConversation || deleteRuns)
  )
    return error("not_found", 404);
  const headers = new Headers({ Accept: "application/json" });
  if (
    turns ||
    documents ||
    (conversation && !deleteConversation) ||
    (runs && !deleteRuns) ||
    results ||
    feedback ||
    cancel ||
    documentFromUrl
  ) {
    const token = request.headers.get("x-kkb-session-token");
    if (!token || !tokenPattern.test(token)) return error("not_found", 404);
    headers.set("X-KKB-Session-Token", token);
  }
  if (knowledge) {
    // The knowledge base is the browser key's: every read and edit names its owner.
    const key = request.headers.get("x-kkb-owner-token");
    if (!key || !tokenPattern.test(key)) return error("not_found", 404);
    headers.set("X-KKB-Owner-Token", key);
  }
  if (list || traceList || creation || deleteConversation || deleteRuns) {
    // The browser's own key: required to list, optional only where the backend says so.
    const key = request.headers.get("x-kkb-owner-token");
    if (key && !tokenPattern.test(key)) return error("not_found", 404);
    if (!key && (list || traceList || deleteConversation || deleteRuns))
      return error("not_found", 404);
    if (key) headers.set("X-KKB-Owner-Token", key);
  }
  let timeoutMs: number;
  try {
    timeoutMs = proxyTimeoutMs(process.env.KKB_PROXY_TIMEOUT_MS);
  } catch {
    return error("unavailable", 503);
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const disconnect = () => controller.abort();
  request.signal.addEventListener("abort", disconnect, { once: true });
  try {
    const backend = backendOrigin(target ?? process.env.KKB_LOCAL_API_URL);
    headers.set("Origin", backend);
    let body: string | Uint8Array<ArrayBuffer> | undefined;
    if (request.method === "POST" && documents) {
      const type = (request.headers.get("content-type") ?? "")
        .split(";")[0]
        .trim()
        .toLowerCase();
      if (!DOCUMENT_TYPES.has(type)) return error("invalid_request", 415);
      const declared = request.headers.get("content-length");
      if (
        declared &&
        (!/^\d+$/.test(declared) || Number(declared) > DOCUMENT_LIMIT)
      )
        return error("body_too_large", 413);
      try {
        body = await boundedRead(
          request.body,
          DOCUMENT_LIMIT,
          controller.signal,
        );
      } catch {
        return error(
          controller.signal.aborted ? "unavailable" : "body_too_large",
          controller.signal.aborted ? 503 : 413,
        );
      }
      headers.set("Content-Type", type);
    } else if (request.method === "POST" || request.method === "PATCH") {
      if (
        !/^application\/json(?:;\s*charset=utf-8)?$/i.test(
          request.headers.get("content-type") ?? "",
        )
      )
        return error("invalid_request", 415);
      const limit = datasetSave ? KNOWLEDGE_LIMIT : BODY_LIMIT;
      const declared = request.headers.get("content-length");
      if (declared && (!/^\d+$/.test(declared) || Number(declared) > limit))
        return error("body_too_large", 413);
      try {
        body = new TextDecoder("utf-8", { fatal: true }).decode(
          await boundedRead(request.body, limit, controller.signal),
        );
      } catch {
        return error(
          controller.signal.aborted ? "unavailable" : "body_too_large",
          controller.signal.aborted ? 503 : 413,
        );
      }
      headers.set("Content-Type", "application/json");
    }
    const upstream = await transport(
      `${backend}/${name}${search ? `?${search}` : ""}`,
      {
        method: request.method,
        headers,
        body,
        cache: "no-store",
        redirect: "error",
        signal: controller.signal,
      },
    );
    if (!upstream.headers.get("content-type")?.startsWith("application/json"))
      return error("unavailable", 502);
    const bytes = await boundedRead(
      upstream.body,
      runs && path.length > 4 ? TRACE_LIMIT : RESPONSE_LIMIT,
      controller.signal,
    );
    return new Response(bytes, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch {
    return error("unavailable", 503);
  } finally {
    clearTimeout(timer);
    request.signal.removeEventListener("abort", disconnect);
  }
}
