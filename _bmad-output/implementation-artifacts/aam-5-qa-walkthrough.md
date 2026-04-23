# aam-5 QA Walkthrough — Migration runbook

**Story**: aam-5-migration-runbook
**Epic**: epic-api-async-migration

## What changed

- New `docs/async-migration-runbook.md`.

## Manual / regression checks

Doc-only story. Validation is "every section the AC names is present and
actionable."

- [x] **TL;DR / 8-step conversion recipe** present with explicit code
      transformations.
- [x] **selectinload / joinedload / noload matrix** present, columns
      labeled, includes the "MissingGreenlet ≡ DetachedInstanceError"
      rule.
- [x] **Greenlet-bridge-forbidden** section names every whitelisted
      sync-on-event-loop path with file path + rationale.
- [x] **Lazy-load audit procedure** includes the literal `rg`
      one-liner and the structured QA-walkthrough format.
- [x] **Dual-register + observation-window procedure** includes the
      `app.include_router` snippet for both directions and the
      <5-minute rollback recipe.
- [x] **Rollback procedures** for both within-window and post-cutover,
      with specific commands.
- [x] **Session-per-request lifecycle diagram** + invariant rules.
- [x] **Per-domain story checklist** structured as a copy-pasteable
      checklist (ready for QA-walkthrough re-use).
- [x] **MCP section** documents `call_endpoint(...)` →
      `call_endpoint_async(...)` swap and MCP smoke-test command.
- [x] **Common Mistakes table** captures every gotcha I hit during the
      aam-1/2/3/4 implementation so the next engineer doesn't.
- [x] **Decision log** records party-mode-locked decisions with dates.

## Cross-references

- `epic-api-async-migration.md` already names this runbook (search
  "docs/async-migration-runbook.md") in the file structure section —
  no edit to the epic needed.
- Future Phase 3 stories cite the runbook from their own ACs (story
  templates carry the reference forward).

## Rollback

Trivial: `git rm docs/async-migration-runbook.md`. No code dependencies.

## Follow-ups

- aam-6 (next): the runbook references `get_current_user_async` and
  the auth race test that aam-6 introduces. Once aam-6 lands, no
  runbook edit needed — the recipe is already worded to match the
  expected aam-6 surface.
- Phase 3 stories: when the first one (aam-10) lands, capture any
  recipe corrections in the runbook's "Common Mistakes" table.
