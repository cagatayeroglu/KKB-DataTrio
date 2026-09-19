"""An admitted image becomes a one-page document the existing PDF path reads (DEC-179).

The organizer's cases include pictures: a screenshot of a table, a scanned page, a chart with
its figures printed on it. The product already reads exactly that when it arrives as a PDF
page without a text layer: the page is rendered, the OCR model writes its text and tables,
and a table counts only when its columns add up (DEC-149). So an image is not given a second
pipeline. It is decoded once, bounded, flattened onto white and wrapped as a single PDF page
whose rendering gives the image back pixel for pixel; from there on it *is* a scanned PDF.

Decoding untrusted image bytes happens in a spawned worker that is terminated at its
deadline, like every other parser here. Nothing is kept beyond the conversation the image
was attached to, and no pixel ever reaches the planner or the writer: only the OCR text does.
"""

from __future__ import annotations

import io
import multiprocessing
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Final

from kkb_agent.ingestion_policy import AdmissionError, AdmissionLimits, RejectionCode

#: `pdf_ocr.RENDER_SCALE` and `MAX_PAGE_PIXELS`: a page of W/2 x H/2 points renders to W x H
#: pixels, and no rendered page may exceed four million of them.
_RENDER_SCALE: Final = 2.0
_PAGE_PIXELS: Final = 4_000_000
#: The largest picture that is decoded at all; larger headers are refused unread.
MAX_SOURCE_PIXELS: Final = 64_000_000
SIGNATURES: Final = {
    "png": (b"\x89PNG\r\n\x1a\n",),
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
}
_FORMATS: Final = {"png": "PNG", "jpg": "JPEG", "jpeg": "JPEG"}


def check_signature(kind: str, content: bytes) -> None:
    if not content.startswith(SIGNATURES[kind]):
        raise AdmissionError(RejectionCode.FORMAT_MISMATCH)


def _convert(content: bytes, kind: str) -> bytes:
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = MAX_SOURCE_PIXELS
    with Image.open(io.BytesIO(content), formats=[_FORMATS[kind]]) as opened:
        width, height = opened.size
        if width <= 0 or height <= 0 or width * height > MAX_SOURCE_PIXELS:
            raise AdmissionError(RejectionCode.LIMIT_EXCEEDED)
        opened.load()
        picture = opened.convert("RGBA") if opened.mode in ("P", "LA", "RGBA") else opened
        if picture.mode == "RGBA":
            flat = Image.new("RGB", picture.size, (255, 255, 255))
            flat.paste(picture, mask=picture.getchannel("A"))
            picture = flat
        elif picture.mode != "RGB":
            picture = picture.convert("RGB")
        if width * height > _PAGE_PIXELS:
            ratio = (_PAGE_PIXELS / (width * height)) ** 0.5
            picture = picture.resize(
                (max(1, int(width * ratio)), max(1, int(height * ratio))), Image.Resampling.LANCZOS
            )
        output = io.BytesIO()
        # 72 points per inch: at 144 dpi the page is half the pixels in points, so the
        # reader's fixed render scale of two gives the picture back as it was.
        picture.save(output, format="PDF", resolution=72.0 * _RENDER_SCALE)
        return output.getvalue()


def _worker(content: bytes, kind: str, output: Path) -> None:
    import warnings

    warnings.simplefilter("ignore")
    try:
        if sys.platform == "linux":
            import resource

            memory = 1024 * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
        data = _convert(content, kind)
    except AdmissionError as error:
        data = b"!" + str(error.code).encode("ascii")
    except MemoryError:
        data = b"!" + RejectionCode.LIMIT_EXCEEDED.value.encode("ascii")
    except Exception:
        # A decoder's own message may quote file content; only a fixed code leaves.
        data = b"!" + RejectionCode.FORMAT_MISMATCH.value.encode("ascii")
    with open(os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb") as stream:
        stream.write(data)


def image_to_pdf(content: bytes, kind: str, limits: AdmissionLimits) -> bytes:
    """The picture as a one-page PDF, or an `AdmissionError` with a fixed code."""
    if kind not in SIGNATURES:
        raise AdmissionError(RejectionCode.UNSUPPORTED_FORMAT)
    check_signature(kind, content)
    context = multiprocessing.get_context("spawn")
    with tempfile.TemporaryDirectory(prefix="kkb-image-") as directory:
        output = Path(directory) / "page.pdf"
        process = context.Process(target=_worker, args=(content, kind, output))
        deadline = time.monotonic() + limits.max_pdf_parser_seconds
        try:
            process.start()
            process.join(max(0, deadline - time.monotonic()))
            if process.is_alive():
                process.terminate()
                process.join(0.2)
                if process.is_alive():
                    process.kill()
                    process.join()
                raise AdmissionError(RejectionCode.LIMIT_EXCEEDED)
            if process.exitcode != 0 or not output.is_file():
                raise AdmissionError(RejectionCode.FORMAT_MISMATCH)
            with output.open("rb") as stream:
                data = stream.read(limits.max_expanded_bytes + 1)
        finally:
            if process.is_alive():
                process.kill()
                process.join()
            process.close()
    if len(data) > limits.max_expanded_bytes:
        raise AdmissionError(RejectionCode.LIMIT_EXCEEDED)
    if data.startswith(b"!"):
        try:
            raise AdmissionError(RejectionCode(data[1:].decode("ascii")))
        except ValueError:
            raise AdmissionError(RejectionCode.FORMAT_MISMATCH) from None
    if data.find(b"%PDF-", 0, 1024) < 0:
        raise AdmissionError(RejectionCode.FORMAT_MISMATCH)
    return data
