from dataclasses import dataclass, field
import hashlib
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
import openpyxl

from app.utilities.pole_normalizer import cell_to_display_str, normalize_header_name


try:
    import xlrd  # type: ignore
except ImportError:
    xlrd = None


POLE_ALIASES = {
    "pole number",
    "pole no",
    "pole no.",
    "pole_no",
    "pole_number",
    "pole id",
    "pole_id",
    "pole code",
    "pole",
    "new pole no",
    "existing pole no",
}

ARM_ALIASES = {
    "arm count",
    "arm_count",
    "arms",
    "no of arms",
    "no. of arms",
    "number of arms",
    "arm",
    "arm type",
    "bracket count",
}

LAMP_ALIASES = {
    "lamp type",
    "lamp_type",
    "type of lamp",
    "lamp",
    "light type",
    "fitting type",
    "luminaire type",
    "fixture type",
}

FOOTER_KEYWORDS = {"total", "grand total", "sub total", "subtotal", "prepared by", "verified by", "approved by", "summary"}


@dataclass
class SheetInspection:
    sheet_names: list[str]
    active_sheet: str
    header_row_index: int  # 1-based Excel row index
    headers: list[str]  # positional headers aligned with column indices (1-based)
    header_col_map: dict[str, int]  # header name -> 1-based column index
    header_signature_hash: str
    total_data_rows: int
    last_data_row_index: int  # 1-based Excel row index of last actual data row
    has_footer_rows: bool
    suggested_mapping: dict[str, str | None]
    needs_mapping_confirmation: bool
    warnings: list[str] = field(default_factory=list)


def compute_header_signature(headers: list[str]) -> str:
    norm = "|".join(normalize_header_name(h) for h in headers if normalize_header_name(h))
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def _detect_header_row_from_rows(rows: list[list[Any]]) -> tuple[int, list[str]]:
    """
    Scan first 25 rows to locate the header row (1-based).
    Scores rows by matching known electrical asset column names and text density.
    """
    best_row_idx = 1
    best_score = -1.0
    max_scan = min(len(rows), 25)

    for idx in range(max_scan):
        row = rows[idx]
        non_empty = [cell_to_display_str(v) for v in row if cell_to_display_str(v)]
        if len(non_empty) < 2:
            continue
        text_count = sum(1 for v in row if isinstance(v, str) and v.strip())
        alias_hits = 0
        for val in non_empty:
            norm = normalize_header_name(val)
            if norm in POLE_ALIASES or norm in ARM_ALIASES or norm in LAMP_ALIASES:
                alias_hits += 1
        # Strongly prioritize rows matching known asset column names
        score = alias_hits * 10.0 + len(non_empty) * 1.5 + text_count * 0.5
        if score > best_score:
            best_score = score
            best_row_idx = idx + 1

    raw_header_row = rows[best_row_idx - 1] if rows else []
    headers: list[str] = []
    seen_counts: dict[str, int] = {}
    for col_idx, val in enumerate(raw_header_row, start=1):
        disp = cell_to_display_str(val)
        if not disp:
            headers.append(f"Column_{col_idx}")
        else:
            key = disp
            if key in seen_counts:
                seen_counts[key] += 1
                headers.append(f"{disp} ({seen_counts[key]})")
            else:
                seen_counts[key] = 1
                headers.append(disp)

    # Trim trailing empty synthetic headers
    while headers and headers[-1].startswith("Column_") and (
        len(raw_header_row) < len(headers) or not cell_to_display_str(raw_header_row[len(headers) - 1])
    ):
        headers.pop()

    return best_row_idx, headers


def suggest_column_mapping(headers: list[str]) -> tuple[dict[str, str | None], bool]:
    """
    Suggest pole_number, arm_count, lamp_type column names from detected headers.
    Returns (mapping_dict, needs_confirmation).
    """
    mapping: dict[str, str | None] = {
        "pole_number": None,
        "arm_count": None,
        "lamp_type": None,
    }
    ambiguous = False

    def find_match(aliases: set[str], fuzzy_tokens: tuple[str, ...]) -> str | None:
        nonlocal ambiguous
        exact_hits = [h for h in headers if normalize_header_name(h) in aliases]
        if len(exact_hits) == 1:
            return exact_hits[0]
        if len(exact_hits) > 1:
            ambiguous = True
            return exact_hits[0]

        fuzzy_hits = [
            h
            for h in headers
            if any(tok in normalize_header_name(h) for tok in fuzzy_tokens)
        ]
        if len(fuzzy_hits) == 1:
            ambiguous = True  # Fuzzy matches should be confirmed by admin
            return fuzzy_hits[0]
        if len(fuzzy_hits) > 1:
            ambiguous = True
            return fuzzy_hits[0]
        return None

    mapping["pole_number"] = find_match(POLE_ALIASES, ("pole",))
    mapping["arm_count"] = find_match(ARM_ALIASES, ("arm",))
    mapping["lamp_type"] = find_match(LAMP_ALIASES, ("lamp", "luminaire", "fixture"))

    missing_required = any(mapping[k] is None for k in ("pole_number", "arm_count", "lamp_type"))
    return mapping, (missing_required or ambiguous)


