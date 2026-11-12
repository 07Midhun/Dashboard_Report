import pytest

from app.services.led_classifier_service import LedClassifier, RuleSpec
from app.services.reconciliation_engine import (
    MappingSpec,
    ReconciliationValidationError,
    reconcile_reports,
)


LAMP_HEADERS = ["Pole Number", "Arm Count", "Lamp Type", "Installation Date", "Contractor"]
SURVEY_HEADERS = ["Pole No", "Number of Arms", "Type of Lamp", "Survey Remarks"]

LAMP_MAP = MappingSpec(
    pole_number_col="Pole Number",
    arm_count_col="Arm Count",
    lamp_type_col="Lamp Type",
)
SURVEY_MAP = MappingSpec(
    pole_number_col="Pole No",
    arm_count_col="Number of Arms",
    lamp_type_col="Type of Lamp",
)


def _lamp_row(idx: int, pole: str, arms="1", lamp="LED 60W", date="2025-01-10", contractor="ABC"):
    return {
        "_excel_row": idx,
        "Pole Number": pole,
        "Arm Count": arms,
        "Lamp Type": lamp,
        "Installation Date": date,
        "Contractor": contractor,
    }


def _survey_row(idx: int, pole, arms="1", lamp="LED", remarks="OK"):
    return {
        "_excel_row": idx,
        "Pole No": pole,
        "Number of Arms": arms,
        "Type of Lamp": lamp,
        "Survey Remarks": remarks,
    }


def test_case_1_all_poles_already_exist():
    lamp_rows = [_lamp_row(2, "P001"), _lamp_row(3, "P002"), _lamp_row(4, "P003")]
    survey_rows = [_survey_row(2, "P001"), _survey_row(3, "P002"), _survey_row(4, "P003")]

    res = reconcile_reports(
        lamp_headers=LAMP_HEADERS,
        lamp_rows=lamp_rows,
        lamp_mapping=LAMP_MAP,
        survey_headers=SURVEY_HEADERS,
        survey_rows=survey_rows,
        survey_mapping=SURVEY_MAP,
    )
    assert res.summary["added_records"] == 0
    assert res.summary["existing_records"] == 3
    assert res.summary["final_merged_records"] == 3
    assert res.newly_added_records == []


def test_case_2_six_survey_poles_first_three_exist():
    lamp_rows = [_lamp_row(2, "P001"), _lamp_row(3, "P002"), _lamp_row(4, "P003")]
    survey_rows = [_survey_row(i + 1, f"P00{i}") for i in range(1, 7)]

    res = reconcile_reports(
        lamp_headers=LAMP_HEADERS,
        lamp_rows=lamp_rows,
        lamp_mapping=LAMP_MAP,
        survey_headers=SURVEY_HEADERS,
        survey_rows=survey_rows,
        survey_mapping=SURVEY_MAP,
    )
    assert [r["generated_pole_number"] for r in res.newly_added_records] == [
        "P004-L4",
        "P005-L5",
        "P006-L6",
    ]
    assert [r["original_pole_number"] for r in res.skipped_existing_records] == [
        "P001",
        "P002",
        "P003",
    ]
    # Unmapped Lamp Installation columns must NOT be fabricated
    for rec in res.newly_added_records:
        assert "Installation Date" not in rec["mapped_values"]
        assert "Contractor" not in rec["mapped_values"]


def test_case_3_three_survey_poles_first_two_exist_preserves_l3():
    lamp_rows = [_lamp_row(2, "P001"), _lamp_row(3, "P002")]
    survey_rows = [_survey_row(2, "P001"), _survey_row(3, "P002"), _survey_row(4, "P003")]

    res = reconcile_reports(
        lamp_headers=LAMP_HEADERS,
        lamp_rows=lamp_rows,
        lamp_mapping=LAMP_MAP,
        survey_headers=SURVEY_HEADERS,
        survey_rows=survey_rows,
        survey_mapping=SURVEY_MAP,
    )
    assert len(res.newly_added_records) == 1
    assert res.newly_added_records[0]["generated_pole_number"] == "P003-L3"


def test_case_4_mixed_led_non_led_and_unknown_lamp_types():
    lamp_rows = [_lamp_row(2, "P001")]
    survey_rows = [
        _survey_row(2, "P001", lamp="LED"),
        _survey_row(3, "P002", lamp="SVL 250W"),
        _survey_row(4, "P003", lamp="Sodium Vapour"),
        _survey_row(5, "P004", lamp="Conventional"),
        _survey_row(6, "P005", lamp="Non-LED 70W"),
        _survey_row(7, "P006", lamp="Induction 80W"),  # Unknown lamp type
        _survey_row(8, "P007", lamp="  led 40w "),
        _survey_row(9, "P008", lamp="LED Street Light"),
    ]

    res = reconcile_reports(
        lamp_headers=LAMP_HEADERS,
        lamp_rows=lamp_rows,
        lamp_mapping=LAMP_MAP,
        survey_headers=SURVEY_HEADERS,
        survey_rows=survey_rows,
        survey_mapping=SURVEY_MAP,
    )
    # Eligible LEDs: P001 (L1, skipped), P007 (L2), P008 (L3)
    assert res.summary["total_led_records"] == 3
    assert res.summary["non_led_records"] == 4
    assert res.summary["unknown_lamp_type_records"] == 1
    assert res.unknown_lamp_types[0]["pole_number"] == "P006"
    assert [r["generated_pole_number"] for r in res.newly_added_records] == [
        "P007-L2",
        "P008-L3",
    ]


