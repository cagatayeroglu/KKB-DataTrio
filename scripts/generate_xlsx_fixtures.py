"""Recreate M1-09 synthetic XLSX fixtures with openpyxl; no external inputs."""

import argparse
from datetime import datetime
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.xml.functions import tostring

STAMP = datetime(2026, 1, 1)


def fixture_bytes(*, multi_sheet: bool) -> bytes:
    workbook = Workbook()
    observations = workbook.active
    observations.title = "Observations"
    for row in (
        ("as_of", "measure", "label"),
        (datetime(2026, 1, 31), 100, "Örnek"),
        (datetime(2026, 2, 28), None, "çığ"),
        (datetime(2026, 3, 31), 125.5, "C"),
    ):
        observations.append(row)
    for cell in observations["A"][1:]:
        cell.number_format = "yyyy-mm-dd"
    if multi_sheet:
        categories = workbook.create_sheet("Categories")
        for row in (("code", "description"), ("A", "Synthetic alpha"), ("B", "Örnek beta")):
            categories.append(row)
    for sheet in workbook.worksheets:
        sheet.sheet_view.showGridLines = False
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width = 22
        for row in sheet:
            for cell in row:
                cell.font = Font(name="Arial", size=11, bold=cell.row == 1)
                cell.alignment = Alignment(vertical="center")
    workbook.properties.creator = "KKB synthetic fixtures"
    workbook.properties.created = STAMP
    output = BytesIO()
    workbook.save(output)
    # openpyxl sets modified time while saving. Normalize its core properties
    # and ZIP timestamps so regeneration is byte-stable with the same toolchain.
    workbook.properties.modified = STAMP
    core = tostring(workbook.properties.to_tree())
    stable = BytesIO()
    with ZipFile(output) as source, ZipFile(stable, "w", ZIP_DEFLATED) as target:
        for name in sorted(source.namelist()):
            info = ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            target.writestr(info, core if name == "docProps/core.xml" else source.read(name))
    workbook.close()
    return stable.getvalue()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output_dir",
        type=Path,
        nargs="?",
        default=Path(__file__).resolve().parents[1] / "tests/fixtures/ingestion",
    )
    destination = parser.parse_args().output_dir
    destination.mkdir(parents=True, exist_ok=True)
    for filename, multiple in (("single_sheet.xlsx", False), ("multi_sheet.xlsx", True)):
        (destination / filename).write_bytes(fixture_bytes(multi_sheet=multiple))
