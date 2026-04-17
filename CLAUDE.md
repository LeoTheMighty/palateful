# Claude Code Reference

> **IMPORTANT:** ALWAYS use `npx nx` commands whenever possible instead of direct commands.

## Project Overview

Palateful is an NX monorepo with Python microservices (FastAPI) and Flutter mobile frontend. This is a kitchen management app with AI-powered recipe and ingredient features.

## Key References

- **`docs/`** - Feature/design docs (MVP, import pipeline, shared shopping cart, calendar, invitations, search, recipe experience, deployment, eval). Source of truth for schema and endpoints is the code itself (`services/api/src/db/models/`, `services/api/src/routers/`).
- **`_bmad-output/planning-artifacts/epics.md`** - Current roadmap and epic status — **primary source for what to do next**
- **`_bmad-output/planning-artifacts/architecture.md`** - Current system architecture

## Project Structure

```
palateful/
├── services/           # Python microservices (api, migrator, parser, worker)
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

## Ops Scripts

Scripts in `services/api/scripts/` are one-off ops tools that talk directly
to the database via `DATABASE_URL`. They do not require the FastAPI app to
be running. Every mutation writes an audit row to `error_logs` with
`service="audit"` so the change is queryable without polluting error
dashboards (which filter on `service="api"`).

### `promote_admin.py` — grant/revoke admin by email

```bash
# Dry-run (default): prints target user + planned change, no writes.
DATABASE_URL=<prod-url> python services/api/scripts/promote_admin.py \
    --email leonid@ac93.org

# Commit the promotion.
DATABASE_URL=<prod-url> python services/api/scripts/promote_admin.py \
    --email leonid@ac93.org --yes

# Revoke admin (mistake recovery or offboarding).
DATABASE_URL=<prod-url> python services/api/scripts/promote_admin.py \
    --email someone@example.com --demote --yes
```

Exit codes: `0` success / no-op, `2` no match or multiple matches, `1`
other errors. Script is idempotent: re-running in the target state is a
no-op.
