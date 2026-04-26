# worker-async-cleanup-1 — QA walkthrough

Lightweight regression check that re-runs the audit greps. ~30 seconds
end-to-end. No app, no DB, no env vars needed.

## 1. Re-run the import grep — expect empty

```
grep -rn "from utils\|import utils\|utils\." \
    services/parser/src services/parser/run_job.py services/parser/tests \
    services/ingredient-scraper/src services/ingredient-scraper/tests
```

**Pass:** zero matches (or a no-op exit code).
**Fail:** any line with `from utils`, `import utils`, or
`utils.services.database` — re-open Story 1 and re-classify the service.

## 2. Re-run the dep grep — expect no `utils` line

```
grep -E "^utils\b|utils = \{" \
    services/parser/pyproject.toml \
    services/ingredient-scraper/pyproject.toml
```

**Pass:** zero matches.
**Fail:** the service has gained a `utils = {path = ...}` dep since the
audit; bump it through Story 2 (add asyncpg pin) before merging.

## 3. Re-run the prod-env grep — expect no `DB_*` injection

```
grep -n "DB_HOST\|DB_USERNAME\|DB_PASSWORD\|DB_NAME" \
    terraform/modules/batch/main.tf \
    services/parser/project.json \
    services/ingredient-scraper/project.json
```

**Pass:** zero matches.
**Fail:** terraform now injects DB env into the parser Batch job (or
ingredient-scraper has been promoted to ECS) — re-open the audit.

## 4. Confirm the classification file is in place

```
test -f _bmad-output/implementation-artifacts/worker-async-cleanup-1-audit-and-classify.md
```

**Pass:** exit 0.
**Fail:** the audit doc is missing; nothing for a future agent to trust.
