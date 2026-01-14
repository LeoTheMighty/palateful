"""Unit model for conversion."""

from decimal import Decimal

from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from utils.models.base import Base


class Unit(Base):
    """Unit model for ingredient measurement conversion."""

    __tablename__ = "units"

    # id, created_at, updated_at, archived_at inherited from Base
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    abbreviation: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)  # volume, weight, count, other
    to_base_factor: Mapped[Decimal] = mapped_column(Numeric(15, 6), nullable=False)
    base_unit: Mapped[str] = mapped_column(String, nullable=False)
