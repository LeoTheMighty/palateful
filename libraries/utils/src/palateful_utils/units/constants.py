"""Unit definitions for cooking measurements."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

UnitType = Literal["volume", "weight", "count", "other"]


@dataclass(frozen=True)
class UnitDefinition:
    """Definition of a cooking measurement unit."""

    name: str
    abbreviations: tuple[str, ...]
    type: UnitType
    to_base: Decimal
    base_unit: str


# Volume units (base: ml)
VOLUME_UNITS: dict[str, UnitDefinition] = {
    "ml": UnitDefinition(
        name="milliliter",
        abbreviations=("ml", "milliliter"),
        type="volume",
        to_base=Decimal("1"),
        base_unit="ml",
    ),
    "l": UnitDefinition(
        name="liter",
        abbreviations=("l", "liter"),
        type="volume",
        to_base=Decimal("1000"),
        base_unit="ml",
    ),
    "tsp": UnitDefinition(
        name="teaspoon",
        abbreviations=("tsp", "teaspoon"),
        type="volume",
        to_base=Decimal("4.929"),
        base_unit="ml",
    ),
    "tbsp": UnitDefinition(
        name="tablespoon",
        abbreviations=("tbsp", "tablespoon"),
        type="volume",
        to_base=Decimal("14.787"),
        base_unit="ml",
    ),
    "cup": UnitDefinition(
        name="cup",
        abbreviations=("c", "cup", "cups"),
        type="volume",
        to_base=Decimal("236.588"),
        base_unit="ml",
    ),
    "floz": UnitDefinition(
        name="fluid ounce",
        abbreviations=("fl oz", "floz"),
        type="volume",
        to_base=Decimal("29.574"),
        base_unit="ml",
    ),
    "pint": UnitDefinition(
        name="pint",
        abbreviations=("pt", "pint"),
        type="volume",
        to_base=Decimal("473.176"),
        base_unit="ml",
    ),
    "quart": UnitDefinition(
        name="quart",
        abbreviations=("qt", "quart"),
        type="volume",
        to_base=Decimal("946.353"),
        base_unit="ml",
    ),
    "gallon": UnitDefinition(
        name="gallon",
        abbreviations=("gal", "gallon"),
        type="volume",
        to_base=Decimal("3785.41"),
        base_unit="ml",
    ),
}

# Weight units (base: g)
WEIGHT_UNITS: dict[str, UnitDefinition] = {
    "g": UnitDefinition(
        name="gram",
        abbreviations=("g", "gram"),
        type="weight",
        to_base=Decimal("1"),
        base_unit="g",
    ),
    "kg": UnitDefinition(
        name="kilogram",
        abbreviations=("kg", "kilogram"),
        type="weight",
        to_base=Decimal("1000"),
        base_unit="g",
    ),
    "oz": UnitDefinition(
        name="ounce",
        abbreviations=("oz", "ounce"),
        type="weight",
        to_base=Decimal("28.3495"),
        base_unit="g",
    ),
    "lb": UnitDefinition(
        name="pound",
        abbreviations=("lb", "lbs", "pound"),
        type="weight",
        to_base=Decimal("453.592"),
        base_unit="g",
    ),
}

# Count units (base: count)
COUNT_UNITS: dict[str, UnitDefinition] = {
    "count": UnitDefinition(
        name="count",
        abbreviations=("", "count", "piece", "each"),
        type="count",
        to_base=Decimal("1"),
        base_unit="count",
    ),
    "dozen": UnitDefinition(
        name="dozen",
        abbreviations=("dozen", "doz"),
        type="count",
        to_base=Decimal("12"),
        base_unit="count",
    ),
}

# Other units (not convertible)
OTHER_UNITS: dict[str, UnitDefinition] = {
    "pinch": UnitDefinition(
        name="pinch",
        abbreviations=("pinch",),
        type="other",
        to_base=Decimal("1"),
        base_unit="pinch",
    ),
    "bunch": UnitDefinition(
        name="bunch",
        abbreviations=("bunch",),
        type="other",
        to_base=Decimal("1"),
        base_unit="bunch",
    ),
    "clove": UnitDefinition(
        name="clove",
        abbreviations=("clove",),
        type="other",
        to_base=Decimal("1"),
        base_unit="clove",
    ),
    "sprig": UnitDefinition(
        name="sprig",
        abbreviations=("sprig",),
        type="other",
        to_base=Decimal("1"),
        base_unit="sprig",
    ),
    "slice": UnitDefinition(
        name="slice",
        abbreviations=("slice",),
        type="other",
        to_base=Decimal("1"),
        base_unit="slice",
    ),
    "can": UnitDefinition(
        name="can",
        abbreviations=("can",),
        type="other",
        to_base=Decimal("1"),
        base_unit="can",
    ),
}

# Combined dictionary of all units
ALL_UNITS: dict[str, UnitDefinition] = {
    **VOLUME_UNITS,
    **WEIGHT_UNITS,
    **COUNT_UNITS,
    **OTHER_UNITS,
}
