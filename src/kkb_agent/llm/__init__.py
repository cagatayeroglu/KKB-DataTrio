"""The only surface through which this product reaches a language model."""

from kkb_agent.llm.config import ProviderConfig
from kkb_agent.llm.doubles import ScriptedProvider, scripted, transcript
from kkb_agent.llm.provider import (
    CapabilityUnavailable,
    Completion,
    ConfigurationError,
    EmbeddingKind,
    LLMProvider,
    Message,
    ModelUnavailable,
    ProviderError,
    RateLimited,
    Refused,
    Role,
    SchemaViolation,
    TransportError,
)
from kkb_agent.llm.structured import extract_json, parse_structured, repair_feedback

__all__ = [
    "CapabilityUnavailable",
    "Completion",
    "ConfigurationError",
    "EmbeddingKind",
    "LLMProvider",
    "Message",
    "ModelUnavailable",
    "ProviderConfig",
    "ProviderError",
    "RateLimited",
    "Refused",
    "Role",
    "SchemaViolation",
    "ScriptedProvider",
    "TransportError",
    "extract_json",
    "parse_structured",
    "repair_feedback",
    "scripted",
    "transcript",
]
