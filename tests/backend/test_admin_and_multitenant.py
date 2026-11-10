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
    return cust["id"], east["id"], zone["id"]


def test_hierarchy_delete_protection_and_inactive_visibility(client, admin_headers, customer_headers):
    bbmp_id, east_id, _ = _get_bbmp_east(client, admin_headers)

    # Create temporary Customer -> Region -> Zone hierarchy
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
        json={"region_id": temp_reg_id, "zone_name": "Ward 10", "status": "active"},
        headers=admin_headers,
    )
    assert z_resp.status_code == 201, z_resp.text
    temp_zone_id = z_resp.json()["id"]

    # Delete protection: Customer with Region -> 409; Region with Zone -> 409
    assert client.delete(f"/api/customers/{temp_cust_id}", headers=admin_headers).status_code == 409
    assert client.delete(f"/api/regions/{temp_reg_id}", headers=admin_headers).status_code == 409

    # Upload a Pole Survey into Ward 10 -> deleting Zone is blocked with 409
    survey_bytes = _make_xlsx_bytes(["Pole No", "Arms", "Lamp Type"], [["W001", 1, "LED 60W"]])
    up_resp = client.post(
        "/api/pole-survey/upload",
        data={"customer_id": temp_cust_id, "region_id": temp_reg_id, "zone_id": temp_zone_id},
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
    assert client.delete(f"/api/zones/{temp_zone_id}", headers=admin_headers).status_code == 409

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

    # Clean empty Customer -> Region -> Zone creation and deletion succeeds leaf-up
    c2 = client.post("/api/customers", json={"customer_name": "Empty Utility"}, headers=admin_headers).json()
    r2 = client.post(
        "/api/regions",
        json={"customer_id": c2["id"], "region_name": "Empty Region"},
        headers=admin_headers,
    ).json()
    z2 = client.post(
        "/api/zones",
        json={"region_id": r2["id"], "zone_name": "Empty Zone"},
        headers=admin_headers,
    ).json()
    assert client.delete(f"/api/zones/{z2['id']}", headers=admin_headers).status_code == 200
    assert client.delete(f"/api/regions/{r2['id']}", headers=admin_headers).status_code == 200
    assert client.delete(f"/api/customers/{c2['id']}", headers=admin_headers).status_code == 200


def test_multitenant_isolation_saved_mapping_extra_columns_and_published_version_pinning(
    client, admin_headers, customer_headers
):
    # Create isolated Customer B hierarchy
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
        json={"region_id": reg_b["id"], "zone_name": "Kuvempunagar", "status": "active"},
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
        data={"customer_id": cust_b["id"], "region_id": reg_b["id"], "zone_id": zone_b["id"]},
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
        data={"customer_id": cust_b["id"], "region_id": reg_b["id"], "zone_id": zone_b["id"]},
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
    assert client.get(f"/api/pole-survey/{ps_id}", headers=customer_headers).status_code == 403
    assert client.get(f"/api/merged-reports/{merged_id}", headers=customer_headers).status_code == 403
    assert client.get(f"/api/merged-reports/{merged_id}/download", headers=customer_headers).status_code == 403

    # Customer B viewer sees Mysore v1 cleanly and not Bangalore BBMP
    cust_b_tree = client.get("/api/hierarchy/tree", headers=cust_b_headers).json()
    assert len(cust_b_tree) == 1
    assert cust_b_tree[0]["id"] == cust_b["id"]

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
        params={"customer_id": cust_b["id"], "region_id": reg_b["id"], "zone_id": zone_b["id"]},
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
    bbmp_id, east_id, zone_id = _get_bbmp_east(client, admin_headers)

    # LED rules CRUD + RBAC
    assert client.get("/api/led-rules", headers=customer_headers).status_code == 403
    create_rule = client.post(
        "/api/led-rules",
        json={"pattern": "SOLAR HYBRID", "match_type": "contains", "classification": "led", "is_active": True},
        headers=admin_headers,
    )
    assert create_rule.status_code == 201
    rule_id = create_rule.json()["id"]
    assert client.put(f"/api/led-rules/{rule_id}", json={"is_active": False}, headers=admin_headers).status_code == 200
    assert client.delete(f"/api/led-rules/{rule_id}", headers=admin_headers).status_code == 200

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

    # Dashboards, Upload History & Audit Logs
    adm_dash = client.get("/api/dashboard/admin", headers=admin_headers)
    assert adm_dash.status_code == 200
    assert adm_dash.json()["total_customers"] >= 1
    assert "report_availability_by_region" in adm_dash.json()

    cust_dash = client.get("/api/dashboard/customer", headers=customer_headers)
    assert cust_dash.status_code == 200
    assert "Bangalore (BBMP)" in cust_dash.json()["customer_names"]

    hist = client.get("/api/upload-history", headers=admin_headers)
    assert hist.status_code == 200
    assert len(hist.json()) >= 1
    assert client.get("/api/upload-history", headers=customer_headers).status_code == 403

    logs = client.get("/api/audit-logs", headers=admin_headers)
    assert logs.status_code == 200
    actions = {item["action"] for item in logs.json()}
    assert "pole_survey.upload" in actions
    assert "merged_report.publish" in actions

    # Invalid / corrupted upload rejections (400 Bad Request)
    bad_ext = client.post(
        "/api/pole-survey/upload",
        data={"customer_id": bbmp_id, "region_id": east_id, "zone_id": zone_id},
        files={"file": ("not_excel.csv", b"a,b,c\n1,2,3\n", "text/csv")},
        headers=admin_headers,
    )
    assert bad_ext.status_code == 400

    bad_magic = client.post(
        "/api/pole-survey/upload",
        data={"customer_id": bbmp_id, "region_id": east_id, "zone_id": zone_id},
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
        data={"customer_id": bbmp_id, "region_id": east_id, "zone_id": zone_id},
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
