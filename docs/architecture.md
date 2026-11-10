# System Architecture

## 1. High-Level Overview

```text
React + Vite SPA (Render Static Site)
        │  HTTPS + JWT Bearer Token
        ▼
FastAPI Backend API (Render Web Service)
  ├── Auth & RBAC Layer (JWT + Revoked Token Store + Customer Scope Verification)
  ├── Hierarchy & Admin Services
  ├── Excel Reader & Structure Inspector (OpenPyXL + xlrd fallback)
  ├── Reconciliation Engine (LED Classifier + Pole Normalizer + L-Numbering)
  ├── Excel Template Writer (OpenPyXL Style/Formula/Merge Preserver)
  └── Storage Service (Persistent Disk Abstraction)
        │                        │
        ▼                        ▼
  PostgreSQL DB           Persistent Volume (/storage)
```

## 2. Backend Design Principles

- **Modular Separation:** Routers (`app/api/routes/`) delegate validation and domain rules to Services (`app/services/`) and ORM Models (`app/models/`).
- **Dual-Pass Excel Handling:**
  - `data_only=True` is used when inspecting values/headers so formula-computed cells evaluate to their actual displayed values.
  - `data_only=False` is used when cloning the Lamp Installation master workbook so existing Excel formulas, cell formatting, column widths, freeze panes, auto-filters, merged cells, and print setup remain intact.
- **Temp Workspace Isolation:** Workbook reads/writes during reconciliation happen inside isolated per-job directories under `TEMP_PROCESSING_DIR` and are cleaned up in `finally` blocks. Source workbooks are never modified in place.
- **Stale Report Detection:** Uploading, replacing, or deleting a zone's source file transitions any existing `MergedReport` in that zone to `outdated`, while retaining previously published versions in `merged_report_versions`.

## 3. Frontend Design Principles

- **Strict Role Separation:** `AuthContext` & `AdminRoute` prevent non-admins from rendering administrative views; all security enforcement is duplicated authoritatively on the backend.
- **Persistent Hierarchy Context:** `HierarchyContext` keeps Customer, Region, and Zone selections synchronized across dashboards, source reports, and the Merged Report workspace.
- **Corporate Design System:** Built around Schnell's teal palette (`#075D6B`, `#0D7780`, `#18A6A0`, `#F4F7F9`, `#FFFFFF`, `#173042`, `#718096`).

