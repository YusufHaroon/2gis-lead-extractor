"""Tests for normalization, phone selection and deduplication."""
import pytest

from app.collectors.base import RawListing
from app.services.processing import (
    clean_listings,
    clean_text,
    dedupe_key,
    normalize_name,
    pick_first_phone,
)


# --- normalize_name / clean_text -------------------------------------------

def test_normalize_name_casefolds_and_collapses_whitespace():
    assert normalize_name("  Example   BUSINESS\tA \n") == "example business a"


def test_normalize_name_unicode_forms_are_equal():
    # Full-width characters and the composed/decomposed "é" normalize to the same key.
    assert normalize_name("ＡＢＣ Café") == normalize_name("ABC Café")


@pytest.mark.parametrize("value", [None, "", "   "])
def test_normalize_name_empty(value):
    assert normalize_name(value) == ""


def test_clean_text_preserves_case():
    assert clean_text("  Example   Business  ") == "Example Business"


# --- pick_first_phone ------------------------------------------------------

def test_pick_first_phone_returns_first_of_many():
    assert pick_first_phone(["+971 4 000 0003", "+971 4 000 0004"]) == "+971 4 000 0003"


@pytest.mark.parametrize("phones", [None, [], [""], ["   "], [None]])
def test_pick_first_phone_blank_when_unavailable(phones):
    assert pick_first_phone(phones) is None


def test_pick_first_phone_skips_entries_without_digits():
    assert pick_first_phone(["  ", "Call us", "+971 4 000 0001"]) == "+971 4 000 0001"


def test_pick_first_phone_does_not_alter_number():
    # Only surrounding whitespace is trimmed; formatting inside is untouched.
    assert pick_first_phone(["  +971 (4) 000-0001 \n"]) == "+971 (4) 000-0001"


# --- dedupe_key ------------------------------------------------------------

def test_dedupe_key_prefers_source_id():
    a = RawListing(name="A", source_id="42", location="Dubai")
    b = RawListing(name="Totally different", source_id="42", location="Abu Dhabi")
    assert dedupe_key(a) == dedupe_key(b)


def test_dedupe_key_blank_source_id_falls_back_to_name_location():
    listing = RawListing(name="Example A", source_id="  ", location="Dubai")
    assert dedupe_key(listing) == ("name_location", "example a", "dubai")


def test_source_id_and_name_keys_never_collide():
    with_id = RawListing(name="x", source_id="example a")
    without_id = RawListing(name="example a")
    assert dedupe_key(with_id) != dedupe_key(without_id)


# --- clean_listings --------------------------------------------------------

def test_clean_listings_one_phone_max_and_blank_preserved():
    records = clean_listings([
        RawListing(name="Example Business B"),
        RawListing(name="Example Business C", phones=["+971 4 000 0003", "+971 4 000 0004"]),
    ])
    assert [(r.business_name, r.phone_number) for r in records] == [
        ("Example Business B", None),
        ("Example Business C", "+971 4 000 0003"),
    ]


def test_clean_listings_removes_duplicate_source_ids_keeping_first():
    records = clean_listings([
        RawListing(name="Example A", phones=["111"], source_id="1"),
        RawListing(name="Example A (copy)", phones=["222"], source_id="1"),
    ])
    assert len(records) == 1
    assert records[0].phone_number == "111"


def test_clean_listings_dedupes_by_normalized_name_and_location():
    records = clean_listings([
        RawListing(name="Example  Business A", location="Dubai"),
        RawListing(name="example business a", location=" DUBAI "),
    ])
    assert len(records) == 1


def test_clean_listings_same_name_different_location_kept():
    records = clean_listings([
        RawListing(name="Example Business A", location="Dubai"),
        RawListing(name="Example Business A", location="Abu Dhabi"),
    ])
    assert len(records) == 2


def test_clean_listings_skips_empty_names_and_cleans_display_name():
    records = clean_listings([
        RawListing(name="   "),
        RawListing(name="  Example   Business  "),
    ])
    assert [r.business_name for r in records] == ["Example Business"]


def test_clean_listings_matches_fixture_expectations():
    # Mirrors backend/fixtures/sample_listings.html: 4 rows -> 3 businesses.
    raw = [
        RawListing(name="Example Business A", phones=["+971 4 000 0001"], source_id="1"),
        RawListing(name="Example Business B", source_id="2"),
        RawListing(name="Example Business C", phones=["+971 4 000 0003", "+971 4 000 0004"], source_id="3"),
        RawListing(name="Example Business A", phones=["+971 4 000 0001"], source_id="1"),
    ]
    assert [(r.business_name, r.phone_number) for r in clean_listings(raw)] == [
        ("Example Business A", "+971 4 000 0001"),
        ("Example Business B", None),
        ("Example Business C", "+971 4 000 0003"),
    ]


def test_clean_listings_empty_input():
    assert clean_listings([]) == []
