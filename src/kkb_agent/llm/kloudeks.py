"""The Kloudeks transport behind LLMProvider (M4-07, DEC-129, SEC-KLO-01).

DEC-129 names one destination: the organizer's OpenAI-compatible endpoint,
authenticated with the team's MIA key. This module is the only code that sends
that key anywhere, so the destination rule is enforced here when the provider
is built and again on every request, rather than trusted to the environment:

- the base URL comes from trusted configuration and must be DEC-129's host
  over https, with no credentials, port, query or fragment in it;
- request paths are fixed and the model must be one the configuration names,
  so neither a user nor a model can steer a request, or the key, elsewhere;
- redirects are never followed, so the key cannot be forwarded to another
  origin, and `trust_env` is off, so no proxy, netrc or certificate override
  is picked up from the environment;
- every response is streamed under a byte cap and a total deadline.

Errors carry a status category and never the key, the prompt or the body the
server returned, since that body may echo the prompt.

The `openai` SDK that DEC-129 permits is not used. It falls back to a base URL
and key read from the environment when none is passed, and retries on its own;
both are behaviours this boundary would have to switch off. A thin client over
`httpx` keeps each rule in one place where a test can see it.
"""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Sequence
from dataclasses import replace
from math import isfinite
from typing import Any, Final
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel

from kkb_agent.llm.config import BASE_URL, ProviderConfig
from kkb_agent.llm.provider import (
    CapabilityUnavailable,
    Completion,
    ConfigurationError,
    EmbeddingKind,
    Message,
    ModelUnavailable,
    ProviderError,
    RateLimited,
    Refused,
    Role,
    TransportError,
    Usage,
)
from kkb_agent.llm.structured import complete_with_repair

#: DEC-129's host and API path. Moving either needs a DECISIONS entry, not an
#: environment variable: the environment is where a wrong destination hides.
APPROVED_HOSTS: Final = frozenset({"mia.csp.kloudeks.com"})
API_PATH: Final = "/v1"
CHAT_PATH: Final = "/chat/completions"
EMBEDDINGS_PATH: Final = "/embeddings"

#: Largest response body read. A chat completion is kilobytes; a batch of
#: embedding vectors can reach megabytes.
MAX_RESPONSE_BYTES: Final = 16 * 1024 * 1024

#: Images are sent inline only — DEC-129 forbids external image URLs. The
#: platform's own size limit is undocumented, so this cap is conservative.
MAX_IMAGE_BYTES: Final = 8 * 1024 * 1024
_IMAGE_SIGNATURES: Final = ((b"\x89PNG\r\n\x1a\n", "image/png"), (b"\xff\xd8\xff", "image/jpeg"))


def approved_base_url(url: str) -> str:
    """The configured base URL, normalized, if DEC-129 allows the key to go there.

    Messages name the setting, never the value: a URL can carry credentials.
    """
    parts = urlsplit(url.strip())
    try:
        port = parts.port
    except ValueError:
        port = -1
    if parts.scheme != "https":
        raise ConfigurationError(f"{BASE_URL} must be an https URL")
    if parts.username is not None or parts.password is not None:
        raise ConfigurationError(f"{BASE_URL} must not carry credentials")
    if parts.query or parts.fragment or port is not None:
        raise ConfigurationError(f"{BASE_URL} must not carry a port, query or fragment")
    host = (parts.hostname or "").lower()
    if host not in APPROVED_HOSTS or parts.path.rstrip("/") != API_PATH:
        raise ConfigurationError(f"{BASE_URL} is not the DEC-129 Kloudeks endpoint")
    return f"https://{host}{API_PATH}"


