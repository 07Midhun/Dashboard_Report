import hashlib
from pathlib import Path
import re
from fastapi import HTTPException, status

from app.core.config import settings


ALLOWED_EXTENSIONS = {".xlsx", ".xls"}
XLSX_MAGIC = b"PK\x03\x04"
XLS_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(filename: str) -> str:
    base = Path(filename or "report.xlsx").name.strip()
    cleaned = _SAFE_NAME_RE.sub("_", base)
    return cleaned or "report.xlsx"


def validate_excel_upload(filename: str, content: bytes) -> tuple[str, str, str]:
    """
    Validate extension, file size, and magic header bytes.
    Returns (sanitized_filename, extension, sha256_hex).
    """
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file name provided.",
        )

    safe_name = sanitize_filename(filename)
    ext = Path(safe_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext or 'unknown'}'. Please upload a valid .xlsx or .xls Excel workbook.",
        )

    size = len(content)
    if size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded Excel file is empty.",
        )

    if size > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the maximum allowed size of {settings.max_upload_size_mb} MB.",
        )

    if ext == ".xlsx" and not content.startswith(XLSX_MAGIC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or corrupted .xlsx file (file signature mismatch).",
        )

    if ext == ".xls" and not content.startswith(XLS_MAGIC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or corrupted .xls file (file signature mismatch).",
        )

    sha256_hex = hashlib.sha256(content).hexdigest()
    return safe_name, ext, sha256_hex

