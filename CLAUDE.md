# Claude Code Reference

> **IMPORTANT:** ALWAYS use `npx nx` commands whenever possible instead of direct commands.

## Project Overview

Palateful is an NX monorepo with Python microservices (FastAPI) and Flutter mobile frontend. This is a kitchen management app with AI-powered recipe and ingredient features.

## Key References

- **`docs/`** - Complete project documentation including database schema, business logic, API reference, and AI tools
- **`TODO.md`** - Migration roadmap and task tracking - **primary source for what to do next**

## Project Structure

```
palateful/
├── services/           # Python microservices (api, migrator, ocr, worker)
├── libraries/          # Shared Python libraries (utils, test_helper)
├── docs/               # Documentation
├── terraform/          # AWS infrastructure
├── archive/            # Original Next.js implementation (reference)
└── scripts/            # Utility scripts
```

## Development Commands

```bash
# Build Docker images
npx nx run api:docker-build
npx nx run migrator:docker-build

# Start all services (primary dev workflow)
docker compose up

# Run migrations (with migrate profile)
docker compose --profile migrate up migrator

# Install dependencies (when needed)
npx nx run api:install
npx nx run migrator:install

# Generate lock files
npx nx run-many -t lock

# Run migrations locally (requires DATABASE_URL)
npx nx run migrator:migrate

# Lint/Test
npx nx run api:lint
npx nx run api:test
```

## Technology Stack

- **API**: FastAPI, SQLAlchemy 2.0 async, PostgreSQL 16 with pgvector
- **Auth**: Auth0 with JWT
- **AI**: OpenAI (gpt-4o-mini), HunyuanOCR for image processing
- **Infrastructure**: AWS (ECS Fargate, RDS, API Gateway, Lambda)
- **Package Manager**: Poetry (Python), Yarn (Node/NX)

## Environment Variables

See `.env.example` for required configuration. Key vars:
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `AUTH0_DOMAIN`, `AUTH0_AUDIENCE`, `AUTH0_CLIENT_ID` - Auth0 config
- `OPENAI_API_KEY` - OpenAI API key
