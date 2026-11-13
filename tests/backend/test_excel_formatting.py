from pathlib import Path
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from app.services.excel_reader_service import inspect_workbook
from app.services.excel_writer_service import write_merged_workbook
from app.services.reconciliation_engine import MappingSpec, reconcile_reports


def _build_master_lamp_workbook(path: Path, with_footer: bool = False) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Lamp Report"

    # Second unrelated sheet that must remain preserved intact
    cover = wb.create_sheet("Summary Cover")
    cover["A1"] = "BBMP EAST ZONE SUMMARY"
    cover["A1"].font = Font(name="Calibri", size=14, bold=True)

    # Title banner merged cells
    ws["A1"] = "SCHNELL ELECTRICAL ASSET REPORT"
    ws.merge_cells("A1:E1")
    ws["A1"].font = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
    ws["A1"].fill = PatternFill("solid", fgColor="075D6B")
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 28

    ws["A2"] = "Zone: CV Raman Nagar"
    ws.merge_cells("A2:E2")

    # Header row at row 4 (non-first row!)
    headers = ["Pole Number", "Arm Count", "Lamp Type", "Wattage", "Installed Date"]
    thin_side = Side(style="thin", color="CCCCCC")
    data_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

    for col_idx, text in enumerate(headers, start=1):
        cell = ws.cell(row=4, column=col_idx, value=text)
        cell.font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="0D7780")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = data_border
    ws.row_dimensions[4].height = 24

    # Existing styled data rows (rows 5 & 6)
    existing_data = [
        ("P001", 1, "LED 60W", 60, "2025-02-01"),
        ("P002", 2, "LED 90W", "=D5+30", "2025-02-02"),  # includes an Excel formula!
    ]
    for offset, row_vals in enumerate(existing_data):
        r = 5 + offset
        ws.row_dimensions[r].height = 21
        for c_idx, val in enumerate(row_vals, start=1):
            c = ws.cell(row=r, column=c_idx, value=val)
            c.font = Font(name="Segoe UI", size=10, color="173042")
            c.fill = PatternFill("solid", fgColor="F9FBFB")
            c.border = data_border
            c.alignment = Alignment(horizontal="left" if c_idx in (1, 3) else "center", vertical="center")
            if c_idx == 2:
                c.number_format = "0"

    if with_footer:
        ws.cell(row=7, column=1, value="Prepared By: Schnell Field Team")
        ws.merge_cells("A7:C7")

    # Column widths, freeze panes, auto filter, print settings
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 14
    ws.column_dimensions["C"].width = 24
    ws.column_dimensions["D"].width = 14
    ws.column_dimensions["E"].width = 18
    ws.freeze_panes = "A5"
    ws.auto_filter.ref = "A4:E6"
    ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE

    wb.save(path)
    wb.close()


