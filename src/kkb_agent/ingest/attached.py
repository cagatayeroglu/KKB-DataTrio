"""M10-04: a document the user uploaded and attached to one question.

The bytes already passed upload admission when they were stored. Readers treat
them exactly like fetched bytes: data, never instructions, through the same
loaders. The locator is an opaque upload reference; no filename is kept.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kkb_agent.core import SourceRef

SOURCE_TYPE = "upload"


@dataclass(frozen=True)
class Attachment:
    content: bytes = field(repr=False)
    media_type: str
    source: SourceRef
