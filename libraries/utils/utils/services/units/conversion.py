"""Unit conversion functions."""

from dataclasses import dataclass
from decimal import Decimal

from palateful_utils.units.constants import ALL_UNITS, UnitDefinition


@dataclass
class NormalizedQuantity:
    """Result of normalizing a quantity to base units."""

    quantity_normalized: Decimal
    unit_normalized: str
    quantity_display: Decimal
    unit_display: str


@dataclass
class ConversionResult:
    """Result of converting between units."""

    success: bool
    quantity: Decimal | None = None
    error: str | None = None


def find_unit(unit: str) -> UnitDefinition | None:
    """Find a unit definition by name or abbreviation."""
    unit_lower = unit.lower().strip()

    # Check by key first
    if unit_lower in ALL_UNITS:
        return ALL_UNITS[unit_lower]

    # Check by abbreviation
    for unit_def in ALL_UNITS.values():
        if unit_lower in (abbr.lower() for abbr in unit_def.abbreviations):
            return unit_def

    return None


def normalize_quantity(quantity: Decimal, unit: str) -> NormalizedQuantity:
    """
    Convert a quantity to normalized base units for storage.

    Args:
        quantity: The amount to normalize
        unit: The unit string (e.g., "cups", "lbs")

    Returns:
        NormalizedQuantity with both display and normalized values
    """
    unit_def = find_unit(unit)

    if unit_def is None or unit_def.type == "other":
        # Non-convertible units stored as-is
        base_unit = unit_def.base_unit if unit_def else unit.lower()
        return NormalizedQuantity(
            quantity_normalized=quantity,
            unit_normalized=base_unit,
            quantity_display=quantity,
            unit_display=unit,
        )

    return NormalizedQuantity(
        quantity_normalized=quantity * unit_def.to_base,
        unit_normalized=unit_def.base_unit,
        quantity_display=quantity,
        unit_display=unit,
    )


def convert_between_units(quantity: Decimal, from_unit: str, to_unit: str) -> ConversionResult:
    """
    Convert a quantity from one unit to another.

    Args:
        quantity: The amount to convert
        from_unit: Source unit
        to_unit: Target unit

    Returns:
        ConversionResult with the converted quantity or error
    """
    from_def = find_unit(from_unit)
    to_def = find_unit(to_unit)

    if from_def is None:
        return ConversionResult(success=False, error=f"Unknown unit: {from_unit}")

    if to_def is None:
        return ConversionResult(success=False, error=f"Unknown unit: {to_unit}")

    if from_def.type == "other" or to_def.type == "other":
        return ConversionResult(
            success=False, error=f"Cannot convert '{from_def.type}' type units"
        )

    if from_def.type != to_def.type:
        return ConversionResult(
            success=False,
            error=f"Cannot convert between {from_def.type} and {to_def.type}",
        )

    # Convert: from -> base -> to
    in_base = quantity * from_def.to_base
    result = in_base / to_def.to_base

    return ConversionResult(success=True, quantity=result)


# Fraction mappings for display
FRACTION_MAP: dict[str, Decimal] = {
    "1/4": Decimal("0.25"),
    "1/3": Decimal("0.33"),
    "1/2": Decimal("0.5"),
    "2/3": Decimal("0.66"),
    "3/4": Decimal("0.75"),
}

TOLERANCE = Decimal("0.05")


def format_quantity(quantity: Decimal, unit: str) -> str:
    """
    Format a quantity with fractions for display.

    Args:
        quantity: The amount to format
        unit: The unit string

    Returns:
        Formatted string like "1 1/2 cups"
    """
    whole = int(quantity)
    fractional = quantity - whole

    # Find matching fraction
    fraction_str = ""
    for frac_display, frac_value in FRACTION_MAP.items():
        if abs(fractional - frac_value) < TOLERANCE:
            fraction_str = frac_display
            break

    if whole == 0 and fraction_str:
        return f"{fraction_str} {unit}"
    elif fraction_str:
        return f"{whole} {fraction_str} {unit}"
    else:
        # Format as decimal, removing trailing zeros
        formatted = f"{quantity:.3f}".rstrip("0").rstrip(".")
        return f"{formatted} {unit}"
