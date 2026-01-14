# Ingredient Scraper

A CLI tool for building a comprehensive ingredient database by scraping from multiple food data sources, normalizing, deduplicating, and enriching the data.

## Features

- **Multi-source scraping**: TheMealDB, USDA FoodData Central, Open Food Facts
- **Data normalization**: Lowercase, singularization, spelling standardization
- **Fuzzy deduplication**: Merge similar ingredients from different sources
- **Auto-categorization**: Rule-based category assignment
- **Embedding generation**: Semantic embeddings for search (sentence-transformers)
- **AI substitutions**: OpenAI-powered substitution suggestions
- **Versioned output**: CSV files with version tracking for incremental updates

## Quick Start

```bash
# Install dependencies
npx nx run ingredient-scraper:install

# Run the full pipeline (scrape from TheMealDB only - no API key needed)
npx nx run ingredient-scraper:run -- pipeline --source themealdb

# Run with all sources (requires USDA API key)
npx nx run ingredient-scraper:run -- pipeline --all --limit 1000
```

## Installation

```bash
cd services/ingredient-scraper
poetry install
```

## Configuration

Create a `.env` file in the service directory or set environment variables:

```bash
# Required for USDA scraping
USDA_API_KEY=your_usda_api_key  # Get from https://fdc.nal.usda.gov/api-key-signup.html

# Required for substitution generation
OPENAI_API_KEY=your_openai_api_key

# Optional settings
SCRAPER_CACHE_DIR=./cache
SCRAPER_OUTPUT_DIR=./output
DEDUP_SIMILARITY_THRESHOLD=0.90
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

## Usage

### Full Pipeline

Run the complete workflow: scrape → normalize → deduplicate → categorize → enrich → export

```bash
# From TheMealDB only (no API key needed)
npx nx run ingredient-scraper:run -- pipeline --source themealdb

# From all sources
npx nx run ingredient-scraper:run -- pipeline --all

# With limits and options
npx nx run ingredient-scraper:run -- pipeline --all --limit 500 --embeddings --substitutions
```

### Individual Commands

#### Scrape

Fetch ingredients from external sources:

```bash
# Scrape from TheMealDB
npx nx run ingredient-scraper:run -- scrape --source themealdb

# Scrape from USDA (requires API key)
npx nx run ingredient-scraper:run -- scrape --source usda --limit 1000

# Scrape from all sources
npx nx run ingredient-scraper:run -- scrape --all --limit 500
```

#### Process

Normalize, deduplicate, and categorize raw data:

```bash
npx nx run ingredient-scraper:run -- process --input ./output/raw --output ./output/processed
```

#### Enrich

Add embeddings and generate substitutions:

```bash
# Generate embeddings only
npx nx run ingredient-scraper:run -- enrich --input ./output/processed --embeddings

# Generate substitutions with OpenAI
npx nx run ingredient-scraper:run -- enrich --input ./output/processed --substitutions
```

#### Export

Copy final CSV files to the migrator seeds directory:

```bash
npx nx run ingredient-scraper:run -- export --output ../../services/migrator/seeds
```

#### Statistics

View dataset statistics:

```bash
npx nx run ingredient-scraper:run -- stats --input ./output/final
```

#### Version Management

```bash
# List all versions
npx nx run ingredient-scraper:run -- versions

# Clear scraper cache
npx nx run ingredient-scraper:run -- clear-cache
```

## Output Format

The tool generates versioned CSV files that map directly to the database schema:

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
| ratio | float | Quantity ratio (e.g., 0.75 means use 75%) |
| notes | string | Usage notes |

### manifest.json

Tracks version history with metadata:

```json
{
  "created_at": "2025-01-15T12:00:00",
  "latest_version": "1.0.2",
  "versions": [
    {
      "version": "1.0.0",
      "created_at": "2025-01-15T12:00:00",
      "ingredient_count": 500,
      "substitution_count": 1200,
      "notes": "Initial scrape"
    }
  ]
}
```

## Data Sources

### TheMealDB (Free, no API key)

- ~500 curated cooking ingredients
- Includes descriptions and images
- Best for common cooking ingredients

### USDA FoodData Central (Free, requires API key)

- 300,000+ foods with detailed nutrition data
- Foundation Foods (~2,000) and SR Legacy (~8,000) datasets
- Best for comprehensive coverage and nutrition info
- Get API key: https://fdc.nal.usda.gov/api-key-signup.html

### Open Food Facts (Free, no API key)

- Community-driven product database
- Filtered for base ingredients only
- Supplements data from other sources

## Categories

The tool assigns ingredients to these categories:

- `produce` - Fruits, vegetables, mushrooms
- `protein` - Meat, poultry, eggs, plant-based proteins
- `seafood` - Fish, shellfish
- `dairy` - Milk, cheese, butter, yogurt
- `grains` - Rice, pasta, bread, flour
- `legumes` - Beans, lentils, chickpeas
- `nuts_seeds` - Nuts, seeds, nut butters
- `herbs_spices` - Fresh herbs, dried spices
- `oils_fats` - Cooking oils, butter alternatives
- `sweeteners` - Sugar, honey, syrups
- `baking` - Baking powder, vanilla, chocolate
- `condiments` - Sauces, vinegars, dressings
- `beverages` - Broths, juices, coffee
- `pantry` - Misc pantry items

## Versioning and Updates

The tool supports incremental updates:

```bash
# Initial scrape
npx nx run ingredient-scraper:run -- pipeline --all

# Later: merge new data with existing
npx nx run ingredient-scraper:run -- pipeline --all --merge
```

New ingredients are added, existing ingredients have their metadata merged (aliases, images, etc. are combined from all sources).

## Development

### Run Tests

```bash
npx nx run ingredient-scraper:test
```

### Lint

```bash
npx nx run ingredient-scraper:lint
```

### Project Structure

```
services/ingredient-scraper/
├── src/
│   ├── main.py                 # CLI entry point
│   ├── config.py               # Settings
│   ├── scrapers/               # Data source scrapers
│   │   ├── base.py             # Base scraper with caching/rate limiting
│   │   ├── themealdb.py        # TheMealDB scraper
│   │   ├── usda.py             # USDA FoodData Central scraper
│   │   └── openfoodfacts.py    # Open Food Facts scraper
│   ├── pipeline/               # Processing pipeline
│   │   ├── normalizer.py       # Name normalization
│   │   ├── deduplicator.py     # Fuzzy deduplication
│   │   ├── categorizer.py      # Category assignment
│   │   └── enricher.py         # Embeddings & substitutions
│   ├── models/                 # Data models
│   │   └── scraped_ingredient.py
│   └── output/                 # Output writers
│       ├── csv_writer.py       # Versioned CSV output
│       └── stats.py            # Statistics generator
├── tests/                      # Unit tests
├── pyproject.toml              # Poetry config
└── README.md                   # This file
```

## Estimated Costs

- **USDA API**: Free (1000 requests/hour limit)
- **TheMealDB**: Free (no limits)
- **Open Food Facts**: Free (rate limited)
- **OpenAI Substitutions**: ~$5-10 for 5,000 ingredients (GPT-4o-mini)
- **Embeddings**: Free (local sentence-transformers model)
