"""The deployment's prompt parts, readable as they are built (M10-UI follow-up).

Every model call's exact messages are already in the trace; this surface shows
the *sources* those messages are assembled from, each with its content digest,
so a trace can be matched to the part that produced a line. Reading is the whole
contract: the parts are code, resolved at import time from the modules that own
them — no list is kept by hand, and nothing here can change what a turn sends.
A browser-side editor was considered and rejected for the same reason DEC-162
rejected verification switches: a session must not be able to weaken the
harness that checks it.
"""

from __future__ import annotations

import hashlib

from kkb_agent.agent import discovery, loop
from kkb_agent.api.contracts import PromptPart, PromptParts

#: (part_id, Turkish title, when the part is sent) -> the owning constant.
_PARTS: tuple[tuple[str, str, str, str], ...] = (
    (
        "planner.system",
        "Planlayıcı sistem istemi",
        "Her plan çağrısında, plan şemasıyla birlikte",
        loop.SYSTEM_PROMPT,
    ),
    (
        "planner.reply",
        "Analiz gerektirmeyen mesajlar",
        "Yalnızca ilk plan çağrısında",
        loop.REPLY_INSTRUCTIONS,
    ),
    (
        "planner.history_header",
        "Geçmiş tur bloğunun başlığı",
        "Sohbetin önceki turları gösterilirken",
        loop.HISTORY_HEADER,
    ),
    (
        "discovery.required",
        "Zorunlu katalog keşfi",
        "Keşif gereken ilk plan çağrısında",
        discovery.REQUIRED_DISCOVERY_BASE,
    ),
    (
        "discovery.instructions",
        "Keşif kuralları",
        "Keşif aşamasında",
        discovery.DISCOVERY_INSTRUCTIONS,
    ),
    (
        "discovery.continuation",
        "Keşif sonrası devam kuralları",
        "Katalog sonuçlarıyla ikinci plan çağrısında",
        discovery.CONTINUATION_INSTRUCTIONS,
    ),
    (
        "discovery.web_address",
        "Web adresi kuralları",
        "Soruda bir https adresi olduğunda",
        discovery.WEB_ADDRESS_INSTRUCTIONS,
    ),
    (
        "writer.synthesis",
        "Yazar (sentez) istemi",
        "Yanıt yazılırken, hesaplanmış sonuçlarla birlikte",
        loop.SYNTHESIS_PROMPT,
    ),
)


def prompt_parts() -> PromptParts:
    """Every part, with the digest a trace line can be matched against."""
    return PromptParts(
        parts=tuple(
            PromptPart(
                part_id=part_id,
                title=title,
                sent_when=sent_when,
                content=content,
                content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            )
            for part_id, title, sent_when, content in _PARTS
        )
    )
