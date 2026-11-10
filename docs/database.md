# Database Schema & Migration Guide

## 1. Entity Relationship Overview

```text
customers 1──* regions 1──* zones 1──* wards
    │            │            │         │
    │            └────────────┴─────────┼──* report_files 1──* report_file_versions
    │                                   │
    │                                   └──* merged_reports 1──* merged_report_versions
    │                                               │
    │                                               └──* processing_logs
    │
    ├──* user_customer_permissions *──1 users
    └──* column_mappings
```

Supporting operational & governance tables:
- `revoked_tokens`: Stores logged-out JWT `jti` identifiers until token expiry so explicit logout invalidates bearer tokens immediately across stateless workers.
- `led_classification_rules`: Configurable case-insensitive rules (`exact`, `prefix`, `contains`, `word`, `regex`) mapping lamp type patterns to `led` or `non_led`.
- `external_links`: Configurable portal links for `om_dashboard` (O&M Dashboard) and `energy_saving_report` (Energy Saving Report).
- `audit_logs`: Chronological record of administrative and download events with user reference, action, target entity, JSON details, and client IP.

---

## 2. Core Tables & Constraints

| Table | Purpose | Key Constraints / Indexes |
| --- | --- | --- |
| `users` | Admin & Customer user accounts (`bcrypt` password hashes) | Unique `email`, unique nullable `username`, index `(role, status)` |
| `user_customer_permissions` | Scopes Customer users to authorized Customers | Unique `(user_id, customer_id)`, cascading delete |
| `revoked_tokens` | JWT revocation denylist | Unique `jti`, index `expires_at` |
| `customers` | Top-level customer organizations (e.g. `Bangalore (BBMP)`) | Unique `customer_name` |
| `regions` | Regions beneath each Customer (`BOMMANAHALLI`, `EAST`) | Unique `(customer_id, region_name)`, `ON DELETE RESTRICT` |
| `zones` | Reporting zones beneath each Region (with `zone_code`) | Unique `(region_id, zone_name)`, `ON DELETE RESTRICT` |
| `wards` | Reporting wards beneath each Zone (sole level for report uploads & merges) | Unique `(zone_id, ward_number)`, Unique `(zone_id, ward_code)`, `ON DELETE RESTRICT` |
| `report_files` | Active & soft-deleted source Excel workbooks (`pole_survey`, `lamp_installation`) per ward | Partial unique index `uq_active_report_file_ward_slot` on `(customer_id, region_id, zone_id, ward_id, report_type)` where `status = 'active'` |
| `report_file_versions` | Immutable upload archive preserving every historical version per ward | Unique `(report_file_id, version)`, nullable/indexed `ward_id` |
| `column_mappings` | Saved `(customer_id, report_type, header_signature_hash)` column mappings (JSONB) | Unique `(customer_id, report_type, header_signature_hash)` |
| `led_classification_rules` | Dynamic LED / non-LED pattern rules | Unique `(pattern, match_type)` |
| `merged_reports` | Latest ward-wise Merged Report state (`draft`, `published`, `outdated`, `failed`) | Unique `(customer_id, region_id, zone_id, ward_id)` (`uq_merged_report_ward_slot`) |
| `merged_report_versions` | Generated workbook & 6-tab JSON preview snapshot per Merged version | Unique `(merged_report_id, version)` |
| `processing_logs` | Per-run ward-level reconciliation metrics (`added_records`, `existing_records`, `duplicate_records`, etc.) | `ward_id` FK (`ON DELETE RESTRICT`), indexes `(merged_report_id, created_at)`, `(ward_id, created_at)`, and `(processing_status, created_at)` |
| `external_links` | Configurable external portal URLs | Unique `link_key` |
| `audit_logs` | Security & operational audit trail | Indexes `(entity_type, entity_id)` and `(user_id, created_at)` |

---

## 3. Referential & Delete Protection

- `regions.customer_id`, `zones.region_id`, `wards.zone_id`, `report_files.*`, `merged_reports.*`, and `processing_logs.ward_id` use `ON DELETE RESTRICT` at the database level **and** explicit pre-delete validation in `hierarchy_service.py` returning HTTP `409 Conflict` when child entities or uploaded/merged reports exist.
- Deactivating a customer, region, zone, or ward sets `status = 'inactive'`, hiding it from Customer portals while preserving historical files and audit trails.

---

## 4. Alembic Migrations & Initial Seeding

```bash
cd backend
alembic upgrade head
python app/database/cli_seed.py
```

Generating a new migration after model edits:
```bash
cd backend
alembic revision --autogenerate -m "describe_change"
alembic upgrade head
```

Note: `seed_initial_data()` is idempotent and safe to run on every deploy (`SEED_DEFAULT_DATA=true`). It ensures the seed Admin account, sample `Bangalore (BBMP)` hierarchy (`BOMMANAHALLI` + `EAST` with 7 zones and 57 individual wards), sample read-only Customer account, default LED classification rules, and `external_links` placeholders exist without overwriting existing records.

