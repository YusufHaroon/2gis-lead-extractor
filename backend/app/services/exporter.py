"""Excel export with exactly two columns: Business Name, Phone Number (Phase 5)."""
import io
import re
from collections.abc import Iterable

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Font

from app.models.schemas import BusinessRecord

HEADERS = ("Business Name", "Phone Number")
SHEET_TITLE = "Leads"
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_FILENAME_UNSAFE = re.compile(r"[^A-Za-z0-9]+")


def _text(value: str | None) -> str | None:
    """Strip control characters that are illegal in .xlsx; keep everything else as-is."""
    if value is None:
        return None
    return ILLEGAL_CHARACTERS_RE.sub("", value) or None


def build_workbook(records: Iterable[BusinessRecord]) -> bytes:
    """Return .xlsx bytes: header row + one row per business, blank cell when no phone.

    Every cell is forced to the text type so that:
    - values starting with "=" are never evaluated as formulas (spreadsheet injection);
    - phone numbers keep their leading "+" and are not converted to numbers.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_TITLE

    ws.append(HEADERS)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    ws.freeze_panes = "A2"

    widths = [len(h) for h in HEADERS]
    for row_idx, record in enumerate(records, start=2):
        for col_idx, value in enumerate((record.business_name, record.phone_number), start=1):
            value = _text(value)
            if value is None:
                continue  # leave the cell truly empty
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.data_type = "s"
            widths[col_idx - 1] = max(widths[col_idx - 1], len(value))

    for col_letter, width in zip("AB", widths):
        ws.column_dimensions[col_letter].width = min(width + 2, 60)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def export_filename(category: str, location: str) -> str:
    """Safe ASCII download name, e.g. ``leads-real-estate-agencies-dubai.xlsx``."""
    parts = [_FILENAME_UNSAFE.sub("-", p).strip("-").lower() for p in (category, location)]
    stem = "-".join(p for p in parts if p)[:80].strip("-")
    return f"leads-{stem}.xlsx" if stem else "leads.xlsx"
