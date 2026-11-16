import pytest

from app.services.led_classifier_service import LedClassifier, RuleSpec
from app.services.reconciliation_engine import (
    MappingSpec,
    ReconciliationValidationError,
    reconcile_reports,
)


LAMP_HEADERS = ["Pole Number", "Arm Count", "Lamp Type", "Installation Date", "Contractor", "Lamp ID"]
SURVEY_HEADERS = ["Pole No", "Number of Arms", "Type of Lamp", "Survey Remarks"]

LAMP_MAP = MappingSpec(
    pole_number_col="Pole Number",
    arm_count_col="Arm Count",
    lamp_type_col="Lamp Type",
    lamp_id_col="Lamp ID",
)
SURVEY_MAP = MappingSpec(
    pole_number_col="Pole No",
    arm_count_col="Number of Arms",
    lamp_type_col="Type of Lamp",
)


def _lamp_row(idx: int, pole: str, arms="1", lamp="LED 60W", date="2025-01-10", contractor="ABC", lamp_id=None):
    return {
        "_excel_row": idx,
        "Pole Number": pole,
        "Arm Count": arms,
        "Lamp Type": lamp,
        "Installation Date": date,
        "Contractor": contractor,
        "Lamp ID": lamp_id or f"LMP-{pole}",
    }


def _survey_row(idx: int, pole, arms="1", lamp="LED", remarks="OK"):
    return {
        "_excel_row": idx,
        "Pole No": pole,
        "Number of Arms": arms,
        "Type of Lamp": lamp,
        "Survey Remarks": remarks,
    }


def test_case_1_arm_count_1_unmatched_and_matched():
    """
    Case 1: Arm Count = 1
    - If Pole Number does not match with Lamp Report:
        Pole Number: P001, Lamp ID: P001-L1
    - If Pole Number matches with Lamp Report:
        Retain actual Lamp Report ID. Do not generate an L1 identifier.
    """
    # Matched pole: P001 exists in Lamp Report
    lamp_rows = [_lamp_row(2, "P001", lamp_id="ACTUAL-LMP-001")]
    # P001 matches (arm=1), P002 does not match (arm=1)
    survey_rows = [
        _survey_row(2, "P001", arms="1"),
        _survey_row(3, "P002", arms="1"),
    ]

    res = reconcile_reports(
        lamp_headers=LAMP_HEADERS,
        lamp_rows=lamp_rows,
        lamp_mapping=LAMP_MAP,
        survey_headers=SURVEY_HEADERS,
        survey_rows=survey_rows,
        survey_mapping=SURVEY_MAP,
    )

    # P001 matches: retained in existing_lamp_records with actual ID, no L1 generated
    assert res.existing_lamp_records[0]["Pole Number"] == "P001"
    assert res.existing_lamp_records[0]["Lamp ID"] == "ACTUAL-LMP-001"

    # P002 unmatched: exactly 1 new row generated with Pole Number = P001, Lamp ID = P002-L1
    assert len(res.newly_added_records) == 1
    added = res.newly_added_records[0]
    assert added["mapped_values"]["Pole Number"] == "P002"
    assert added["mapped_values"]["Lamp ID"] == "P002-L1"
    assert added["original_pole_number"] == "P002"
    assert added["generated_lamp_id"] == "P002-L1"
    assert added["l_sequence"] == 1


def test_case_2_arm_count_2_neither_matches_and_first_arm_matches():
    """
    Case 2: Arm Count = 2
    - If neither arm matches with Lamp Report:
        Pole Number: P002, Lamp ID: P002-L1
        Pole Number: P002, Lamp ID: P002-L2
    - If first arm matches and second arm does not:
        Pole Number: P002, Lamp ID: Actual Lamp Report ID
        Pole Number: P002, Lamp ID: P002-L2
      Important: When a match is found in Lamp Report, L1 must not be generated or displayed.
      Only the unmatched L2 identifier should be generated.
    """
    # Part A: Neither arm matches (P002 not in Lamp Report)
    survey_neither = [_survey_row(2, "P002", arms="2")]
    res_neither = reconcile_reports(
        lamp_headers=LAMP_HEADERS,
        lamp_rows=[],
        lamp_mapping=LAMP_MAP,
        survey_headers=SURVEY_HEADERS,
        survey_rows=survey_neither,
        survey_mapping=SURVEY_MAP,
    )
    assert len(res_neither.newly_added_records) == 2
    rec1, rec2 = res_neither.newly_added_records
    # Pole Number column must contain ONLY original pole number (never append L1/L2)
    assert rec1["mapped_values"]["Pole Number"] == "P002"
    assert rec1["mapped_values"]["Lamp ID"] == "P002-L1"
    assert rec2["mapped_values"]["Pole Number"] == "P002"
    assert rec2["mapped_values"]["Lamp ID"] == "P002-L2"

    # Part B: First arm matches (P002 has 1 record in Lamp Report)
    lamp_first_match = [_lamp_row(2, "P002", lamp_id="ACTUAL-LMP-002-ARM1")]
    res_partial = reconcile_reports(
        lamp_headers=LAMP_HEADERS,
        lamp_rows=lamp_first_match,
        lamp_mapping=LAMP_MAP,
        survey_headers=SURVEY_HEADERS,
        survey_rows=survey_neither,
        survey_mapping=SURVEY_MAP,
    )
    # Existing row retained with genuine ID
    assert res_partial.existing_lamp_records[0]["Pole Number"] == "P002"
    assert res_partial.existing_lamp_records[0]["Lamp ID"] == "ACTUAL-LMP-002-ARM1"

    # Only 1 new row generated for unmatched L2. L1 must NOT be generated or displayed!
    assert len(res_partial.newly_added_records) == 1
    unmatched_rec = res_partial.newly_added_records[0]
    assert unmatched_rec["mapped_values"]["Pole Number"] == "P002"
    assert unmatched_rec["mapped_values"]["Lamp ID"] == "P002-L2"
    assert unmatched_rec["generated_lamp_id"] == "P002-L2"
    assert unmatched_rec["l_sequence"] == 2


