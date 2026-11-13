import re
from dataclasses import dataclass, field
from typing import Any

from app.services.led_classifier_service import LedClassifier
from app.utilities.pole_normalizer import cell_to_display_str, normalize_header_name, normalize_pole_key


class ReconciliationValidationError(Exception):
    """Raised when mandatory columns or input structures fail validation."""


@dataclass
class MappingSpec:
    pole_number_col: str
    arm_count_col: str | None = None
    lamp_type_col: str | None = None
    extra_mappings: dict[str, str] = field(default_factory=dict)  # survey_col -> lamp_col


@dataclass
class EligibleSurveyRecord:
    excel_row: int
    original_pole_number: str
    normalized_pole_key: str
    arm_count: str
    lamp_type: str
    l_sequence: int
    raw_record: dict[str, Any]


@dataclass
class ReconciliationResult:
    summary: dict[str, int]
    existing_lamp_records: list[dict[str, Any]]
    newly_added_records: list[dict[str, Any]]
    skipped_existing_records: list[dict[str, Any]]
    duplicate_records: list[dict[str, Any]]
    invalid_records: list[dict[str, Any]]
    unknown_lamp_types: list[dict[str, Any]]
    empty_records: list[dict[str, Any]]
    non_led_records: list[dict[str, Any]]
    warnings: list[str]


def parse_arm_count_to_l_number(value: Any) -> int:
    """
    Extracts positive integer arm count from survey record to determine L-number (L1, L2, L3, ...).
    Strictly arm-count-based per business requirements:
    - Arm count 1 -> 1 (L1)
    - Arm count 2 -> 2 (L2)
    - Arm count 3 -> 3 (L3)
    - Arm count N -> N (LN)
    If value is None, blank, non-numeric, or <= 0, defaults safely to 1 (L1).
    """
    if value is None:
        return 1
    if isinstance(value, bool):
        return 1
    if isinstance(value, (int, float)):
        try:
            val_int = int(value)
            return val_int if val_int > 0 else 1
        except (ValueError, OverflowError):
            return 1

    val_str = cell_to_display_str(value).strip()
    if not val_str:
        return 1

    # Check common word representations
    word_map = {
        "single": 1,
        "double": 2,
        "triple": 3,
        "quad": 4,
        "quadruple": 4,
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
    }
    lower_str = val_str.lower()
    if lower_str in word_map:
        return word_map[lower_str]

    # Try float parsing e.g. "2.0"
    try:
        val_float = float(val_str)
        val_int = int(val_float)
        return val_int if val_int > 0 else 1
    except (ValueError, OverflowError):
        pass

    # Search for first sequence of digits
    match = re.search(r"\d+", val_str)
    if match:
        val_int = int(match.group(0))
        return val_int if val_int > 0 else 1

    return 1


