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


def _get_bbmp_ward(client, headers, zone_name: str, ward_number: str | None = None):
    tree = client.get("/api/hierarchy/tree", headers=headers).json()
    cust = next(c for c in tree if c["customer_name"] == "Bangalore (BBMP)")
    for reg in cust["regions"]:
        for z in reg["zones"]:
            if z["zone_name"] == zone_name:
                wards = z["wards"]
                target = (
                    next(w for w in wards if w["ward_number"] == ward_number)
                    if ward_number is not None
                    else wards[0]
                )
                return cust["id"], reg["id"], z["id"], target["id"], target["ward_number"]
    raise AssertionError(f"Zone {zone_name} / Ward {ward_number} not found")


def test_seeded_bbmp_zones_and_wards_configuration(client, admin_headers):
    tree = client.get("/api/hierarchy/tree", headers=admin_headers).json()
    bbmp = next(c for c in tree if c["customer_name"] == "Bangalore (BBMP)")

    expected = {
        "BOMMANAHALLI": {
            ("Bommanahalli", "BMH"): [f"W{n}" for n in range(202, 213)],
        },
        "EAST": {
            ("CV Raman Nagar", "CVRN"): [f"W{n}" for n in range(108, 116)],
            ("Hebbal", "HEB"): [f"W{n}" for n in range(61, 69)],
            ("Pulakeshi Nagar", "PN"): [f"W{n}" for n in range(69, 76)],
            ("Sarvagna Nagar", "SN"): [f"W{n}" for n in range(76, 86)],
            ("Shanthi Nagar", "SNTR"): [f"W{n}" for n in range(166, 173)],
            ("Sivaji Nagar", "SVJR"): [f"W{n}" for n in range(116, 122)],
        },
    }

    regions_by_name = {r["region_name"]: r for r in bbmp["regions"]}
    assert set(expected.keys()).issubset(regions_by_name.keys())

    total_seeded = 0
    for region_name, zone_map in expected.items():
        zones_by_name = {z["zone_name"]: z for z in regions_by_name[region_name]["zones"]}
        for (zone_name, zone_code), expected_wards in zone_map.items():
            assert zone_name in zones_by_name
            z = zones_by_name[zone_name]
            assert z["zone_code"] == zone_code
            actual_numbers = [w["ward_number"] for w in z["wards"]]
            assert actual_numbers == expected_wards
            assert len({w["id"] for w in z["wards"]}) == len(expected_wards)
            total_seeded += len(expected_wards)

    assert total_seeded == 57


