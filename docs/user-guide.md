# Schnell Asset Report Dashboard — User Guide

## 1. Portal Login

Open the application login page and select your portal access tab:
- **Admin Login:** Full management access (requires an Administrator account).
- **Customer Login:** Read-only portal access (requires an assigned Customer Viewer account).

Enter either your **Email** or **Username** plus your **Password**. Toggle the eye icon to inspect your password or check **Remember me for 7 days** if using a trusted workstation.

---

## 2. Administrator Workflows

### A. Managing Hierarchy & Customer Accounts
1. Open **Customer Management**, **Region Management**, and **Zone Management** to add or rename Customers, Regions, and Zones, or toggle active/inactive status.
   - Regions or Zones with existing uploaded files or Merged Reports cannot be deleted accidentally — deactivate them instead to hide them from Customers while preserving archives.
2. Open **User Management** to create Customer read-only accounts and assign which Customer(s) they may access.

### B. Uploading Pole Survey & Lamp Installation Reports
1. Open **Pole Survey Report** or **Lamp Installation Report** from the left sidebar.
2. Use the **Region & Zone Hierarchy** navigator on the left to select the target **Customer → Region → Zone**.
3. Drag and drop (or browse) a valid `.xlsx` workbook (up to 25 MB; `.xls` is also supported where available).
4. Click **Validate & Upload**. If the selected Zone already has an active workbook, confirm replacement — previous versions remain preserved in **Upload History**.
   - **Important:** Replacing or deleting a zone's source file automatically flags any previously generated **Merged Report** in that zone as **Outdated** so it can be regenerated safely.

### C. Generating & Publishing Merged Reports (LED Reconciliation)
1. Open **Merged Report** and choose the target **Zone**. Both **Pole Survey Report** and **Lamp Installation Report** must be active in that zone.
2. Review the detected worksheets, header rows, and suggested/saved column mappings:
   - **Pole Survey (Extract Only):** Map `Pole Number *`, `Arm Count *`, and `Lamp Type *`.
   - **Lamp Installation (Master Template):** Map `Pole Number Cell *` (where formatted `OriginalPole-Ln` will be written), plus optional `Arm Count` / `Lamp Type` or extra field pairs. Unmapped template columns remain blank and are never fabricated.
3. Click **Generate Merged Report**. The reconciliation engine:
   - Reads Pole Survey rows sequentially and excludes blank Pole Numbers and non-LED lamps.
   - Flags any unrecognized lamp strings under **Unknown Lamp Types** for admin review.
   - Deduplicates repeated Pole Numbers in Pole Survey (retaining the first occurrence).
   - Assigns sequential `L1, L2, L3, ...` numbers across unique eligible LED survey rows **before** comparing against Lamp Installation, then skips any Pole already present in Lamp Installation without shifting sequence numbers (e.g., if rows 1–3 exist and Pole 4 is new, Pole 4 becomes `P004-L4`).
   - Clones the zone's Lamp Installation master `.xlsx` via OpenPyXL, preserving original formatting, formulas, column widths, merged cells, freeze panes, filters, and shifting any footer rows downward.
4. Review the **Processing Summary** and inspect all 6 tabs (**Processing Summary**, **Newly Added LED**, **Existing Lamp Install**, **Skipped Existing**, **Duplicates**, **Invalid / Unknown**).
5. If unknown lamp types need to be accepted as LED (or excluded), add rules under **Settings → LED Lamp Classification Rules**, then regenerate.
6. Once satisfied, click **Publish to Customer** to make the version accessible to authorized Customer users.

### D. Configuring Connected Portals
Under **Settings → External Dashboard Links**, set the HTTPS URLs for **O&M Dashboard** and **Energy Saving Report** so the sidebar links open those applications in a new tab.

---

## 3. Customer (Read-Only) Workflows

1. Sign in via **Customer Login**.
2. Use the left **Region & Zone Hierarchy** search box (`Search wards or zones...`) or expand regions to filter by zone.
3. Open:
   - **Pole Survey Report:** Search, column-filter, preview, and download active source files.
   - **Lamp Installation Report:** Search, column-filter, preview, and download active master installation files.
   - **Merged Report:** View published reconciliation summaries, search all preview tabs, and download formatted `.xlsx` Merged Reports.
4. Open **O&M Dashboard** or **Energy Saving Report** directly from the sidebar when configured by your administrator.

