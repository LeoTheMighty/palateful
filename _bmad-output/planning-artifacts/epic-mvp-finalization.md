# Epic: Finalization of MVP — Dogfood-Confidence Release

## Overview

This epic exists to get Palateful to the state where Leo (and, by proxy, early users) trusts the pipeline enough to use the app daily. It is not a feature epic — it is a **confidence epic**. Every story removes a specific friction point that currently makes the end-to-end flow feel fragile, cramped, or untrustworthy.

The epic is scoped narrowly and ruthlessly: if a change doesn't ladder up to "I will actually open this app tomorrow morning," it doesn't belong here.

## Scope Themes

Three themes, one epic:

1. **Parser correctness** — the multi-image path must produce one recipe per group, reliably (mvp-1).
2. **Pipeline recovery & trust** — failed imports must be visible, retryable, and dismissible. No more ghost "in progress" imports that the app can't explain or clear (mvp-5 through mvp-9).
3. **Extraction quality** — JSON structured output for recipe steps so the end-to-end debug output feels coherent (mvp-2).
4. **Home screen breathing room** — the main surface should feel calm, not cramped (mvp-3, mvp-4).

## Design Principles (from Party Mode discussions)

1. **Parser and pipeline reliability is the #1 engineering investment** — if OCR import isn't trustworthy, nothing else matters.
2. **The pipeline must not lie about state** — no ghost "in progress" imports that have actually crashed. If something failed, the UI says so.
3. **Every failed state is recoverable** — retry and dismiss are two buttons that appear together, always. Nothing disappears silently, nothing stays forever.
4. **Retry resumes from the last successful stage** — we do not re-run OCR when only matching failed. Stage markers on `ImportItem` make this possible.
5. **JSON all the way down** — the extractor already produces structured JSON for the whole recipe; recipe steps should match, not be a markdown blob.
6. **Graceful degradation** — when structured extraction fails, fall back to legacy text rather than erroring. Leo would rather see something than nothing while dogfooding.
7. **Delete to clean up** — the best UI cleanup is removal. Prefer eliminating widgets over restyling them.
8. **Concurrent retry is an accepted risk** — Leo has explicitly accepted the possibility of two tasks racing on the same item for MVP. This is documented in mvp-6 and will be revisited if duplicate-recipe corruption is observed.

## Story Map

| # | Story | Theme | Priority | Est. Effort | Dependencies |
|---|-------|-------|----------|-------------|--------------|
| mvp-1 | Fix multi-image `group_index` bug | Parser correctness | 🔴 P0 | TBD | Diagnosis blocked — see status below |
| mvp-5 | Backend: `last_successful_stage` column + stuck-import sweeper | Pipeline recovery | 🔴 P0 | 1–2 d | None |
| mvp-6 | Backend: retry endpoint + stage-aware dispatch | Pipeline recovery | 🔴 P0 | 2 d | mvp-5 |
| mvp-7 | Backend: hard-dismiss endpoints (single + bulk) | Pipeline recovery | 🟡 P1 | 0.5 d | mvp-5 |
| mvp-8 | Flutter: failed-state row UI with Retry + Dismiss | Pipeline recovery | 🟡 P1 | 1–2 d | mvp-6, mvp-7 |
| mvp-2 | Structured recipe steps — schema, prompt, persistence, graceful fallback | Extraction quality | 🟡 P1 | 2–3 d | mvp-1, mvp-5 |
| mvp-3 | Home header: add Recipe Book icon, remove "See All" link | Home polish | 🟢 P2 | 0.5 d | None |
| mvp-4 | Filter redesign — pill + bottom sheet | Home polish | 🟢 P2 | 1–2 d | mvp-3 |
| mvp-9 | Flutter: "Clear all failed" in import hub + swipe-to-dismiss | Pipeline recovery | 🟢 P2 | 0.5 d | mvp-7, mvp-8 |

**Total estimated effort: 9–13 days**

