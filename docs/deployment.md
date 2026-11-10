# Deployment, Storage & Backup Guide (Render)

## 1. Render Services Blueprint

`render.yaml` at the repository root defines a complete Render Blueprint deployment:

1. **PostgreSQL (`schnell-asset-reports-db`)**
   - Managed PostgreSQL instance holding hierarchy metadata, users/permissions, file version metadata, saved column mappings, LED rules, processing logs, and audit logs.
2. **Backend Web Service (`schnell-asset-reports-api`)**
   - Root directory: `backend`
   - Build command: `pip install -r requirements.txt`
   - Pre-deploy command: `alembic upgrade head && python app/database/cli_seed.py`
   - Start command: `gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
   - Persistent Disk (`schnell-excel-storage`): mounted at `/var/data/schnell_storage` (`STORAGE_ROOT=/var/data/schnell_storage`, `TEMP_PROCESSING_DIR=/var/data/schnell_storage/_tmp`) so uploaded source files and generated Merged Reports survive service restarts and redeployments.
   - Health check endpoint: `/api/health`
3. **Frontend Static Site (`schnell-asset-reports`)**
   - Root directory: `frontend`
   - Build command: `npm install && npm run build`
   - Publish path: `dist`
   - SPA Rewrite Rule: `/* -> /index.html`

---

## 2. Production Environment Variables

Configure these values on Render before the first production deploy:

### Backend (`schnell-asset-reports-api`)
- `APP_ENV=production`
- `DEBUG=false`
- `DATABASE_URL` (automatically injected from Render PostgreSQL `connectionString`)
- `JWT_SECRET_KEY` (generated securely by Render)
- `STORAGE_ROOT=/var/data/schnell_storage`
- `TEMP_PROCESSING_DIR=/var/data/schnell_storage/_tmp`
- `MAX_UPLOAD_SIZE_MB=25`
- `CORS_ORIGINS=https://<your-frontend-service>.onrender.com`
- `SEED_DEFAULT_DATA=true`
- `SEED_ADMIN_EMAIL=<your-admin-email>`
- `SEED_ADMIN_PASSWORD=<strong-production-password>`

### Frontend (`schnell-asset-reports`)
- `VITE_API_BASE_URL=https://<your-backend-service>.onrender.com/api`

---

## 3. PostgreSQL Backup & Restore Procedures

### Manual Logical Backup (`pg_dump`)
```bash
pg_dump "$DATABASE_URL" --format=custom --no-owner --file="schnell_backup_$(date +%Y%m%d_%H%M%S).dump"
```

### Restore Backup (`pg_restore`)
```bash
pg_restore --dbname="$DATABASE_URL" --clean --if-exists --no-owner schnell_backup_YYYYMMDD_HHMMSS.dump
```

---

## 4. Excel File Storage Backup & Recovery

All uploaded source Excel workbooks and generated Merged Reports + preview JSON snapshots live under `STORAGE_ROOT` organized deterministically as:

```text
<STORAGE_ROOT>/
  ├── customer_<id>/
  │     └── region_<id>/
  │           └── zone_<id>/
  │                 ├── pole_survey/v1.xlsx
  │                 ├── lamp_installation/v1.xlsx
  │                 ├── merged_reports/v1.xlsx
  │                 └── merged_previews/v1.json
  └── _tmp/
```

To back up both PostgreSQL metadata and physical Excel files consistently:
1. Enable **Render Disk Snapshots** (scheduled daily) on `schnell-excel-storage` **or** periodically archive `/var/data/schnell_storage` (excluding `_tmp`) to encrypted object storage.
2. Pair storage snapshots with Render PostgreSQL daily backups so `report_files.storage_path` and `merged_reports.generated_file_path` remain synchronized with disk contents.

---

## 5. Production Pre-Flight Checklist

- Change default seed passwords (`SEED_ADMIN_PASSWORD`, `SEED_CUSTOMER_USER_PASSWORD`) or disable sample customer seeding before opening to external users.
- Ensure `CORS_ORIGINS` strictly lists the deployed frontend HTTPS origin (no wildcard `*` when `allow_credentials=true`).
- Confirm `O&M Dashboard` and `Energy Saving Report` URLs under **Settings** use `https://` URLs.
- Keep **Workers** reasonable (`2`–`4`) on the persistent disk since Render Persistent Disk is attached to a single service instance (multi-instance scaling requires shared S3-compatible object storage).

