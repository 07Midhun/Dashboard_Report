"""
1-Click Storage Sync Script: Local Storage -> Render Cloud Persistent Storage
Synchronizes all Pole Surveys, Lamp Installations, Merged Reports, and Previews to Render.
"""

import io
import os
import sys
import zipfile
import requests

DEFAULT_RENDER_URL = "https://schnell-backend.onrender.com"
STORAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "storage")

BATCH_MAX_BYTES = 18 * 1024 * 1024  # 18 MB uncompressed chunks for safe HTTP transmission


def login_admin(base_url: str, username: str, password: str) -> str:
    login_url = f"{base_url.rstrip('/')}/api/auth/login"
    print(f"--> Authenticating with {login_url} as {username}...")
    try:
        resp = requests.post(
            login_url,
            data={"username": username, "password": password},
            timeout=25,
        )
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Render backend: {e}")
        sys.exit(1)

    if resp.status_code != 200:
        print(f"Login failed (HTTP {resp.status_code}): {resp.text}")
        sys.exit(1)

    token = resp.json().get("access_token")
    if not token:
        print("Login response did not return an access_token.")
        sys.exit(1)

    print(" Authentication successful!")
    return token


def collect_storage_files(storage_root: str):
    file_list = []
    customers_dir = os.path.join(storage_root, "customers")
    if not os.path.exists(customers_dir):
        print(f"Error: {customers_dir} does not exist.")
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


def sync_batch_zip(base_url: str, token: str, batch, batch_idx: int, total_batches: int):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for full_path, rel_path, _ in batch:
            zf.write(full_path, arcname=rel_path)

    zip_bytes = zip_buffer.getvalue()
    zip_size_mb = len(zip_bytes) / 1024 / 1024
    sync_url = f"{base_url.rstrip('/')}/api/admin/storage-sync-zip"

    print(
        f"--> [Batch {batch_idx}/{total_batches}] Uploading {len(batch)} files ({zip_size_mb:.2f} MB compressed)..."
    )

    resp = requests.post(
        sync_url,
        headers={"Authorization": f"Bearer {token}"},
        files={"zip_file": ("sync_batch.zip", zip_bytes, "application/zip")},
        timeout=180,
    )

    if resp.status_code == 200:
        data = resp.json()
        print(f"     Success: {data.get('files_extracted', len(batch))} files extracted on Render.")
        return True
    else:
        print(f"     Batch upload failed (HTTP {resp.status_code}): {resp.text}")
        print("    Falling back to individual file sync for this batch...")
        return sync_batch_individual(base_url, token, batch)


def sync_batch_individual(base_url: str, token: str, batch):
    sync_file_url = f"{base_url.rstrip('/')}/api/admin/storage-sync-file"
    all_ok = True
    for full_path, rel_path, _ in batch:
        with open(full_path, "rb") as f:
            content = f.read()
        resp = requests.post(
            sync_file_url,
            headers={"Authorization": f"Bearer {token}"},
            data={"relative_path": rel_path},
            files={"file": (os.path.basename(rel_path), content)},
            timeout=60,
        )
        if resp.status_code == 200:
            print(f"     Uploaded: {rel_path}")
        else:
            print(f"     Failed: {rel_path} (HTTP {resp.status_code})")
            all_ok = False
    return all_ok


def main():
    print("================================================================")
    print(" SCHNELL ASSET REPORTS - 1-CLICK CLOUD STORAGE SYNC")
    print("================================================================")

    render_url = os.environ.get("RENDER_BACKEND_URL", DEFAULT_RENDER_URL)
    if len(sys.argv) > 1:
        render_url = sys.argv[1]

    print(f"Target Server: {render_url}")
    print(f"Source Folder: {STORAGE_DIR}")

    username = os.environ.get("ADMIN_EMAIL", "admin@gmail.com")
    password = os.environ.get("ADMIN_PASSWORD", "admin123")

    token = login_admin(render_url, username, password)

    files = collect_storage_files(STORAGE_DIR)
    if not files:
        print("No files found in storage/customers. Nothing to sync.")
        return

    total_mb = sum(f[2] for f in files) / 1024 / 1024
    print(f"Found {len(files)} files to sync ({total_mb:.2f} MB total uncompressed).")

    batches = create_zip_batches(files)
    print(f"Split into {len(batches)} efficient upload batches.")
    print("Starting sync...")

    success_count = 0
    for idx, batch in enumerate(batches, start=1):
        ok = sync_batch_zip(render_url, token, batch, idx, len(batches))
        if ok:
            success_count += 1

    print("================================================================")
    if success_count == len(batches):
        print(" ALL FILES SYNCED TO RENDER SUCCESSFULLY!")
        print("Every ward on your deployed dashboard is now populated and ready!")
    else:
        print(f" Sync finished with some warnings ({success_count}/{len(batches)} batches succeeded).")
    print("================================================================")


if __name__ == "__main__":
    main()
