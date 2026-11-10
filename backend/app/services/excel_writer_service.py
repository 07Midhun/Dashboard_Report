from copy import copy
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from app.services.excel_reader_service import _load_raw_grid


def _copy_cell_style(src_cell, dst_cell) -> None:
    if src_cell.has_style:
        dst_cell.font = copy(src_cell.font)
        dst_cell.fill = copy(src_cell.fill)
        dst_cell.border = copy(src_cell.border)
        dst_cell.alignment = copy(src_cell.alignment)
        dst_cell.number_format = src_cell.number_format
        dst_cell.protection = copy(src_cell.protection)


def _convert_xls_to_xlsx(xls_path: Path, xlsx_out_path: Path) -> None:
    """
    Safe fallback conversion for legacy .xls templates into .xlsx when needed.
    """
    sheet_names, _, _, _ = _load_raw_grid(xls_path)
    import xlrd  # type: ignore

    book = xlrd.open_workbook(str(xls_path))
    wb = openpyxl.Workbook()
    # Remove default sheet after creating actual sheets
    default_ws = wb.active
    for sname in sheet_names:
        xs = book.sheet_by_name(sname)
        ws = wb.create_sheet(title=sname[:31])
        for r in range(xs.nrows):
            for c in range(xs.ncols):
                ws.cell(row=r + 1, column=c + 1, value=xs.cell_value(r, c))
    wb.remove(default_ws)
    wb.save(xlsx_out_path)


def _shift_merged_cells_down(ws: Worksheet, insert_at_row: int, amount: int) -> None:
    if amount <= 0:
        return
    ranges_to_shift = [rng for rng in list(ws.merged_cells.ranges) if rng.min_row >= insert_at_row]
    for rng in ranges_to_shift:
        ws.unmerge_cells(str(rng))
        ws.merge_cells(
            start_row=rng.min_row + amount,
            start_column=rng.min_col,
            end_row=rng.max_row + amount,
            end_column=rng.max_col,
        )


def write_merged_workbook(
    *,
    master_path: Path,
    output_path: Path,
    sheet_name: str,
    header_row_index: int,
    header_col_map: dict[str, int],
    last_data_row_index: int,
    has_footer_rows: bool,
    newly_added_records: list[dict[str, Any]],
) -> list[str]:
    """
    Clone the original Lamp Installation master workbook and append newly added
    LED records while preserving sheets, styles, formulas, widths, heights,
    merged cells, freeze panes, filters, and print settings.
    """
    warnings: list[str] = []
    source_xlsx = master_path

    if master_path.suffix.lower() == ".xls":
        temp_converted = output_path.with_suffix(".converted.xlsx")
        _convert_xls_to_xlsx(master_path, temp_converted)
        source_xlsx = temp_converted
        warnings.append(
            "Master Lamp Installation file was legacy .xls and was converted to .xlsx; binary .xls styling could not be fully retained."
        )

    wb = openpyxl.load_workbook(source_xlsx, data_only=False)
    try:
        if sheet_name not in wb.sheetnames:
            raise ValueError(f"Target worksheet '{sheet_name}' not found in Lamp Installation workbook.")

        ws = wb[sheet_name]
        max_mapped_col = max(header_col_map.values(), default=ws.max_column)
        num_cols = max(max_mapped_col, len(header_col_map))

        # Determine template row for formatting inheritance
        has_data_template_row = last_data_row_index > header_row_index
        template_row = last_data_row_index if has_data_template_row else header_row_index
        # If template_row is merged across columns, step backward to find an unmerged data row
        merged_coords = {
            (r, c)
            for rng in ws.merged_cells.ranges
            for r in range(rng.min_row, rng.max_row + 1)
            for c in range(rng.min_col, rng.max_col + 1)
        }
        if has_data_template_row:
            for candidate in range(last_data_row_index, header_row_index, -1):
                if not any((candidate, c) in merged_coords for c in range(1, num_cols + 1)):
                    template_row = candidate
                    break

        insert_start_row = last_data_row_index + 1
        rows_to_add = len(newly_added_records)

        if rows_to_add > 0:
            if has_footer_rows:
                # Shift trailing summary/footer rows and merges downward safely
                _shift_merged_cells_down(ws, insert_start_row, rows_to_add)
                ws.insert_rows(insert_start_row, amount=rows_to_add)

            template_height = ws.row_dimensions[template_row].height if has_data_template_row else None

            for idx, record in enumerate(newly_added_records):
                target_row = insert_start_row + idx
                if template_height is not None:
                    ws.row_dimensions[target_row].height = template_height

                raw_values = record.get("_raw_mapped_values", {})

                for col_idx in range(1, num_cols + 1):
                    src_cell = ws.cell(row=template_row, column=col_idx)
                    dst_cell = ws.cell(row=target_row, column=col_idx)
                    if has_data_template_row:
                        _copy_cell_style(src_cell, dst_cell)
                    dst_cell.value = None

                # Populate ONLY explicitly mapped columns (including Pole Number cell with P004-L4)
                for col_name, col_idx in header_col_map.items():
                    if col_name in raw_values:
                        dst_cell = ws.cell(row=target_row, column=col_idx)
                        val = raw_values[col_name]
                        dst_cell.value = val

            # Extend auto-filter range if an auto-filter was attached to the data block
            if ws.auto_filter and ws.auto_filter.ref:
                try:
                    start_ref, end_ref = ws.auto_filter.ref.split(":")
                    end_col_letters = "".join(ch for ch in end_ref if ch.isalpha())
                    new_end_row = insert_start_row + rows_to_add - 1
                    ws.auto_filter.ref = f"{start_ref}:{end_col_letters}{new_end_row}"
                except Exception:
                    pass

        wb.save(output_path)
    finally:
        wb.close()
        if source_xlsx != master_path and source_xlsx.exists():
            source_xlsx.unlink(missing_ok=True)

    return warnings
