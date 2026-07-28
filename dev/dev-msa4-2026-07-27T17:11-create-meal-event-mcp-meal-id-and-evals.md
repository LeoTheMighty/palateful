---
hash: msa4
type: dev
created: 2026-07-27T17:11:00-06:00
title: create_meal_event MCP tool accepts meal_id plus 7 CI-gated eval fixtures
from: _bmad-output/planning-artifacts/epic-meals-sharing-and-ai.md
status: in-progress
owner: /devx-loop-2026-07-27T21-15-34-312-36147
branch: feat/dev-msa4
---

## Goal
Extend the existing `create_meal_event` MCP tool with an optional `meal_id` parameter (XOR with `recipe_id`, validation owned by the calendar epic's `CreateMealEvent` Endpoint) so the AI can schedule a Meal in one conversational turn. Land the epic's 7 minimum eval fixtures in `services/eval/fixtures/`, all CI-gated — AI-driven mutations need a fixture per mutation path and per ambiguity path, and a single fixture failure blocks ship. msa-1/2/3 have landed, and the hard dependency (epic-meals-calendar) is done.

## Acceptance criteria
- [ ] `services/api/src/mcp_server/tools/meal_planning.py` `create_meal_event` tool signature gains optional `meal_id: str | None = None` parameter. Docstring updated: "Pair a `recipe_id` or `meal_id` (not both) when planning from an existing recipe or Meal."
- [ ] XOR enforcement is delegated to the underlying `CreateMealEvent` Endpoint (calendar epic mcal-3 owns the Pydantic `model_validator` + DB check constraint `ck_meal_events_recipe_xor_meal`). MCP tool just passes through.
- [ ] Existing recipe-only path: behavior and response are byte-identical to pre-epic. Regression fixture asserts this.
- [ ] Eval fixtures — 7 minimum in `services/eval/fixtures/`, all CI-gated:
  1. `meal_create_from_explicit_ids.json` — unambiguous names → single `create_meal` call with 2 component IDs.
  2. `meal_create_from_fuzzy_names.json` — ambiguous "kale one" → AI clarifies BEFORE writing (zero-write assertion).
  3. `meal_create_with_clarification_needed.json` — no signal → AI lists candidates and asks (zero-write assertion).
  4. `meal_update_name.json` — rename only → one `update_meal` call.
  5. `meal_add_and_remove_component.json` — add then remove (non-degenerate) → two sequential tool calls, both silent. Variation: 2-component Meal + remove → `CONFIRMATION_REQUIRED`; user says "archive instead" → `archive_meal`.
  6. `meal_archive_with_references.json` — AI hits `CONFIRMATION_REQUIRED`, surfaces reference list, user confirms → `archive_meal(confirmed=True)`.
  7. `meal_event_with_meal_id.json` — "schedule the Summer Lunch Meal for Monday dinner" → `create_meal_event(meal_id=..., scheduled_at=..., meal_type="dinner")` with `recipe_id=null`.
- [ ] All 7 fixtures pass in the eval CI job. A single failure blocks ship.
- [ ] Regression: existing `create_meal_event` tests (calendar epic) pass unchanged. The XOR-reject path (422 `MEAL_EVENT_RECIPE_XOR_MEAL`) is tested here via the MCP boundary too — a tool call with both `recipe_id` and `meal_id` set surfaces the 422 as an MCP error.
- [ ] 100% branch coverage on the extended dispatch logic in `meal_planning.py`.

## Technical notes
- Signature extension only, not a rewrite — zero business logic in the MCP module; the calendar epic owns XOR validation at the API layer (epic § "Existing MCP tool — create_meal_event extension" and Design Principle 14).
- Fixture intents, expected tool traces, and the "why 7" rationale live in epic § "Eval fixtures — services/eval/fixtures/". The AI confirmation policy those fixtures exercise (CONFIRMATION_REQUIRED on degenerate remove and live-reference archive; everything else silent) landed with msa-3 and is specified in epic § "MCP Tools" — reuse it, don't re-implement.
- Eval harness: fixtures live in the existing `services/eval/fixtures/` directory; the CI job gains the 7 fixtures. If the harness is not yet CI-enforced, add it as a required check for this epic (epic § "Infrastructure Changes").
- No migration, no new AWS resources, no new env vars. API coverage is pinned at 100% — any uncovered line in services/api breaks CI.
- Dependency note: hard dependency on epic-meals-calendar (landed) for the `meal_events.meal_id` XOR migration + `CreateMealEvent` handler extension; soft dependency satisfied.
- Original BMAD story key: msa-4-backend-create-meal-event-mcp-accepts-meal-id-and-eval-fixtures.

## Status log
- 2026-07-27T17:10 — imported from BMAD (epic file + sprint-status.yaml) during BMAD→devx migration
- 2026-07-27T18:33:17-06:00 — claimed by /devx in session /devx-loop-2026-07-27T21-15-34-312-36147
- 2026-07-28T00:44:44.938Z — loop iteration 1: Extended the create_meal_event MCP tool with meal_id (plus calendar_id passthrough), fixed a dispatcher bug that made every MCP endpoint call fail at runtime, and added MCP-boundary tests including the XOR 422 path.
  - Change: create_meal_event MCP tool signature gains optional meal_id and calendar_id, forwarded verbatim to CreateMealEvent.Params; docstring updated to the spec wording; no XOR logic added to the MCP module
  - Change: Fixed call_endpoint/call_endpoint_async in mcp_server/server.py to pass endpoint args to the Endpoint constructor instead of to run(), which takes no arguments — previously every real MCP tool call returned 'Error: run() got an unexpected keyword argument ...'
  - Change: Updated the fake endpoints in test_server.py and test_integration.py to the real Endpoint calling convention and added a regression test pinning args-on-constructor
  - Change: Added MCP tests: recipe-only regression (meal_id/calendar_id stay None), meal-only path, both-ids passthrough, and an end-to-end boundary test through the real call_endpoint_async + real CreateMealEvent asserting the 422 MEAL_EVENT_RECIPE_XOR_MEAL surfaces as a single 'Error: ... mutually exclusive' tool result
  - Learning: call_endpoint/call_endpoint_async were dispatching args to run() rather than the constructor, so the entire MCP tool surface was non-functional at runtime. Every existing MCP test masked it (they patch call_endpoint_async or use fakes with run(*args, **kwargs)). Fixed here because AC6's boundary test cannot pass otherwise.
  - Learning: The MCP create_meal_event tool never sent calendar_id, which the calendar epic made required — the endpoint 400s before ever reaching the XOR gate. calendar_id was added as a passthrough to unblock the AC, but no MCP tool exposes calendar ids to the model, so the tool still can't succeed in a real conversation. Fixture #7 will need a decision on this.
  - Learning: tests/test_health.py is a deliberate red-stage commit on main (5a6174de) importing a nonexistent utils.services.db_probe: 17 errors + 1 failure and the only coverage gap (health_router.py:25-27, 99.98%). Expect this baseline red in every services/api full-suite run on this branch — do not chase it.
  - Learning: The worktree had no services/api venv; `poetry install` (~several minutes) plus `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/test` is required before any pytest run. No live DB is needed — conftest mocks it — but the Settings model rejects an empty DATABASE_URL at import time.
  - Learning: MockAsyncDatabase.find_by returns an owner-role CalendarUser for any (user_id, calendar_id) pair, which makes real-endpoint dispatch tests through the MCP boundary cheap to write.
  - Learning: services/eval has no chat/tool-trace fixture format yet — all existing fixtures are recipe-extraction (text/expected pairs) or ingredient_fidelity YAML. The 7 msa-4 fixtures need a new fixture shape and an evaluator wiring decision, likely building on ChatAgentEvaluator's qa_pairs.json + tool_calls trace.
