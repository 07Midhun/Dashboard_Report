# REST API Reference

Base URL (local development): `http://localhost:8000/api`  
Interactive OpenAPI docs when backend is running: `http://localhost:8000/docs`

All protected endpoints expect `Authorization: Bearer <jwt_token>`.  
All **Admin** routes enforce `require_admin` on the backend and return `403 Forbidden` if called with a Customer token.  
All **Customer** routes scope results via `authorized_customer_ids` derived from `user_customer_permissions`.

---

## 1. Health & Authentication

| Method | Endpoint | Access | Description |
| --- | --- | --- | --- |
| `GET` | `/api/health` | Public | Verifies API and PostgreSQL connectivity |
| `POST` | `/api/auth/login` | Public | Authenticates Admin (`login_type: "admin"`) or Customer (`login_type: "customer"`) via email or username |
| `POST` | `/api/auth/logout` | Authenticated | Revokes the current JWT (`revoked_tokens`) |
| `GET` | `/api/auth/me` | Authenticated | Returns active user profile and assigned customers |

---

## 2. Dynamic Hierarchy (`Customer → Region → Zone`)

| Method | Endpoint | Access | Description |
| --- | --- | --- | --- |
| `GET` | `/api/hierarchy/tree` | Authenticated | Full dynamic Customer → Region → Zone tree with zone report readiness flags |
| `GET` | `/api/customers` | Authenticated | List customers (scoped for Customer users) |
| `POST` | `/api/customers` | Admin | Create customer |
| `PUT` | `/api/customers/{id}` | Admin | Rename or activate/deactivate customer |
| `DELETE` | `/api/customers/{id}` | Admin | Delete customer (returns `409` if regions or reports exist) |
| `GET` | `/api/regions` | Authenticated | List regions (`?customer_id=`) |
| `POST` | `/api/regions` | Admin | Create region under a customer |
| `PUT` | `/api/regions/{id}` | Admin | Rename or activate/deactivate region |
| `DELETE` | `/api/regions/{id}` | Admin | Delete region (`409` if zones or reports exist) |
| `GET` | `/api/zones` | Authenticated | List zones (`?customer_id=&region_id=`) |
| `POST` | `/api/zones` | Admin | Create zone under a region |
| `PUT` | `/api/zones/{id}` | Admin | Rename or activate/deactivate zone |
| `DELETE` | `/api/zones/{id}` | Admin | Delete zone (`409` if uploaded/merged reports exist) |

---

## 3. Pole Survey & Lamp Installation Source Reports

Identical route structure under `/api/pole-survey` and `/api/lamp-installation`:

| Method | Endpoint | Access | Description |
| --- | --- | --- | --- |
| `POST` | `/api/{module}/upload` | Admin | Multipart form upload (`customer_id`, `region_id`, `zone_id`, `replace_existing`, `file` `.xlsx`/`.xls`). Creates new version and marks zone Merged Report `outdated`. Returns `409` if file exists and `replace_existing=false`. |
| `GET` | `/api/{module}` | Authenticated | List reports (`?customer_id=&region_id=&zone_id=`) |
| `GET` | `/api/{module}/{id}` | Authenticated | Get report metadata & version history |
| `GET` | `/api/{module}/{id}/preview` | Authenticated | Paginated, searchable, column-filterable workbook preview (`?version=&sheet_name=&header_row_index=&search=&filter_column=&filter_value=&page=&page_size=`) |
| `GET` | `/api/{module}/{id}/download` | Authenticated | Authorized workbook download (`?version=` restricted to Admin for historical versions) |
| `DELETE` | `/api/{module}/{id}` | Admin | Soft-deletes active file and marks zone Merged Report `outdated` |

---

## 4. Merged Reports & Reconciliation Engine

| Method | Endpoint | Access | Description |
| --- | --- | --- | --- |
| `GET` | `/api/merged-reports/inspect` | Admin | Inspects zone's active Pole Survey + Lamp Installation sheets, headers, suggested & saved mappings, and blocking errors (`?customer_id=&region_id=&zone_id=&pole_sheet=&pole_header_row=&lamp_sheet=&lamp_header_row=`) |
| `POST` | `/api/merged-reports/generate` | Admin | Executes zone-isolated LED reconciliation, writes formatted `.xlsx` preserving Lamp Installation master template, stores 6-tab JSON snapshot, logs metrics to `processing_logs`, optionally saves column mappings |
| `GET` | `/api/merged-reports` | Authenticated | Lists Merged Reports (Customers see only `published` reports in authorized customers) |
| `GET` | `/api/merged-reports/{id}` | Authenticated | Detailed Merged Report metadata & version list (`403` for Customers on unpublished drafts) |
| `GET` | `/api/merged-reports/{id}/preview` | Authenticated | Returns 6-tab inspection payload (`summary`, `existing_lamp_records`, `newly_added_records`, `skipped_existing_records`, `duplicate_records`, `invalid_records`, `unknown_lamp_types`) |
| `POST` | `/api/merged-reports/{id}/publish` | Admin | Publishes current Merged Report version for Customer access |
| `GET` | `/api/merged-reports/{id}/download` | Authenticated | Downloads formatted Merged `.xlsx` workbook |

---

## 5. Dashboards, External Links & Administration

| Method | Endpoint | Access | Description |
| --- | --- | --- | --- |
| `GET` | `/api/dashboard/admin` | Admin | KPI totals, recent uploads, recent merged reports, processing activity, regional availability |
| `GET` | `/api/dashboard/customer` | Authenticated | Customer-scoped counts, regional availability, recent available reports |
| `GET` | `/api/external-links` | Authenticated | Fetch `om_dashboard` & `energy_saving_report` configured links |
| `PUT` | `/api/external-links` | Admin | Update external URLs / enabled flags |
| `GET` | `/api/users` | Admin | List user accounts & customer permissions |
| `POST` | `/api/users` | Admin | Create Admin or Customer user account |
| `PUT` | `/api/users/{id}` | Admin | Update status, password, or assigned customer scopes |
| `GET` | `/api/led-rules` | Admin | List LED classification rules |
| `POST` | `/api/led-rules` | Admin | Add LED / non-LED classification rule |
| `PUT` | `/api/led-rules/{id}` | Admin | Update LED classification rule |
| `DELETE` | `/api/led-rules/{id}` | Admin | Remove LED classification rule |
| `GET` | `/api/upload-history` | Admin | Immutable version archive across Pole Survey & Lamp Installation (`?report_type=&limit=`) |
| `GET` | `/api/audit-logs` | Admin | Latest system audit trail entries (`?limit=`) |

