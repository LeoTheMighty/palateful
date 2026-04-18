"""UnitAlias model — freeform-string → canonical-unit lookup.

Powers `normalize_unit_display` so every write path can coerce LLM- or
user-typed unit strings ("tablespoon", "Tbsp.", "grams") to the canonical
token set the rest of the app uses ("tbsp", "g", …). See riip-1 / riip-2.
"""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from utils.models.joins_base import JoinsBase


class UnitAlias(JoinsBase):
    """Map a freeform unit string to its canonical `units.name` token."""

    __tablename__ = "unit_aliases"

    # created_at / updated_at / archived_at inherited from JoinsBase.
    alias: Mapped[str] = mapped_column(String(80), primary_key=True)
    canonical_unit: Mapped[str] = mapped_column(
        String(32), ForeignKey("units.name", ondelete="RESTRICT"), nullable=False
    )
