"""Synthetic PDFs for the M7-09/M7-10 tests, written by hand.

No PDF library writes these: each is a few objects with exact offsets, so a
test states precisely what a page contains — which text, which ruling lines,
which font, which encryption entry — and nothing else. Coordinates passed in
are PDF user space (origin bottom-left, 612 x 792 points); pdfplumber reports
them from the top-left.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass, field

WIDTH, HEIGHT = 612, 792
HELVETICA = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
# A composite font with no ToUnicode map: pdfminer can place its glyphs but
# cannot say which characters they are.
UNMAPPED_FONT = (
    b"<< /Type /Font /Subtype /Type0 /BaseFont /Synthetic /Encoding /Identity-H "
    b"/DescendantFonts [<< /Type /Font /Subtype /CIDFontType2 /BaseFont /Synthetic "
    b"/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> >>] >>"
)


@dataclass
class Page:
    texts: list[tuple[float, float, str]] = field(default_factory=list)
    lines: list[tuple[float, float, float, float]] = field(default_factory=list)
    unmapped: list[tuple[float, float, str]] = field(default_factory=list)
    raw: bytes = b""
    compress: bool = False

    def content(self) -> bytes:
        ops = [f"{x1} {y1} m {x2} {y2} l S" for x1, y1, x2, y2 in self.lines]
        ops += [f"BT /F1 10 Tf {x} {y} Td ({_escape(text)}) Tj ET" for x, y, text in self.texts]
        ops += [f"BT /F2 10 Tf {x} {y} Td <{hexed}> Tj ET" for x, y, hexed in self.unmapped]
        return "\n".join(ops).encode("latin-1") + self.raw


def ruled_table(
    x0: float, top: float, rows: list[list[str]], *, cell_w: float = 100, cell_h: float = 20
) -> Page:
    """A table drawn with ruling lines, its top edge at `top` in PDF user space."""
    page = Page()
    columns = max(len(row) for row in rows)
    for r in range(len(rows) + 1):
        y = top - r * cell_h
        page.lines.append((x0, y, x0 + columns * cell_w, y))
    for c in range(columns + 1):
        x = x0 + c * cell_w
        page.lines.append((x, top, x, top - len(rows) * cell_h))
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            page.texts.append((x0 + c * cell_w + 4, top - (r + 1) * cell_h + 6, value))
    return page


def build(pages: list[Page], *, trailer_extra: bytes = b"") -> bytes:
    """A complete PDF: catalog, page tree, two fonts, one content stream per page."""
    kids = " ".join(f"{5 + 2 * index} 0 R" for index in range(len(pages)))
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode(),
        HELVETICA,
        UNMAPPED_FONT,
    ]
    for index, page in enumerate(pages):
        stream = page.content()
        filters = b""
        if page.compress:
            stream, filters = zlib.compress(stream), b" /Filter /FlateDecode"
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {WIDTH} {HEIGHT}] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> "
            f"/Contents {6 + 2 * index} 0 R >>".encode()
        )
        objects.append(
            f"<< /Length {len(stream)}".encode()
            + filters
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        )
    return _assemble(objects, trailer_extra)


def password_protected(pages: list[Page]) -> bytes:
    """A standard security handler whose empty password does not authenticate."""
    encrypt = (
        b" /Encrypt << /Filter /Standard /V 1 /R 2 /Length 40 /P -44"
        b" /O <" + b"11" * 32 + b"> /U <" + b"22" * 32 + b"> >>"
        b" /ID [<" + b"33" * 16 + b"> <" + b"33" * 16 + b">]"
    )
    return build(pages, trailer_extra=encrypt)


def _assemble(objects: list[bytes], trailer_extra: bytes) -> bytes:
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R".encode() + trailer_extra
    out += f" >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
