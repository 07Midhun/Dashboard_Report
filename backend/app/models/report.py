from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, utcnow


class ReportFile(Base):
    __tablename__ = "report_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    region_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("regions.id", ondelete="RESTRICT"), nullable=False
    )
    zone_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("zones.id", ondelete="RESTRICT"), nullable=False
    )
    ward_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("wards.id", ondelete="RESTRICT"), nullable=False
    )
    report_type: Mapped[str] = mapped_column(String(32), nullable=False)  # pole_survey | lamp_installation
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_extension: Mapped[str] = mapped_column(String(16), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    sheet_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    header_row_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")  # active | deleted
    uploaded_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    versions: Mapped[list["ReportFileVersion"]] = relationship(
        back_populates="report_file", cascade="all, delete-orphan", order_by="ReportFileVersion.version.desc()"
    )

    __table_args__ = (
        Index(
            "uq_active_report_file_slot",
            "customer_id",
            "region_id",
            "zone_id",
            "ward_id",
            "report_type",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_report_files_zone_type", "zone_id", "report_type"),
        Index("ix_report_files_ward_type", "ward_id", "report_type"),
        Index("ix_report_files_customer_id", "customer_id"),
    )


class ReportFileVersion(Base):
    __tablename__ = "report_file_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_file_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("report_files.id", ondelete="CASCADE"), nullable=False
    )
    ward_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("wards.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_extension: Mapped[str] = mapped_column(String(16), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    sheet_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    header_row_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    uploaded_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    report_file: Mapped["ReportFile"] = relationship(back_populates="versions")

    __table_args__ = (
        UniqueConstraint("report_file_id", "version", name="uq_report_file_version"),
        Index("ix_rfv_report_file_id", "report_file_id"),
        Index("ix_rfv_ward_id", "ward_id"),
    )


class MergedReport(Base):
    __tablename__ = "merged_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    region_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("regions.id", ondelete="RESTRICT"), nullable=False
    )
    zone_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("zones.id", ondelete="RESTRICT"), nullable=False
    )
    ward_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("wards.id", ondelete="RESTRICT"), nullable=False
    )
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft"
    )  # draft | published | outdated | failed
    generated_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_pole_survey_file_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("report_files.id", ondelete="SET NULL"), nullable=True
    )
    source_pole_survey_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_lamp_installation_file_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("report_files.id", ondelete="SET NULL"), nullable=True
    )
    source_lamp_installation_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generated_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    published_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    versions: Mapped[list["MergedReportVersion"]] = relationship(
        back_populates="merged_report", cascade="all, delete-orphan", order_by="MergedReportVersion.version.desc()"
    )
    processing_logs: Mapped[list["ProcessingLog"]] = relationship(
        back_populates="merged_report", cascade="all, delete-orphan", order_by="ProcessingLog.created_at.desc()"
    )

    __table_args__ = (
        UniqueConstraint("customer_id", "region_id", "zone_id", "ward_id", name="uq_merged_report_ward_slot"),
        Index("ix_merged_reports_ward_id", "ward_id"),
        Index("ix_merged_reports_status", "status"),
    )


class MergedReportVersion(Base):
    __tablename__ = "merged_report_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    merged_report_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("merged_reports.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    source_pole_survey_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_lamp_installation_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    preview_snapshot_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    generated_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    published_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    merged_report: Mapped["MergedReport"] = relationship(back_populates="versions")

    __table_args__ = (
        UniqueConstraint("merged_report_id", "version", name="uq_merged_report_version"),
        Index("ix_mrv_merged_report_id", "merged_report_id"),
    )


class ProcessingLog(Base):
    __tablename__ = "processing_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    merged_report_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("merged_reports.id", ondelete="CASCADE"), nullable=True
    )
    merged_report_version_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("merged_report_versions.id", ondelete="SET NULL"), nullable=True
    )
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    region_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("regions.id", ondelete="RESTRICT"), nullable=False
    )
    zone_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("zones.id", ondelete="RESTRICT"), nullable=False
    )
    ward_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("wards.id", ondelete="RESTRICT"), nullable=False
    )
    total_lamp_installation_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_survey_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_led_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_eligible_led_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    existing_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    added_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unknown_lamp_type_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    empty_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    final_merged_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warnings_json: Mapped[list | dict | None] = mapped_column(JSONB, nullable=True)
    processing_status: Mapped[str] = mapped_column(String(32), nullable=False)  # success | warning | failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    merged_report: Mapped["MergedReport | None"] = relationship(back_populates="processing_logs")

    __table_args__ = (
        Index("ix_processing_logs_merged_report_created", "merged_report_id", "created_at"),
        Index("ix_processing_logs_ward_created", "ward_id", "created_at"),
        Index("ix_processing_logs_status_created", "processing_status", "created_at"),
    )