def _is_footer_row(row_values: list[Any]) -> bool:
    texts = [cell_to_display_str(v).lower() for v in row_values if cell_to_display_str(v)]
    if not texts:
        return False
    joined = " ".join(texts[:3])
    return any(kw == t or t.startswith(kw + ":") or kw in joined for t in texts[:2] for kw in FOOTER_KEYWORDS)


def _load_raw_grid(
    file_path: Path,
    sheet_name: str | None = None,
) -> tuple[list[str], str, list[list[Any]], list[str]]:
    ext = file_path.suffix.lower()
    warnings: list[str] = []

    if ext == ".xlsx":
        try:
            wb_val = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to read Excel workbook: {exc}",
            ) from exc

        try:
            sheet_names = list(wb_val.sheetnames)
            if not sheet_names:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="The uploaded Excel workbook contains no worksheets.",
                )

            selected_sheet = sheet_name if sheet_name in sheet_names else None
            if selected_sheet is None:
                # Choose best visible sheet by checking header match
                best_sheet = sheet_names[0]
                best_sheet_score = -1.0
                for sname in sheet_names:
                    ws = wb_val[sname]
                    if getattr(ws, "sheet_state", "visible") != "visible":
                        continue
                    sample_rows = [
                        list(r)
                        for _, r in zip(range(25), ws.iter_rows(values_only=True))
                    ]
                    _, cand_headers = _detect_header_row_from_rows(sample_rows)
                    m, _ = suggest_column_mapping(cand_headers)
                    hits = sum(1 for v in m.values() if v is not None)
                    score = hits * 100.0 + len(cand_headers)
                    if score > best_sheet_score:
                        best_sheet_score = score
                        best_sheet = sname
                selected_sheet = best_sheet

            ws = wb_val[selected_sheet]
            grid = [list(row) for row in ws.iter_rows(values_only=True)]
        finally:
            wb_val.close()

        # Quick check for formulas / external links / VBA warnings
        try:
            wb_meta = openpyxl.load_workbook(file_path, data_only=False, read_only=True)
            try:
                if getattr(wb_meta, "vba_archive", None) is not None:
                    warnings.append("Workbook contains VBA macros which may not be preserved cleanly.")
                ws_meta = wb_meta[selected_sheet]
                formula_count = 0
                for _, row in zip(range(200), ws_meta.iter_rows(values_only=True)):
                    for val in row:
                        if isinstance(val, str) and val.startswith("="):
                            formula_count += 1
                if formula_count > 0:
                    warnings.append(
                        f"Worksheet '{selected_sheet}' contains {formula_count}+ Excel formulas; existing formulas will be preserved in Merged Reports."
                    )
            finally:
                wb_meta.close()
        except Exception:
            pass

        return sheet_names, selected_sheet, grid, warnings

    if ext == ".xls":
        if xlrd is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Legacy .xls support requires 'xlrd'. Please install xlrd or convert the workbook to .xlsx.",
            )
        try:
            book = xlrd.open_workbook(str(file_path))
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to read legacy .xls workbook: {exc}",
            ) from exc

        sheet_names = book.sheet_names()
        if not sheet_names:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded .xls workbook contains no worksheets.",
            )
        selected_sheet = sheet_name if sheet_name in sheet_names else sheet_names[0]
        sheet = book.sheet_by_name(selected_sheet)
        grid = [
            [sheet.cell_value(r, c) for c in range(sheet.ncols)]
            for r in range(sheet.nrows)
        ]
        warnings.append(
            "Legacy .xls format detected. Binary .xls styling and print settings cannot be fully preserved; converting to .xlsx is recommended."
        )
        return sheet_names, selected_sheet, grid, warnings

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unsupported workbook extension.",
    )


