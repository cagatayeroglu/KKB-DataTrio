"""Explicit projection of a gated turn and its exactly published workspace value."""

from __future__ import annotations

import re
from uuid import UUID, uuid5

from kkb_agent.agent.discovery import CLARIFICATION_TEXT
from kkb_agent.agent.loop import Answered
from kkb_agent.agent.presentation import display_value
from kkb_agent.agent.verifier import AnswerStatus
from kkb_agent.api.contracts import (
    MAX_RESPONSE_BYTES,
    MAX_VALUES,
    Answer,
    Cell,
    Proof,
    Result,
    unavailable_proof,
)
from kkb_agent.core import AnalyticalResult


class OutputRefused(ValueError):
    """Fixed boundary failure; never include the rejected output."""


# Prevent accidental locator/path/credential presentation. This is deliberately
# conservative and not a general secret detector; raw internals are excluded by
# construction. Literal credentials known to the operator can be supplied too.
_INTERNAL = re.compile(
    r"https?://\S+|file://\S+|[A-Za-z]:[\\/]\S+|(?:^|\s)/(?:home|tmp|var|Users)/\S+"
    r"|(?:bearer\s+\S+)|(?:api[_-]?key|token|password|secret)\s*[:=]\s*\S+",
    re.IGNORECASE,
)


def safe_text(text: str, *, limit: int = 8192, secrets: tuple[str, ...] = ()) -> str:
    if len(text) > limit or len(text.encode("utf-8")) > limit * 4:
        raise OutputRefused("output_limit")
    cleaned = _INTERNAL.sub("[gizli bilgi kaldırıldı]", text)
    for secret in secrets:
        if secret:
            cleaned = cleaned.replace(secret, "[gizli bilgi kaldırıldı]")
    return "".join(c for c in cleaned if ord(c) >= 32 or c in "\n\t")


def _owned_proof(proof: Proof | None, version: str) -> Proof:
    """A proof must describe exactly this published version, or none is shown."""
    if proof is None:
        return unavailable_proof()
    canonical = Proof.model_validate_json(proof.model_dump_json())
    if canonical.steps and canonical.steps[0].result_version != version:
        raise OutputRefused("publication_mismatch")
    return canonical


def project_result(
    published: AnalyticalResult,
    *,
    turn_id: str,
    secrets: tuple[str, ...] = (),
    proof: Proof | None = None,
) -> Result:
    """The public table for a published value: deterministic from the turn and the digest.

    Read back from a stored publication after a restart, it yields the very same
    `result_ref` and `version` the conversation's messages recorded, so a
    reopened conversation shows the table it showed then, proof included.
    """
    namespace = UUID(hex=turn_id)
    canonical = AnalyticalResult.model_validate_json(published.model_dump_json())
    if len(canonical.values) > MAX_VALUES:
        raise OutputRefused("output_limit")
    version = canonical.digest()
    return Result(
        result_ref=uuid5(namespace, version).hex,
        version=version,
        kind=canonical.kind,
        claim_kind=canonical.claim_kind,
        cells=tuple(
            Cell(
                cell_id=uuid5(namespace, f"{version}:{slot}").hex,
                slot=slot,
                label=safe_text(value.label, limit=240, secrets=secrets),
                value=value.value,
                display=display_value(value),
                unit=safe_text(value.unit, limit=240, secrets=secrets) if value.unit else None,
                scale=value.scale,
                measure=value.measure,
                period=value.period,
                samples=value.samples,
                lag=value.lag,
            )
            for slot, value in enumerate(canonical.values)
        ),
        proof=_owned_proof(proof, version),
    )


def project_answer(
    answered: Answered,
    *,
    turn_id: str,
    published: AnalyticalResult | None,
    secrets: tuple[str, ...] = (),
    proof: Proof | None = None,
) -> Answer:
    """The caller proves publication by reading its own workspace, not by a flag.

    No candidate result, raw outcome, omitted sentence, verdict exception,
    locator, transformation parameters or source content is serialized.
    """
    gate = answered.answer
    notices = []
    text = ""
    if gate.status is AnswerStatus.ABSTAINED:
        reason = answered.planned.plan.clarification
        text = (
            CLARIFICATION_TEXT[reason]
            if reason is not None
            else (
                "Bu soru için doğrulanabilir bir sonuç üretilemedi. "
                "Veri kapsamını ve tanımı kontrol edin."
            )
        )
    else:
        text = safe_text(gate.text, secrets=secrets)
    if gate.omitted:
        notices.append("Doğrulanamayan bazı ifadeler yanıttan çıkarıldı.")
    if gate.limitations:
        # These are gate-owned qualifications, still treated as untrusted text.
        if len(gate.limitations) > 12:
            raise OutputRefused("output_limit")
        notices.extend(safe_text(item, limit=2048, secrets=secrets) for item in gate.limitations)
    result = None
    if published is not None:
        if (
            gate.status is not AnswerStatus.ACCEPTED
            or not answered.results
            or published.digest() != answered.results[-1].digest()
        ):
            raise OutputRefused("publication_mismatch")
        result = project_result(published, turn_id=turn_id, secrets=secrets, proof=proof)
    elif gate.status is not AnswerStatus.ABSTAINED and answered.planned.plan.reply is None:
        # A conversational reply never publishes, so saying so would be noise.
        notices.append("Bu turda yeni bir doğrulanmış tablo çalışma alanına yayımlanmadı.")
    answer = Answer(
        status=gate.status,
        text=text,
        omitted_claims=len(gate.omitted),
        notices=tuple(notices),
        result=result,
    )
    if len(answer.model_dump_json().encode()) > MAX_RESPONSE_BYTES - 4096:
        raise OutputRefused("output_limit")
    return answer
