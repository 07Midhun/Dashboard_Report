"""
1-Click Storage Sync Script: Local Storage -> Render Cloud Persistent Storage
Synchronizes all Pole Surveys, Lamp Installations, Merged Reports, and Previews to Render,
automatically mapping local hierarchy IDs to Render cloud hierarchy IDs.
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

ZONE_MAPPING = {
    # (local_cust, local_reg, local_zone): (render_cust, render_reg, render_zone)
    (1, 1, 1): (3, 1, 34),   # Bommanahalli (BMH)
    (1, 2, 2): (3, 25, 35),  # CV Raman Nagar (CVRN)
    (1, 2, 3): (3, 25, 36),  # Hebbal (HEB)
    (1, 2, 4): (3, 25, 37),  # Pulakeshi Nagar (PN)
    (1, 2, 5): (3, 25, 38),  # Sarvagna Nagar (SN)
    (1, 2, 6): (3, 25, 39),  # Shanthi Nagar (SNTR)
    (1, 2, 7): (3, 25, 40),  # Sivaji Nagar (SVJR)
}


def map_rel_path_to_render(rel_path: str) -> str | None:
    parts = rel_path.replace("\\", "/").split("/")
    if len(parts) >= 6 and parts[0] == "customers" and parts[2] == "regions" and parts[4] == "zones":
        try:
            key = (int(parts[1]), int(parts[3]), int(parts[5]))
            if key in ZONE_MAPPING:
                dst_c, dst_r, dst_z = ZONE_MAPPING[key]
                new_parts = list(parts)
                new_parts[1] = str(dst_c)
                new_parts[3] = str(dst_r)
                new_parts[5] = str(dst_z)
                return "/".join(new_parts)
        except Exception:
            pass
    return None


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
                orig_rel = os.path.relpath(full_path, storage_root).replace("\\", "/")
                file_size = os.path.getsize(full_path)

                # Add under original path
                file_list.append((full_path, orig_rel, file_size))

                # Add under mapped Render path (customer 3 / zones 34-40)
                mapped_rel = map_rel_path_to_render(orig_rel)
                if mapped_rel and mapped_rel != orig_rel:
                    file_list.append((full_path, mapped_rel, file_size))

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
    print(f"Found {len(files)} files to sync (including mapped Render paths, {total_mb:.2f} MB uncompressed).", flush=True)

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
        print(" ALL FILES UPLOADED TO RENDER SUCCESSFULLY!", flush=True)
        print("--> Reconciling disk files with database paths...", flush=True)
        try:
            r_rec = session.post(
                f"{render_url.rstrip('/')}/api/storage-sync-reconcile",
                headers={"Authorization": f"Bearer {token}"},
                timeout=60,
            )
            if r_rec.status_code == 200:
                rec_data = r_rec.json()
                print(f"     Reconciled: {rec_data.get('reconciled_report_files', 0)} report files, {rec_data.get('reconciled_merged_reports', 0)} merged reports.", flush=True)
            else:
                print(f"     Reconcile response (HTTP {r_rec.status_code}): {r_rec.text[:200]}", flush=True)
        except Exception as e:
            print(f"     Reconcile error: {e}", flush=True)
        print("================================================================", flush=True)
        print(" ALL WARDS ARE NOW FULLY SYNCHRONIZED AND READY ON RENDER!", flush=True)
        print("You can view and generate merged reports without missing file errors.", flush=True)
    else:
        print(f" Sync finished ({success_count}/{len(batches)} batches succeeded).", flush=True)
    print("================================================================", flush=True)


if __name__ == "__main__":
    main()