def inspect_workbook(
    file_path: Path,
    *,
    sheet_name: str | None = None,
    header_row_index: int | None = None,
) -> tuple[SheetInspection, list[dict[str, Any]]]:
    """
    Inspect workbook structure and return (SheetInspection, extracted_row_records).
    Each extracted record dict contains '_excel_row' plus values keyed by exact header names.
    """
    sheet_names, selected_sheet, grid, warnings = _load_raw_grid(file_path, sheet_name=sheet_name)
    if not grid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Worksheet '{selected_sheet}' is empty.",
        )

    detected_row_idx, headers = _detect_header_row_from_rows(grid)
    if header_row_index is not None and 1 <= header_row_index <= len(grid):
        detected_row_idx = header_row_index
        # Re-extract headers at explicit row
        _, headers = _detect_header_row_from_rows([grid[header_row_index - 1]])
        # Fix row index back since _detect_header_row_from_rows saw a 1-row slice
        detected_row_idx = header_row_index

    if not headers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not detect column headers in worksheet '{selected_sheet}'.",
        )

    header_col_map = {h: idx + 1 for idx, h in enumerate(headers)}
    sig_hash = compute_header_signature(headers)
    suggested_mapping, needs_confirmation = suggest_column_mapping(headers)

    records: list[dict[str, Any]] = []
    last_data_row = detected_row_idx
    has_footer = False

    raw_data_slice = grid[detected_row_idx:]
    # Trim completely blank trailing rows first
    while raw_data_slice and all(cell_to_display_str(v) == "" for v in raw_data_slice[-1]):
        raw_data_slice.pop()

    # Check if trailing non-empty rows look like summary/footer rows
    trailing_footer_count = 0
    while raw_data_slice and _is_footer_row(raw_data_slice[-1]):
        has_footer = True
        trailing_footer_count += 1
        raw_data_slice.pop()

    if trailing_footer_count > 0:
        warnings.append(
            f"Detected {trailing_footer_count} trailing summary/footer row(s) below data table; new records will be inserted above the footer."
        )

    for offset, row_vals in enumerate(raw_data_slice, start=1):
        excel_row = detected_row_idx + offset
        if all(cell_to_display_str(v) == "" for v in row_vals):
            continue
        row_dict: dict[str, Any] = {"_excel_row": excel_row}
        for col_idx, header in enumerate(headers):
            val = row_vals[col_idx] if col_idx < len(row_vals) else None
            row_dict[header] = val
        records.append(row_dict)
        last_data_row = excel_row

    inspection = SheetInspection(
        sheet_names=sheet_names,
        active_sheet=selected_sheet,
        header_row_index=detected_row_idx,
        headers=headers,
        header_col_map=header_col_map,
        header_signature_hash=sig_hash,
        total_data_rows=len(records),
        last_data_row_index=last_data_row,
        has_footer_rows=has_footer,
        suggested_mapping=suggested_mapping,
        needs_mapping_confirmation=needs_confirmation,
        warnings=warnings,
    )
    return inspection, records


def preview_workbook(
    file_path: Path,
    *,
    sheet_name: str | None = None,
    header_row_index: int | None = None,
    search: str | None = None,
    filter_column: str | None = None,
    filter_value: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    inspection, records = inspect_workbook(
        file_path, sheet_name=sheet_name, header_row_index=header_row_index
    )

    filtered = records
    if filter_column and filter_value and filter_column in inspection.headers:
        fv = filter_value.strip().lower()
        filtered = [
            r for r in filtered if fv in cell_to_display_str(r.get(filter_column)).lower()
        ]

    if search and search.strip():
        q = search.strip().lower()
        filtered = [
            r
            for r in filtered
            if any(q in cell_to_display_str(r.get(col)).lower() for col in inspection.headers)
        ]

    total = len(filtered)
    start = max((page - 1) * page_size, 0)
    end = start + page_size
    page_rows = []
    for r in filtered[start:end]:
        serializable = {"_excel_row": r["_excel_row"]}
        for col in inspection.headers:
            serializable[col] = cell_to_display_str(r.get(col))
        page_rows.append(serializable)

    return {
        "sheets": inspection.sheet_names,
        "active_sheet": inspection.active_sheet,
        "header_row_index": inspection.header_row_index,
        "columns": inspection.headers,
        "header_signature_hash": inspection.header_signature_hash,
        "suggested_mapping": inspection.suggested_mapping,
        "needs_mapping_confirmation": inspection.needs_mapping_confirmation,
        "warnings": inspection.warnings,
        "total_rows": total,
        "page": page,
        "page_size": page_size,
        "rows": page_rows,
    }