class KloudeksProvider:
    """`LLMProvider` over DEC-129's OpenAI-compatible chat and embedding endpoints.

    Transport faults are not retried here; that policy is M4-10's. Schema
    repair is: `complete_with_repair` feeds a malformed answer's fault back
    within the configured attempt budget, exactly as the scripted double does.
    """

    def __init__(
        self, config: ProviderConfig, *, transport: httpx.BaseTransport | None = None
    ) -> None:
        self._config = config
        # The chat model also reads images (DEC-129), so any configured chat
        # identifier may be named by a caller; nothing else may.
        self._chat_models = frozenset(
            name
            for name in (config.planner_model, config.router_model, config.vision_model)
            if name is not None
        )
        self._client = httpx.Client(
            base_url=approved_base_url(config.base_url),
            timeout=httpx.Timeout(config.request_timeout),
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )

    @classmethod
    def from_env(cls) -> KloudeksProvider:
        return cls(ProviderConfig.from_env())

    def __repr__(self) -> str:
        return f"KloudeksProvider(base_url={str(self._client.base_url)!r})"

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> KloudeksProvider:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def complete(
        self,
        messages: Sequence[Message],
        *,
        model: str | None = None,
        schema: type[BaseModel] | None = None,
    ) -> Completion:
        chosen = self._config.planner_model if model is None else model
        if chosen not in self._chat_models:
            # Not echoed: a model name can arrive from text nobody vetted.
            raise CapabilityUnavailable("The requested model is not one this deployment configures")
        json_mode = schema is not None and self._config.structured_output
        # A structured request is a plan; free text is the writer's sentence.
        thinking = (
            self._config.planner_thinking if schema is not None else self._config.writer_thinking
        )
        spent: list[Usage] = []
        reasoning: list[str] = []

        def ask(conversation: list[Message]) -> tuple[str, str | None]:
            body: dict[str, object] = {
                "model": chosen,
                "messages": _wire_messages(conversation),
                # Plans and summaries should not change between identical runs.
                "temperature": 0.0,
            }
            if json_mode:
                # Opt-in only: Q-K-03 has not confirmed guaranteed JSON output,
                # so strict local validation still decides.
                body["response_format"] = {"type": "json_object"}
            if not thinking:
                # The served Qwen reasons by default; its chat template takes this
                # switch (observed 2026-09-18: reasoning tokens 274 -> 0).
                body["chat_template_kwargs"] = {"enable_thinking": False}
            document = self._post(CHAT_PATH, body)
            reply = _choice(document)
            # Recorded for traces only; neither changes what the caller receives.
            if (usage := _usage(document)) is not None:
                spent.append(usage)
            if (thought := _reasoning(document)) is not None:
                reasoning.append(thought)
            return reply

        completion = complete_with_repair(
            ask, messages, schema=schema, max_attempts=self._config.max_attempts, model=chosen
        )
        return replace(
            completion,
            usage=_summed(spent) if spent else None,
            reasoning="\n\n---\n\n".join(reasoning) if reasoning else None,
        )

    def embed(self, texts: Sequence[str], *, kind: EmbeddingKind) -> list[list[float]]:
        model = self._config.embedding_model
        if model is None:
            raise CapabilityUnavailable("This deployment has no embedding model")
        if kind not in ("query", "passage"):
            raise ProviderError("Embedding kind must be 'query' or 'passage'")
        items = list(texts)
        if not items:
            return []
        # The platform documents no query/passage prefix (Q-K-05). Input policies
        # are applied above this boundary (kkb_agent.catalog.embedding, DEC-142),
        # so the provider sends exactly the texts it receives.
        document = self._post(
            EMBEDDINGS_PATH, {"model": model, "input": items, "encoding_format": "float"}
        )
        return _vectors(document, len(items))

    def vision(self, image_bytes: bytes, prompt: str) -> Completion:
        model = self._config.vision_model
        if model is None:
            raise CapabilityUnavailable("This deployment has no vision model")
        if not image_bytes:
            raise ProviderError("No image supplied")
        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise ProviderError("Image exceeds the size limit")
        media = next(
            (kind for signature, kind in _IMAGE_SIGNATURES if image_bytes.startswith(signature)),
            None,
        )
        if media is None:
            raise ProviderError("Only PNG and JPEG images are sent")
        inline = base64.b64encode(image_bytes).decode("ascii")
        body: dict[str, object] = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{media};base64,{inline}"},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            "temperature": 0.0,
        }
        text, finish_reason = _choice(self._post(CHAT_PATH, body))
        return Completion(text=text, model=model, finish_reason=finish_reason)

    def ocr(self, images: Sequence[bytes]) -> Completion:
        """DEC-129 OCR, inline PNG only; no arbitrary prompt or model override.

        SDK extra_body entries are top-level HTTP JSON fields (httpx sends
        the wire body directly). PDF extraction calls this once per page.
        """
        model = self._config.ocr_model
        if model is None:
            raise CapabilityUnavailable("This deployment has no OCR model")
        if model != "kkbhackathon2026/Unlimited-OCR":
            raise ConfigurationError("OCR model must match DEC-129")
        if not 1 <= len(images) <= 3:
            raise ProviderError("OCR requires one to three images")
        blocks = []
        for png in images:
            if not png.startswith(b"\x89PNG\r\n\x1a\n") or len(png) > MAX_IMAGE_BYTES:
                raise ProviderError("OCR requires bounded PNG images")
            inline = base64.b64encode(png).decode("ascii")
            blocks.append(
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{inline}"}}
            )
        blocks.append({"type": "text", "text": "<image>\ndocument parsing"})
        text, finish = _choice(
            self._post(
                CHAT_PATH,
                {
                    "model": model,
                    "messages": [{"role": "user", "content": blocks}],
                    "max_tokens": 8192,
                    "temperature": 0.0,
                    "skip_special_tokens": False,
                    "vllm_xargs": {
                        "ngram_size": 35,
                        "window_size": 128 if len(images) == 1 else 1024,
                    },
                },
            )
        )
        return Completion(text=text, model=model, finish_reason=finish)

    def _post(self, path: str, body: dict[str, object]) -> dict[str, Any]:
        if path not in (CHAT_PATH, EMBEDDINGS_PATH):
            raise ProviderError("Unknown provider path")
        request = self._client.build_request(
            "POST",
            path,
            json=body,
            headers={"Authorization": f"Bearer {self._config.credential.get_secret_value()}"},
        )
        # Checked again per request: an absolute URL would override base_url.
        if request.url.scheme != "https" or request.url.host not in APPROVED_HOSTS:
            raise ConfigurationError("Refusing to send the credential outside the DEC-129 endpoint")
        deadline = time.monotonic() + self._config.request_timeout
        try:
            response = self._client.send(request, stream=True)
        except httpx.HTTPError as error:
            raise TransportError(f"Kloudeks request failed ({type(error).__name__})") from None
        try:
            _check_status(response.status_code)
            payload = _read_capped(response, deadline)
        finally:
            response.close()
        try:
            document = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ProviderError("Kloudeks returned a body that is not JSON") from None
        if not isinstance(document, dict):
            raise ProviderError("Kloudeks returned JSON that is not an object")
        return document