def test_zone_level_bypass_and_cross_ward_mismatch_rejected(client, admin_headers):
    cust_id, reg_id, cv_zone_id, _, _ = _get_bbmp_ward(client, admin_headers, "CV Raman Nagar", "W108")
    _, _, _, heb_ward_id, _ = _get_bbmp_ward(client, admin_headers, "Hebbal", "W61")

    dummy_bytes = _make_xlsx_bytes(["Pole No", "Arms", "Lamp Type"], [["P001", 1, "LED 60W"]])

    # Missing ward_id must be rejected at API boundary (422 Unprocessable Entity)
    assert (
        client.post(
            "/api/pole-survey/upload",
            data={"customer_id": cust_id, "region_id": reg_id, "zone_id": cv_zone_id},
            files={"file": ("survey.xlsx", dummy_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=admin_headers,
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/lamp-installation/upload",
            data={"customer_id": cust_id, "region_id": reg_id, "zone_id": cv_zone_id},
            files={"file": ("lamp.xlsx", dummy_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=admin_headers,
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/api/merged-reports/inspect",
            params={"customer_id": cust_id, "region_id": reg_id, "zone_id": cv_zone_id},
            headers=admin_headers,
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/merged-reports/generate",
            json={
                "customer_id": cust_id,
                "region_id": reg_id,
                "zone_id": cv_zone_id,
                "pole_survey_mapping": {"pole_number_col": "Pole No", "arm_count_col": "Arms", "lamp_type_col": "Lamp Type"},
                "lamp_installation_mapping": {"pole_number_col": "Pole No", "arm_count_col": "Arms", "lamp_type_col": "Lamp Type"},
            },
            headers=admin_headers,
        ).status_code
        == 422
    )

    # Mismatched zone_id vs ward_id must fail with 400 Bad Request
    mismatch = client.post(
        "/api/pole-survey/upload",
        data={
            "customer_id": cust_id,
            "region_id": reg_id,
            "zone_id": cv_zone_id,
            "ward_id": heb_ward_id,
        },
        files={"file": ("mismatch.xlsx", dummy_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=admin_headers,
    )
    assert mismatch.status_code == 400


def test_case_9_10_12_full_workflow_ward_isolation_stale_and_customer_rbac(client, admin_headers, customer_headers):
    # Pick TWO DIFFERENT WARDS inside the SAME ZONE (CV Raman Nagar: W108 vs W109)
    cust_id, reg_id, zone_id, ward_a_id, _ = _get_bbmp_ward(client, admin_headers, "CV Raman Nagar", "W108")
    _, _, _, ward_b_id, _ = _get_bbmp_ward(client, admin_headers, "CV Raman Nagar", "W109")

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
        data={"customer_id": cust_id, "region_id": reg_id, "zone_id": zone_id, "ward_id": ward_a_id},
        files={"file": ("survey.xlsx", survey_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=customer_headers,
    )
    assert cust_upload.status_code == 403

    # 2. Admin uploads Pole Survey for Ward W108 only -> inspecting without Lamp Installation blocks generation (Case 9)
    up_survey_a = client.post(
        "/api/pole-survey/upload",
        data={"customer_id": cust_id, "region_id": reg_id, "zone_id": zone_id, "ward_id": ward_a_id},
        files={"file": ("w108_survey.xlsx", survey_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=admin_headers,
    )
    assert up_survey_a.status_code == 201, up_survey_a.text
    assert up_survey_a.json()["ward_id"] == ward_a_id
    assert up_survey_a.json()["ward_number"] == "W108"

    inspect_missing = client.get(
        "/api/merged-reports/inspect",
        params={"customer_id": cust_id, "region_id": reg_id, "zone_id": zone_id, "ward_id": ward_a_id},
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
            "zone_id": zone_id,
            "ward_id": ward_a_id,
            "pole_survey_mapping": {"pole_number_col": "Pole No", "arm_count_col": "Number of Arms", "lamp_type_col": "Type of Lamp"},
            "lamp_installation_mapping": {"pole_number_col": "Pole Number", "arm_count_col": "Arm Count", "lamp_type_col": "Lamp Type"},
        },
        headers=admin_headers,
    )
    assert gen_missing.status_code == 400

    # 3. Admin uploads Lamp Installation for W108 + independent files for sibling Ward W109 in SAME zone
    up_lamp_a = client.post(
        "/api/lamp-installation/upload",
        data={"customer_id": cust_id, "region_id": reg_id, "zone_id": zone_id, "ward_id": ward_a_id},
        files={"file": ("w108_lamp.xlsx", lamp_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=admin_headers,
    )
    assert up_lamp_a.status_code == 201, up_lamp_a.text

    # Sibling Ward W109 has identical poles in survey, but NO P001/P002 in its own Lamp Installation (only P999)
    lamp_b_bytes = _make_xlsx_bytes(
        ["Pole Number", "Arm Count", "Lamp Type"],
        [["P999", 1, "LED 60W"]],
    )
    assert (
        client.post(
            "/api/pole-survey/upload",
            data={"customer_id": cust_id, "region_id": reg_id, "zone_id": zone_id, "ward_id": ward_b_id},
            files={"file": ("w109_survey.xlsx", survey_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=admin_headers,
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/lamp-installation/upload",
            data={"customer_id": cust_id, "region_id": reg_id, "zone_id": zone_id, "ward_id": ward_b_id},
            files={"file": ("w109_lamp.xlsx", lamp_b_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=admin_headers,
        ).status_code
        == 201
    )

    # 4. Generate Merged Report for Ward W108 -> only P003-L3 added
    gen_a = client.post(
        "/api/merged-reports/generate",
        json={
            "customer_id": cust_id,
            "region_id": reg_id,
            "zone_id": zone_id,
            "ward_id": ward_a_id,
            "pole_survey_mapping": {"pole_number_col": "Pole No", "arm_count_col": "Number of Arms", "lamp_type_col": "Type of Lamp"},
            "lamp_installation_mapping": {"pole_number_col": "Pole Number", "arm_count_col": "Arm Count", "lamp_type_col": "Lamp Type"},
        },
        headers=admin_headers,
    )
    assert gen_a.status_code == 201, gen_a.text
    preview_a = gen_a.json()
    merged_a_id = preview_a["merged_report"]["id"]
    assert preview_a["merged_report"]["ward_id"] == ward_a_id
    assert preview_a["merged_report"]["ward_number"] == "W108"
    assert [r["generated_pole_number"] for r in preview_a["newly_added_records"]] == ["P003-L3"]

    # Generate Merged Report for sibling Ward W109 -> completely isolated from W108!
    gen_b = client.post(
        "/api/merged-reports/generate",
        json={
            "customer_id": cust_id,
            "region_id": reg_id,
            "zone_id": zone_id,
            "ward_id": ward_b_id,
            "pole_survey_mapping": {"pole_number_col": "Pole No", "arm_count_col": "Number of Arms", "lamp_type_col": "Type of Lamp"},
            "lamp_installation_mapping": {"pole_number_col": "Pole Number", "arm_count_col": "Arm Count", "lamp_type_col": "Lamp Type"},
        },
        headers=admin_headers,
    )
    assert gen_b.status_code == 201
    merged_b_id = gen_b.json()["merged_report"]["id"]
    assert [r["generated_pole_number"] for r in gen_b.json()["newly_added_records"]] == [
        "P001-L1",
        "P002-L2",
        "P003-L3",
    ]

    # 5. Customer CANNOT access Draft Merged Report or publish it
    assert client.get(f"/api/merged-reports/{merged_a_id}", headers=customer_headers).status_code == 403
    assert client.post(f"/api/merged-reports/{merged_a_id}/publish", headers=customer_headers).status_code == 403
    assert client.get("/api/merged-reports", headers=customer_headers).json() == []

    # 6. Admin publishes Ward W108 Merged Report -> Customer CAN now view & download it (filtered by ward_id)
    pub_a = client.post(f"/api/merged-reports/{merged_a_id}/publish", headers=admin_headers)
    assert pub_a.status_code == 200
    assert pub_a.json()["status"] == "published"

    cust_merged_list = client.get("/api/merged-reports", params={"ward_id": ward_a_id}, headers=customer_headers).json()
    assert len(cust_merged_list) == 1
    assert cust_merged_list[0]["id"] == merged_a_id
    assert client.get("/api/merged-reports", params={"ward_id": ward_b_id}, headers=customer_headers).json() == []

    dl_merged = client.get(f"/api/merged-reports/{merged_a_id}/download", headers=customer_headers)
    assert dl_merged.status_code == 200
    assert len(dl_merged.content) > 500

    # 7. Admin replaces Pole Survey for W108 -> ONLY W108 becomes outdated; W109 remains untouched draft!
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
        data={
            "customer_id": cust_id,
            "region_id": reg_id,
            "zone_id": zone_id,
            "ward_id": ward_a_id,
            "replace_existing": "false",
        },
        files={"file": ("w108_survey_v2.xlsx", survey_v2_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=admin_headers,
    )
    assert conflict_up.status_code == 409

    ok_replace = client.post(
        "/api/pole-survey/upload",
        data={
            "customer_id": cust_id,
            "region_id": reg_id,
            "zone_id": zone_id,
            "ward_id": ward_a_id,
            "replace_existing": "true",
        },
        files={"file": ("w108_survey_v2.xlsx", survey_v2_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=admin_headers,
    )
    assert ok_replace.status_code == 201
    assert ok_replace.json()["version"] == 2

    mr_a_detail = client.get(f"/api/merged-reports/{merged_a_id}", headers=admin_headers).json()
    assert mr_a_detail["status"] == "outdated"
    assert mr_a_detail["is_outdated"] is True
    assert mr_a_detail["active_pole_survey_version"] == 2
    assert mr_a_detail["source_pole_survey_version"] == 1

    mr_b_detail = client.get(f"/api/merged-reports/{merged_b_id}", headers=admin_headers).json()
    assert mr_b_detail["status"] == "draft"
    assert mr_b_detail["is_outdated"] is False


def _region_lamps_map(dash_json: dict) -> dict[str, int]:
    return {
        item["region_name"]: item["merged_lamps_count"]
        for item in dash_json.get("merged_lamps_by_region", [])
    }


def test_admin_dashboard_region_merged_lamps_published_only_and_no_double_count(client, admin_headers):
    tree = client.get("/api/hierarchy/tree", headers=admin_headers).json()
    bbmp = next(c for c in tree if c["customer_name"] == "Bangalore (BBMP)")
    east_reg = next(r for r in bbmp["regions"] if r["region_name"] == "EAST")
    bomm_reg = next(r for r in bbmp["regions"] if r["region_name"] == "BOMMANAHALLI")

    hebbal_zone = next(z for z in east_reg["zones"] if z["zone_name"] == "Hebbal")
    hebbal_ward = hebbal_zone["wards"][0]
    bmh_zone = bomm_reg["zones"][0]
    bmh_ward = bmh_zone["wards"][0]

    base_dash = client.get(
        "/api/dashboard/admin",
        params={"customer_id": bbmp["id"]},
        headers=admin_headers,
    )
    assert base_dash.status_code == 200
    base_counts = _region_lamps_map(base_dash.json())
    base_east = base_counts["EAST"]
    base_bomm = base_counts["BOMMANAHALLI"]

    # 1. Draft Merged Report in EAST (Hebbal W61) must NOT be counted until published
    east_lamp_v1 = _make_xlsx_bytes(
        ["Pole Number", "Arm Count", "Lamp Type"],
        [["E001", 1, "LED 60W"], ["E002", 1, "LED 60W"]],
    )
    east_survey_v1 = _make_xlsx_bytes(
        ["Pole No", "Arms", "Lamp Type"],
        [["E001", 1, "LED 60W"], ["E003", 1, "LED 60W"], ["E003", 1, "LED 60W"]],
    )
    assert (
        client.post(
            "/api/lamp-installation/upload",
            data={"customer_id": bbmp["id"], "region_id": east_reg["id"], "zone_id": hebbal_zone["id"], "ward_id": hebbal_ward["id"]},
            files={"file": ("hebbal_lamp.xlsx", east_lamp_v1, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=admin_headers,
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/pole-survey/upload",
            data={"customer_id": bbmp["id"], "region_id": east_reg["id"], "zone_id": hebbal_zone["id"], "ward_id": hebbal_ward["id"]},
            files={"file": ("hebbal_survey.xlsx", east_survey_v1, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=admin_headers,
        ).status_code
        == 201
    )
    gen_e_v1 = client.post(
        "/api/merged-reports/generate",
        json={
            "customer_id": bbmp["id"],
            "region_id": east_reg["id"],
            "zone_id": hebbal_zone["id"],
            "ward_id": hebbal_ward["id"],
            "pole_survey_mapping": {"pole_number_col": "Pole No", "arm_count_col": "Arms", "lamp_type_col": "Lamp Type"},
            "lamp_installation_mapping": {"pole_number_col": "Pole Number", "arm_count_col": "Arm Count", "lamp_type_col": "Lamp Type"},
        },
        headers=admin_headers,
    )
    assert gen_e_v1.status_code == 201
    assert gen_e_v1.json()["summary"]["final_merged_records"] == 3
    east_mr_id = gen_e_v1.json()["merged_report"]["id"]

    still_draft_counts = _region_lamps_map(
        client.get("/api/dashboard/admin", params={"customer_id": bbmp["id"]}, headers=admin_headers).json()
    )
    assert still_draft_counts["EAST"] == base_east
    assert still_draft_counts["BOMMANAHALLI"] == base_bomm

    # 2. Publish EAST v1 -> EAST increments by +3, BOMMANAHALLI stays at base
    assert client.post(f"/api/merged-reports/{east_mr_id}/publish", headers=admin_headers).status_code == 200
    pub_v1_counts = _region_lamps_map(
        client.get("/api/dashboard/admin", params={"customer_id": bbmp["id"]}, headers=admin_headers).json()
    )
    assert pub_v1_counts["EAST"] == base_east + 3
    assert pub_v1_counts["BOMMANAHALLI"] == base_bomm

    # 3. Upload v2 survey & generate v2 DRAFT -> published count remains +3 until v2 is published
    east_survey_v2 = _make_xlsx_bytes(
        ["Pole No", "Arms", "Lamp Type"],
        [["E001", 1, "LED 60W"], ["E003", 1, "LED 60W"], ["E004", 1, "LED 90W"]],
    )
    assert (
        client.post(
            "/api/pole-survey/upload",
            data={
                "customer_id": bbmp["id"],
                "region_id": east_reg["id"],
                "zone_id": hebbal_zone["id"],
                "ward_id": hebbal_ward["id"],
                "replace_existing": "true",
            },
            files={"file": ("hebbal_survey_v2.xlsx", east_survey_v2, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=admin_headers,
        ).status_code
        == 201
    )
    gen_e_v2 = client.post(
        "/api/merged-reports/generate",
        json={
            "customer_id": bbmp["id"],
            "region_id": east_reg["id"],
            "zone_id": hebbal_zone["id"],
            "ward_id": hebbal_ward["id"],
            "pole_survey_mapping": {"pole_number_col": "Pole No", "arm_count_col": "Arms", "lamp_type_col": "Lamp Type"},
            "lamp_installation_mapping": {"pole_number_col": "Pole Number", "arm_count_col": "Arm Count", "lamp_type_col": "Lamp Type"},
        },
        headers=admin_headers,
    )
    assert gen_e_v2.status_code == 201
    assert gen_e_v2.json()["summary"]["final_merged_records"] == 4

    v2_draft_counts = _region_lamps_map(
        client.get("/api/dashboard/admin", params={"customer_id": bbmp["id"]}, headers=admin_headers).json()
    )
    assert v2_draft_counts["EAST"] == base_east + 3

    # 4. Publish EAST v2 -> updates cleanly from +3 to +4 (never double-counting v1 + v2)
    assert client.post(f"/api/merged-reports/{east_mr_id}/publish", headers=admin_headers).status_code == 200
    v2_pub_counts = _region_lamps_map(
        client.get("/api/dashboard/admin", params={"customer_id": bbmp["id"]}, headers=admin_headers).json()
    )
    assert v2_pub_counts["EAST"] == base_east + 4

    # 5. Upload, generate, and publish BOMMANAHALLI (W202) -> +5 independently (3 existing + 2 added)
    bmh_lamp = _make_xlsx_bytes(
        ["Pole Number", "Arm Count", "Lamp Type"],
        [["B001", 1, "LED 60W"], ["B002", 1, "LED 60W"], ["B003", 2, "LED 90W"]],
    )
    bmh_survey = _make_xlsx_bytes(
        ["Pole No", "Arms", "Lamp Type"],
        [["B001", 1, "LED 60W"], ["B004", 1, "LED 60W"], ["B005", 1, "LED 40W"], ["B005", 1, "LED 40W"]],
    )
    assert (
        client.post(
            "/api/lamp-installation/upload",
            data={"customer_id": bbmp["id"], "region_id": bomm_reg["id"], "zone_id": bmh_zone["id"], "ward_id": bmh_ward["id"]},
            files={"file": ("bmh_lamp.xlsx", bmh_lamp, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=admin_headers,
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/pole-survey/upload",
            data={"customer_id": bbmp["id"], "region_id": bomm_reg["id"], "zone_id": bmh_zone["id"], "ward_id": bmh_ward["id"]},
            files={"file": ("bmh_survey.xlsx", bmh_survey, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=admin_headers,
        ).status_code
        == 201
    )
    gen_bmh = client.post(
        "/api/merged-reports/generate",
        json={
            "customer_id": bbmp["id"],
            "region_id": bomm_reg["id"],
            "zone_id": bmh_zone["id"],
            "ward_id": bmh_ward["id"],
            "pole_survey_mapping": {"pole_number_col": "Pole No", "arm_count_col": "Arms", "lamp_type_col": "Lamp Type"},
            "lamp_installation_mapping": {"pole_number_col": "Pole Number", "arm_count_col": "Arm Count", "lamp_type_col": "Lamp Type"},
        },
        headers=admin_headers,
    )
    assert gen_bmh.status_code == 201
    assert gen_bmh.json()["summary"]["final_merged_records"] == 5
    bmh_mr_id = gen_bmh.json()["merged_report"]["id"]
    assert client.post(f"/api/merged-reports/{bmh_mr_id}/publish", headers=admin_headers).status_code == 200

    final_counts = _region_lamps_map(
        client.get("/api/dashboard/admin", params={"customer_id": bbmp["id"]}, headers=admin_headers).json()
    )
    assert final_counts["EAST"] == base_east + 4
    assert final_counts["BOMMANAHALLI"] == base_bomm + 5

    # 6. Filtering by Bommanahalli region scopes regional totals accurately
    filtered_bmh = _region_lamps_map(
        client.get(
            "/api/dashboard/admin",
            params={"customer_id": bbmp["id"], "region_id": bomm_reg["id"]},
            headers=admin_headers,
        ).json()
    )
    assert filtered_bmh == {"BOMMANAHALLI": base_bomm + 5}

