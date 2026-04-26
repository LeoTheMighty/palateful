# worker-async-cleanup-1 — audit + classify

**Epic:** `epic-worker-async-engine-cleanup`
**Status:** done
**Parent ACs:** epic-worker-async-engine-cleanup § Story 1

## Scope

Audit every service under `services/` that has *not* already been pinned
to `asyncpg = "^0.30"` (i.e. excluding `api`, `worker`, `migrator`,
`eval`) for whether it trips on the unconditional
`create_async_engine(...)` call introduced in
`libraries/utils/utils/services/database.py` by aam-2 (2026-04-23).

A service trips iff **both** of:

  (a) It imports `utils.services.database`, or anything that transitively
      pulls it in (`utils.tasks`, `utils.api.endpoint`,
      `utils.services.celery`, etc.).
  (b) Its production runtime env has the `DB_HOST` / `DB_USERNAME` /
      `DB_PASSWORD` / `DB_NAME` component vars set, so
      `utils.constants.ASYNC_DATABASE_URL` resolves to a non-empty value.

If only (a) holds and (b) doesn't, the service stays safe — `ASYNC_DATABASE_URL`
is `None` and `create_async_engine` never fires. If only (b) holds, the
async-engine path never executes because `utils.services.database` never
loads.

## Services in scope

- `services/parser/`
- `services/ingredient-scraper/`

(`services/e2e/` is a Cypress harness, not a Python service — out of
scope.)

## Findings

### `services/parser/` — **no fix needed**

**(a) Imports `utils.services.database`?** **No.**

`services/parser/pyproject.toml` lists only `fastapi`, `uvicorn`,
`torch`, `transformers`, `accelerate`, `pillow`, `python-multipart`,
`httpx`, `boto3`. There is **no** `utils = {path = ...}` dependency, so
the `utils` package is not even present in the parser's Poetry venv.

Confirmed by grep across the entire parser source tree (returns empty):

```
grep -rn "from utils\|import utils\|utils\." \
    services/parser/src services/parser/run_job.py services/parser/tests
```

The parser is a standalone OCR service: `run_job.py` (the AWS Batch
entry) imports only `boto3`, `torch`, `transformers`, `PIL`, and
stdlib; `src/main.py` (FastAPI dev server) imports only `fastapi`, `PIL`,
`pydantic`, and the local `src.config` / `src.model` modules.

**(b) Has `DB_*` env vars in prod?** **No.**

Parser runs as an AWS Batch job, not as an ECS service. Its job
definition lives in `terraform/modules/batch/main.tf`. The container
env (`aws_batch_job_definition.parser`) injects only S3 URIs,
`MODEL_NAME`, `BATCH_MANIFEST_URI`, and `API_CALLBACK_URL` — no
`DB_HOST` / `DB_USERNAME` / `DB_PASSWORD` / `DB_NAME`. The parser
container talks to the API over HTTPS (`API_CALLBACK_URL`), never
directly to the database.

**Verdict:** parser hits **neither** (a) nor (b). Safe.

### `services/ingredient-scraper/` — **no fix needed**

**(a) Imports `utils.services.database`?** **No.**

`services/ingredient-scraper/pyproject.toml` lists only `httpx`,
`pydantic`, `pydantic-settings`, `typer`, `rich`,
`sentence-transformers`, `rapidfuzz`, `inflect`, `openai`, `tenacity`.
No `utils` dependency.

Confirmed by grep across the entire scraper source tree (returns empty):

```
grep -rn "from utils\|import utils\|utils\." \
    services/ingredient-scraper/src services/ingredient-scraper/tests
```

The scraper writes results to CSV files (see
`src/output/csv_writer.py`); the migrator picks those CSVs up at seed
time. There is no live DB connection from the scraper itself.

**(b) Has `DB_*` env vars in prod?** **No.**

ingredient-scraper is a developer-only CLI tool (`typer` entry point at
`src.main:app`, registered in `pyproject.toml` as
`ingredient-scraper = "src.main:app"`). It is not deployed to AWS:
`services/ingredient-scraper/project.json` defines only `lock`,
`install`, `lint`, `test`, `run`, `scrape`, `scrape-test` targets —
**no** `docker-build`, `push`, or `deploy` targets. There is no ECS
service, no Batch job, and no terraform module for it. It runs only
on a developer's machine.

**Verdict:** scraper hits **neither** (a) nor (b). Safe.

## Conclusion

Neither `services/parser/` nor `services/ingredient-scraper/` needs the
asyncpg pin. **Story 2 will be a no-op** — the sprint-status entry
records this so the audit isn't lost — and we proceed straight to
Story 3 (the defensive guard in `database.py`), which is the durable
fix that prevents the next service from tripping the same wire when
it eventually picks up `utils.services.database`.

## QA Checklist

- [x] `pyproject.toml` of every flagged service inspected for the `utils`
      dep — neither parser nor scraper has it.
- [x] Source tree of every flagged service grepped for `utils.*` imports —
      both return empty.
- [x] Terraform/runtime config of every flagged service inspected for
      `DB_HOST` injection — parser's Batch job def + scraper's
      project.json confirm no DB env in either runtime.
- [x] Classification persisted in this file so a future agent doesn't
      re-do the audit.

## File List

- Created: `_bmad-output/implementation-artifacts/worker-async-cleanup-1-audit-and-classify.md`
- Created: `_bmad-output/implementation-artifacts/worker-async-cleanup-1-qa-walkthrough.md`
- Modified: `_bmad-output/implementation-artifacts/sprint-status.yaml`