def _build_survey_workbook(path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Field Survey"
    ws.append(["Pole No", "Number of Arms", "Type of Lamp"])
    ws.append(["P001", 1, "LED 60W"])
    ws.append(["P002", 2, "LED 90W"])
    ws.append(["P003", 1, "LED 40W"])
    ws.append(["P004", 2, "LED Street Light"])
    wb.save(path)
    wb.close()


def test_case_11_preserves_original_excel_formatting_and_writes_in_same_pole_cell(tmp_path: Path):
    master_path = tmp_path / "lamp_master.xlsx"
    survey_path = tmp_path / "pole_survey.xlsx"
    merged_path = tmp_path / "merged_output.xlsx"

    _build_master_lamp_workbook(master_path, with_footer=True)
    _build_survey_workbook(survey_path)

    l_insp, l_rows = inspect_workbook(master_path)
    p_insp, p_rows = inspect_workbook(survey_path)

    assert l_insp.active_sheet == "Lamp Report"
    assert l_insp.header_row_index == 4
    assert l_insp.has_footer_rows is True

    result = reconcile_reports(
        lamp_headers=l_insp.headers,
        lamp_rows=l_rows,
        lamp_mapping=MappingSpec(
            pole_number_col="Pole Number",
            arm_count_col="Arm Count",
            lamp_type_col="Lamp Type",
        ),
        survey_headers=p_insp.headers,
        survey_rows=p_rows,
        survey_mapping=MappingSpec(
            pole_number_col="Pole No",
            arm_count_col="Number of Arms",
            lamp_type_col="Type of Lamp",
        ),
    )
    assert [r["generated_pole_number"] for r in result.newly_added_records] == [
        "P003-L1",
        "P004-L2",
    ]

    write_merged_workbook(
        master_path=master_path,
        output_path=merged_path,
        sheet_name=l_insp.active_sheet,
        header_row_index=l_insp.header_row_index,
        header_col_map=l_insp.header_col_map,
        last_data_row_index=l_insp.last_data_row_index,
        has_footer_rows=l_insp.has_footer_rows,
        newly_added_records=result.newly_added_records,
    )

    out_wb = openpyxl.load_workbook(merged_path, data_only=False)
    try:
        assert out_wb.sheetnames == ["Lamp Report", "Summary Cover"]
        assert out_wb["Summary Cover"]["A1"].value == "BBMP EAST ZONE SUMMARY"

        ws = out_wb["Lamp Report"]
        # Header & column structure unchanged (no extra L-number column!)
        assert [ws.cell(4, c).value for c in range(1, 6)] == [
            "Pole Number",
            "Arm Count",
            "Lamp Type",
            "Wattage",
            "Installed Date",
        ]
        # Existing rows & formula intact
        assert ws["A5"].value == "P001"
        assert ws["D6"].value == "=D5+30"

        # Newly added rows written directly in Column A (Pole Number) with inherited styles
        assert ws["A7"].value == "P003-L1"
        assert ws["B7"].value == 1
        assert ws["C7"].value == "LED 40W"
        assert ws["D7"].value is None  # unmapped column left blank
        assert ws["E7"].value is None

        assert ws["A8"].value == "P004-L2"
        assert ws["B8"].value == 2
        assert ws["C8"].value == "LED Street Light"

        # Footer row shifted cleanly from row 7 to row 9
        assert ws["A9"].value == "Prepared By: Schnell Field Team"
        assert "A9:C9" in {str(rng) for rng in ws.merged_cells.ranges}

        # Styles, widths, row heights, freeze panes, print setup preserved
        assert ws["A7"].font.name == "Segoe UI"
        assert ws["A7"].font.size == 10
        assert ws["A7"].fill.fgColor.rgb.endswith("F9FBFB")
        assert ws["A7"].border.left.style == "thin"
        assert ws["B7"].number_format == "0"
        assert ws.row_dimensions[7].height == 21
        assert ws.column_dimensions["A"].width == 22
        assert ws.freeze_panes == "A5"
        assert ws.page_setup.orientation == ws.ORIENTATION_LANDSCAPE
        assert ws.auto_filter.ref == "A4:E8"
    finally:
        out_wb.close()


def test_large_batch_cached_style_copy_preserves_independent_row_styles(tmp_path: Path):
    master_path = tmp_path / "lamp_master_large.xlsx"
    merged_path = tmp_path / "merged_large.xlsx"

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Lamp Report"
    headers = ["Pole Number", "Arm Count", "Lamp Type", "Notes"]
    for c_idx, text in enumerate(headers, start=1):
        ws.cell(row=1, column=c_idx, value=text)

    ws.row_dimensions[2].height = 20
    ws["A2"] = "P001"
    ws["A2"].font = Font(name="Segoe UI", size=10, bold=True)
    ws["B2"] = 1
    ws["B2"].number_format = "0"
    ws["C2"] = "LED 60W"
    ws["C2"].fill = PatternFill("solid", fgColor="F9FBFB")
    # Column D intentionally has no custom style on template row
    ws["D2"] = "Existing note"
    wb.save(master_path)
    wb.close()

    records = [
        {
            "generated_pole_number": f"P{100 + i}-L{i}",
            "_raw_mapped_values": {
                "Pole Number": f"P{100 + i}-L{i}",
                "Arm Count": 2,
                "Lamp Type": "LED 90W",
            },
        }
        for i in range(1, 151)
    ]

    write_merged_workbook(
        master_path=master_path,
        output_path=merged_path,
        sheet_name="Lamp Report",
        header_row_index=1,
        header_col_map={h: idx for idx, h in enumerate(headers, start=1)},
        last_data_row_index=2,
        has_footer_rows=False,
        newly_added_records=records,
    )

    out_wb = openpyxl.load_workbook(merged_path, data_only=False)
    try:
        out_ws = out_wb["Lamp Report"]
        assert out_ws["A3"].value == "P101-L1"
        assert out_ws["A152"].value == "P250-L150"
        assert out_ws["D3"].value is None
        assert out_ws["A3"]._style is not out_ws["A4"]._style
        assert out_ws["A152"].font.name == "Segoe UI"
        assert out_ws["A152"].font.bold is True
        assert out_ws["B152"].number_format == "0"
        assert out_ws["C152"].fill.fgColor.rgb.endswith("F9FBFB")
        assert out_ws["D152"].has_style is False
        assert out_ws.row_dimensions[152].height == 20
    finally:
        out_wb.close()