def test_case_3_arm_count_3_none_match_and_first_second_arms_match():
    """
    Case 3: Arm Count = 3
    - If none of the three arms matches with Lamp Report:
        Pole Number: P003, Lamp ID: P003-L1
        Pole Number: P003, Lamp ID: P003-L2
        Pole Number: P003, Lamp ID: P003-L3
    - If first and second arms match:
        Pole Number: P003, Lamp ID: Actual Lamp Report ID 1
        Pole Number: P003, Lamp ID: Actual Lamp Report ID 2
        Pole Number: P003, Lamp ID: P003-L3
      Only unmatched L3 identifier should be generated. Do not generate or display L1 when match found.
    - If first arm matches and arms 2 & 3 do not:
        Only L2 and L3 generated. L1 must NOT be generated.
    """
    # Part A: None match
    survey_none = [_survey_row(2, "P003", arms="3")]
    res_none = reconcile_reports(
        lamp_headers=LAMP_HEADERS,
        lamp_rows=[],
        lamp_mapping=LAMP_MAP,
        survey_headers=SURVEY_HEADERS,
        survey_rows=survey_none,
        survey_mapping=SURVEY_MAP,
    )
    assert len(res_none.newly_added_records) == 3
    assert [r["mapped_values"]["Pole Number"] for r in res_none.newly_added_records] == [
        "P003",
        "P003",
        "P003",
    ]
    assert [r["mapped_values"]["Lamp ID"] for r in res_none.newly_added_records] == [
        "P003-L1",
        "P003-L2",
        "P003-L3",
    ]

    # Part B: First and second arms match (2 records in Lamp Report for P003)
    lamp_two_matches = [
        _lamp_row(2, "P003", lamp_id="ACTUAL-LMP-003-A1"),
        _lamp_row(3, "P003", lamp_id="ACTUAL-LMP-003-A2"),
    ]
    res_two = reconcile_reports(
        lamp_headers=LAMP_HEADERS,
        lamp_rows=lamp_two_matches,
        lamp_mapping=LAMP_MAP,
        survey_headers=SURVEY_HEADERS,
        survey_rows=survey_none,
        survey_mapping=SURVEY_MAP,
    )
    # Only unmatched L3 generated! L1 and L2 not generated.
    assert len(res_two.newly_added_records) == 1
    assert res_two.newly_added_records[0]["mapped_values"]["Pole Number"] == "P003"
    assert res_two.newly_added_records[0]["mapped_values"]["Lamp ID"] == "P003-L3"
    assert res_two.newly_added_records[0]["l_sequence"] == 3

    # Part C: First arm matches (1 record in Lamp Report for P003)
    lamp_one_match = [_lamp_row(2, "P003", lamp_id="ACTUAL-LMP-003-A1")]
    res_one = reconcile_reports(
        lamp_headers=LAMP_HEADERS,
        lamp_rows=lamp_one_match,
        lamp_mapping=LAMP_MAP,
        survey_headers=SURVEY_HEADERS,
        survey_rows=survey_none,
        survey_mapping=SURVEY_MAP,
    )
    # Unmatched L2 and L3 generated! L1 is NOT generated.
    assert len(res_one.newly_added_records) == 2
    assert [r["mapped_values"]["Pole Number"] for r in res_one.newly_added_records] == [
        "P003",
        "P003",
    ]
    assert [r["mapped_values"]["Lamp ID"] for r in res_one.newly_added_records] == [
        "P003-L2",
        "P003-L3",
    ]


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
    # Default arm count is 1 for survey rows -> all unmatched classify as L1 in Lamp ID
    assert [r["mapped_values"]["Pole Number"] for r in res.newly_added_records] == [
        "P004",
        "P005",
        "P006",
    ]
    assert [r["mapped_values"]["Lamp ID"] for r in res.newly_added_records] == [
        "P004-L1",
        "P005-L1",
        "P006-L1",
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


def test_case_4_mixed_led_non_led_and_unknown_lamp_types():
    lamp_rows = [_lamp_row(2, "P001")]
    survey_rows = [
        _survey_row(2, "P001", arms="1", lamp="LED"),
        _survey_row(3, "P002", arms="1", lamp="SVL 250W"),
        _survey_row(4, "P003", arms="2", lamp="Sodium Vapour"),
        _survey_row(5, "P004", arms="1", lamp="Conventional"),
        _survey_row(6, "P005", arms="1", lamp="Non-LED 70W"),
        _survey_row(7, "P006", arms="1", lamp="Induction 80W"),  # Unknown lamp type
        _survey_row(8, "P007", arms="1", lamp="  led 40w "),
        _survey_row(9, "P008", arms="2", lamp="LED Street Light"),
    ]

    res = reconcile_reports(
        lamp_headers=LAMP_HEADERS,
        lamp_rows=lamp_rows,
        lamp_mapping=LAMP_MAP,
        survey_headers=SURVEY_HEADERS,
        survey_rows=survey_rows,
        survey_mapping=SURVEY_MAP,
    )
    # Eligible LEDs: P001 (arms=1, skipped), P007 (arms=1 -> L1), P008 (arms=2 -> L1, L2)
    assert res.summary["total_led_records"] == 3
    assert res.summary["non_led_records"] == 4
    assert res.summary["unknown_lamp_type_records"] == 1
    assert res.unknown_lamp_types[0]["pole_number"] == "P006"
    assert [r["mapped_values"]["Pole Number"] for r in res.newly_added_records] == [
        "P007",
        "P008",
        "P008",
    ]
    assert [r["mapped_values"]["Lamp ID"] for r in res.newly_added_records] == [
        "P007-L1",
        "P008-L1",
        "P008-L2",
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
    # P002 first occurrence has arms="1" -> P002-L1; P003 has arms="2" -> P003-L1, P003-L2
    assert [r["mapped_values"]["Pole Number"] for r in res.newly_added_records] == [
        "P002",
        "P003",
        "P003",
    ]
    assert [r["mapped_values"]["Lamp ID"] for r in res.newly_added_records] == [
        "P002-L1",
        "P003-L1",
        "P003-L2",
    ]
    assert res.newly_added_records[0]["arm_count"] == "1"


def test_case_6_case_whitespace_and_numeric_normalization():
    lamp_rows = [
        _lamp_row(2, "  p001 "),
        _lamp_row(3, 102.0),
    ]
    survey_rows = [
        _survey_row(2, "P001", arms="1", lamp="led"),
        _survey_row(3, "102", arms="1", lamp="LED 60W"),
        _survey_row(4, 103.0, arms="1", lamp="LED 90W"),
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
    assert len(res.newly_added_records) == 1
    assert res.newly_added_records[0]["mapped_values"]["Pole Number"] == "103"
    assert res.newly_added_records[0]["mapped_values"]["Lamp ID"] == "103-L1"


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
    assert len(res.newly_added_records) == 1
    assert res.newly_added_records[0]["mapped_values"]["Pole Number"] == "P002"
    assert res.newly_added_records[0]["mapped_values"]["Lamp ID"] == "P002-L1"


def test_custom_led_classification_rule_support():
    classifier = LedClassifier(
        [
            RuleSpec("SOLAR LED", "contains", "led"),
            RuleSpec("LED", "word", "led"),
            RuleSpec("FL LED", "contains", "led"),
            RuleSpec("FL LED,LED", "contains", "led"),
            RuleSpec("FL", "contains", "non_led"),
        ]
    )
    assert classifier.classify("Solar LED 30W")[0] == "led"
    assert classifier.classify("FL LED")[0] == "led"
    assert classifier.classify("FL LED,LED")[0] == "led"
    assert classifier.classify("FL")[0] == "non_led"
    assert classifier.classify("Sealed Beam")[0] == "unknown"


def test_case_9_empty_lamp_types_hyphen_and_blank_classified_as_empty():
    lamp_rows = [_lamp_row(2, "P001")]
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
        _survey_row(3, "P002", lamp="-"),
        _survey_row(4, "P003", lamp=" - "),
        _survey_row(5, "P004", lamp=""),
        _survey_row(6, "P005", lamp="   "),
        _survey_row(7, "P006", lamp=None),
        _survey_row(8, "P007", lamp="n/a"),
        _survey_row(9, "P008", lamp="LED-60W"),
        _survey_row(10, "P009", lamp="Non-LED - 70W"),
        _survey_row(11, "P010", lamp="Induction"),
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
    assert len(res.newly_added_records) == 1
    assert res.newly_added_records[0]["mapped_values"]["Pole Number"] == "P008"
    assert res.newly_added_records[0]["mapped_values"]["Lamp ID"] == "P008-L1"


def test_lights_empty_and_lamp_id_mapping_for_newly_added_records():
    """
    Validates user requirement:
    - In 'Pole Number' column, ONLY the original Pole Number is displayed (never -L1/-L2).
    - In 'Lamp ID' column, POLE_NUMBER-L1, POLE_NUMBER-L2, etc. is displayed exclusively.
    - In 'Light's /Empty Pole ' column, newly added LED is displayed (e.g. 'LED').
    - Existing records preserve their original values untouched.
    """
    bbmp_lamp_headers = [
        "Sr #",
        "Switch Point Number",
        "Pole Number",
        "Pole Type",
        "Light's /Empty Pole ",
        "Old Light's Wattage",
        "Old Arm Status ",
        "Lamp ID",
    ]
    bbmp_lamp_map = MappingSpec(
        pole_number_col="Pole Number",
        arm_count_col="Old Arm Status ",
        lamp_type_col="Light's /Empty Pole ",
        lamp_id_col="Lamp ID",
    )

    existing_rows = [
        {
            "_excel_row": 2,
            "Sr #": 1,
            "Switch Point Number": "SP01",
            "Pole Number": "EXISTING-P001",
            "Pole Type": "RCC",
            "Light's /Empty Pole ": "SVL",
            "Old Light's Wattage": "150W",
            "Old Arm Status ": "Good",
            "Lamp ID": "LEV-0034-01-00-12/25-A17403",
        }
    ]

    survey_headers = ["Pole ID", "Arm Count", "Lamp Type"]
    survey_map = MappingSpec(
        pole_number_col="Pole ID",
        arm_count_col="Arm Count",
        lamp_type_col="Lamp Type",
    )
    survey_rows = [
        {
            "_excel_row": 10,
            "Pole ID": "EXISTING-P001",
            "Arm Count": "1",
            "Lamp Type": "LED",
        },
        {
            "_excel_row": 11,
            "Pole ID": "NEW-P0010",
            "Arm Count": "2",
            "Lamp Type": "LED",
        },
        {
            "_excel_row": 12,
            "Pole ID": "NEW-P0011",
            "Arm Count": "1",
            "Lamp Type": "LED 40W",
        },
    ]

    res = reconcile_reports(
        lamp_headers=bbmp_lamp_headers,
        lamp_rows=existing_rows,
        lamp_mapping=bbmp_lamp_map,
        survey_headers=survey_headers,
        survey_rows=survey_rows,
        survey_mapping=survey_map,
    )

    # EXISTING-P001 had arm=1 and matched the 1 row in lamp report -> 0 new rows (L1 not generated)
    assert res.summary["existing_records"] == 1
    # NEW-P0010 has arm=2 (unmatched) -> 2 rows (L1 and L2)
    # NEW-P0011 has arm=1 (unmatched) -> 1 row (L1)
    # Total added = 3
    assert res.summary["added_records"] == 3

    # Check NEW-P0010 Arm 1
    rec1 = res.newly_added_records[0]
    assert rec1["original_pole_number"] == "NEW-P0010"
    assert rec1["mapped_values"]["Pole Number"] == "NEW-P0010"
    assert rec1["mapped_values"]["Lamp ID"] == "NEW-P0010-L1"
    assert rec1["mapped_values"]["Light's /Empty Pole "] == "LED"
    assert rec1["mapped_values"]["Old Arm Status "] == "2"

    # Check NEW-P0010 Arm 2
    rec2 = res.newly_added_records[1]
    assert rec2["original_pole_number"] == "NEW-P0010"
    assert rec2["mapped_values"]["Pole Number"] == "NEW-P0010"
    assert rec2["mapped_values"]["Lamp ID"] == "NEW-P0010-L2"
    assert rec2["mapped_values"]["Light's /Empty Pole "] == "LED"
    assert rec2["mapped_values"]["Old Arm Status "] == "2"

    # Check NEW-P0011 Arm 1
    rec3 = res.newly_added_records[2]
    assert rec3["original_pole_number"] == "NEW-P0011"
    assert rec3["mapped_values"]["Pole Number"] == "NEW-P0011"
    assert rec3["mapped_values"]["Lamp ID"] == "NEW-P0011-L1"
    assert rec3["mapped_values"]["Light's /Empty Pole "] == "LED 40W"
    assert rec3["mapped_values"]["Old Arm Status "] == "1"
