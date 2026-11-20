"""Tests for the Excel exporter."""
import io

from openpyxl import load_workbook

from app.models.schemas import BusinessRecord
from app.services.exporter import HEADERS, build_workbook, export_filename


def _load(records):
    return load_workbook(io.BytesIO(build_workbook(records))).active


def test_headers_exact_and_two_columns_only():
    ws = _load([BusinessRecord(business_name="Example Business A", phone_number="+971 4 000 0001")])
    assert [c.value for c in ws[1]] == ["Business Name", "Phone Number"]
    assert tuple(c.value for c in ws[1]) == HEADERS
    assert ws.max_column == 2


def test_one_row_per_business_and_blank_phone_preserved():
    ws = _load([
        BusinessRecord(business_name="Example Business A", phone_number="+971 4 000 0001"),
        BusinessRecord(business_name="Example Business B", phone_number=None),
        BusinessRecord(business_name="Example Business C", phone_number="+971 4 000 0003"),
    ])
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    assert rows == [
        ("Example Business A", "+971 4 000 0001"),
        ("Example Business B", None),
        ("Example Business C", "+971 4 000 0003"),
    ]


def test_empty_results_produce_header_only_file():
    ws = _load([])
    assert ws.max_row == 1
    assert [c.value for c in ws[1]] == list(HEADERS)


def test_phone_stored_as_text_not_number():
    ws = _load([BusinessRecord(business_name="X", phone_number="+971400000001")])
    cell = ws["B2"]
    assert cell.value == "+971400000001"
    assert cell.data_type == "s"


def test_formula_like_values_are_stored_as_text():
    payload = '=HYPERLINK("http://evil.example","click")'
    ws = _load([BusinessRecord(business_name=payload, phone_number="=1+1")])
    assert ws["A2"].value == payload
    assert ws["A2"].data_type == "s"
    assert ws["B2"].data_type == "s"


def test_illegal_control_characters_are_stripped():
    ws = _load([BusinessRecord(business_name="Example\x00 Business\x07", phone_number="\x01")])
    assert ws["A2"].value == "Example Business"
    assert ws["B2"].value is None


def test_export_filename_is_sanitized():
    assert export_filename("Real estate agencies", "Dubai, UAE") == "leads-real-estate-agencies-dubai-uae.xlsx"
    assert export_filename("../../etc", '"x"') == "leads-etc-x.xlsx"
    assert export_filename("مطاعم", "دبي") == "leads.xlsx"
