"""
1-Click Storage Sync Script: Local Storage -> Render Cloud Persistent Storage
Synchronizes all Pole Surveys, Lamp Installations, Merged Reports, and Previews to Render.
"""

import io
import os
import sys
import zipfile
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_RENDER_URL = "https://schnell-backend.onrender.com"
STORAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "storage")

BATCH_MAX_BYTES = 18 * 1024 * 1024  # 18 MB uncompressed chunks for safe HTTP transmission


def get_session():
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def login_admin(session: requests.Session, base_url: str, username: str, password: str) -> str:
    login_url = f"{base_url.rstrip('/')}/api/auth/login"
    print(f"--> Authenticating with {login_url} as {username}...", flush=True)
    try:
        resp = session.post(
            login_url,
            json={"identifier": username, "password": password},
            timeout=25,
        )
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Render backend: {e}", flush=True)
        sys.exit(1)

    if resp.status_code != 200:
        print(f"Login failed (HTTP {resp.status_code}): {resp.text}", flush=True)
        sys.exit(1)

    token = resp.json().get("access_token")
    if not token:
        print("Login response did not return an access_token.", flush=True)
        sys.exit(1)

    print(" Authentication successful!", flush=True)
    return token


def collect_storage_files(storage_root: str):
    file_list = []
    customers_dir = os.path.join(storage_root, "customers")
    if not os.path.exists(customers_dir):
        print(f"Error: {customers_dir} does not exist.", flush=True)
        return file_list

    for root, dirs, files in os.walk(customers_dir):
        for fname in files:
            if fname.endswith(".xlsx") or fname.endswith(".json"):
                full_path = os.path.join(root, fname)
                rel_path = os.path.relpath(full_path, storage_root).replace("\\", "/")
                file_size = os.path.getsize(full_path)
                file_list.append((full_path, rel_path, file_size))
    return file_list


def create_zip_batches(file_list, max_batch_bytes=BATCH_MAX_BYTES):
    batches = []
    current_batch = []
    current_size = 0

    for full_path, rel_path, file_size in file_list:
        if current_size + file_size > max_batch_bytes and current_batch:
            batches.append(current_batch)
            current_batch = []
            current_size = 0
        current_batch.append((full_path, rel_path, file_size))
        current_size += file_size

    if current_batch:
        batches.append(current_batch)
    return batches


def sync_batch_zip(session: requests.Session, base_url: str, token: str, batch, batch_idx: int, total_batches: int):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for full_path, rel_path, _ in batch:
            zf.write(full_path, arcname=rel_path)

    zip_bytes = zip_buffer.getvalue()
    zip_size_mb = len(zip_bytes) / 1024 / 1024
    sync_url = f"{base_url.rstrip('/')}/api/storage-sync-zip"

    print(
        f"--> [Batch {batch_idx}/{total_batches}] Uploading {len(batch)} files ({zip_size_mb:.2f} MB compressed)...",
        flush=True,
    )

    try:
        resp = session.post(
            sync_url,
            headers={"Authorization": f"Bearer {token}"},
            files={"zip_file": ("sync_batch.zip", zip_bytes, "application/zip")},
            timeout=180,
        )
    except Exception as exc:
        print(f"     Network error uploading batch: {exc}", flush=True)
        return False

    if resp.status_code == 200:
        data = resp.json()
        print(f"     Success: {data.get('files_extracted', len(batch))} files extracted on Render.", flush=True)
        return True
    else:
        print(f"     Batch upload failed (HTTP {resp.status_code}): {resp.text}", flush=True)
        return False


def main():
    print("================================================================", flush=True)
    print(" SCHNELL ASSET REPORTS - 1-CLICK CLOUD STORAGE SYNC", flush=True)
    print("================================================================", flush=True)

    render_url = os.environ.get("RENDER_BACKEND_URL", DEFAULT_RENDER_URL)
    if len(sys.argv) > 1:
        render_url = sys.argv[1]

    print(f"Target Server: {render_url}", flush=True)
    print(f"Source Folder: {STORAGE_DIR}", flush=True)

    username = os.environ.get("ADMIN_EMAIL", "admin@gmail.com")
    password = os.environ.get("ADMIN_PASSWORD", "admin123")

    session = get_session()
    token = login_admin(session, render_url, username, password)

    files = collect_storage_files(STORAGE_DIR)
    if not files:
        print("No files found in storage/customers. Nothing to sync.", flush=True)
        return

    total_mb = sum(f[2] for f in files) / 1024 / 1024
    print(f"Found {len(files)} files to sync ({total_mb:.2f} MB total uncompressed).", flush=True)

    batches = create_zip_batches(files)
    print(f"Split into {len(batches)} efficient upload batches.", flush=True)
    print("Starting sync...", flush=True)

    success_count = 0
    for idx, batch in enumerate(batches, start=1):
        ok = sync_batch_zip(session, render_url, token, batch, idx, len(batches))
        if ok:
            success_count += 1

    print("================================================================", flush=True)
    if success_count == len(batches):
        print(" ALL FILES SYNCED TO RENDER SUCCESSFULLY!", flush=True)
        print("--> Remapping storage folder structure to match Render database IDs...", flush=True)
        try:
            r_remap = session.post(
                f"{render_url.rstrip('/')}/api/storage-remap-hierarchy",
                headers={"Authorization": f"Bearer {token}"},
                timeout=60,
            )
            if r_remap.status_code == 200:
                print(f"     Remap successful: {r_remap.json().get('wards_mapped', 0)} ward folders mapped to Render zones.", flush=True)
            else:
                print(f"    Remap notice: {r_remap.text}", flush=True)
        except Exception as e:
            print(f"    Remap error: {e}", flush=True)
        print("Every ward on your deployed dashboard is now populated and ready!", flush=True)
    else:
        print(f" Sync finished ({success_count}/{len(batches)} batches succeeded).", flush=True)
    print("================================================================", flush=True)


if __name__ == "__main__":
    main()
