"""Provider configuration from the environment (M4-06).

Every platform-specific value is read here and nowhere else. Model identifiers,
the base URL and capability flags come from the operator's environment, not
source constants; DEC-129 supplies the confirmed values (see `.env.example`).
The one rule fixed in source is where the key may go: `kloudeks` refuses any
base URL but DEC-129's, because the environment is where a wrong one would hide.

Errors name the setting that is wrong. They never carry its value, since the
value in question is often a credential.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from pydantic import SecretStr

from kkb_agent.llm.provider import ConfigurationError

#: The environment names. DEC-129 fixes the values, not the names; these are
#: local conventions, which is why they live in one place.
PREFIX = "KLOUDEKS_"
BASE_URL = f"{PREFIX}BASE_URL"
CREDENTIAL = f"{PREFIX}API_KEY"
PLANNER_MODEL = f"{PREFIX}PLANNER_MODEL"
ROUTER_MODEL = f"{PREFIX}ROUTER_MODEL"
OCR_MODEL = f"{PREFIX}OCR_MODEL"
VISION_MODEL = f"{PREFIX}VISION_MODEL"
EMBEDDING_MODEL = f"{PREFIX}EMBEDDING_MODEL"
STRUCTURED_OUTPUT = f"{PREFIX}STRUCTURED_OUTPUT"
REQUEST_TIMEOUT = f"{PREFIX}REQUEST_TIMEOUT"
MAX_ATTEMPTS = f"{PREFIX}MAX_ATTEMPTS"
#: Whether the served model may reason before it answers. A plan is a decision
#: and keeps it by default; a sentence written from given values does not need
#: it, and on 2026-09-18 its hidden reasoning cost the writer minutes per turn.
PLANNER_THINKING = f"{PREFIX}PLANNER_THINKING"
WRITER_THINKING = f"{PREFIX}WRITER_THINKING"
#: An upper bound on tokens one completion may generate. Not a latency knob:
#: it is a memory/safety ceiling on runaway generation, set well above the
#: most a real plan or answer has ever needed (7,897 reasoning tokens on
#: 2026-09-18), so a legitimate call is never truncated. Zero would truncate
#: answers, so the floor is generous.
MAX_OUTPUT_TOKENS = f"{PREFIX}MAX_OUTPUT_TOKENS"

REQUIRED = (BASE_URL, CREDENTIAL, PLANNER_MODEL, ROUTER_MODEL)

_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    """Resolved settings for one deployment.

    `credential` is a `SecretStr`, so printing this object, logging it or
    including it in a traceback shows `**********` rather than the key.
    """

    base_url: str
    credential: SecretStr
    planner_model: str
    router_model: str
    structured_output: bool = False
    vision_model: str | None = None
    embedding_model: str | None = None
    request_timeout: float = 30.0
    max_attempts: int = 3
    ocr_model: str | None = None
    planner_thinking: bool = True
    writer_thinking: bool = True
    max_output_tokens: int = 16384

    def __post_init__(self) -> None:
        if not self.base_url.startswith("https://"):
            # A plaintext endpoint would send the credential in the clear.
            raise ConfigurationError(f"{BASE_URL} must be an https URL")
        if self.request_timeout <= 0:
            raise ConfigurationError(f"{REQUEST_TIMEOUT} must be positive")
        if self.max_attempts < 1:
            raise ConfigurationError(f"{MAX_ATTEMPTS} must be at least 1")
        if self.max_output_tokens < 4096:
            # Below this a real reasoning-plus-answer call would be truncated.
            raise ConfigurationError(f"{MAX_OUTPUT_TOKENS} must be at least 4096")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> ProviderConfig:
        """Build from the environment, naming every missing or unusable setting.

        All problems are reported at once. Discovering configuration faults one
        restart at a time is how a demo-day deployment burns twenty minutes.
        """
        source = os.environ if environ is None else environ
        missing = [name for name in REQUIRED if not source.get(name, "").strip()]
        if missing:
            raise ConfigurationError("Missing required settings: " + ", ".join(sorted(missing)))
        return cls(
            base_url=source[BASE_URL].strip(),
            credential=SecretStr(source[CREDENTIAL].strip()),
            planner_model=source[PLANNER_MODEL].strip(),
            router_model=source[ROUTER_MODEL].strip(),
            structured_output=_flag(source, STRUCTURED_OUTPUT, default=False),
            vision_model=_optional(source, VISION_MODEL),
            ocr_model=_optional(source, OCR_MODEL),
            embedding_model=_optional(source, EMBEDDING_MODEL),
            request_timeout=_number(source, REQUEST_TIMEOUT, default=30.0),
            max_attempts=int(_number(source, MAX_ATTEMPTS, default=3.0)),
            planner_thinking=_flag(source, PLANNER_THINKING, default=True),
            writer_thinking=_flag(source, WRITER_THINKING, default=True),
            max_output_tokens=int(_number(source, MAX_OUTPUT_TOKENS, default=16384.0)),
        )

    def capabilities(self) -> dict[str, bool]:
        """What this deployment can actually do (M4-05).

        Reported from configuration rather than assumed, so a caller that needs
        embeddings finds out here instead of at the first retrieval.
        """
        return {
            "complete": True,
            "structured_output": self.structured_output,
            "embed": self.embedding_model is not None,
            "vision": self.vision_model is not None,
        }


def _optional(source: Mapping[str, str], name: str) -> str | None:
    value = source.get(name, "").strip()
    return value or None


def _flag(source: Mapping[str, str], name: str, *, default: bool) -> bool:
    raw = source.get(name, "").strip().lower()
    if not raw:
        return default
    if raw in _TRUE:
        return True
    if raw in _FALSE:
        return False
    raise ConfigurationError(f"{name} must be a boolean flag")


def _number(source: Mapping[str, str], name: str, *, default: float) -> float:
    raw = source.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as error:
        # The value is deliberately not echoed; it came from the environment.
        raise ConfigurationError(f"{name} must be a number") from error
