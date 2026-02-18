"""Display formatting utilities."""

from decimal import Decimal
from fractions import Fraction

# Units that should display as fractions (cooking measurements)
_FRACTION_UNITS = {
    "cup", "cups", "tbsp", "tsp", "oz", "lb", "lbs",
    "whole", "large", "small", "medium", "pieces", "piece",
    "cloves", "clove", "loaf", "loaves", "bunch", "bunches",
    "pint", "pints", "quart", "quarts", "gallon", "gallons",
    "stick", "sticks", "slice", "slices", "head", "heads",
    "bag", "bags", "bottle", "bottles", "can", "cans",
}


def format_quantity(quantity: Decimal, unit: str) -> str:
    """Format a quantity for display.

    Cooking units (cups, tbsp, etc.) get fraction formatting: 1/2, 1 1/4, etc.
    Metric units (g, ml, kg) get clean decimal formatting: 227, 1.5, etc.
    """
    if unit.lower() in _FRACTION_UNITS:
        return _decimal_to_fraction(quantity)
    return _decimal_to_clean(quantity)


def _decimal_to_fraction(value: Decimal) -> str:
    """Convert a decimal to a fraction string. 0.5 -> '1/2', 1.5 -> '1 1/2'."""
    frac = Fraction(value).limit_denominator(8)
    whole = frac.numerator // frac.denominator
    remainder = frac - whole

    if remainder == 0:
        return str(whole)
    if whole == 0:
        return f"{remainder.numerator}/{remainder.denominator}"
    return f"{whole} {remainder.numerator}/{remainder.denominator}"


def _decimal_to_clean(value: Decimal) -> str:
    """Format a decimal without unnecessary trailing zeros. 227.000 -> '227'."""
    normalized = value.normalize()
    if normalized == int(normalized):
        return str(int(normalized))
    return str(normalized)
