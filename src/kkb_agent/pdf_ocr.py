"""M7-11: bounded rendering and untrusted OCR text, never analytical cells.

Rendering runs only inside the PDF parser's terminated worker. The caller
explicitly supplies OCR capability; nothing loads credentials or enables it.
"""

from __future__ import annotations

import base64
import io
import math
import re
from collections.abc import Sequence
from typing import Protocol

from kkb_agent.llm.provider import Completion, ProviderError

MAX_OCR_PAGES = 3
MAX_PAGE_PIXELS = 4_000_000
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_OCR_TEXT = 65536
RENDER_SCALE = 2.0
_LAYOUT_TAG = re.compile(r"<\|[^<>\r\n]{1,64}\|>")


class OcrProvider(Protocol):
    def ocr(self, images: Sequence[bytes]) -> Completion: ...


class OcrError(ValueError):
    """Only fixed local codes, never provider/document text."""


def render_pages(content: bytes, pages: list[dict[str, object]]) -> None:
    """Attach bounded inline PNGs only for pages without a text layer."""
    # This bounded native renderer ships no typing marker/stubs. Its image/page
    # sizes still pass the explicit checks below; only this import is untyped.
    import pypdfium2 as pdfium  # type: ignore[import-untyped]

    missing: list[tuple[dict[str, object], int]] = []
    for record in pages:
        if not isinstance(record.get("has_text"), bool):
            raise OcrError("PARSER_FAILED")
        if not record["has_text"]:
            number = record.get("number")
            if isinstance(number, bool) or not isinstance(number, int) or number < 1:
                raise OcrError("PARSER_FAILED")
            missing.append((record, number))
    if len(missing) > MAX_OCR_PAGES:
        raise OcrError("LIMIT_EXCEEDED")
    if not missing:
        return
    with pdfium.PdfDocument(content) as pdf:
        # Validate all sizes before allocating the first bitmap.
        for _record, number in missing:
            page = pdf[number - 1]
            try:
                width, height = page.get_size()
                if not all(math.isfinite(v) and v > 0 for v in (width, height)):
                    raise OcrError("LIMIT_EXCEEDED")
                if (
                    math.ceil(width * RENDER_SCALE) * math.ceil(height * RENDER_SCALE)
                    > MAX_PAGE_PIXELS
                ):
                    raise OcrError("LIMIT_EXCEEDED")
            finally:
                page.close()
        for record, number in missing:
            page = pdf[number - 1]
            try:
                bitmap = page.render(scale=RENDER_SCALE)
                try:
                    image = bitmap.to_pil()
                    try:
                        if image.width * image.height > MAX_PAGE_PIXELS:
                            raise OcrError("LIMIT_EXCEEDED")
                        output = io.BytesIO()
                        image.save(output, format="PNG")
                        png = output.getvalue()
                        if len(png) > MAX_IMAGE_BYTES:
                            raise OcrError("LIMIT_EXCEEDED")
                        record["ocr_png"] = base64.b64encode(png).decode("ascii")
                    finally:
                        image.close()
                finally:
                    bitmap.close()
            finally:
                page.close()


def extract_text(provider: OcrProvider, png: bytes, *, max_chars: int) -> str:
    """One page per call, no retry or interpretation; reject incomplete output."""
    try:
        result = provider.ocr((png,))
    except ProviderError:
        raise OcrError("OCR_FAILED") from None
    if result.finish_reason != "stop":
        raise OcrError("OCR_INCOMPLETE")
    if len(result.text) > min(max_chars, MAX_OCR_TEXT):
        raise OcrError("LIMIT_EXCEEDED")
    text = _LAYOUT_TAG.sub("", result.text).strip()
    if not text:
        raise OcrError("OCR_EMPTY")
    return text
