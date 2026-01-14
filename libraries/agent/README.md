# Agent Library

AI-powered meal suggestion agent library for Palateful. Uses LangGraph for state-based workflow orchestration with support for multiple LLM providers.

## Overview

The agent library provides proactive meal suggestions based on:
- User's pantry contents
- Expiring ingredients
- Dietary preferences
- Cuisine preferences

## Architecture

```
agent/
├── config.py          # Settings and configuration
├── runner.py          # Main entry point for running agents
├── llm/               # LLM provider abstraction
│   ├── provider.py    # Abstract base class
│   ├── openai.py      # OpenAI implementation
│   ├── anthropic.py   # Anthropic implementation
│   └── ollama.py      # Ollama (local) implementation
├── tools/             # Agent tools
│   ├── base.py        # Tool base class
│   ├── pantry.py      # Get pantry items
│   ├── recipes.py     # Search and suggest recipes
│   └── preferences.py # Get user preferences
└── graph/             # LangGraph state machine
    ├── state.py       # State TypedDict definitions
    ├── graph.py       # Graph definition
    └── nodes.py       # Node functions
```

## Usage

### Basic Usage

```python
from agent import run_suggestion_agent

# Run for a single user
result = await run_suggestion_agent(
    user_id="user-uuid",
    trigger_type="daily",  # or "pantry_update", "expiring"
)

print(f"Created {len(result['created_suggestion_ids'])} suggestions")
```

### Run for All Users (Daily Task)

```python
from agent import run_daily_suggestions_for_all

# Run for all users with notifications enabled
result = await run_daily_suggestions_for_all()
print(f"Success: {result['success']}, Errors: {result['errors']}")
```

### Using with Existing DB Session

```python
from agent import run_suggestion_agent

async with db_session() as db:
    result = await run_suggestion_agent(
        user_id="user-uuid",
        trigger_type="pantry_update",
        context={"added_ingredients": ["chicken", "tomatoes"]},
        db=db,  # Use existing session
    )
```

## LLM Providers

The library supports multiple LLM providers:

### OpenAI (default)
```bash
export OPENAI_API_KEY=your-key
export AGENT_DEFAULT_PROVIDER=openai
export AGENT_MODEL=gpt-4o-mini
```

### Anthropic
```bash
export ANTHROPIC_API_KEY=your-key
export AGENT_DEFAULT_PROVIDER=anthropic
```

### Ollama (local)
```bash
export OLLAMA_BASE_URL=http://localhost:11434
export AGENT_DEFAULT_PROVIDER=ollama
```

## Configuration

Environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | - |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `ANTHROPIC_API_KEY` | Anthropic API key | - |
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `AGENT_DEFAULT_PROVIDER` | Default LLM provider | `openai` |
| `AGENT_MODEL` | Model to use | `gpt-4o-mini` |
| `AGENT_TEMPERATURE` | LLM temperature | `0.7` |
| `EMBEDDING_MODEL` | Sentence transformer model | `all-MiniLM-L6-v2` |

## Development

```bash
# Install dependencies
cd libraries/agent
poetry install

# Run tests
poetry run pytest

# Lint
poetry run ruff check agent/
```

## Trigger Types

- `daily`: Morning meal suggestion based on pantry contents
- `pantry_update`: Suggestions after adding new ingredients
- `expiring`: Urgent suggestions for ingredients about to expire

## Integration with Worker

The agent library is designed to be called from Celery tasks:

```python
from celery import Celery
from agent import run_suggestion_agent, run_daily_suggestions_for_all

@celery_app.task
def daily_suggestions_task():
    """Daily scheduled task to generate suggestions for all users."""
    import asyncio
    return asyncio.run(run_daily_suggestions_for_all())

@celery_app.task
def trigger_user_suggestion(user_id: str, trigger_type: str, context: dict = None):
    """Trigger suggestions for a specific user."""
    import asyncio
    return asyncio.run(run_suggestion_agent(user_id, trigger_type, context))
```