def test_case_5_duplicate_pole_numbers_retains_first_occurrence():
    lamp_rows = [_lamp_row(2, "P001")]
    survey_rows = [
        _survey_row(2, "P001", arms="1", lamp="LED"),
        _survey_row(3, "P002", arms="1", lamp="LED 60W"),
        _survey_row(4, " p002 ", arms="2", lamp="LED 90W"),  # duplicate of P002
        _survey_row(5, "P003", arms="2", lamp="LED 40W"),
    ]

    res = reconcile_reports(
        lamp_headers=LAMP_HEADERS,
        lamp_rows=lamp_rows,
        lamp_mapping=LAMP_MAP,
        survey_headers=SURVEY_HEADERS,
        survey_rows=survey_rows,
        survey_mapping=SURVEY_MAP,
    )
    assert res.summary["duplicate_records"] == 1
    assert res.duplicate_records[0]["first_seen_row"] == 3
    assert [r["generated_pole_number"] for r in res.newly_added_records] == [
        "P002-L2",
        "P003-L3",
    ]
    # First occurrence arm count retained
    assert res.newly_added_records[0]["arm_count"] == "1"


def test_case_6_case_whitespace_and_numeric_normalization():
    lamp_rows = [
        _lamp_row(2, "  p001 "),
        _lamp_row(3, 102.0),  # Excel numeric float representing integer 102
    ]
    survey_rows = [
        _survey_row(2, "P001", lamp="led"),
        _survey_row(3, "102", lamp="LED 60W"),
        _survey_row(4, 103.0, lamp="LED 90W"),
    ]

    res = reconcile_reports(
        lamp_headers=LAMP_HEADERS,
        lamp_rows=lamp_rows,
        lamp_mapping=LAMP_MAP,
        survey_headers=SURVEY_HEADERS,
        survey_rows=survey_rows,
        survey_mapping=SURVEY_MAP,
    )
    assert res.summary["existing_records"] == 2
    assert [r["generated_pole_number"] for r in res.newly_added_records] == ["103-L3"]


def test_case_7_missing_mandatory_columns_raises_validation_error():
    with pytest.raises(ReconciliationValidationError, match="Lamp Type"):
        reconcile_reports(
            lamp_headers=LAMP_HEADERS,
            lamp_rows=[],
            lamp_mapping=LAMP_MAP,
            survey_headers=["Pole No", "Number of Arms"],
            survey_rows=[],
            survey_mapping=MappingSpec(
                pole_number_col="Pole No",
                arm_count_col="Number of Arms",
                lamp_type_col="Type of Lamp",
            ),
        )


def test_case_8_blank_pole_numbers_excluded_and_reported():
    lamp_rows = [_lamp_row(2, "P001")]
    survey_rows = [
        _survey_row(2, "", lamp="LED"),
        _survey_row(3, None, lamp="LED 40W"),
        _survey_row(4, "   ", lamp="LED 60W"),
        _survey_row(5, "P002", lamp="LED 60W"),
    ]

    res = reconcile_reports(
        lamp_headers=LAMP_HEADERS,
        lamp_rows=lamp_rows,
        lamp_mapping=LAMP_MAP,
        survey_headers=SURVEY_HEADERS,
        survey_rows=survey_rows,
        survey_mapping=SURVEY_MAP,
    )
    assert res.summary["invalid_records"] == 3
    assert [r["generated_pole_number"] for r in res.newly_added_records] == ["P002-L1"]


def test_custom_led_classification_rule_support():
    classifier = LedClassifier(
        [
            RuleSpec("SOLAR LED", "contains", "led"),
            RuleSpec("LED", "word", "led"),
        ]
    )
    assert classifier.classify("Solar LED 30W")[0] == "led"
    assert classifier.classify("Sealed Beam")[0] == "unknown"


def test_case_9_empty_lamp_types_hyphen_and_blank_classified_as_empty():
    lamp_rows = [_lamp_row(2, "P001")]
    # Simulate an admin adding '-' with default 'contains' match_type alongside custom '--'
    classifier = LedClassifier(
        [
            RuleSpec("NON-LED", "contains", "non_led"),
            RuleSpec("LED", "word", "led"),
            RuleSpec("-", "contains", "empty"),
            RuleSpec("--", "exact", "empty"),
            RuleSpec("N/A", "exact", "empty"),
        ]
    )
    survey_rows = [
        _survey_row(2, "P001", lamp="LED"),
        _survey_row(3, "P002", lamp="-"),         # hyphen -> empty
        _survey_row(4, "P003", lamp=" - "),       # padded hyphen -> empty
        _survey_row(5, "P004", lamp=""),          # blank -> empty
        _survey_row(6, "P005", lamp="   "),       # whitespace -> empty
        _survey_row(7, "P006", lamp=None),        # None -> empty
        _survey_row(8, "P007", lamp="n/a"),       # custom empty rule -> empty
        _survey_row(9, "P008", lamp="LED-60W"),   # hyphenated LED stays eligible LED
        _survey_row(10, "P009", lamp="Non-LED - 70W"),  # stays non_led
        _survey_row(11, "P010", lamp="Induction"),      # still flagged unknown
    ]

    res = reconcile_reports(
        lamp_headers=LAMP_HEADERS,
        lamp_rows=lamp_rows,
        lamp_mapping=LAMP_MAP,
        survey_headers=SURVEY_HEADERS,
        survey_rows=survey_rows,
        survey_mapping=SURVEY_MAP,
        classifier=classifier,
    )
    assert res.summary["empty_records"] == 6
    assert [r["pole_number"] for r in res.empty_records] == ["P002", "P003", "P004", "P005", "P006", "P007"]
    assert res.summary["non_led_records"] == 1
    assert res.summary["unknown_lamp_type_records"] == 1
    assert res.unknown_lamp_types[0]["pole_number"] == "P010"
    assert [r["generated_pole_number"] for r in res.newly_added_records] == ["P008-L2"]

