# QA walkthrough — pim-6 CONCURRENTLY migration audit

## What shipped

Documentation-only. No code change, no terraform change, no migration.
The full audit findings and rationale live in
`pim-6-concurrently-migration-backport-audit.md`.

## How to verify

1. **Reproduce the strict-AC audit**:
   ```bash
   grep -Rn 'op\.execute.*CREATE INDEX' services/migrator/migrations/versions/
   ```
   Expected: every hit contains `CONCURRENTLY` (confirmed via the
   agent audit — zero counter-examples).

2. **Reproduce the broader-scope list** (reference):
   ```bash
   grep -Rn 'op\.create_index' services/migrator/migrations/versions/ | wc -l
   # ~92 total op.create_index calls across 34 files
   ```
   The story file enumerates the 18 that target pre-existing
   production tables.

3. **Confirm no new migration file** was added under
   `services/migrator/migrations/versions/` for this story:
   ```bash
   git log --diff-filter=A --name-only origin/main..HEAD -- \
     services/migrator/migrations/versions/
   # Expect: empty
   ```

## Before/after numbers

N/A. Audit-only story — no runtime change, no latency impact.

## Acceptance criteria — all met

- AC1 ✅ Strict audit of `op.execute("CREATE INDEX ...")` without
  CONCURRENTLY: zero findings.
- AC2 — N/A (no findings).
- AC3 ✅ Empty-audit closure: commit lists surveyed migrations,
  no empty migration file created.
- AC4 — N/A.

## Follow-ups

- **Locked principle going forward**: every new index lands via
  `op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS ...")`
  inside an `op.get_context().autocommit_block()` with a matching
  `DROP INDEX CONCURRENTLY IF EXISTS ...` downgrade. Mirror:
  `20260420050000_add_see_all_partial_indexes.py`.
- Downstream perf epics (query-tuning, client-polish) that may add
  new indexes must follow this pattern by contract.
