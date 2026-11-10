# SCHNELL – Electrical Asset Report Management Dashboard

Enterprise full-stack platform for managing region-, zone-, and ward-wise **Pole Survey Reports**, **Lamp Installation Reports**, and automated **Merged Reports** with strict Excel template formatting preservation, role-based access control, and configurable external portal links.

---

## Core Capabilities

- **4-Level Dynamic Hierarchy:** `Customer → Region → Zone → Ward → Reports` stored in PostgreSQL and extensible by administrators. The **Ward** is the lowest and sole operational level at which uploads, previews, and Merged Report reconciliation occur.
- **Role-Based Access Control (Backend-Enforced):**
  - **Admin:** Full management of customers, regions, zones, wards, user accounts, ward-level file uploads/replacements/deletions, column mappings, LED classification rules, Merged Report generation/publishing, external links, and audit logs.
  - **Customer:** Strictly read-only access scoped to assigned customers; can search/select wards and preview, filter, and download active source workbooks and published Merged Reports.
- **Ward-Isolated Merged Report Reconciliation Engine:**
  - Processes strictly within the selected `(customer, region, zone, ward)` — never mixing or comparing poles across wards even within the same zone.
  - Extracts `Pole Number`, `Arm Count`, and `Lamp Type` via saved/confirmed column mappings.
  - Identifies LED records case-insensitively and flags unknown lamp types for review.
  - Deduplicates Pole Survey LED poles within that ward (first occurrence kept) and assigns sequential `L1..Ln` positions **before** comparing against that ward's Lamp Installation, skipping existing poles without shifting sequence numbers.
  - Writes `OriginalPoleNumber-Ln` directly into the existing **Pole Number** cell while preserving original Lamp Installation sheets, styles, borders, widths, heights, freeze panes, filters, print setup, and formulas per ward.
- **Persistent Versioned Storage:** Ward-scoped source files and generated Merged Reports are stored safely outside temp folders (`customer_<id>/region_<id>/zone_<id>/ward_<id>/`) with immutable version history and per-ward stale report detection.

---

## Tech Stack

- **Frontend:** React 18, Vite, TypeScript, Tailwind CSS, Lucide React, Axios, React Router v6
- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2, OpenPyXL, Pandas, PyJWT, bcrypt
- **Database:** PostgreSQL

---

## Quick Start (Local Development)

### 1. Environment Configuration
Copy `.env.example` to `.env` and review database/seed settings:
```bash
cp .env.example .env
```

### 2. Start PostgreSQL
Using Docker Compose:
```bash
docker compose up -d postgres
```
*(Or point `DATABASE_URL` in `.env` to a local PostgreSQL 16/18 instance.)*

### 3. Run Database Migrations & Initial Seed
```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
python app/database/cli_seed.py
```

Default seeded sample hierarchy (**57 individual wards across 7 zones**):
- Customer: `Bangalore (BBMP)`
- Region `BOMMANAHALLI`:
  - `Bommanahalli (BMH)` → `W202`–`W212` (11 wards)
- Region `EAST`:
  - `CV Raman Nagar (CVRN)` → `W108`–`W115` (8 wards)
  - `Hebbal (HEB)` → `W61`–`W68` (8 wards)
  - `Pulakeshi Nagar (PN)` → `W69`–`W75` (7 wards)
  - `Sarvagna Nagar (SN)` → `W76`–`W85` (10 wards)
  - `Shanthi Nagar (SNTR)` → `W166`–`W172` (7 wards)
  - `Sivaji Nagar (SVJR)` → `W116`–`W121` (6 wards)

### 4. Start Backend API
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

### 5. Start Frontend Dashboard
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173`.

---

## Running Automated Tests

Ensure PostgreSQL is running and `TEST_DATABASE_URL` points to your test database (default `postgresql+psycopg://postgres@127.0.0.1:5432/schnell_reports_test`):

```bash
python -m pytest tests/backend -v
```

---

## Documentation

- [Architecture Overview](docs/architecture.md)
- [Database Schema](docs/database.md)
- [API Reference](docs/api.md)
- [Render Deployment & Backup Guide](docs/deployment.md)
- [User Guide](docs/user-guide.md)

