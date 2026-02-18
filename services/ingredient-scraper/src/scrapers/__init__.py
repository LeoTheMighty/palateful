from .base import BaseScraper
from .openfoodfacts import OpenFoodFactsScraper
from .themealdb import TheMealDBScraper
from .usda import USDAFoodDataScraper

__all__ = [
    "BaseScraper",
    "TheMealDBScraper",
    "USDAFoodDataScraper",
    "OpenFoodFactsScraper",
]
