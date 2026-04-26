# worker-async-cleanup-2 — add asyncpg to affected services

**Epic:** `epic-worker-async-engine-cleanup`
**Status:** done — recorded no-op
**Parent ACs:** epic-worker-async-engine-cleanup § Story 2

## Outcome

**Story 2 is a recorded no-op.** Story 1
(`worker-async-cleanup-1-audit-and-classify.md`) flagged zero services
in the in-scope set (`services/parser/`,
`services/ingredient-scraper/`) as needing the asyncpg pin.

The pin is required only for services that satisfy **both**:

  (a) Import `utils.services.database` (directly or transitively).
  (b) Run in prod with `DB_HOST` / `DB_USERNAME` / `DB_PASSWORD` /
      `DB_NAME` set, so `utils.constants.ASYNC_DATABASE_URL` resolves.

Neither parser nor ingredient-scraper hits either condition (full
evidence in the Story 1 doc). Adding `asyncpg = "^0.30"` to a service
that doesn't import `utils.services.database` would be dead weight in
the venv — increases container size and pulls a C extension into a
build that doesn't need it.

We are deliberately *not* adding the dep to either service.

## Why keep the story (instead of deleting it)

Two reasons:

1. **Audit trail.** Future agents picking up the epic from
   sprint-status.yaml see a coherent three-story arc (`audit → pin →
   guard`) instead of a missing middle story. The no-op is the *result*
   of the audit, not an absence of work.
2. **Safety net.** If a future change adds `utils = {path = ...}` to
   one of these services' `pyproject.toml`, the QA walkthrough's dep-grep
   will fail and the maintainer will know to re-open this story and add
   the pin.

## Acceptance Criteria

- [x] Every service flagged in Story 1 receives the asyncpg pin **and**
      a regenerated `poetry.lock`. — Vacuously satisfied: zero services
      flagged.
- [x] Each pinned service ships in its own commit with the
      `fix(<svc>): pin asyncpg to keep prod container importable`
      message. — Vacuously satisfied: zero commits needed.
- [x] No service that *wasn't* flagged gains the pin. — Confirmed:
      `services/parser/pyproject.toml` and
      `services/ingredient-scraper/pyproject.toml` are untouched in this
      epic's diff range.

## QA Checklist

- [x] `git diff origin/main..HEAD -- services/parser/pyproject.toml
      services/parser/poetry.lock services/ingredient-scraper/pyproject.toml
      services/ingredient-scraper/poetry.lock` shows zero changes.
- [x] Story 1's classification doc explicitly justifies the no-op.
- [x] Sprint-status entry for this story is `done` (recorded
      no-op).

## File List

- Created: `_bmad-output/implementation-artifacts/worker-async-cleanup-2-add-asyncpg-to-affected-services.md`
- Created: `_bmad-output/implementation-artifacts/worker-async-cleanup-2-qa-walkthrough.md`
- Modified: `_bmad-output/implementation-artifacts/sprint-status.yaml`
