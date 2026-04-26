# worker-async-cleanup-2 — QA walkthrough

Story 2 ships zero code. The walkthrough is a one-liner: prove no
service drift happened.

## 1. Confirm zero diff in pyproject/poetry.lock for in-scope services

```
git diff --name-only origin/main..HEAD -- \
    services/parser/pyproject.toml \
    services/parser/poetry.lock \
    services/ingredient-scraper/pyproject.toml \
    services/ingredient-scraper/poetry.lock
```

**Pass:** zero output (no files in the list changed).
**Fail:** any file printed — Story 2 was supposed to be a no-op but
something snuck in. Investigate and either revert or upgrade the entry
to a real fix commit.

## 2. Confirm asyncpg is *not* in either service's pyproject

```
grep -n "asyncpg" services/parser/pyproject.toml \
                  services/ingredient-scraper/pyproject.toml
```

**Pass:** zero matches.
**Fail:** the pin was added — re-classify the service in Story 1 (it
must satisfy (a) AND (b), not just (a)) before keeping the dep.
