# Schnell Asset Report Dashboard — User Guide

## 1. Portal Login

Open the application login page and select your portal access tab:
- **Admin Login:** Full management access (requires an Administrator account).
- **Customer Login:** Read-only portal access (requires an assigned Customer Viewer account).

Enter either your **Email** or **Username** plus your **Password**. Toggle the eye icon to inspect your password or check **Remember me for 7 days** if using a trusted workstation.

---

## 2. Administrator Workflows

### A. Managing Hierarchy & Customer Accounts
1. Open **Customer Management**, **Region Management**, **Zone Management**, and **Ward Management** to add or rename Customers, Regions, Zones (with Zone Codes), and individual Wards (Ward Number, Ward Name, Ward Code), or toggle active/inactive status.
   - Regions, Zones, or Wards with child entities, existing uploaded files, or Merged Reports cannot be deleted accidentally — deactivate them instead to hide them from Customers while preserving archives.
2. Open **User Management** to create Customer read-only accounts and assign which Customer(s) they may access.

### B. Uploading Pole Survey & Lamp Installation Reports (Ward Level)
1. Open **Pole Survey Report** or **Lamp Installation Report** from the left sidebar.
2. Use the 4-level **Hierarchy Explorer** on the left to expand and select the target **Customer → Region → Zone → Ward**. Uploads are only permitted after selecting a specific Ward.
3. Drag and drop (or browse) a valid `.xlsx` workbook (up to 25 MB; `.xls` is also supported where available).
4. Click **Validate & Upload**. If the selected Ward already has an active workbook, confirm replacement — previous versions remain preserved in **Upload History**.
   - **Important:** Replacing or deleting a ward's source file automatically flags only that ward's previously generated **Merged Report** as **Outdated** so it can be regenerated safely.

### C. Generating & Publishing Merged Reports (Ward-Isolated LED Reconciliation)
1. Open **Merged Report** and select the target **Ward**. Both **Pole Survey Report** and **Lamp Installation Report** must be active inside that ward. Reconciliation runs strictly within that ward and never compares poles across different wards.
2. Review the detected worksheets, header rows, and suggested/saved column mappings:
   - **Pole Survey (Extract Only):** Map `Pole Number *`, `Arm Count *`, and `Lamp Type *`.
   - **Lamp Installation (Master Template):** Map `Pole Number Cell *` (where formatted `OriginalPole-Ln` will be written), plus optional `Arm Count` / `Lamp Type` or extra field pairs. Unmapped template columns remain blank and are never fabricated.
3. Click **Generate Merged Report**. The reconciliation engine:
   - Reads that ward's Pole Survey rows sequentially and excludes blank Pole Numbers and non-LED lamps.
   - Flags any unrecognized lamp strings under **Unknown Lamp Types** for admin review.
   - Deduplicates repeated Pole Numbers in that ward's Pole Survey (retaining the first occurrence).
   - Assigns sequential `L1, L2, L3, ...` numbers across unique eligible LED survey rows **before** comparing against that ward's Lamp Installation, then skips any Pole already present in that ward without shifting sequence numbers (e.g., if rows 1–3 exist and Pole 4 is new, Pole 4 becomes `P004-L4`).
   - Clones that ward's Lamp Installation master `.xlsx` via OpenPyXL, preserving original formatting, formulas, column widths, merged cells, freeze panes, filters, and shifting any footer rows downward.
4. Review the **Processing Summary** and inspect all 6 tabs (**Processing Summary**, **Newly Added LED**, **Existing Lamp Install**, **Skipped Existing**, **Duplicates**, **Invalid / Unknown**).
5. If unknown lamp types need to be accepted as LED (or excluded), add rules under **Settings → LED Lamp Classification Rules**, then regenerate.
6. Once satisfied, click **Publish to Customer** to make the ward's version accessible to authorized Customer users.

### D. Configuring Connected Portals
Under **Settings → External Dashboard Links**, set the HTTPS URLs for **O&M Dashboard** and **Energy Saving Report** so the sidebar links open those applications in a new tab.

---

## 3. Customer (Read-Only) Workflows

1. Sign in via **Customer Login**.
2. Use the left 4-level **Hierarchy Explorer** search box (`Search ward, zone, region...`) or expand zones to select a ward (green/blue/orange status dots indicate uploaded Pole Survey, Lamp Installation, and Merged Reports).
3. Open:
   - **Dashboard:** View ward-level completion summary and filter availability by customer, region, or zone.
   - **Pole Survey Report:** Search, column-filter, preview, and download active source files by ward.
   - **Lamp Installation Report:** Search, column-filter, preview, and download active master installation files by ward.
   - **Merged Report:** View published ward reconciliation summaries, search all preview tabs, and download formatted `.xlsx` Merged Reports.
4. Open **O&M Dashboard** or **Energy Saving Report** directly from the sidebar when configured by your administrator.

