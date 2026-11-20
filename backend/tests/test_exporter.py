"""Tests for the Excel exporter."""
import io

from openpyxl import load_workbook

from app.models.schemas import BusinessRecord
from app.services.exporter import HEADERS, build_workbook, export_filename


def _load(records):
    return load_workbook(io.BytesIO(build_workbook(records))).active


EXPECTED_HEADERS = ["Business Name", "Phone Number", "Address", "Category", "Opening Hours"]


def test_headers_exact_and_column_order():
    ws = _load([BusinessRecord(business_name="Example Business A", phone_number="+971 4 000 0001")])
    assert [c.value for c in ws[1]] == EXPECTED_HEADERS
    assert tuple(c.value for c in ws[1]) == HEADERS
    assert ws.max_column == len(EXPECTED_HEADERS)


def test_one_row_per_business_all_columns_and_blanks_preserved():
    ws = _load([
        BusinessRecord(business_name="Example Business A", phone_number="+971 4 000 0001",
                       address="1 Example St", category="Restaurants", opening_hours="Mon-Sun 09:00-22:00"),
        BusinessRecord(business_name="Example Business B", phone_number=None,
                       address="2 Example St", category="Clinics", opening_hours=None),
        BusinessRecord(business_name="Example Business C", phone_number="+971 4 000 0003",
                       address=None, category=None, opening_hours="Open 24/7"),
    ])
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    assert rows == [
        ("Example Business A", "+971 4 000 0001", "1 Example St", "Restaurants", "Mon-Sun 09:00-22:00"),
        ("Example Business B", None, "2 Example St", "Clinics", None),
        ("Example Business C", "+971 4 000 0003", None, None, "Open 24/7"),
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
