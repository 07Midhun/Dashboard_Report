from contextlib import contextmanager
from pathlib import Path
import shutil
from typing import Iterator
from uuid import uuid4

from fastapi import HTTPException, status

from app.core.config import settings


class StorageService:
    """
    Persistent file storage abstraction storing files outside OS temp folders
    with deterministic hierarchy paths and safe temporary processing workspaces.
    """

    def __init__(self, root: Path | None = None, temp_root: Path | None = None) -> None:
        self.root = (root or settings.storage_root).resolve()
        self.temp_root = (temp_root or settings.temp_processing_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.temp_root.mkdir(parents=True, exist_ok=True)

    def _resolve_relative(self, relative_path: str) -> Path:
        candidate = (self.root / relative_path).resolve()
        if self.root != candidate and self.root not in candidate.parents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid storage path reference.",
            )
        return candidate

    def save_report_bytes(
        self,
        *,
        customer_id: int,
        region_id: int,
        zone_id: int,
        ward_id: int,
        category: str,
        version: int,
        extension: str,
        content: bytes,
    ) -> str:
        rel_dir = (
            Path("customers")
            / str(customer_id)
            / "regions"
            / str(region_id)
            / "zones"
            / str(zone_id)
            / "wards"
            / str(ward_id)
            / category
        )
        target_dir = self._resolve_relative(str(rel_dir))
        target_dir.mkdir(parents=True, exist_ok=True)

        unique_name = f"v{version}_{uuid4().hex[:12]}{extension}"
        rel_path = rel_dir / unique_name
        abs_path = self._resolve_relative(str(rel_path))
        abs_path.write_bytes(content)
        return rel_path.as_posix()

    def save_json_bytes(
        self,
        *,
        customer_id: int,
        region_id: int,
        zone_id: int,
        ward_id: int,
        category: str,
        version: int,
        content: bytes,
    ) -> str:
        return self.save_report_bytes(
            customer_id=customer_id,
            region_id=region_id,
            zone_id=zone_id,
            ward_id=ward_id,
            category=category,
            version=version,
            extension=".json",
            content=content,
        )

    def get_absolute_path(self, relative_path: str) -> Path:
        abs_path = self._resolve_relative(relative_path)
        if not abs_path.exists() or not abs_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Stored report file could not be found on persistent storage.",
            )
        return abs_path

    def copy_temp_file_to_storage(
        self,
        *,
        src_path: Path,
        customer_id: int,
        region_id: int,
        zone_id: int,
        ward_id: int,
        category: str,
        version: int,
        extension: str,
    ) -> tuple[str, int]:
        rel_dir = (
            Path("customers")
            / str(customer_id)
            / "regions"
            / str(region_id)
            / "zones"
            / str(zone_id)
            / "wards"
            / str(ward_id)
            / category
        )
        target_dir = self._resolve_relative(str(rel_dir))
        target_dir.mkdir(parents=True, exist_ok=True)

        unique_name = f"v{version}_{uuid4().hex[:12]}{extension}"
        rel_path = rel_dir / unique_name
        abs_path = self._resolve_relative(str(rel_path))
        shutil.copy2(src_path, abs_path)
        return rel_path.as_posix(), abs_path.stat().st_size

    @contextmanager
    def temp_workspace(self) -> Iterator[Path]:
        self.temp_root.mkdir(parents=True, exist_ok=True)
        work_dir = self.temp_root / f"job_{uuid4().hex}"
        work_dir.mkdir(parents=True, exist_ok=True)
        try:
            yield work_dir
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)


storage_service = StorageService()

