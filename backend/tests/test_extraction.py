from datetime import date

import pytest

from app.extraction.classify import classify
from app.extraction.fields import extract_fields, field_value, mask, masked_fields, parse_date
from app.extraction.matching import compare_names, name_similarity
from tests import samples


@pytest.mark.parametrize("text,expected", [
    (samples.AADHAAR, "AADHAAR"),
    (samples.PAN, "PAN"),
    (samples.DRIVING_LICENCE, "DRIVING_LICENCE"),
    (samples.PASSPORT, "PASSPORT"),
    (samples.RC, "RC"),
    (samples.INSURANCE, "VEHICLE_INSURANCE"),
    (samples.PUC, "PUC"),
    ("hello world, nothing here", "UNKNOWN"),
    ("", "UNKNOWN"),
])
def test_classify(text, expected):
    assert classify(text)[0] == expected


def _f(doc_type, text):
    found = extract_fields(doc_type, text)
    return {f["key"]: f["value"] for f in found}


def test_aadhaar_fields():
    f = _f("AADHAAR", samples.AADHAAR)
    assert f["aadhaar_number"] == "2345 6789 0123"
    assert f["name"] == "Rahul Kumar Sharma"
    assert f["date_of_birth"] == "14/08/1990"
    assert f["gender"] == "Male"
    assert f["address"].endswith("452001")


def test_pan_fields():
    f = _f("PAN", samples.PAN)
    assert f["pan_number"] == "ABCPS1234K"
    assert f["name"] == "RAHUL KUMAR SHARMA"
    assert f["father_name"] == "SURESH SHARMA"


def test_dl_fields():
    f = _f("DRIVING_LICENCE", samples.DRIVING_LICENCE)
    assert f["dl_number"] == "MP09 20150012345"
    assert f["name"] == "R KUMAR SHARMA"
    assert f["valid_till"] == "13/08/2030"


def test_dl_number_survives_letter_o_for_zero():
    f = _f("DRIVING_LICENCE", "Driving Licence\nDL No MPO9 2O150012345\nName: R K SHARMA")
    assert f["dl_number"] == "MP09 20150012345"


def test_ocr_boxes_are_grouped_into_lines():
    from app.extraction.ocr import _lines

    def box(text, x, y, h=40):
        return {"text": text, "bbox": {"x": x, "y": y, "width": 100, "height": h}}

    # Real EasyOCR output: one printed line split into three boxes, out of order.
    words = [box("SHARMA", 530, 252), box("Name:", 38, 252), box("RAHUL KUMAR", 198, 250),
             box("DOB:", 38, 352), box("14/08/1990", 165, 349)]
    assert _lines(words) == ["Name: RAHUL KUMAR SHARMA", "DOB: 14/08/1990"]


def test_passport_reads_mrz():
    f = _f("PASSPORT", samples.PASSPORT)
    assert f["passport_number"] == "K1234567"
    assert f["name"] == "RAHUL KUMAR SHARMA"
    assert f["expiry_date"] == "09/01/2028"


def test_rc_fields():
    f = _f("RC", samples.RC)
    assert f["registration_number"] == "MP09 AB 1234"
    assert f["owner_name"] == "RAHUL KUMAR SHARMA"
    assert f["chassis_number"] == "MA3EYD81S00123456"
    assert f["valid_upto"] == "04/06/2034"


def test_insurance_period():
    f = _f("VEHICLE_INSURANCE", samples.INSURANCE)
    assert f["policy_start"] == "01/07/2025"
    assert f["policy_end"] == "30/06/2026"
    assert f["insured_name"] == "RAHUL KUMAR SHARMA"


def test_puc_fields():
    f = _f("PUC", samples.PUC)
    assert f["valid_upto"] == "15/12/2026"
    assert f["registration_number"] == "MP09 AB 1234"


def test_parse_date_is_day_first():
    assert parse_date("09/01/2028") == date(2028, 1, 9)
    assert parse_date("31.12.2030") == date(2030, 12, 31)
    assert parse_date("31/02/2030") is None
    assert parse_date("") is None


def test_mask_keeps_last_four():
    assert mask("2345 6789 0123") == "XXXX XXXX 0123"
    assert mask("ABCPS1234K") == "XXXXXX234K"


def test_masked_fields_only_masks_sensitive():
    found = extract_fields("PAN", samples.PAN)
    out = {f["key"]: f["value"] for f in masked_fields(found)}
    assert out["pan_number"] == "XXXXXX234K"
    assert out["name"] == "RAHUL KUMAR SHARMA"
    assert field_value(found, "pan_number") == "ABCPS1234K"  # original untouched


def test_name_similarity():
    assert name_similarity("Rahul Kumar Sharma", "RAHUL KUMAR SHARMA") == 1.0
    assert name_similarity("Mr. Rahul Sharma", "Rahul Sharma") == 1.0
    assert name_similarity("R KUMAR SHARMA", "RAHUL KUMAR SHARMA") >= 0.85
    assert name_similarity("RAHUL SHARMA", "PRIYA VERMA") < 0.85


def test_compare_names_flags_mismatch():
    rows = compare_names([("PAN", "RAHUL SHARMA"), ("Aadhaar", "RAHUL SHARMA"), ("RC", "AMIT JAIN")])
    assert len(rows) == 3
    assert [r["match"] for r in rows] == [True, False, False]


# --- OCR normalisation (added with the eval suite) ---------------------------------

from app.extraction.fields import normalize_ocr_text  # noqa: E402


def test_normalize_repairs_labels_and_dates():
    text = normalize_ocr_text("D0B: 0I/O9/1984\nVa1id Ti1l: 3O-06-2O27")
    assert "DOB: 01/09/1984" in text
    assert "Valid Till: 30/06/2027" in text


def test_normalize_leaves_ids_that_look_like_dates_alone():
    # No real separator: an ID number, not a date.
    assert normalize_ocr_text("Ref 1211212025") == "Ref 1211212025"
    # Not a calendar date.
    assert normalize_ocr_text("Code 45/19/2025") == "Code 45/19/2025"


def test_normalize_strips_hindi_half_of_bilingual_labels():
    assert normalize_ocr_text("Name / नाम\nPOOJA MISHRA") == "Name\nPOOJA MISHRA"


def test_names_with_digit_swaps_are_repaired_and_dates_are_not_names():
    pan = "INCOME TAX DEPARTMENT\nPermanent Account Number\nABCPS1234K\nName\nRAME5H 5HARMA\nDate of Birth\n14/08/1990"
    assert field_value(extract_fields("PAN", pan), "name") == "RAMESH SHARMA"
    no_name = "INCOME TAX DEPARTMENT\nABCPS1234K\nName\n14/08/1990"
    assert field_value(extract_fields("PAN", no_name), "name") == ""


def test_policy_number_letter_swaps_fixed():
    text = "Policy No: 86I5/72O37396/16/000\nInsured Name: A KUMAR"
    assert field_value(extract_fields("VEHICLE_INSURANCE", text), "policy_number") == "8615/72037396/16/000"
