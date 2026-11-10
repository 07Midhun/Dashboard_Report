import io
import openpyxl


def _make_xlsx_bytes(headers: list[str], rows: list[list]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    wb.close()
    return buf.getvalue()


def _get_bbmp_zone(client, headers, zone_name: str):
    tree = client.get("/api/hierarchy/tree", headers=headers).json()
    cust = next(c for c in tree if c["customer_name"] == "Bangalore (BBMP)")
    for reg in cust["regions"]:
        for z in reg["zones"]:
            if z["zone_name"] == zone_name:
                return cust["id"], reg["id"], z["id"]
    raise AssertionError(f"Zone {zone_name} not found")


def test_case_9_10_12_full_workflow_zone_isolation_stale_and_customer_rbac(client, admin_headers, customer_headers):
    cust_id, reg_id, zone_a_id = _get_bbmp_zone(client, admin_headers, "CV Raman Nagar")
    _, _, zone_b_id = _get_bbmp_zone(client, admin_headers, "Hebbal")

    # 1. Customer cannot access admin endpoints or upload/modify/delete/publish
    assert client.get("/api/dashboard/admin", headers=customer_headers).status_code == 403
    assert client.get("/api/users", headers=customer_headers).status_code == 403
    assert client.get("/api/audit-logs", headers=customer_headers).status_code == 403
    assert (
        client.post(
            "/api/customers",
            json={"customer_name": "Unauthorized Corp"},
            headers=customer_headers,
        ).status_code
        == 403
    )

    survey_bytes = _make_xlsx_bytes(
        ["Pole No", "Number of Arms", "Type of Lamp"],
        [
            ["P001", 1, "LED 60W"],
            ["P002", 1, "LED 60W"],
            ["P003", 2, "LED 90W"],
        ],
    )
    lamp_bytes = _make_xlsx_bytes(
        ["Pole Number", "Arm Count", "Lamp Type", "Remarks"],
        [
            ["P001", 1, "LED 60W", "Installed"],
            ["P002", 1, "LED 60W", "Installed"],
        ],
    )

    # Customer upload blocked with 403
    cust_upload = client.post(
        "/api/pole-survey/upload",
        data={"customer_id": cust_id, "region_id": reg_id, "zone_id": zone_a_id},
        files={"file": ("survey.xlsx", survey_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=customer_headers,
    )
    assert cust_upload.status_code == 403

    # 2. Admin uploads Pole Survey for Zone A only -> inspecting without Lamp Installation blocks generation (Case 9)
    up_survey_a = client.post(
        "/api/pole-survey/upload",
        data={"customer_id": cust_id, "region_id": reg_id, "zone_id": zone_a_id},
        files={"file": ("cv_survey.xlsx", survey_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=admin_headers,
    )
    assert up_survey_a.status_code == 201, up_survey_a.text

    inspect_missing = client.get(
        "/api/merged-reports/inspect",
        params={"customer_id": cust_id, "region_id": reg_id, "zone_id": zone_a_id},
        headers=admin_headers,
    )
    assert inspect_missing.status_code == 200
    assert inspect_missing.json()["blocking_error"] is not None
    assert "Lamp Installation" in inspect_missing.json()["blocking_error"]

    # Attempting to generate without Lamp Installation fails with 400
    gen_missing = client.post(
        "/api/merged-reports/generate",
        json={
            "customer_id": cust_id,
            "region_id": reg_id,
            "zone_id": zone_a_id,
            "pole_survey_mapping": {"pole_number_col": "Pole No", "arm_count_col": "Number of Arms", "lamp_type_col": "Type of Lamp"},
            "lamp_installation_mapping": {"pole_number_col": "Pole Number", "arm_count_col": "Arm Count", "lamp_type_col": "Lamp Type"},
        },
        headers=admin_headers,
    )
    assert gen_missing.status_code == 400

    # 3. Admin uploads Lamp Installation for Zone A + independent files for Zone B (Case 10)
    up_lamp_a = client.post(
        "/api/lamp-installation/upload",
        data={"customer_id": cust_id, "region_id": reg_id, "zone_id": zone_a_id},
        files={"file": ("cv_lamp.xlsx", lamp_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=admin_headers,
    )
    assert up_lamp_a.status_code == 201, up_lamp_a.text

    # Zone B has identical poles in survey, but NO P001/P002 in its own Lamp Installation (only P999)
    lamp_b_bytes = _make_xlsx_bytes(
        ["Pole Number", "Arm Count", "Lamp Type"],
        [["P999", 1, "LED 60W"]],
    )
    assert (
        client.post(
            "/api/pole-survey/upload",
            data={"customer_id": cust_id, "region_id": reg_id, "zone_id": zone_b_id},
            files={"file": ("hebbal_survey.xlsx", survey_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=admin_headers,
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/lamp-installation/upload",
            data={"customer_id": cust_id, "region_id": reg_id, "zone_id": zone_b_id},
            files={"file": ("hebbal_lamp.xlsx", lamp_b_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=admin_headers,
        ).status_code
        == 201
    )

    # 4. Generate Merged Report for Zone A -> only P003-L3 added
    gen_a = client.post(
        "/api/merged-reports/generate",
        json={
            "customer_id": cust_id,
            "region_id": reg_id,
            "zone_id": zone_a_id,
            "pole_survey_mapping": {"pole_number_col": "Pole No", "arm_count_col": "Number of Arms", "lamp_type_col": "Type of Lamp"},
            "lamp_installation_mapping": {"pole_number_col": "Pole Number", "arm_count_col": "Arm Count", "lamp_type_col": "Lamp Type"},
        },
        headers=admin_headers,
    )
    assert gen_a.status_code == 201, gen_a.text
    preview_a = gen_a.json()
    merged_a_id = preview_a["merged_report"]["id"]
    assert [r["generated_pole_number"] for r in preview_a["newly_added_records"]] == ["P003-L3"]

    # Generate Merged Report for Zone B -> independent! P001-L1, P002-L2, P003-L3 all added!
    gen_b = client.post(
        "/api/merged-reports/generate",
        json={
            "customer_id": cust_id,
            "region_id": reg_id,
            "zone_id": zone_b_id,
            "pole_survey_mapping": {"pole_number_col": "Pole No", "arm_count_col": "Number of Arms", "lamp_type_col": "Type of Lamp"},
            "lamp_installation_mapping": {"pole_number_col": "Pole Number", "arm_count_col": "Arm Count", "lamp_type_col": "Lamp Type"},
        },
        headers=admin_headers,
    )
    assert gen_b.status_code == 201
    assert [r["generated_pole_number"] for r in gen_b.json()["newly_added_records"]] == [
        "P001-L1",
        "P002-L2",
        "P003-L3",
    ]

    # 5. Customer CANNOT access Draft Merged Report or publish it
    assert client.get(f"/api/merged-reports/{merged_a_id}", headers=customer_headers).status_code == 403
    assert client.post(f"/api/merged-reports/{merged_a_id}/publish", headers=customer_headers).status_code == 403
    assert client.get("/api/merged-reports", headers=customer_headers).json() == []

    # 6. Admin publishes Zone A Merged Report -> Customer CAN now view & download it
    pub_a = client.post(f"/api/merged-reports/{merged_a_id}/publish", headers=admin_headers)
    assert pub_a.status_code == 200
    assert pub_a.json()["status"] == "published"

    cust_merged_list = client.get("/api/merged-reports", headers=customer_headers).json()
    assert len(cust_merged_list) == 1
    assert cust_merged_list[0]["id"] == merged_a_id

    dl_merged = client.get(f"/api/merged-reports/{merged_a_id}/download", headers=customer_headers)
    assert dl_merged.status_code == 200
    assert len(dl_merged.content) > 500

    # 7. Admin replaces Pole Survey for Zone A -> Merged Report A becomes outdated/stale
    survey_v2_bytes = _make_xlsx_bytes(
        ["Pole No", "Number of Arms", "Type of Lamp"],
        [
            ["P001", 1, "LED 60W"],
            ["P002", 1, "LED 60W"],
            ["P003", 2, "LED 90W"],
            ["P004", 2, "LED 90W"],
        ],
    )
    # Without replace_existing=true -> 409 conflict
    conflict_up = client.post(
        "/api/pole-survey/upload",
        data={"customer_id": cust_id, "region_id": reg_id, "zone_id": zone_a_id, "replace_existing": "false"},
        files={"file": ("cv_survey_v2.xlsx", survey_v2_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=admin_headers,
    )
    assert conflict_up.status_code == 409

    ok_replace = client.post(
        "/api/pole-survey/upload",
        data={"customer_id": cust_id, "region_id": reg_id, "zone_id": zone_a_id, "replace_existing": "true"},
        files={"file": ("cv_survey_v2.xlsx", survey_v2_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=admin_headers,
    )
    assert ok_replace.status_code == 201
    assert ok_replace.json()["version"] == 2

    mr_detail = client.get(f"/api/merged-reports/{merged_a_id}", headers=admin_headers).json()
    assert mr_detail["status"] == "outdated"
    assert mr_detail["is_outdated"] is True
    assert mr_detail["active_pole_survey_version"] == 2
    assert mr_detail["source_pole_survey_version"] == 1

