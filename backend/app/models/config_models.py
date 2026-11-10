from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, utcnow


class ColumnMapping(Base, TimestampMixin):
    __tablename__ = "column_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=True
    )
    report_type: Mapped[str] = mapped_column(String(32), nullable=False)  # pole_survey | lamp_installation
    header_signature_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    sheet_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    header_row_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    mapping_config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "customer_id",
            "report_type",
            "header_signature_hash",
            name="uq_column_mapping_signature",
        ),
        Index("ix_column_mappings_lookup", "report_type", "header_signature_hash"),
    )


class LedClassificationRule(Base):
    __tablename__ = "led_classification_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pattern: Mapped[str] = mapped_column(String(150), nullable=False)
    match_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="contains"
    )  # exact | prefix | contains | regex
    classification: Mapped[str] = mapped_column(String(32), nullable=False)  # led | non_led
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("pattern", "match_type", name="uq_led_rule_pattern_type"),
    )


class ExternalLink(Base):
    __tablename__ = "external_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    link_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    link_name: Mapped[str] = mapped_column(String(120), nullable=False)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    __table_args__ = (
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
        Index("ix_audit_logs_user_created", "user_id", "created_at"),
    )

