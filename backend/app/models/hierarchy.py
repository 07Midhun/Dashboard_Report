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
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")

    customer: Mapped["Customer"] = relationship(back_populates="regions")
    zones: Mapped[list["Zone"]] = relationship(
        back_populates="region", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("customer_id", "region_name", name="uq_regions_customer_region_name"),
        Index("ix_regions_customer_id", "customer_id"),
    )


class Zone(Base, TimestampMixin):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    region_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("regions.id", ondelete="RESTRICT"), nullable=False
    )
    zone_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")

    region: Mapped["Region"] = relationship(back_populates="zones")

    __table_args__ = (
        UniqueConstraint("region_id", "zone_name", name="uq_zones_region_zone_name"),
        Index("ix_zones_region_id", "region_id"),
    )