## Sequencing

**Phase 1 — Parser correctness (blocked):** `mvp-1`. Awaiting diagnostic information from Leo. Initial fix hypothesis was invalidated by code review (see mvp-1 story "Blocker" section).

**Phase 2 — Pipeline recovery (backend):** `mvp-5 → mvp-6` (sequential, mvp-6 depends on stage markers from mvp-5). `mvp-7` can land in parallel with `mvp-6` once `mvp-5` is merged.

**Phase 3 — Pipeline recovery (frontend):** `mvp-8 → mvp-9`. Cannot start until backend endpoints from Phase 2 are live.

**Phase 4 — Extraction quality:** `mvp-2` goes after the pipeline recovery backbone is in place so that when structured-output failures occur, the retry + dismiss flow is already there to handle them. This is the biggest behavioral change and benefits most from landing on a stable base.

**Phase 5 — Home polish (parallelizable throughout):** `mvp-3 → mvp-4`. These are pure Flutter frontend with zero backend dependencies and can be picked up whenever a frontend slot opens up.

### Cross-phase priority

If forced to sequence strictly serially, the order is:

**mvp-5 → mvp-6 → mvp-7 → mvp-8 → mvp-1 → mvp-2 → mvp-3 → mvp-4 → mvp-9**

Rationale: pipeline recovery (mvp-5 through mvp-8) buys the most dogfood confidence per day of work. Once it lands, Leo can retry any failed import — including any caused by the still-undiagnosed multi-image bug in mvp-1 — which meaningfully reduces the urgency of mvp-1 itself. UI polish (mvp-3, mvp-4, mvp-9) goes last because it does not affect the trust gate.

## Explicit Cuts (Not In Scope)

These were discussed in Party Mode and deliberately excluded from this epic:

- **Dropping the legacy `recipes.instructions` column.** Keep-nullable for one release; delete in a follow-up tech-debt story once metrics confirm nothing still reads from it.
- **Step-level features** (per-step timers, ingredient-to-step references, cooking-mode integration). These are downstream of structured steps and belong in a future epic.
- **New filter capabilities.** This epic only *rehomes* existing meal and vibe filters into a bottom sheet — it does not add new filter types.
- **Live per-stage progress UI** (the "State 1" design Sally proposed): per-stage progress sheet with live elapsed timers. Goes into a future "Pipeline Transparency" epic.
- **Proactive "taking longer than expected" detection** (the "State 2" design): requires stage-level telemetry infrastructure. Future epic.
- **Concurrent retry guard** (`retry_in_progress` column + atomic check): Leo has accepted the risk of concurrent retries racing on the same item. Can be added later if duplicate-recipe corruption is observed in practice.
- **Soft-delete / 24h trash bin for dismissed imports.** Dismissals are hard — a snackbar undo in the UI is the only safety net.

## Definition of Done (Epic Level)

- All 9 stories merged and deployed to Leo's dogfood build.
- Leo has imported at least 10 recipes via multi-image photo flow without hitting the `group_index` bug (mvp-1 resolved).
- Every failed import Leo encounters can be retried from the last successful stage, or dismissed in one tap.
- The "In Progress" section on the Add Recipe screen never shows imports older than 15 minutes unless they are genuinely still running.
- Extractor structured-output fallback rate < 5% on Leo's real recipe inputs.
- Leo's subjective "would I open this app tomorrow" answer is yes.

## References

- Party Mode discussions covering scoping, sequencing, risk assessment (Round 1 and Round 2)
- Existing parser pipeline: `libraries/utils/utils/tasks/import_tasks/watch_parser_batch_task.py`
- Existing extractor: `libraries/utils/utils/services/recipe_extractors/ai_extractor.py`
- Home screen: `app/lib/features/home/home_screen.dart`
- Recipe books route: `/recipe-books` via `app/lib/core/router/app_router.dart`
- Import pipeline research findings live in the Round 2 Party Mode discussion
