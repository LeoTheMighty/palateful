---
hash: aoc000
type: plan
created: 2026-07-27T17:25:00-06:00
title: Activity orphan cleanup — hard DELETE of soft-archived import_* user_activity rows
from: _bmad-output/implementation-artifacts/sprint-status.yaml
status: ready
mode: YOLO
---

## Scope
Placeholder epic (planned 2026-04-20) that finishes the orphan-row cleanup started by `epic-activity-badge-integrity`. That epic removed orphan `import_*` `user_activity` writes at 5 call sites (abi-2a) and soft-archived the existing orphan rows via migration with a 100k-row safety gate (abi-2b) — hard deletion was deliberately deferred to this follow-up epic. Scope is a single Alembic migration performing the hard DELETE of the rows abi-2b soft-archived, with no new schema, after a soak period confirms no downstream consumer surfaces them. Scheduling condition is now met: it was gated one release after `epic-activity-full-history`, which has shipped (all afh stories done in sprint-status).

## Pre-split stories (BMAD)
- (none — placeholder epic; only definition is the sprint-status.yaml comment block plus abi-2a/abi-2b context in epic-activity-badge-integrity. Natural shape is a single story: pre-delete verification query + hard-DELETE migration + row-count audit row.)

## Dependencies / notes
- Source epic key: `epic-activity-orphan-cleanup` (backlog in sprint-status.yaml; no epic file exists under _bmad-output/planning-artifacts/).
- Hard dependency satisfied: `epic-activity-badge-integrity` is done (abi-2b performed the soft-archive) and `epic-activity-full-history` has shipped — the "one release after" scheduling gate has passed.
- Soak-period check is a pre-flight AC, not a formality: verify no consumer (Activity Hub list, See-all pagination from full-history, badge counts) surfaces the soft-archived `import_*` rows before deleting; the deletion is irreversible.
- Single migration, no new schema; should reuse abi-2b's row-selection predicate exactly so the DELETE targets precisely the soft-archived set, and mirror its safety gate (bounded row count, batched delete) for the prod run.
- When /devx-plan picks this up it should emit dev specs from the shape above (effectively one story) rather than re-chunking from scratch.

## Status log
- 2026-07-27T17:25 — imported from BMAD (sprint-status.yaml placeholder comment + epic-activity-badge-integrity context) during BMAD→devx migration; no implementation commits on main as of import
