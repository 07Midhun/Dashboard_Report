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
    # Default arm count is 1 for survey rows -> all classify as L1
    assert [r["generated_pole_number"] for r in res.newly_added_records] == [
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


def test_case_3_three_survey_poles_arm_count_determines_l_classification():
    lamp_rows = [_lamp_row(2, "P001"), _lamp_row(3, "P002")]
    # P003 has arm count 3 -> must be classified strictly as P003-L3
    survey_rows = [
        _survey_row(2, "P001", arms="1"),
        _survey_row(3, "P002", arms="2"),
        _survey_row(4, "P003", arms="3"),
    ]

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
    assert res.newly_added_records[0]["l_sequence"] == 3


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
    # Eligible LEDs: P001 (arms=1, skipped), P007 (arms=1 -> L1), P008 (arms=2 -> L2)
    assert res.summary["total_led_records"] == 3
    assert res.summary["non_led_records"] == 4
    assert res.summary["unknown_lamp_type_records"] == 1
    assert res.unknown_lamp_types[0]["pole_number"] == "P006"
    assert [r["generated_pole_number"] for r in res.newly_added_records] == [
        "P007-L1",
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
    # P002 first occurrence has arms="1" -> P002-L1; P003 has arms="2" -> P003-L2
    assert [r["generated_pole_number"] for r in res.newly_added_records] == [
        "P002-L1",
        "P003-L2",
    ]
    # First occurrence arm count retained
    assert res.newly_added_records[0]["arm_count"] == "1"


def test_case_6_case_whitespace_and_numeric_normalization():
    lamp_rows = [
        _lamp_row(2, "  p001 "),
        _lamp_row(3, 102.0),  # Excel numeric float representing integer 102
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
    assert [r["generated_pole_number"] for r in res.newly_added_records] == ["103-L1"]


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
    assert [r["generated_pole_number"] for r in res.newly_added_records] == ["P008-L1"]


def test_arm_count_based_l_classification_matrix():
    """
    Validates the exact specification table and rules from the user requirement:
    - L1, L2, L3 and subsequent classifications are strictly based on original Pole Arm Count.
    - Number of matched or unmatched lamps does not alter the L-classification.
    - Arm count 1 -> L1
    - Arm count 2 -> L2
    - Arm count 3 -> L3
    - Arm count 4 -> L4
    - Higher counts (L5, L12) -> LN
    - Word representations ('Single', 'Double', 'Triple', '2 Arms') -> LN
    - Blank / None / non-numeric arm count defaults safely to L1
    """
    lamp_rows = [
        _lamp_row(2, "EXIST-1ARM", arms="1"),
        _lamp_row(3, "EXIST-2ARM", arms="2"),
        _lamp_row(4, "EXIST-3ARM", arms="3"),
    ]

    survey_rows = [
        # Matched records (already in lamp installation) -> skipped
        _survey_row(2, "EXIST-1ARM", arms="1"),
        _survey_row(3, "EXIST-2ARM", arms="2"),
        _survey_row(4, "EXIST-3ARM", arms="3"),

        # Unmatched records with different arm counts
        _survey_row(5, "POLE-1A", arms="1"),
        _survey_row(6, "POLE-2A", arms="2"),
        _survey_row(7, "POLE-3A", arms="3"),
        _survey_row(8, "POLE-4A", arms="4"),
        _survey_row(9, "POLE-5A", arms="5"),
        _survey_row(10, "POLE-12A", arms=12),
        _survey_row(11, "POLE-FLT", arms=2.0),
        _survey_row(12, "POLE-WORD1", arms="Single"),
        _survey_row(13, "POLE-WORD2", arms="Double"),
        _survey_row(14, "POLE-STR", arms=" 3 Arms "),
        _survey_row(15, "POLE-BLANK", arms=""),
        _survey_row(16, "POLE-NONE", arms=None),
        _survey_row(17, "POLE-ZERO", arms=0),
    ]

    res = reconcile_reports(
        lamp_headers=LAMP_HEADERS,
        lamp_rows=lamp_rows,
        lamp_mapping=LAMP_MAP,
        survey_headers=SURVEY_HEADERS,
        survey_rows=survey_rows,
        survey_mapping=SURVEY_MAP,
    )

    assert res.summary["existing_records"] == 3
    assert [r["original_pole_number"] for r in res.skipped_existing_records] == [
        "EXIST-1ARM",
        "EXIST-2ARM",
        "EXIST-3ARM",
    ]
    # Skipped records retain arm-count-based classification in preview
    assert [r["l_sequence"] for r in res.skipped_existing_records] == [1, 2, 3]

    expected_added = [
        ("POLE-1A", "POLE-1A-L1", 1),
        ("POLE-2A", "POLE-2A-L2", 2),
        ("POLE-3A", "POLE-3A-L3", 3),
        ("POLE-4A", "POLE-4A-L4", 4),
        ("POLE-5A", "POLE-5A-L5", 5),
        ("POLE-12A", "POLE-12A-L12", 12),
        ("POLE-FLT", "POLE-FLT-L2", 2),
        ("POLE-WORD1", "POLE-WORD1-L1", 1),
        ("POLE-WORD2", "POLE-WORD2-L2", 2),
        ("POLE-STR", "POLE-STR-L3", 3),
        ("POLE-BLANK", "POLE-BLANK-L1", 1),  # defaults safely to 1
        ("POLE-NONE", "POLE-NONE-L1", 1),   # defaults safely to 1
        ("POLE-ZERO", "POLE-ZERO-L1", 1),   # 0 defaults safely to 1
    ]

    assert len(res.newly_added_records) == len(expected_added)
    for rec, (exp_orig, exp_gen, exp_l) in zip(res.newly_added_records, expected_added):
        assert rec["original_pole_number"] == exp_orig
        assert rec["generated_pole_number"] == exp_gen
        assert rec["l_sequence"] == exp_l


def test_lights_empty_and_lamp_id_mapping_for_newly_added_records():
    """
    Validates user requirement:
    - In 'Light's /Empty Pole ' column, newly added LED is displayed (e.g. 'LED').
    - In 'Lamp ID' column (LED ID), the pole number with L1/L2 is displayed (e.g. 'P0010-L2')
      for newly added survey records alone (same as Pole Number).
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

    assert res.summary["existing_records"] == 1
    assert res.summary["added_records"] == 2

    # Check newly added records mapped_values
    rec1 = res.newly_added_records[0]
    assert rec1["original_pole_number"] == "NEW-P0010"
    assert rec1["generated_pole_number"] == "NEW-P0010-L2"
    assert rec1["mapped_values"]["Pole Number"] == "NEW-P0010-L2"
    # User requirement: In Lamp ID (LED ID), display pole number with L1/L2
    assert rec1["mapped_values"]["Lamp ID"] == "NEW-P0010-L2"
    # User requirement: In Light's /Empty Pole, display newly added LED
    assert rec1["mapped_values"]["Light's /Empty Pole "] == "LED"
    assert rec1["mapped_values"]["Old Arm Status "] == "2"

    rec2 = res.newly_added_records[1]
    assert rec2["original_pole_number"] == "NEW-P0011"
    assert rec2["generated_pole_number"] == "NEW-P0011-L1"
    assert rec2["mapped_values"]["Pole Number"] == "NEW-P0011-L1"
    assert rec2["mapped_values"]["Lamp ID"] == "NEW-P0011-L1"
    assert rec2["mapped_values"]["Light's /Empty Pole "] == "LED 40W"
    assert rec2["mapped_values"]["Old Arm Status "] == "1"



