# Ingredient Scraper Service - Design Document

## Overview

The `ingredient-scraper` is a CLI tool that builds a comprehensive ingredient database by scraping from multiple authoritative food data sources, normalizing the data, generating embeddings for semantic search, and outputting versioned CSV seed files for the database.

## Goals

1. **Comprehensive Coverage**: 5,000+ ingredients across all food categories
2. **Rich Metadata**: Aliases, categories, common units
3. **Search Optimized**: Pre-computed embeddings for semantic search (384-dim vectors)
4. **Substitution Mapping**: AI-generated ingredient substitutions
5. **Reproducible**: Versioned CSV files that can be committed and tracked

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ingredient-scraper service                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Scrapers   │    │   Pipeline   │    │   Enricher   │      │
│  │              │    │              │    │              │      │
│  │ • USDA       │───▶│ • Normalize  │───▶│ • Embeddings │      │
│  │ • OpenFood   │    │ • Dedupe     │    │ • OpenAI     │      │
│  │ • TheMealDB  │    │ • Categorize │    │   Subs       │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                     CSV Output Writer                     │  │
│  │  • ingredients_v{version}.csv (maps to DB schema)         │  │
│  │  • substitutions_v{version}.csv                           │  │
│  │  • manifest.json (version tracking)                       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Data Sources

| Source | Type | Data Available | Rate Limits |
|--------|------|----------------|-------------|
| **USDA FoodData Central** | REST API (free) | 300k+ foods, nutrition | 1000/hour |
| **Open Food Facts** | REST API (free) | 2M+ products | Generous |
| **TheMealDB** | REST API (free) | ~500 curated ingredients | None |

## Data Model

The `ScrapedIngredient` maps directly to the database `Ingredient` model:

```python
@dataclass
class ScrapedIngredient:
    canonical_name: str       # Primary name (unique, lowercase)
    aliases: list[str]        # Alternative names
    category: str | None      # produce, protein, dairy, etc.
    flavor_profile: list[str] # sweet, salty, sour, etc.
    default_unit: str | None  # Preferred measurement unit
    is_canonical: bool        # True for base ingredients
    pending_review: bool      # False for scraped data
    image_url: str | None     # Reference image
    embedding: list[float]    # 384-dimension vector
```

## CSV Output Format

### ingredients_v{version}.csv

| Column | Type | Description |
|--------|------|-------------|
| canonical_name | string | Primary ingredient name (unique, lowercase) |
| aliases | JSON array | Alternative names |
| category | string | Category (produce, protein, dairy, etc.) |
| flavor_profile | JSON array | Flavor characteristics |
| default_unit | string | Default measurement unit |
| is_canonical | boolean | Whether this is a canonical ingredient |
| pending_review | boolean | Whether needs manual review |
| image_url | string | Reference image URL |
| embedding | JSON array | 384-dimension embedding vector |

### substitutions_v{version}.csv

| Column | Type | Description |
|--------|------|-------------|
| ingredient | string | Original ingredient canonical_name |
| substitute | string | Substitute ingredient name |
| context | string | When to use: baking, cooking, raw, any |
| quality | string | How good: perfect, good, workable |
| ratio | float | Quantity ratio |
| notes | string | Usage notes |

## Category Taxonomy

```
produce/        - Fruits, vegetables, mushrooms
protein/        - Meat, poultry, eggs, plant-based
seafood/        - Fish, shellfish
dairy/          - Milk, cheese, butter, yogurt
grains/         - Rice, pasta, bread, flour
legumes/        - Beans, lentils, chickpeas
nuts_seeds/     - Nuts, seeds, nut butters
herbs_spices/   - Fresh herbs, dried spices
oils_fats/      - Cooking oils, butter alternatives
sweeteners/     - Sugar, honey, syrups
baking/         - Baking powder, vanilla, chocolate
condiments/     - Sauces, vinegars, dressings
beverages/      - Broths, juices, coffee
pantry/         - Misc pantry items
```

## Pipeline Steps

1. **Scrape**: Fetch data from external APIs with rate limiting and caching
2. **Normalize**: Lowercase, remove qualifiers, singularize, standardize spelling
3. **Deduplicate**: Fuzzy match (>90% similarity) and merge metadata
4. **Categorize**: Rule-based category assignment
5. **Enrich**: Generate embeddings, optionally generate substitutions with OpenAI
6. **Export**: Write versioned CSV files

## Versioning

The tool supports incremental updates:

- Each run creates a new version (1.0.0, 1.0.1, etc.)
- `manifest.json` tracks version history with metadata
- `--merge` flag combines new data with existing versions
- New ingredients are added, existing ingredients have metadata merged

## Usage

```bash
# Quick test with TheMealDB (no API key needed)
npx nx run ingredient-scraper:run -- pipeline --source themealdb

# Full pipeline with all sources
npx nx run ingredient-scraper:run -- pipeline --all --limit 1000

# With substitutions (requires OPENAI_API_KEY)
npx nx run ingredient-scraper:run -- pipeline --all --substitutions

# Export to migrator seeds
npx nx run ingredient-scraper:run -- export --output ../../services/migrator/seeds
```

## Environment Variables

```bash
USDA_API_KEY=...        # Required for USDA scraping
OPENAI_API_KEY=...      # Required for substitution generation
SCRAPER_CACHE_DIR=...   # Optional: cache directory
```

## Cost Estimates

- **USDA API**: Free (1000 requests/hour)
- **TheMealDB**: Free
- **Open Food Facts**: Free
- **OpenAI Substitutions**: ~$5-10 for 5,000 ingredients
- **Embeddings**: Free (local sentence-transformers)

## File Structure

```
services/ingredient-scraper/
├── src/
│   ├── main.py              # CLI entry point
│   ├── config.py            # Settings
│   ├── scrapers/            # Data source scrapers
│   ├── pipeline/            # Processing pipeline
│   ├── models/              # Data models
│   └── output/              # CSV writers
├── tests/                   # Unit tests
├── pyproject.toml           # Dependencies
└── README.md                # Usage guide
```
