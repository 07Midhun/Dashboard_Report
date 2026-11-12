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


def _get_bbmp_east(client, headers):
    tree = client.get("/api/hierarchy/tree", headers=headers).json()
    cust = next(c for c in tree if c["customer_name"] == "Bangalore (BBMP)")
    east = next(r for r in cust["regions"] if r["region_name"] == "EAST")
    zone = east["zones"][0]
    ward = zone["wards"][0]
    return cust["id"], east["id"], zone["id"], ward["id"]


def test_hierarchy_delete_protection_and_inactive_visibility(client, admin_headers, customer_headers):
    bbmp_id, east_id, _, _ = _get_bbmp_east(client, admin_headers)

    # Create temporary Customer -> Region -> Zone -> Ward hierarchy
    c_resp = client.post(
        "/api/customers",
        json={"customer_name": "Temp Municipal Authority", "status": "active"},
        headers=admin_headers,
    )
    assert c_resp.status_code == 201, c_resp.text
    temp_cust_id = c_resp.json()["id"]

    r_resp = client.post(
        "/api/regions",
        json={"customer_id": temp_cust_id, "region_name": "Temp North", "status": "active"},
        headers=admin_headers,
    )
    assert r_resp.status_code == 201, r_resp.text
    temp_reg_id = r_resp.json()["id"]

    z_resp = client.post(
        "/api/zones",
        json={"region_id": temp_reg_id, "zone_name": "Temp Zone A", "zone_code": "TZA", "status": "active"},
        headers=admin_headers,
    )
    assert z_resp.status_code == 201, z_resp.text
    temp_zone_id = z_resp.json()["id"]

    w_resp = client.post(
        "/api/wards",
        json={
            "zone_id": temp_zone_id,
            "ward_name": "Temp Ward 10",
            "ward_number": "W10",
            "ward_code": "W10",
            "status": "active",
        },
        headers=admin_headers,
    )
    assert w_resp.status_code == 201, w_resp.text
    temp_ward_id = w_resp.json()["id"]

    # Duplicate ward_number or ward_code in the same zone -> 409 Conflict
    dup_w = client.post(
        "/api/wards",
        json={
            "zone_id": temp_zone_id,
            "ward_name": "Duplicate Ward 10",
            "ward_number": "w10",
            "ward_code": "W10_ALT",
            "status": "active",
        },
        headers=admin_headers,
    )
    assert dup_w.status_code == 409

    # Delete protection: Customer w/ Region -> 409; Region w/ Zone -> 409; Zone w/ Ward -> 409
    assert client.delete(f"/api/customers/{temp_cust_id}", headers=admin_headers).status_code == 409
    assert client.delete(f"/api/regions/{temp_reg_id}", headers=admin_headers).status_code == 409
    assert client.delete(f"/api/zones/{temp_zone_id}", headers=admin_headers).status_code == 409

    # Upload a Pole Survey into Ward W10 -> deleting Ward is blocked with 409
    survey_bytes = _make_xlsx_bytes(["Pole No", "Arms", "Lamp Type"], [["W001", 1, "LED 60W"]])
    up_resp = client.post(
        "/api/pole-survey/upload",
        data={
            "customer_id": temp_cust_id,
            "region_id": temp_reg_id,
            "zone_id": temp_zone_id,
            "ward_id": temp_ward_id,
        },
        files={
            "file": (
                "ward10_survey.xlsx",
                survey_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=admin_headers,
    )
    assert up_resp.status_code == 201, up_resp.text
    assert client.delete(f"/api/wards/{temp_ward_id}", headers=admin_headers).status_code == 409

    # Deactivating BBMP region hides it from customer viewer cleanly
    deact_resp = client.put(
        f"/api/regions/{east_id}",
        json={"status": "inactive"},
        headers=admin_headers,
    )
    assert deact_resp.status_code == 200
    cust_regions = client.get(f"/api/regions?customer_id={bbmp_id}", headers=customer_headers).json()
    assert all(r["id"] != east_id for r in cust_regions)

    # Reactivate BBMP region for subsequent tests
    assert (
        client.put(f"/api/regions/{east_id}", json={"status": "active"}, headers=admin_headers).status_code
        == 200
    )

    # Deactivating a ward hides it from customer /api/wards & tree
    _, _, _, w61_id = _get_bbmp_east(client, admin_headers)
    # Grab first BBMP EAST ward safely (CV Raman Nagar W108)
    assert client.put(f"/api/wards/{w61_id}", json={"status": "inactive"}, headers=admin_headers).status_code == 200
    cust_wards = client.get(f"/api/wards?region_id={east_id}", headers=customer_headers).json()
    assert all(w["id"] != w61_id for w in cust_wards)
    assert client.put(f"/api/wards/{w61_id}", json={"status": "active"}, headers=admin_headers).status_code == 200

    # Clean empty Customer -> Region -> Zone -> Ward creation and leaf-up deletion succeeds
    c2 = client.post("/api/customers", json={"customer_name": "Empty Utility"}, headers=admin_headers).json()
    r2 = client.post(
        "/api/regions",
        json={"customer_id": c2["id"], "region_name": "Empty Region"},
        headers=admin_headers,
    ).json()
    z2 = client.post(
        "/api/zones",
        json={"region_id": r2["id"], "zone_name": "Empty Zone", "zone_code": "EZ"},
        headers=admin_headers,
    ).json()
    w2 = client.post(
        "/api/wards",
        json={"zone_id": z2["id"], "ward_name": "Empty Ward", "ward_number": "W999"},
        headers=admin_headers,
    ).json()
    assert w2["ward_code"] == "W999"
    assert client.delete(f"/api/zones/{z2['id']}", headers=admin_headers).status_code == 409
    assert client.delete(f"/api/wards/{w2['id']}", headers=admin_headers).status_code == 200
    assert client.delete(f"/api/zones/{z2['id']}", headers=admin_headers).status_code == 200
    assert client.delete(f"/api/regions/{r2['id']}", headers=admin_headers).status_code == 200
    assert client.delete(f"/api/customers/{c2['id']}", headers=admin_headers).status_code == 200


def test_multitenant_isolation_saved_mapping_extra_columns_and_published_version_pinning(
    client, admin_headers, customer_headers
):
    # Create isolated Customer B hierarchy with Ward W01
    cust_b = client.post(
        "/api/customers",
        json={"customer_name": "Mysore Corporation", "status": "active"},
        headers=admin_headers,
    ).json()
    reg_b = client.post(
        "/api/regions",
        json={"customer_id": cust_b["id"], "region_name": "Mysore South", "status": "active"},
        headers=admin_headers,
    ).json()
    zone_b = client.post(
        "/api/zones",
        json={"region_id": reg_b["id"], "zone_name": "Kuvempunagar", "zone_code": "KVN", "status": "active"},
        headers=admin_headers,
    ).json()
    ward_b = client.post(
        "/api/wards",
        json={
            "zone_id": zone_b["id"],
            "ward_name": "Kuvempunagar Central",
            "ward_number": "W01",
            "ward_code": "W01",
            "status": "active",
        },
        headers=admin_headers,
    ).json()

    # Upload custom-header workbooks for Mysore -> test extra_mappings & blank unmapped column preservation
    survey_v1 = _make_xlsx_bytes(
        ["Survey Pole", "Brackets", "Fixture Spec", "Street Sector"],
        [
            ["M001", 1, "LED 60W", "Sector 1"],
            ["M002", 2, "LED 90W", "Sector 2"],
        ],
    )
    lamp_v1 = _make_xlsx_bytes(
        ["Asset Pole", "Arm Qty", "Fitting Model", "Ward Road", "Unmapped Col"],
        [["M001", 1, "LED 60W", "Main Rd", "Keep Existing"]],
    )

    ps_up = client.post(
        "/api/pole-survey/upload",
        data={
            "customer_id": cust_b["id"],
            "region_id": reg_b["id"],
            "zone_id": zone_b["id"],
            "ward_id": ward_b["id"],
        },
        files={
            "file": (
                "mysore_survey.xlsx",
                survey_v1,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=admin_headers,
    )
    assert ps_up.status_code == 201
    ps_id = ps_up.json()["id"]

    li_up = client.post(
        "/api/lamp-installation/upload",
        data={
            "customer_id": cust_b["id"],
            "region_id": reg_b["id"],
            "zone_id": zone_b["id"],
            "ward_id": ward_b["id"],
        },
        files={
            "file": (
                "mysore_lamp.xlsx",
                lamp_v1,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=admin_headers,
    )
    assert li_up.status_code == 201

    gen_v1 = client.post(
        "/api/merged-reports/generate",
        json={
            "customer_id": cust_b["id"],
            "region_id": reg_b["id"],
            "zone_id": zone_b["id"],
            "ward_id": ward_b["id"],
            "pole_survey_mapping": {
                "pole_number_col": "Survey Pole",
                "arm_count_col": "Brackets",
                "lamp_type_col": "Fixture Spec",
                "extra_mappings": {"Street Sector": "Ward Road"},
            },
            "lamp_installation_mapping": {
                "pole_number_col": "Asset Pole",
                "arm_count_col": "Arm Qty",
                "lamp_type_col": "Fitting Model",
            },
            "save_mapping": True,
        },
        headers=admin_headers,
    )
    assert gen_v1.status_code == 201, gen_v1.text
    merged_id = gen_v1.json()["merged_report"]["id"]
    assert gen_v1.json()["merged_report"]["ward_id"] == ward_b["id"]
    assert [r["generated_pole_number"] for r in gen_v1.json()["newly_added_records"]] == ["M002-L2"]

    # Download v1 workbook -> verify Content-Type + extra mapping copied Sector 2 and Unmapped Col stayed blank
    ps_dl = client.get(f"/api/pole-survey/{ps_id}/download", headers=admin_headers)
    assert ps_dl.status_code == 200
    assert "spreadsheetml.sheet" in ps_dl.headers["content-type"]

    dl_v1 = client.get(f"/api/merged-reports/{merged_id}/download", headers=admin_headers)
    assert dl_v1.status_code == 200
    assert "spreadsheetml.sheet" in dl_v1.headers["content-type"]
    wb = openpyxl.load_workbook(io.BytesIO(dl_v1.content), data_only=False)
    try:
        ws = wb.active
        assert ws["A3"].value == "M002-L2"
        assert ws["B3"].value == 2
        assert ws["C3"].value == "LED 90W"
        assert ws["D3"].value == "Sector 2"
        assert ws["E3"].value is None
    finally:
        wb.close()

    # Publish v1
    assert client.post(f"/api/merged-reports/{merged_id}/publish", headers=admin_headers).status_code == 200

    # Create a Customer B viewer user and verify tenant isolation in BOTH directions
    user_b_resp = client.post(
        "/api/users",
        json={
            "name": "Mysore Viewer",
            "email": "viewer@mysore.local",
            "username": "mysore_viewer",
            "password": "MysoreViewer123!",
            "role": "customer",
            "status": "active",
            "customer_ids": [cust_b["id"]],
        },
        headers=admin_headers,
    )
    assert user_b_resp.status_code == 201, user_b_resp.text

    login_b = client.post(
        "/api/auth/login",
        json={
            "identifier": "mysore_viewer",
            "password": "MysoreViewer123!",
            "login_type": "customer",
        },
    )
    assert login_b.status_code == 200
    cust_b_headers = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    # Customer A (BBMP viewer) MUST NOT see Customer B resources
    assert all(c["id"] != cust_b["id"] for c in client.get("/api/customers", headers=customer_headers).json())
    assert client.get(f"/api/regions?customer_id={cust_b['id']}", headers=customer_headers).status_code == 403
    assert client.get(f"/api/wards?customer_id={cust_b['id']}", headers=customer_headers).status_code == 403
    assert client.get(f"/api/pole-survey/{ps_id}", headers=customer_headers).status_code == 403
    assert client.get(f"/api/merged-reports/{merged_id}", headers=customer_headers).status_code == 403
    assert client.get(f"/api/merged-reports/{merged_id}/download", headers=customer_headers).status_code == 403
    assert client.get(f"/api/dashboard/customer?customer_id={cust_b['id']}", headers=customer_headers).status_code == 403

    # Customer B viewer sees Mysore v1 cleanly inside W01 and not Bangalore BBMP
    cust_b_tree = client.get("/api/hierarchy/tree", headers=cust_b_headers).json()
    assert len(cust_b_tree) == 1
    assert cust_b_tree[0]["id"] == cust_b["id"]
    assert cust_b_tree[0]["regions"][0]["zones"][0]["wards"][0]["id"] == ward_b["id"]

    # Upload Pole Survey v2 with identical custom headers -> saved mapping re-used & v2 draft created
    survey_v2 = _make_xlsx_bytes(
        ["Survey Pole", "Brackets", "Fixture Spec", "Street Sector"],
        [
            ["M001", 1, "LED 60W", "Sector 1"],
            ["M002", 2, "LED 90W", "Sector 2"],
            ["M003", 1, "LED 40W", "Sector 3"],
        ],
    )
    assert (
        client.post(
            "/api/pole-survey/upload",
            data={
                "customer_id": cust_b["id"],
                "region_id": reg_b["id"],
                "zone_id": zone_b["id"],
                "ward_id": ward_b["id"],
                "replace_existing": "true",
            },
            files={
                "file": (
                    "mysore_survey_v2.xlsx",
                    survey_v2,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            headers=admin_headers,
        ).status_code
        == 201
    )

    inspect_v2 = client.get(
        "/api/merged-reports/inspect",
        params={
            "customer_id": cust_b["id"],
            "region_id": reg_b["id"],
            "zone_id": zone_b["id"],
            "ward_id": ward_b["id"],
        },
        headers=admin_headers,
    )
    assert inspect_v2.status_code == 200
    insp_json = inspect_v2.json()
    assert insp_json["pole_survey_saved_mapping"]["pole_number_col"] == "Survey Pole"
    assert insp_json["pole_survey_saved_mapping"]["extra_mappings"] == {"Street Sector": "Ward Road"}
    assert insp_json["lamp_saved_mapping"]["pole_number_col"] == "Asset Pole"
    assert insp_json["pole_survey_needs_confirmation"] is False

    # Generate DRAFT v2 while v1 remains the only published version
    gen_v2 = client.post(
        "/api/merged-reports/generate",
        json={
            "customer_id": cust_b["id"],
            "region_id": reg_b["id"],
            "zone_id": zone_b["id"],
            "ward_id": ward_b["id"],
            "pole_survey_mapping": {
                "pole_number_col": "Survey Pole",
                "arm_count_col": "Brackets",
                "lamp_type_col": "Fixture Spec",
                "extra_mappings": {"Street Sector": "Ward Road"},
            },
            "lamp_installation_mapping": {
                "pole_number_col": "Asset Pole",
                "arm_count_col": "Arm Qty",
                "lamp_type_col": "Fitting Model",
            },
            "save_mapping": True,
        },
        headers=admin_headers,
    )
    assert gen_v2.status_code == 201
    assert gen_v2.json()["merged_report"]["current_version"] == 2
    assert gen_v2.json()["merged_report"]["status"] == "draft"

    # Customer B MUST still see published v1 metadata and summary (+1 added), NOT draft v2!
    cust_mr_detail = client.get(f"/api/merged-reports/{merged_id}", headers=cust_b_headers)
    assert cust_mr_detail.status_code == 200
    detail_json = cust_mr_detail.json()
    assert detail_json["current_version"] == 1
    assert detail_json["status"] == "published"
    assert detail_json["latest_summary"]["added_records"] == 1
    assert [v["version"] for v in detail_json["versions"]] == [1]

    cust_mr_preview = client.get(f"/api/merged-reports/{merged_id}/preview", headers=cust_b_headers)
    assert cust_mr_preview.status_code == 200
    assert [r["generated_pole_number"] for r in cust_mr_preview.json()["newly_added_records"]] == ["M002-L2"]


def test_led_rules_external_links_upload_history_dashboards_audit_and_file_validation(
    client, admin_headers, customer_headers
):
    bbmp_id, east_id, zone_id, ward_id = _get_bbmp_east(client, admin_headers)

    # LED rules CRUD + RBAC (including Empty rules for hyphen '-' & blank data)
    assert client.get("/api/led-rules", headers=customer_headers).status_code == 403
    seeded_rules = client.get("/api/led-rules", headers=admin_headers)
    assert seeded_rules.status_code == 200
    assert any(r["pattern"] == "-" and r["classification"] == "empty" for r in seeded_rules.json())
    assert any(r["pattern"] == "(blank)" and r["classification"] == "empty" for r in seeded_rules.json())

    create_rule = client.post(
        "/api/led-rules",
        json={"pattern": "SOLAR HYBRID", "match_type": "contains", "classification": "led", "is_active": True},
        headers=admin_headers,
    )
    assert create_rule.status_code == 201
    rule_id = create_rule.json()["id"]
    assert client.put(f"/api/led-rules/{rule_id}", json={"is_active": False}, headers=admin_headers).status_code == 200
    assert client.put(f"/api/led-rules/{rule_id}", json={"pattern": "   "}, headers=admin_headers).status_code == 400
    assert client.delete(f"/api/led-rules/{rule_id}", headers=admin_headers).status_code == 200

    # Blank pattern is rejected for led/non_led (422) but normalized to '(blank)' for empty
    assert (
        client.post(
            "/api/led-rules",
            json={"pattern": "   ", "match_type": "exact", "classification": "led", "is_active": True},
            headers=admin_headers,
        ).status_code
        == 422
    )
    empty_rule = client.post(
        "/api/led-rules",
        json={"pattern": "--", "match_type": "contains", "classification": "empty", "is_active": True},
        headers=admin_headers,
    )
    assert empty_rule.status_code == 201
    assert empty_rule.json()["classification"] == "empty"
    empty_rule_id = empty_rule.json()["id"]
    upd_empty = client.put(
        f"/api/led-rules/{empty_rule_id}",
        json={"pattern": ""},
        headers=admin_headers,
    )
    assert upd_empty.status_code == 200
    assert upd_empty.json()["pattern"] == "(blank)"
    # Duplicate update against seeded ('(blank)', 'exact') returns 409 Conflict
    assert (
        client.put(
            f"/api/led-rules/{empty_rule_id}",
            json={"match_type": "exact"},
            headers=admin_headers,
        ).status_code
        == 409
    )
    assert client.delete(f"/api/led-rules/{empty_rule_id}", headers=admin_headers).status_code == 200

    blank_create = client.post(
        "/api/led-rules",
        json={"pattern": "", "match_type": "contains", "classification": "empty", "is_active": True},
        headers=admin_headers,
    )
    assert blank_create.status_code == 201
    assert blank_create.json()["pattern"] == "(blank)"
    assert client.delete(f"/api/led-rules/{blank_create.json()['id']}", headers=admin_headers).status_code == 200

    # External Links GET (both roles) + PUT (admin only)
    assert client.get("/api/external-links", headers=customer_headers).status_code == 200
    assert (
        client.put(
            "/api/external-links",
            json={"links": [{"link_key": "om_dashboard", "url": "https://evil.example"}]},
            headers=customer_headers,
        ).status_code
        == 403
    )
    upd_links = client.put(
        "/api/external-links",
        json={
            "links": [
                {
                    "link_key": "om_dashboard",
                    "link_name": "O&M Dashboard",
                    "url": "https://om.schnell.local/portal",
                    "is_enabled": True,
                }
            ]
        },
        headers=admin_headers,
    )
    assert upd_links.status_code == 200
    assert any(l["url"] == "https://om.schnell.local/portal" for l in upd_links.json())

    # Ward-level Dashboard statistics + Customer / Region / Zone filters
    adm_dash = client.get("/api/dashboard/admin", headers=admin_headers)
    assert adm_dash.status_code == 200
    adm_body = adm_dash.json()
    assert adm_body["total_customers"] >= 1
    assert adm_body["total_wards"] >= 57
    assert "wards_with_pole_survey" in adm_body
    assert "wards_with_lamp_installation" in adm_body
    assert "wards_with_completed_merged" in adm_body
    assert "wards_awaiting_uploads" in adm_body
    assert "wards_with_processing_errors" in adm_body
    assert "report_availability_by_region" in adm_body
    assert "zone_availability" in adm_body

    # Filtered dashboard for BBMP -> EAST -> CV Raman Nagar (8 wards)
    filtered_adm = client.get(
        "/api/dashboard/admin",
        params={"customer_id": bbmp_id, "region_id": east_id, "zone_id": zone_id},
        headers=admin_headers,
    )
    assert filtered_adm.status_code == 200
    f_body = filtered_adm.json()
    assert f_body["total_zones"] == 1
    assert f_body["total_wards"] == 8
    before_ps = f_body["wards_with_pole_survey"]
    before_li = f_body["wards_with_lamp_installation"]
    before_merged = f_body["wards_with_completed_merged"]
    before_awaiting = f_body["wards_awaiting_uploads"]
    before_err = f_body["wards_with_processing_errors"]

    # Mismatched customer_id vs region_id returns 400 Bad Request
    other_reg = next((r for r in client.get("/api/regions", headers=admin_headers).json() if r["customer_id"] != bbmp_id), None)
    if other_reg is not None:
        assert (
            client.get(
                "/api/dashboard/admin",
                params={"customer_id": bbmp_id, "region_id": other_reg["id"]},
                headers=admin_headers,
            ).status_code
            == 400
        )

    cust_dash = client.get(
        "/api/dashboard/customer",
        params={"customer_id": bbmp_id, "region_id": east_id},
        headers=customer_headers,
    )
    assert cust_dash.status_code == 200
    assert "Bangalore (BBMP)" in cust_dash.json()["customer_names"]
    assert "wards_awaiting_uploads" in cust_dash.json()
    assert "zone_availability" in cust_dash.json()

    # Trigger a processing failure in an isolated BBMP ward to verify wards_with_processing_errors increments then clears on success
    err_ward_id = client.get(f"/api/wards?zone_id={zone_id}", headers=admin_headers).json()[-1]["id"]
    bad_map_survey = _make_xlsx_bytes(
        ["Pole No", "Arms", "Lamp Type"],
        [["ERR1", 1, "LED 60W"], ["ERR2", 1, "-"], ["ERR3", 1, ""]],
    )
    bad_map_lamp = _make_xlsx_bytes(["Pole Number", "Arm Count", "Lamp Type"], [["ERR0", 1, "LED 60W"]])
    assert (
        client.post(
            "/api/pole-survey/upload",
            data={"customer_id": bbmp_id, "region_id": east_id, "zone_id": zone_id, "ward_id": err_ward_id},
            files={"file": ("err_survey.xlsx", bad_map_survey, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=admin_headers,
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/lamp-installation/upload",
            data={"customer_id": bbmp_id, "region_id": east_id, "zone_id": zone_id, "ward_id": err_ward_id},
            files={"file": ("err_lamp.xlsx", bad_map_lamp, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=admin_headers,
        ).status_code
        == 201
    )
    fail_gen = client.post(
        "/api/merged-reports/generate",
        json={
            "customer_id": bbmp_id,
            "region_id": east_id,
            "zone_id": zone_id,
            "ward_id": err_ward_id,
            "pole_survey_mapping": {"pole_number_col": "WRONG_COL", "arm_count_col": "Arms", "lamp_type_col": "Lamp Type"},
            "lamp_installation_mapping": {"pole_number_col": "Pole Number", "arm_count_col": "Arm Count", "lamp_type_col": "Lamp Type"},
        },
        headers=admin_headers,
    )
    assert fail_gen.status_code == 400
    err_dash = client.get(
        "/api/dashboard/admin",
        params={"customer_id": bbmp_id, "region_id": east_id, "zone_id": zone_id},
        headers=admin_headers,
    ).json()
    assert err_dash["wards_with_processing_errors"] == before_err + 1

    # Now succeed on that ward -> wards_with_processing_errors drops back to before_err and completion counters advance!
    ok_gen = client.post(
        "/api/merged-reports/generate",
        json={
            "customer_id": bbmp_id,
            "region_id": east_id,
            "zone_id": zone_id,
            "ward_id": err_ward_id,
            "pole_survey_mapping": {"pole_number_col": "Pole No", "arm_count_col": "Arms", "lamp_type_col": "Lamp Type"},
            "lamp_installation_mapping": {"pole_number_col": "Pole Number", "arm_count_col": "Arm Count", "lamp_type_col": "Lamp Type"},
        },
        headers=admin_headers,
    )
    assert ok_gen.status_code == 201
    ok_body = ok_gen.json()
    assert ok_body["summary"]["empty_records"] == 2
    assert ok_body["summary"]["unknown_lamp_type_records"] == 0
    assert [r["pole_number"] for r in ok_body["empty_records"]] == ["ERR2", "ERR3"]
    err_preview = client.get(f"/api/merged-reports/{ok_body['merged_report']['id']}/preview", headers=admin_headers)
    assert err_preview.status_code == 200
    assert err_preview.json()["summary"]["empty_records"] == 2
    assert [r["pole_number"] for r in err_preview.json()["empty_records"]] == ["ERR2", "ERR3"]
    recovered_dash = client.get(
        "/api/dashboard/admin",
        params={"customer_id": bbmp_id, "region_id": east_id, "zone_id": zone_id},
        headers=admin_headers,
    ).json()
    assert recovered_dash["wards_with_processing_errors"] == before_err
    assert recovered_dash["wards_with_pole_survey"] == before_ps + 1
    assert recovered_dash["wards_with_lamp_installation"] == before_li + 1
    assert recovered_dash["wards_with_completed_merged"] == before_merged + 1
    assert recovered_dash["wards_awaiting_uploads"] == before_awaiting - 1

    hist = client.get("/api/upload-history", params={"ward_id": err_ward_id}, headers=admin_headers)
    assert hist.status_code == 200
    assert len(hist.json()) == 2
    assert all(item["ward_id"] == err_ward_id for item in hist.json())
    assert client.get("/api/upload-history", headers=customer_headers).status_code == 403

    logs = client.get("/api/audit-logs", headers=admin_headers)
    assert logs.status_code == 200
    actions = {item["action"] for item in logs.json()}
    assert "pole_survey.upload" in actions
    assert "merged_report.publish" in actions

    # Invalid / corrupted upload rejections (400 Bad Request)
    bad_ext = client.post(
        "/api/pole-survey/upload",
        data={"customer_id": bbmp_id, "region_id": east_id, "zone_id": zone_id, "ward_id": ward_id},
        files={"file": ("not_excel.csv", b"a,b,c\n1,2,3\n", "text/csv")},
        headers=admin_headers,
    )
    assert bad_ext.status_code == 400

    bad_magic = client.post(
        "/api/pole-survey/upload",
        data={"customer_id": bbmp_id, "region_id": east_id, "zone_id": zone_id, "ward_id": ward_id},
        files={
            "file": (
                "corrupted.xlsx",
                b"NOT_A_ZIP_HEADER",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=admin_headers,
    )
    assert bad_magic.status_code == 400

    empty_file = client.post(
        "/api/lamp-installation/upload",
        data={"customer_id": bbmp_id, "region_id": east_id, "zone_id": zone_id, "ward_id": ward_id},
        files={
            "file": (
                "empty.xlsx",
                b"",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=admin_headers,
    )
    assert empty_file.status_code == 400
