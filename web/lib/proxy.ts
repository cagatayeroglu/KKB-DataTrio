/** Fixed loopback bridge. Browser input never chooses a destination or capability. */
export const BODY_LIMIT = 16 * 1024;
/** M10-04: the one non-JSON body, a document upload, has its own byte and type limits. */
export const DOCUMENT_LIMIT = 10 * 1024 * 1024;
export const DOCUMENT_TYPES = new Set([
  "text/csv",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/pdf",
  "text/html",
]);
export const RESPONSE_LIMIT = 1024 * 1024;
const REF = "[a-f0-9]{32}";
const route = new RegExp(`^v1/sessions/${REF}/turns(?:/${REF})?$`);
const documentRoute = new RegExp(`^v1/sessions/${REF}/documents$`);
const conversationRoute = new RegExp(`^v1/conversations/${REF}$`);
const runRoute = new RegExp(`^v1/conversations/${REF}/runs(?:/${REF})?$`);
const feedbackRoute = new RegExp(`^v1/conversations/${REF}/feedback$`);
/** Only the conversation list carries a query, and only these bounded filters. */
export const LIST_QUERY =
  /^(?:archived=(?:true|false)|search=[^&]{0,120})(?:&(?:archived=(?:true|false)|search=[^&]{0,120}))?$/;
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
  if (request.method === "POST" && origin !== `http://${host}`)
    return error("forbidden", 403);
  const name = path.join("/");
  const publicGet = ["v1/health", "v1/dataset"].includes(name);
  const creation = name === "v1/sessions";
  const owner = name === "v1/owner";
  const list = name === "v1/conversations";
  const conversation = conversationRoute.test(name);
  const runs = runRoute.test(name);
  const feedback = feedbackRoute.test(name);
  const turns = route.test(name);
  const documents = documentRoute.test(name);
  const getTurn = turns && path.length === 5;
  const search = new URL(request.url).search.replace(/^\?/, "");
  if (search && !(list && LIST_QUERY.test(search)))
    return error("forbidden", 403);
  if (
    !(
      request.method === "GET" &&
      (publicGet || getTurn || list || conversation || runs || feedback)
    ) &&
    !(
      request.method === "POST" &&
      (creation ||
        owner ||
        documents ||
        feedback ||
        (turns && path.length === 4))
    ) &&
    !(request.method === "PATCH" && conversation)
  )
    return error("not_found", 404);
  const headers = new Headers({ Accept: "application/json" });
  if (turns || documents || conversation || runs || feedback) {
    const token = request.headers.get("x-kkb-session-token");
    if (!token || !tokenPattern.test(token)) return error("not_found", 404);
    headers.set("X-KKB-Session-Token", token);
  }
  if (list || creation) {
    // The browser's own key: required to list, optional only where the backend says so.
    const key = request.headers.get("x-kkb-owner-token");
    if (key && !tokenPattern.test(key)) return error("not_found", 404);
    if (!key && list) return error("not_found", 404);
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
      const declared = request.headers.get("content-length");
      if (
        declared &&
        (!/^\d+$/.test(declared) || Number(declared) > BODY_LIMIT)
      )
        return error("body_too_large", 413);
      try {
        body = new TextDecoder("utf-8", { fatal: true }).decode(
          await boundedRead(request.body, BODY_LIMIT, controller.signal),
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
      RESPONSE_LIMIT,
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
