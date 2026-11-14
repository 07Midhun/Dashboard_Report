from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")

    regions: Mapped[list["Region"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )
    user_permissions: Mapped[list["UserCustomerPermission"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )


class Region(Base, TimestampMixin):
    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    region_name: Mapped[str] = mapped_column(String(200), nullable=False)
    region_code: Mapped[str] = mapped_column(String(32), nullable=False)
    corporation: Mapped[str] = mapped_column(
        String(100), nullable=False, default="BBMP", server_default="BBMP"
    )
    division: Mapped[str | None] = mapped_column(
        String(100), nullable=True, default="", server_default=""
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")

    customer: Mapped["Customer"] = relationship(back_populates="regions")
    zones: Mapped[list["Zone"]] = relationship(
        back_populates="region", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("customer_id", "region_name", name="uq_regions_customer_region_name"),
        Index("ix_regions_customer_id", "customer_id"),
        Index("ix_regions_region_code", "region_code"),
    )


class Zone(Base, TimestampMixin):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    region_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("regions.id", ondelete="RESTRICT"), nullable=False
    )
    zone_name: Mapped[str] = mapped_column(String(200), nullable=False)
    zone_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")

    region: Mapped["Region"] = relationship(back_populates="zones")
    wards: Mapped[list["Ward"]] = relationship(
        back_populates="zone", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("region_id", "zone_name", name="uq_zones_region_zone_name"),
        Index("ix_zones_region_id", "region_id"),
    )


class Ward(Base, TimestampMixin):
    __tablename__ = "wards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    zone_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("zones.id", ondelete="RESTRICT"), nullable=False
    )
    ward_name: Mapped[str] = mapped_column(String(200), nullable=False)
    ward_number: Mapped[str] = mapped_column(String(64), nullable=False)
    ward_code: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")

    zone: Mapped["Zone"] = relationship(back_populates="wards")

    __table_args__ = (
        UniqueConstraint("zone_id", "ward_number", name="uq_wards_zone_ward_number"),
        UniqueConstraint("zone_id", "ward_code", name="uq_wards_zone_ward_code"),
        Index("ix_wards_zone_id", "zone_id"),
    )

