# Palateful

Kitchen-management app with AI-powered recipe, pantry, and meal-planning features.

## Stack

- **Frontend**: Flutter (iOS, Android, Web via Cloudflare Pages)
- **Backend**: Python 3.11 microservices — FastAPI (`api`), Celery workers (`worker`), Alembic migrations (`migrator`), AWS Batch OCR (`parser`)
- **Shared libs**: `libraries/utils` (models, DB, services), `libraries/agent` (LLM providers + tools), `libraries/test-helper`
- **Database**: PostgreSQL 16 with pgvector + pg_trgm
- **Auth**: Auth0 (JWT)
- **AI**: OpenAI (chat/tools), HunyuanOCR (recipe image parsing)
- **Infrastructure**: AWS (ECS Fargate, RDS, ALB, SQS, S3, ECR, Batch) via Terraform
- **Monorepo tooling**: NX with `@nxlv/python` + Yarn

## Repo layout

```
palateful/
├── app/                    # Flutter app (iOS/Android/Web)
├── services/
│   ├── api/                # FastAPI HTTP API
│   ├── worker/             # Celery async workers
│   ├── migrator/           # Alembic migrations + seeds
│   ├── parser/             # HunyuanOCR AWS Batch job
│   ├── e2e/                # End-to-end test suite
│   ├── eval/               # Recipe-extraction eval harness
│   └── ingredient-scraper/ # Ingredient DB build CLI
├── libraries/              # Shared Python libs (utils, agent, test-helper)
├── terraform/              # AWS infra (modules + environments)
├── docs/                   # Feature/design docs
├── _bmad/                  # BMAD planning framework
├── _bmad-output/           # Live PRD, architecture, epics, stories
├── bin/                    # Ops & deploy scripts
├── scripts/                # Dev scripts (dev.sh, flutter-run.sh)
└── seeds/                  # SQL test fixtures
```

## Getting started

See **[docs/SETUP.md](./docs/SETUP.md)** for the full setup walkthrough (local dev, Auth0, database, Firebase, AWS).

Quick local start once set up:

```bash
# Backend: Postgres + API + worker + migrator via Docker Compose
docker compose up

# Flutter app
cd app && flutter run
```

## Common commands

```bash
# Build backend images
npx nx run api:docker-build
npx nx run migrator:docker-build

# Run migrations locally (needs DATABASE_URL)
npx nx run migrator:migrate

# Lint / test backend
npx nx run api:lint
npx nx run api:test

# Run recipe-extraction evals
npx nx run eval:run-fixtures
```

See [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md) for production deploy procedures.

## Roadmap

Current epics and story status live in **[_bmad-output/planning-artifacts/epics.md](./_bmad-output/planning-artifacts/epics.md)**. Architecture is captured in [_bmad-output/planning-artifacts/architecture.md](./_bmad-output/planning-artifacts/architecture.md).