def reconcile_reports(
    *,
    lamp_headers: list[str],
    lamp_rows: list[dict[str, Any]],
    lamp_mapping: MappingSpec,
    survey_headers: list[str],
    survey_rows: list[dict[str, Any]],
    survey_mapping: MappingSpec,
    classifier: LedClassifier | None = None,
) -> ReconciliationResult:
    """
    Core Schnell reconciliation engine (Part 8 & Arm-Count-Based L1, L2, L3 Classification).

    L-Number Classification Rule:
    1. Read Pole Survey records in original order.
    2. Exclude invalid/blank Pole Numbers.
    3. Filter eligible LED records using LedClassifier (excluding non-LED & empty, flagging unknown).
    4. Deduplicate Pole Survey LED records by normalized Pole Number, retaining first occurrence.
    5. Determine L-number classification strictly by the Arm Count of the Pole Survey record:
       - Arm Count 1 -> L1
       - Arm Count 2 -> L2
       - Arm Count 3 -> L3
       - Arm Count N -> LN
       (Defaults to L1 if arm count is blank, non-numeric, or <= 0).
       The number of matched or unmatched lamps does not alter the L-classification.
    6. Compare against existing Lamp Installation poles:
       - If present -> Skip (marked as existing matched record).
       - If absent -> Add with '<OriginalPoleNumber>-L<arm_count>' in the target Pole Number cell.
    """
    # Validate mandatory columns
    if not survey_mapping.pole_number_col or survey_mapping.pole_number_col not in survey_headers:
        raise ReconciliationValidationError(
            "Pole Survey workbook is missing the mandatory 'Pole Number' column mapping."
        )
    if not survey_mapping.arm_count_col or survey_mapping.arm_count_col not in survey_headers:
        raise ReconciliationValidationError(
            "Pole Survey workbook is missing the mandatory 'Arm Count' column mapping."
        )
    if not survey_mapping.lamp_type_col or survey_mapping.lamp_type_col not in survey_headers:
        raise ReconciliationValidationError(
            "Pole Survey workbook is missing the mandatory 'Lamp Type' column mapping."
        )

    if not lamp_mapping.pole_number_col or lamp_mapping.pole_number_col not in lamp_headers:
        raise ReconciliationValidationError(
            "Lamp Installation workbook is missing the mandatory 'Pole Number' column mapping."
        )

    led_classifier = classifier or LedClassifier()
    warnings: list[str] = []

    # Step 1: Index existing Lamp Installation records
    existing_pole_keys: set[str] = set()
    existing_lamp_records: list[dict[str, Any]] = []
    lamp_blank_count = 0

    for row in lamp_rows:
        raw_pole = row.get(lamp_mapping.pole_number_col)
        norm_key = normalize_pole_key(raw_pole)
        disp_pole = cell_to_display_str(raw_pole)
        if norm_key is None:
            lamp_blank_count += 1
        else:
            existing_pole_keys.add(norm_key)

        record_out = {"_excel_row": row.get("_excel_row")}
        for col in lamp_headers:
            record_out[col] = cell_to_display_str(row.get(col))
        existing_lamp_records.append(record_out)

    if lamp_blank_count > 0:
        warnings.append(
            f"Lamp Installation workbook contains {lamp_blank_count} row(s) with blank Pole Numbers; existing rows were preserved unchanged."
        )

    # Step 2-4: Process Pole Survey rows in exact original order
    invalid_records: list[dict[str, Any]] = []
    unknown_lamp_types: list[dict[str, Any]] = []
    empty_records: list[dict[str, Any]] = []
    non_led_records: list[dict[str, Any]] = []
    duplicate_records: list[dict[str, Any]] = []
    eligible_unique_leds: list[EligibleSurveyRecord] = []

    seen_led_keys: dict[str, int] = {}  # norm_key -> first seen excel row
    total_led_records = 0

    for row in survey_rows:
        excel_row = row.get("_excel_row")
        raw_pole = row.get(survey_mapping.pole_number_col)
        raw_arm = row.get(survey_mapping.arm_count_col)
        raw_lamp = row.get(survey_mapping.lamp_type_col)

        disp_pole = cell_to_display_str(raw_pole)
        disp_arm = cell_to_display_str(raw_arm)
        disp_lamp = cell_to_display_str(raw_lamp)
        norm_key = normalize_pole_key(raw_pole)

        if norm_key is None:
            invalid_records.append(
                {
                    "excel_row": excel_row,
                    "pole_number": disp_pole,
                    "arm_count": disp_arm,
                    "lamp_type": disp_lamp,
                    "reason": "Blank Pole Number",
                }
            )
            continue

        classification, matched_rule = led_classifier.classify(disp_lamp)
        if classification == "non_led":
            non_led_records.append(
                {
                    "excel_row": excel_row,
                    "pole_number": disp_pole,
                    "arm_count": disp_arm,
                    "lamp_type": disp_lamp,
                    "matched_rule": matched_rule,
                }
            )
            continue

        if classification == "empty":
            empty_records.append(
                {
                    "excel_row": excel_row,
                    "pole_number": disp_pole,
                    "arm_count": disp_arm,
                    "lamp_type": disp_lamp or "(blank)",
                    "matched_rule": matched_rule,
                    "reason": "Classified as Empty (hyphen/blank/empty rule)",
                }
            )
            continue

        if classification == "unknown":
            unknown_lamp_types.append(
                {
                    "excel_row": excel_row,
                    "pole_number": disp_pole,
                    "arm_count": disp_arm,
                    "lamp_type": disp_lamp or "(blank)",
                    "reason": "Unrecognized lamp type (not classified as LED without confirmation)",
                }
            )
            continue

        # Eligible LED record
        total_led_records += 1

        if norm_key in seen_led_keys:
            duplicate_records.append(
                {
                    "excel_row": excel_row,
                    "pole_number": disp_pole,
                    "normalized_pole_key": norm_key,
                    "arm_count": disp_arm,
                    "lamp_type": disp_lamp,
                    "first_seen_row": seen_led_keys[norm_key],
                    "reason": f"Duplicate Pole Number in Pole Survey (first seen at row {seen_led_keys[norm_key]})",
                }
            )
            continue

        seen_led_keys[norm_key] = excel_row
        arm_l_number = parse_arm_count_to_l_number(raw_arm)
        eligible_unique_leds.append(
            EligibleSurveyRecord(
                excel_row=excel_row,
                original_pole_number=disp_pole,
                normalized_pole_key=norm_key,
                arm_count=disp_arm,
                lamp_type=disp_lamp,
                l_sequence=arm_l_number,
                raw_record=row,
            )
        )

    # Step 5-7: Compare against existing Lamp Installation records without resetting L-numbers
    skipped_existing_records: list[dict[str, Any]] = []
    newly_added_records: list[dict[str, Any]] = []

    # Detect key target columns in Lamp Installation workbook
    target_lamp_id_col: str | None = None
    target_lights_empty_col: str | None = None
    target_arm_col: str | None = None

    for h in lamp_headers:
        norm_h = normalize_header_name(h)
        if target_lamp_id_col is None and (
            norm_h in {"lamp id", "led id", "lamp_id", "led_id", "led lamp id", "lamp id (new)", "lamp id (new detail's)"}
            or norm_h.endswith("lamp id")
            or norm_h.endswith("led id")
        ):
            target_lamp_id_col = h

        if target_lights_empty_col is None and (
            norm_h in {
                "light's /empty pole",
                "lights /empty pole",
                "light's / empty pole",
                "lights / empty pole",
                "lights/empty pole",
                "light/empty pole",
                "light's/empty pole",
                "light / empty pole",
                "light's /empty",
                "lights /empty",
                "light / empty",
                "light/empty",
                "empty pole",
            }
            or ("light" in norm_h and "empty" in norm_h)
        ):
            target_lights_empty_col = h

        if target_arm_col is None and (
            norm_h in {"old arm status", "arm status", "arm count", "bracket count"}
            or "arm" in norm_h
        ):
            target_arm_col = h

    if lamp_mapping.arm_count_col and lamp_mapping.arm_count_col in lamp_headers:
        target_arm_col = lamp_mapping.arm_count_col

    for item in eligible_unique_leds:
        generated_pole = f"{item.original_pole_number}-L{item.l_sequence}"
        if item.normalized_pole_key in existing_pole_keys:
            skipped_existing_records.append(
                {
                    "excel_row": item.excel_row,
                    "original_pole_number": item.original_pole_number,
                    "l_sequence": item.l_sequence,
                    "arm_count": item.arm_count,
                    "lamp_type": item.lamp_type,
                    "status": "Skipped (Already Exists in Lamp Installation)",
                }
            )
            continue

        # Construct mapped row values for Lamp Installation target workbook:
        # 1. Pole Number cell receives generated pole (e.g. GBA-SNL-W69-P2250-SP120-L2)
        # 2. Lamp ID / LED ID cell also receives generated pole for newly added survey records
        # 3. Light's / Empty Pole cell receives the survey LED lamp type (e.g. LED)
        # 4. Old Arm Status cell receives the arm count (e.g. 1, 2)
        effective_lamp_type = (
            item.raw_record.get(survey_mapping.lamp_type_col)
            if survey_mapping.lamp_type_col
            else item.lamp_type
        ) or item.lamp_type or "LED"

        mapped_values: dict[str, Any] = {
            lamp_mapping.pole_number_col: generated_pole,
        }

        # Lamp ID / LED ID column receives generated_pole with -L1/-L2
        if target_lamp_id_col:
            mapped_values[target_lamp_id_col] = generated_pole

        # Arm Count / Old Arm Status receives survey arm count
        if target_arm_col:
            raw_arm_val = (
                item.raw_record.get(survey_mapping.arm_count_col)
                if survey_mapping.arm_count_col
                else item.arm_count
            )
            mapped_values[target_arm_col] = raw_arm_val or item.arm_count

        # Light's / Empty Pole receives survey lamp type (LED)
        if target_lights_empty_col:
            mapped_values[target_lights_empty_col] = effective_lamp_type

        # If lamp_mapping.lamp_type_col was explicitly mapped and is not Lamp ID, populate it
        if (
            lamp_mapping.lamp_type_col
            and lamp_mapping.lamp_type_col in lamp_headers
            and lamp_mapping.lamp_type_col != target_lamp_id_col
            and "id" not in normalize_header_name(lamp_mapping.lamp_type_col)
        ):
            mapped_values[lamp_mapping.lamp_type_col] = effective_lamp_type

        for survey_col, lamp_col in survey_mapping.extra_mappings.items():
            if survey_col in survey_headers and lamp_col in lamp_headers and lamp_col not in mapped_values:
                mapped_values[lamp_col] = item.raw_record.get(survey_col)

        newly_added_records.append(
            {
                "survey_excel_row": item.excel_row,
                "original_pole_number": item.original_pole_number,
                "generated_pole_number": generated_pole,
                "l_sequence": item.l_sequence,
                "arm_count": item.arm_count,
                "lamp_type": item.lamp_type,
                "mapped_values": {k: cell_to_display_str(v) for k, v in mapped_values.items()},
                "_raw_mapped_values": mapped_values,
            }
        )

    if unknown_lamp_types:
        warnings.append(
            f"{len(unknown_lamp_types)} record(s) had unknown lamp types and were excluded pending confirmation."
        )

    summary = {
        "total_lamp_installation_records": len(lamp_rows),
        "total_survey_records": len(survey_rows),
        "total_led_records": total_led_records,
        "unique_eligible_led_records": len(eligible_unique_leds),
        "existing_records": len(skipped_existing_records),
        "added_records": len(newly_added_records),
        "duplicate_records": len(duplicate_records),
        "invalid_records": len(invalid_records),
        "unknown_lamp_type_records": len(unknown_lamp_types),
        "empty_records": len(empty_records),
        "non_led_records": len(non_led_records),
        "final_merged_records": len(lamp_rows) + len(newly_added_records),
    }

    return ReconciliationResult(
        summary=summary,
        existing_lamp_records=existing_lamp_records,
        newly_added_records=newly_added_records,
        skipped_existing_records=skipped_existing_records,
        duplicate_records=duplicate_records,
        invalid_records=invalid_records,
        unknown_lamp_types=unknown_lamp_types,
        empty_records=empty_records,
        non_led_records=non_led_records,
        warnings=warnings,
    )