def _wire_messages(conversation: Sequence[Message]) -> list[dict[str, str]]:
    """The conversation in the shape the platform accepts.

    The served chat model rejects a request carrying two system messages (400,
    observed in M4-15's live run on 2026-09-11), while the product keeps its
    instructions and its tool list as separate system turns. The leading
    system turns are joined into one, in order; nothing else changes.
    """
    leading = 0
    while leading < len(conversation) and conversation[leading].role is Role.SYSTEM:
        leading += 1
    wire: list[dict[str, str]] = []
    if leading:
        joined = "\n\n".join(message.content for message in conversation[:leading])
        wire.append({"role": Role.SYSTEM.value, "content": joined})
    wire.extend(
        {"role": message.role.value, "content": message.content}
        for message in conversation[leading:]
    )
    return wire


def _check_status(status: int) -> None:
    """Map a status to the provider taxonomy. The body is never read into a message."""
    if 200 <= status < 300:
        return
    if 300 <= status < 400:
        raise TransportError(f"Kloudeks answered with a redirect ({status}); it is not followed")
    if status == 401:
        raise ConfigurationError("Kloudeks rejected the credential (401)")
    if status in (403, 404):
        raise ModelUnavailable(f"Kloudeks refused this model or path ({status})")
    if status == 429:
        # DEC-129: wait per the organizer's guidance; never switch provider.
        raise RateLimited("Kloudeks rate or quota limit reached (429)")
    if status == 408 or status >= 500:
        raise TransportError(f"Kloudeks transport failure ({status})")
    raise ProviderError(f"Kloudeks rejected the request ({status})")


