import csv
from html import unescape
from io import BytesIO, StringIO
from typing import Literal

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

COLUMNS = (
    ("Nama Calon Anggota", "full_name"),
    ("NIM Mahasiswa", "student_id"),
    ("Program Studi", "program_of_study"),
    ("Peminatan Riset", "interest_track"),
    ("No. WhatsApp", "contact_info"),
    ("Email UPNVJ", "email"),
    ("Tanggal Submit", "submit_date"),
    ("Status Seleksi", "status"),
)


def _text_value(value) -> str:
    if isinstance(value, list):
        value = ", ".join(value)
    return ILLEGAL_CHARACTERS_RE.sub("", unescape(str(value))) if value is not None else ""


def _csv_cell(value: str) -> str:
    if value.startswith(("\t", "\r", "\n")) or value.lstrip().startswith(tuple("=+-@＝＋－＠")):
        return "'" + value
    return value


def render_registration_export(rows: list[dict], file_format: Literal["csv", "xlsx"]) -> bytes:
    header = [label for label, _ in COLUMNS]
    if file_format == "csv":
        output = StringIO(newline="")
        writer = csv.writer(output, quoting=csv.QUOTE_ALL)
        writer.writerow(header)
        for row in rows:
            writer.writerow(_csv_cell(_text_value(row.get(key))) for _, key in COLUMNS)
        return output.getvalue().encode("utf-8-sig")

    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("Seleksi Anggota")
    sheet.append(header)
    for row in rows:
        cells = []
        for _, key in COLUMNS:
            cell = WriteOnlyCell(sheet, value=_text_value(row.get(key)))
            cell.data_type = "s"
            cells.append(cell)
        sheet.append(cells)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()
