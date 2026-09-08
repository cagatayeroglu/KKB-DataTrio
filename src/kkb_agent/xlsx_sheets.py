"""M1-09 sheet selection only; opening/validating uploads belongs to M1-10."""

from dataclasses import dataclass
from typing import Literal

from openpyxl import Workbook


@dataclass(frozen=True)
class SheetSelection:
    """Metadata result, never an accepted table or an M1-01 `ok` profile."""

    status: Literal["selected", "needs_input", "rejected"]
    sheets: tuple[str, ...]
    selection: str | None = None
    code: Literal["SELECTION_REQUIRED", "UNKNOWN_SHEET", "NO_WORKSHEETS"] | None = None


def select_sheet(workbook: Workbook, selection: str | None = None) -> SheetSelection:
    """List tabular worksheets in workbook order and resolve an exact sheet name.

    Includes hidden worksheets; excludes chartsheets. Visibility/active-tab state
    must not silently remove ambiguity. Names remain untrusted metadata. No cells
    are read, converted or profiled, and no paths or streams are opened here.
    The caller owns safe workbook opening, resource limits and closing.
    """
    sheets = tuple(sheet.title for sheet in workbook.worksheets)
    if not sheets:
        return SheetSelection("rejected", sheets, code="NO_WORKSHEETS")
    if selection is not None:
        if selection not in sheets:
            return SheetSelection("needs_input", sheets, code="UNKNOWN_SHEET")
        return SheetSelection("selected", sheets, selection)
    if len(sheets) > 1:
        return SheetSelection("needs_input", sheets, code="SELECTION_REQUIRED")
    return SheetSelection("selected", sheets, sheets[0])
