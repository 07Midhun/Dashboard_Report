<#
Convenience launcher for local Windows development of Schnell Dashboard.
Starts the local PostgreSQL 18 cluster (.pgdata\dev), FastAPI backend (port 8000),
and Vite frontend dev server (port 5173) in separate PowerShell windows.
#>

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $PSScriptRoot
$PgCtl = "C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe"
$PgData = Join-Path $RootDir ".pgdata\dev"
$PgLog = Join-Path $RootDir ".pgdata\dev.log"

if (Test-Path $PgCtl) {
    if (Test-Path $PgData) {
        $status = & $PgCtl -D $PgData status 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Starting local PostgreSQL dev cluster..." -ForegroundColor Cyan
            & $PgCtl -D $PgData -l $PgLog -o "-p 5432 -h 127.0.0.1" start
        } else {
            Write-Host "Local PostgreSQL cluster is already running." -ForegroundColor Green
        }
    } else {
        Write-Warning "PostgreSQL data directory $PgData not found. Ensure PostgreSQL is running on port 5432."
    }
}

Write-Host "Running Alembic migrations and idempotent database seed..." -ForegroundColor Cyan
Push-Location (Join-Path $RootDir "backend")
python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "Alembic upgrade failed." }
python app\database\cli_seed.py
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "Database seed failed." }
Pop-Location

Write-Host "Launching FastAPI backend on http://127.0.0.1:8000 ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$RootDir\backend'; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

Write-Host "Launching Vite frontend on http://127.0.0.1:5173 ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$RootDir\frontend'; npm run dev -- --host 127.0.0.1 --port 5173"

Write-Host "Schnell Dashboard services launched." -ForegroundColor Green

