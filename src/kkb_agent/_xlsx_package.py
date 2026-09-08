"""M1-10 streaming package checks, before openpyxl sees any XML."""

import io
import posixpath
import re
from dataclasses import dataclass, field
from urllib.parse import unquote, urlsplit
from xml.parsers import expat
from zipfile import ZipFile

from kkb_agent.ingestion_policy import AdmissionError, AdmissionLimits, RejectionCode

SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CELL = re.compile(r"([A-Z]{1,3})([1-9][0-9]{0,6})\Z")


class XlsxRejected(ValueError):
    """Fixed public code only, never document text or parser exceptions."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _reject(code: str = "UNSAFE_XLSX") -> None:
    raise XlsxRejected(code)


def _target(member: str, target: str, names: set[str]) -> str:
    target = unquote(target)
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or "\\" in target:
        _reject()
    if member == "_rels/.rels":
        base = ""
    else:
        directory, filename = posixpath.split(member)
        if not directory.endswith("/_rels") or not filename.endswith(".rels"):
            _reject("FORMAT_MISMATCH")
        base = directory.removesuffix("/_rels")
    resolved = posixpath.normpath(
        target.lstrip("/") if target.startswith("/") else posixpath.join(base, target)
    )
    if resolved not in names or resolved.startswith("../") or resolved == "..":
        _reject("FORMAT_MISMATCH")
    return resolved


@dataclass
class Package:
    sizes: dict[str, tuple[int, int]] = field(default_factory=dict)
    sheets: list[tuple[str, str]] = field(default_factory=list)
    relationships: dict[str, dict[str, tuple[str, str]]] = field(default_factory=dict)

    def worksheet_sizes(self) -> dict[str, tuple[int, int]]:
        root = self.relationships.get("_rels/.rels", {})
        documents = [target for kind, target in root.values() if kind == f"{REL_NS}/officeDocument"]
        if documents != ["xl/workbook.xml"]:
            _reject("FORMAT_MISMATCH")
        links = self.relationships.get("xl/_rels/workbook.xml.rels", {})
        result = {}
        seen = set()
        for name, rel_id in self.sheets:
            if name.casefold() in seen or rel_id not in links:
                _reject("FORMAT_MISMATCH")
            seen.add(name.casefold())
            kind, target = links[rel_id]
            if kind == f"{REL_NS}/worksheet" and target in self.sizes:
                result[name] = self.sizes[target]
            elif kind != f"{REL_NS}/chartsheet":
                _reject("FORMAT_MISMATCH")
        return result


class _XmlGuard:
    def __init__(self, member: str, names: set[str], limits: AdmissionLimits, package: Package):
        self.member, self.names, self.limits, self.package = member, names, limits, package
        self.stack: list[str] = []
        self.text_lengths: list[int] = []
        self.is_sheet = False
        self.row = self.column = self.max_column = 0
        self.nodes = 0

    def start(self, name: str, attrs: dict[str, str]) -> None:
        self.nodes += 1
        if len(self.stack) >= 64 or self.nodes > self.limits.max_cells * 8 + 100_000:
            raise AdmissionError(RejectionCode.LIMIT_EXCEEDED)
        for value in attrs.values():
            self.limits.check_field(value)
        local = name.rsplit("}", 1)[-1]
        if not self.stack:
            self.is_sheet = name == f"{SHEET_NS}}}worksheet"
        self.stack.append(name)
        if local in {"f", "formula", "formula1", "formula2", "definedName"}:
            _reject("FORMULA_UNSUPPORTED")
        content_type = attrs.get("ContentType", "").lower()
        if any(word in content_type for word in ("macroenabled", "vbaproject", "activex")):
            _reject()
        if name == f"{PACKAGE_REL_NS}}}Relationship":
            self.relationship(attrs)
        if self.member == "xl/workbook.xml" and name == f"{SHEET_NS}}}sheet":
            title, rel_id = attrs.get("name", ""), attrs.get(f"{REL_NS}}}id", "")
            self.limits.check_field(title, label=True)
            if not title or not rel_id:
                _reject("FORMAT_MISMATCH")
            self.package.sheets.append((title, rel_id))
            if len(self.package.sheets) > self.limits.max_sheets:
                raise AdmissionError(RejectionCode.LIMIT_EXCEEDED)
        if self.is_sheet and name == f"{SHEET_NS}}}mergeCell":
            _reject("MERGED_CELLS_UNSUPPORTED")
        if self.is_sheet and name == f"{SHEET_NS}}}row":
            if len(self.stack) < 3 or self.stack[-2] != f"{SHEET_NS}}}sheetData":
                _reject("MALFORMED_TABLE")
            row = int(attrs.get("r", "0"))
            if row <= self.row:
                _reject("MALFORMED_TABLE")
            self.limits.check_table_size(rows=row - 1, columns=self.max_column)
            self.row, self.column = row, 0
        if self.is_sheet and name == f"{SHEET_NS}}}c":
            match = CELL.fullmatch(attrs.get("r", ""))
            if not match or int(match[2]) != self.row or self.stack[-2] != f"{SHEET_NS}}}row":
                _reject("MALFORMED_TABLE")
            column = 0
            for letter in match[1]:
                column = column * 26 + ord(letter) - ord("A") + 1
            if column <= self.column:
                _reject("MALFORMED_TABLE")
            self.column = column
            self.max_column = max(column, self.max_column)
            self.limits.check_table_size(rows=self.row - 1, columns=self.max_column)
        if name in {f"{SHEET_NS}}}c", f"{SHEET_NS}}}si"}:
            self.text_lengths.append(0)

    def relationship(self, attrs: dict[str, str]) -> None:
        if attrs.get("TargetMode", "Internal") != "Internal":
            _reject("EXTERNAL_LINK_UNSUPPORTED")
        kind, rel_id, target = attrs.get("Type", ""), attrs.get("Id", ""), attrs.get("Target", "")
        if any(word in kind.lower() for word in ("vba", "oleobject", "activex", "externallink")):
            _reject()
        links = self.package.relationships.setdefault(self.member, {})
        if not kind or not rel_id or not target or rel_id in links:
            _reject("FORMAT_MISMATCH")
        links[rel_id] = kind, _target(self.member, target, self.names)

    def text(self, value: str) -> None:
        for i in range(len(self.text_lengths)):
            self.text_lengths[i] += len(value)
            if self.text_lengths[i] > self.limits.max_field_chars:
                raise AdmissionError(RejectionCode.LIMIT_EXCEEDED)

    def end(self, name: str) -> None:
        if name in {f"{SHEET_NS}}}c", f"{SHEET_NS}}}si"}:
            self.text_lengths.pop()
        self.stack.pop()
        if not self.stack and self.is_sheet:
            self.package.sizes[self.member] = self.row, self.max_column


def inspect_package(content: bytes, limits: AdmissionLimits) -> dict[str, tuple[int, int]]:
    """Read every member to EOF in bounded chunks; validate CRC/XML and relationships.

    Admission must run first. Dimensions are derived from actual ordered cell
    coordinates, never trusted from the optional worksheet dimension attribute.
    DTD/entities, formulas (including caches), macros, external relationships and
    merged cells are unsupported. This function runs only inside the timed worker.
    """
    package = Package()
    expanded = 0
    with ZipFile(io.BytesIO(content)) as archive:
        names = set(archive.namelist())
        for member in archive.infolist():
            parser = None
            # Tabular-only support: inspect every non-directory part as XML, even
            # if a relationship/content-type disguises XML behind another suffix.
            # Binary/image/embedded parts are explicitly unsupported in this loader.
            if not member.filename.endswith("/"):
                guard = _XmlGuard(member.filename, names, limits, package)
                parser = expat.ParserCreate(namespace_separator="}")
                parser.StartElementHandler = guard.start
                parser.EndElementHandler = guard.end
                parser.CharacterDataHandler = guard.text
                parser.StartDoctypeDeclHandler = lambda *args: _reject()
                parser.EntityDeclHandler = lambda *args: _reject()
                parser.ExternalEntityRefHandler = lambda *args: _reject()
            actual = 0
            with archive.open(member) as stream:
                while True:
                    chunk = stream.read(min(65_536, limits.max_expanded_bytes - expanded + 1))
                    expanded += len(chunk)
                    actual += len(chunk)
                    if expanded > limits.max_expanded_bytes or actual > (
                        limits.max_compression_ratio * max(1, member.compress_size)
                    ):
                        raise AdmissionError(RejectionCode.LIMIT_EXCEEDED)
                    if parser:
                        parser.Parse(chunk, not chunk)
                    if not chunk:
                        break
            if actual != member.file_size:
                _reject("FORMAT_MISMATCH")
    return package.worksheet_sizes()