def _read_capped(response: httpx.Response, deadline: float) -> bytes:
    declared = response.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_RESPONSE_BYTES:
        raise ProviderError("Kloudeks response exceeds the size limit")
    chunks: list[bytes] = []
    size = 0
    try:
        for chunk in response.iter_bytes():
            size += len(chunk)
            if size > MAX_RESPONSE_BYTES:
                raise ProviderError("Kloudeks response exceeds the size limit")
            if time.monotonic() > deadline:
                raise TransportError("Kloudeks response exceeded the request deadline")
            chunks.append(chunk)
    except httpx.HTTPError as error:
        raise TransportError(f"Kloudeks response failed ({type(error).__name__})") from None
    return b"".join(chunks)


def _choice(document: dict[str, Any]) -> tuple[str, str | None]:
    """The first choice's text and finish reason, or why there is none."""
    choices = document.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ProviderError("Kloudeks returned no choices")
    first = choices[0]
    finish_reason = first.get("finish_reason")
    if not isinstance(finish_reason, str):
        finish_reason = None
    message = first.get("message")
    if finish_reason == "content_filter" or (
        isinstance(message, dict) and isinstance(message.get("refusal"), str)
    ):
        raise Refused("The model declined to answer")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        raise ProviderError("Kloudeks returned no message content")
    return content, finish_reason


def _usage(document: dict[str, Any]) -> Usage | None:
    """Token counts as the platform reported them, or None when it reported none."""
    usage = document.get("usage")
    if not isinstance(usage, dict):
        return None
    prompt, completion = usage.get("prompt_tokens"), usage.get("completion_tokens")
    if not (isinstance(prompt, int) and isinstance(completion, int)):
        return None
    details = usage.get("completion_tokens_details")
    reasoning = details.get("reasoning_tokens") if isinstance(details, dict) else None
    return Usage(
        prompt_tokens=prompt,
        completion_tokens=completion,
        reasoning_tokens=reasoning if isinstance(reasoning, int) else None,
    )


def _summed(spent: list[Usage]) -> Usage:
    reasoning = [item.reasoning_tokens for item in spent if item.reasoning_tokens is not None]
    return Usage(
        prompt_tokens=sum(item.prompt_tokens for item in spent),
        completion_tokens=sum(item.completion_tokens for item in spent),
        reasoning_tokens=sum(reasoning) if reasoning else None,
    )


def _reasoning(document: dict[str, Any]) -> str | None:
    """The served model's reasoning text (vLLM names it `reasoning` or `reasoning_content`)."""
    choices = document.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return None
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return None
    for key in ("reasoning", "reasoning_content"):
        value = message.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _vectors(document: dict[str, Any], expected: int) -> list[list[float]]:
    """Embedding vectors in input order, all finite and of one dimension."""
    data = document.get("data")
    if not isinstance(data, list) or len(data) != expected:
        raise ProviderError("Kloudeks returned the wrong number of embeddings")
    ordered: list[list[float] | None] = [None] * expected
    for position, item in enumerate(data):
        if not isinstance(item, dict):
            raise ProviderError("Kloudeks returned a malformed embedding")
        index = item.get("index", position)
        vector = item.get("embedding")
        if (
            not isinstance(index, int)
            or isinstance(index, bool)
            or not 0 <= index < expected
            or ordered[index] is not None
            or not isinstance(vector, list)
            or not vector
        ):
            raise ProviderError("Kloudeks returned a malformed embedding")
        values: list[float] = []
        for value in vector:
            if isinstance(value, bool) or not isinstance(value, int | float) or not isfinite(value):
                raise ProviderError("Kloudeks returned a non-numeric embedding value")
            values.append(float(value))
        ordered[index] = values
    vectors = [vector for vector in ordered if vector is not None]
    if len({len(vector) for vector in vectors}) != 1:
        raise ProviderError("Kloudeks returned embeddings of different dimensions")
    return vectors
