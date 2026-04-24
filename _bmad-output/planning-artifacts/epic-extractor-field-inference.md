<!-- refined via party-mode 2026-04-20 -->
# Epic: Extractor Field-Level Inference — Best-Guess Recipe Metadata with Sparkle Provenance

## Overview

Every extractor prompt today carries the rule *"Only include fields you can find in the content"*. That's safe, but it leaves Review Import with blank `cook_time_minutes`, `prep_time_minutes`, `total_time_minutes`, `servings`, `description`, `cuisine`, `category`, and vibe fields on any source that doesn't surface them — which, in practice, is most OCR'd cookbook pages and a good chunk of TikTok-style URL imports. Leo's ask: the extractor should ballpark these fields, even if it tanks the confidence score, because "throwing something up there" is better UX than a blank cook-time input when the rest of the recipe is clearly a 30-minute weeknight dinner.

This epic ships end-to-end **recipe-level field inference**:

1. **Extractor prompts** (ai, vision, text) get a new "extract OR best-guess" rule for a fixed 9-field allow-list, plus instructions to self-report which fields were guessed via a top-level `inferred_fields` array.
2. **Backend guardrails** clamp inferred numeric values to sane ranges, cap string fields, drop invalid vibes, and log every clamp/drop to `error_logs`.
3. **Confidence penalty** — each inferred field subtracts 0.05 from the resolved score (capped at 0.25 total). The user asked for "tanks the confidence score"; this is that tanking, calibrated.
4. **API surface** — `inferred_fields: list[str]` hoisted to the response root on `GetImportItem` / `list_import_items` / `list_import_jobs` / `GetRecipe`. New `POST /v1/import-items/{id}/corrections` captures user overrides.
5. **Flutter `InferredFieldBadge`** — a 14pt sparkle (`Icons.auto_awesome`) next to any inferable-field label on Review Import and Recipe Edit. Tap opens a short bottom-sheet explainer. Badge disappears the instant the user edits the field; any edit is treated as acceptance-or-override.
6. **Eval** — two new soft-gate metrics: `field_inference_accuracy` (how close inferred values land to ground truth) and `hallucination_rate` (an anti-metric — how often the extractor guessed despite the source having an answer).

**Per-ingredient inference is explicitly out of scope.** Leo flagged the hallucination risk; this epic proves the pattern on recipe-level fields only, and the correction-log data it generates informs a follow-up `epic-extractor-ingredient-inference`.

## Goal

A user photo-imports a cookbook page that has no cook time printed. Review Import opens, cook_time shows "25" with a sparkle badge next to the label. Leo taps the sparkle: "AI guessed this value. Verify or edit it below — your correction helps the extractor learn." He changes it to 30. The badge vanishes. An `error_logs` row captures `{field: "cook_time_minutes", original: 25, corrected: 30, was_inferred: true}`. He taps Save. The recipe lands in the book with `inferred_fields: ["prep_time_minutes", "servings", "cuisine"]` still present (he didn't touch those — so they stay flagged as guesses even after save, and Recipe Edit will show the sparkles next time).

## End-User Flow

1. Leo photo-imports a cookbook page (`Salted Caramel Brownies`). The source has a title, ingredient list, and numbered steps — but no printed cook time, prep time, servings, or intro description.
2. Backend runs the usual pipeline: parser → `ai_extractor` → `match_ingredients_task` → persists `parsed_recipe`.
3. The extractor prompt is now in inference mode (default). The model reads the steps ("Bake at 350°F for 25–30 minutes"), infers `cook_time_minutes: 27`, infers `prep_time_minutes: 15` from the ingredient complexity, infers `servings: 16` (from a 9×13 pan implied by the recipe), infers `cuisine: "American"`, infers `category: "Dessert"`, infers `description: "Rich, fudgy brownies with a salted caramel swirl."`, infers `primary_vibe: "indulgent"`. It emits `inferred_fields: ["prep_time_minutes", "cook_time_minutes", "servings", "description", "cuisine", "category", "primary_vibe"]`.
4. `extract_recipe_task` runs the inferred values through guardrails — all pass the clamp ranges. Applies a confidence penalty of `0.05 × 5 = 0.25` (capped) on top of the base 0.72 heuristic, yielding `confidence_score: 0.47`, `confidence_source: "heuristic"`. Persists `parsed_recipe.inferred_fields` with the 7 names.
5. Leo opens Review Import. The header shows a `ConfidenceBadge` of 47% (yellow — Needs Review — by existing thresholds). Cook time field shows "27" with a ✨ next to the "Cook time" label. Prep time: "15" ✨. Servings: "16" ✨. Description field auto-expanded (populated; not blank) with "Rich, fudgy brownies…" and a ✨ next to the label. Cuisine dropdown: "American" ✨. Category: "Dessert" ✨. Primary vibe: `indulgent` ✨. Ingredients and steps have no sparkles — those were extracted, not inferred.
6. Leo taps the sparkle next to "Cook time" — a quick bottom sheet: *"AI guessed this value. Verify or edit it below — your correction helps the extractor learn."* He dismisses the sheet.
7. Leo changes cook time from "27" to "30" — the sparkle disappears the instant the value changes. On focus-loss (~1.5s debounced), the client dispatches `POST /v1/import-items/{id}/corrections` with `{field: "cook_time_minutes", corrected: 30}`. Server resolves original from `parsed_recipe.cook_time_minutes` (still 27 on disk), writes an `error_logs` row: `{service: "audit", error_type: "InferredFieldCorrected", metadata: {field: "cook_time_minutes", original: 27, corrected: 30, was_inferred: true}}`.
8. Leo leaves prep_time, servings, description, cuisine, category, vibe alone. Taps Save. `create_recipe_task` copies `inferred_fields` minus `cook_time_minutes` (he edited it — it's no longer inferred) into `recipes.inferred_fields`.
9. A week later, Leo opens the recipe and taps Edit. Recipe Edit screen loads with `inferred_fields = ["prep_time_minutes", "servings", "description", "cuisine", "category", "primary_vibe"]`. Sparkles still on those 6 fields. He edits prep_time from 15 to 10 — sparkle vanishes, field's correction is logged locally only (recipe-edit dispatch deferred per design principle 9). He saves. `recipes.inferred_fields` updates to a 5-item list.
10. Some other recipe he imports gets cook_time extracted cleanly from source — `ai_extractor` returns `cook_time_minutes: 45`, `inferred_fields: []`. Confidence score reflects only the base heuristic, no penalty. No sparkle on any field. Review Import looks like Review Import always has.

## Frontend Changes

**Required — small.** One new widget; two screens get badge wiring + correction-dispatch on Review Import.

### New `InferredFieldBadge` widget

- Path: `app/lib/features/recipes/add_recipe/widgets/inferred_field_badge.dart`.
- Stateless. Props: `{VoidCallback? onTap}`.
- Renders a 14pt `Icons.auto_awesome` glyph in `colorScheme.tertiary`. Default `onTap` opens a `showModalBottomSheet` with explainer text: *"AI guessed this value. Verify or edit it below — your correction helps the extractor learn."*
- Semantics: `Semantics(label: "AI-inferred value, tap for details", button: true)`.
- 40pt tap target via `InkWell` with 13pt all-around padding.

### Review Import wiring

- `import_item_review_screen.dart` — pull `inferred_fields: Set<String>` from the loaded `ImportItem`. Store in local `_inferredFields` state so edits can mutate the set.
- For each of the 9 inferable fields, render the badge inline next to the field label when `_inferredFields.contains(<field_name>)`:
  - `prep_time_minutes` — next to "Prep (min)" label.
  - `cook_time_minutes` — next to "Cook (min)" label.
  - `total_time_minutes` — next to "Total (min)" label (if field visible).
  - `servings` — next to "Servings" label.
  - `description` — next to the description section header.
  - `cuisine` — next to "Cuisine" label.
  - `category` — next to "Category" label.
  - `primary_vibe` — next to primary vibe chip.
  - `secondary_vibe` — next to secondary vibe chip.
- On first value change of a badged field: remove the field name from `_inferredFields` (badge disappears immediately). Schedule a 1500ms debounced dispatch of `POST /v1/import-items/{id}/corrections` with `{field, corrected}` on focus-loss. Dispatch is best-effort — network errors swallow silently with a debug log.
- Inferable-field allow-list lives in `app/lib/core/constants/inferable_fields.dart` as `const kInferableFields = {...}` (mirrors backend, hand-synced — tested by a contract test in `app/test/core/constants/inferable_fields_test.dart` that asserts the set matches the backend response shape).

### Recipe Edit wiring

- `edit_recipe_screen.dart` — symmetric pattern. Pull `inferred_fields` from the recipe payload. Render badges next to the same 9 field labels when present. Removing a field from the local set on edit is identical.
- **Correction dispatch is NOT wired on Recipe Edit in v1** — `POST /v1/import-items/{id}/corrections` is the only endpoint; recipe-edit corrections don't have a target. Design principle 9 makes this an explicit deferral; the behaviour (badge dismissal on edit) is wired so the UX stays consistent.
- On save, Recipe Edit sends the mutated `inferred_fields` set back in the `UpdateRecipe` payload. Backend trusts the client's set (server-side integrity: `GetRecipe` always reads from `recipes.inferred_fields`, and the value can only shrink — a server-side assertion enforces `new_set ⊆ old_set`).

### `ApiClient` additions

- `Future<void> submitImportCorrection({required String itemId, required String field, required dynamic corrected})` — wraps `POST /v1/import-items/{itemId}/corrections`. Accepts dynamic because fields can be int (times, servings), string (description, cuisine, category, vibes).

## Backend Changes

**Required — medium.** Prompt rewrites across three extractors, one new module for inference-mode prompt assembly, a guardrails module, a schema + dataclass field, a migration for `recipes.inferred_fields`, API-surface exposure, and one new endpoint.

### `EXTRACTOR_INFER_MISSING_FIELDS` flag + `inference_prompt.py`

- New module `libraries/utils/utils/services/recipe_extractors/inference_prompt.py`:
  ```python
  INFERABLE_FIELDS: tuple[str, ...] = (
      "prep_time_minutes",
      "cook_time_minutes",
      "total_time_minutes",
      "servings",
      "description",
      "cuisine",
      "category",
      "primary_vibe",
      "secondary_vibe",
  )

  def infer_missing_fields() -> bool: ...
  def inference_rule() -> str: ...  # Prompt fragment — empty string when flag off.
  ```
- `inference_rule()` returns the prompt block spelling out:
  - Which fields may be inferred (from `INFERABLE_FIELDS`).
  - That inferred values must be **plausible given the visible recipe content** — not invented from nothing.
  - That every inferred field name MUST appear in a top-level `inferred_fields` array.
  - `inferred_fields` defaults to `[]` (empty list, not null) when nothing was inferred.
  - One worked example of an inference flowing into the annotation.
- Flag read pattern matches `confidence_prompt.py` — `os.environ.get("EXTRACTOR_INFER_MISSING_FIELDS", "true")`, read at call time.

### Extractor prompt rewrites (`ai_extractor.py`, `vision_extractor.py`, `text_extractor.py`)

- Each prompt's current "Only include fields you can find" or "Set missing fields to null rather than guessing" rule is scoped to NON-inferable fields only when the flag is on. When flag is off, the rule reverts to its prior text (fully suppresses inference).
- Each prompt's field listing splices `inference_rule()` in after the confidence rule. Empty string (flag off) means the block vanishes entirely.
- `json_ld.py` untouched. Its output always has `inferred_fields: []`.

### `ExtractedRecipe.inferred_fields`

- `libraries/utils/utils/services/recipe_extractors/base.py` — add `inferred_fields: list[str] = field(default_factory=list)` on `ExtractedRecipe`.
- Each extractor's `_parse_ai_response` (or equivalent) populates it from the raw LLM payload: `data.get("inferred_fields") or []` — defensive-default to empty list. Filters out any entry not in `INFERABLE_FIELDS` and dedupes.

### `inference_guardrails.py`

- `libraries/utils/utils/services/recipe_extractors/inference_guardrails.py` exposes `apply_guardrails(recipe: ExtractedRecipe, import_item_id: str | None) -> ExtractedRecipe`. Iterates `recipe.inferred_fields`; per field:
  - `prep_time_minutes`: clamp to [1, 240]; log to `error_logs` if raw value was outside.
  - `cook_time_minutes`: clamp to [1, 720]; log if outside.
  - `total_time_minutes`: clamp to [1, 960]; log if outside.
  - `servings`: clamp to [1, 24]; log if outside.
  - `description`: truncate to 240 chars at word boundary; log if truncated.
  - `cuisine`: truncate to 40 chars; log if truncated.
  - `category`: truncate to 40 chars; log if truncated.
  - `primary_vibe`, `secondary_vibe`: must pass `validate_vibe()`; drop to None + remove from `inferred_fields` if invalid; log drop.
- Log rows go via a new helper `log_inferred_field_clamp(import_item_id, field, raw, clamped_or_dropped)` in `libraries/utils/utils/logging/inference_logging.py` — `service="audit"`, `error_type="InferredFieldClamped"`. AST-lint test enforces no bare log calls use the same error_type (follows the precedent established by `riip-*` and `irrd-*`).
- Returns a new / mutated `ExtractedRecipe` — the caller is responsible for persisting the result.

### `confidence_heuristic.py` — `apply_inference_penalty`

- New helper:
  ```python
  def apply_inference_penalty(score: float, inferred_count: int) -> float:
      penalty = 0.05 * min(inferred_count, 5)
      return max(0.0, min(1.0, score - penalty))
  ```
- Called by `extract_recipe_task` AFTER `resolve_confidence()` regardless of source (model or heuristic). No-op when `inferred_count == 0`.

### `extract_recipe_task.py`

- Sequence after extraction:
  1. Apply `inference_guardrails.apply_guardrails(recipe, import_item_id)`.
  2. Persist `parsed_recipe.inferred_fields = recipe.inferred_fields` (top-level key, alongside `confidence_score` + `confidence_source`).
  3. Resolve confidence via existing `resolve_confidence(raw_data, recipe)`.
  4. Apply `apply_inference_penalty(score, len(recipe.inferred_fields))`.
  5. Persist penalized score as `parsed_recipe.confidence_score`.
- Unchanged: normalization of units, ingredient handling, recipe serialization.

### `recipes.inferred_fields` column + `create_recipe_task`

- Migration: `ALTER TABLE recipes ADD COLUMN inferred_fields JSONB NOT NULL DEFAULT '[]'::jsonb;`. Reversible. Down-migration drops the column.
- `libraries/utils/utils/models/recipe.py` — SQLAlchemy column added.
- `create_recipe_task.py` — when creating the recipe from an approved import item, copy `import_item.parsed_recipe.get("inferred_fields", [])` into `Recipe.inferred_fields`. Filter to allow-list server-side (defense in depth).
- `GetRecipe` + `UpdateRecipe` surface + accept the field. `UpdateRecipe` enforces `new_set ⊆ old_set` (can only shrink) — 400 if client tries to add new fields, with error message `"inferred_fields can only be reduced, not expanded"`.

### API surface

- `GetImportItem`, `list_import_items`, `list_import_jobs` — hoist `inferred_fields` from `parsed_recipe` to the item response root (mirrors the existing `confidence_score` hoist pattern). Always present, never null — empty list for non-inferred items. Legacy rows without the key return `[]`.
- `GetRecipe`, `UpdateRecipe` — surface `recipes.inferred_fields` at response root. UpdateRecipe accepts `inferred_fields` as optional input; enforces shrink-only rule.

### `POST /v1/import-items/{id}/corrections` endpoint

- Path: `services/api/src/api/v1/import_item/submit_correction.py`.
- Body: `{field: str, corrected: Any}`.
- Validation:
  - `field` must be in `INFERABLE_FIELDS` (imported from `utils.services.recipe_extractors.inference_prompt`). 400 otherwise.
  - Caller must own the import-item. 403 otherwise.
  - 404 if item doesn't exist.
- Server looks up `original` from `parsed_recipe[field]`, reads `was_inferred` from `field in parsed_recipe.get("inferred_fields", [])`, writes one `error_logs` row with `service="audit"`, `error_type="InferredFieldCorrected"`, `import_item_id = item.id`, `user_id = caller.id`, `metadata = {"field", "original", "corrected", "was_inferred"}`.
- Response: 204 No Content on success.
- No new indexes needed; `error_logs` is already indexed on `created_at + service` (from prior epics).

### Eval metrics

- `services/eval/src/metrics/field_inference_accuracy.py`:
  - Iterates fixtures; for each inferable field with ground-truth AND extractor-output presence in `inferred_fields`, scores:
    - Numeric (times, servings): 1.0 if within ±20% (or ±1 for servings where 20% rounds to 0); 0.0 otherwise.
    - Vibes / cuisine / category: 1.0 if exact-match (case-insensitive); 0.0 otherwise.
    - Description: Levenshtein-based similarity against first 200 chars of ground truth; 1.0 if similarity ≥ 0.6, otherwise the raw similarity.
  - Reports per-field means and an overall mean. Soft gate: overall ≥ 0.6.
- `services/eval/src/metrics/hallucination_rate.py`:
  - For each fixture × each inferable field where ground-truth exists, if extractor marked it in `inferred_fields`, count as hallucination (source had the answer, model guessed).
  - Rate = hallucinations / (total extractable field × fixture count). Soft gate: ≤ 0.15.
- Both metrics register in `services/eval/eval.config.yaml`. Baselines pinned to `services/eval/baselines/field_inference_baseline.json` post-first-run.

## Infrastructure Changes

**None.**

- One Alembic migration for `recipes.inferred_fields` column.
- One new feature-flag env var (`EXTRACTOR_INFER_MISSING_FIELDS`) — no Terraform changes (flipped via ECS task-def flag flip, same pattern as existing `EXTRACTOR_EMIT_CONFIDENCE`).
- No new AWS resources, no new secrets, no new IAM, no CI/CD changes.

## Design Principles (refined via party-mode 2026-04-20)

1. **Inference is a bounded allow-list.** Nine fields, fixed. Name, ingredients, steps, source-URL etc. are never inferred — their absence stays absence. The allow-list is a single source of truth (`INFERABLE_FIELDS`) that backend guardrails, the correction endpoint, and the Flutter contract test all read from.
2. **Server-authoritative clamps.** The client trusts the persisted value and does no re-validation. The guardrails module is the single truth for range enforcement. This keeps Flutter free of duplicated business rules and makes the prompt → persisted value contract testable server-only.
3. **Confidence penalty is flat, not weighted.** `0.05 × min(inferred_count, 5)` regardless of which fields were inferred. Weighting is premature until we have correction-log data. The rule is simple, legible, and tuneable via a single constant.
4. **Badge is derived state, not UI state.** `InferredFieldBadge` visibility is driven exclusively by the parent's `inferredFields` set. The parent mutates the set on user edit; the badge re-renders automatically. No ref, no imperative show/hide.
5. **Any-edit counts as acceptance.** No "accept" button. The user engaging with the field is the signal; whether they keep the inferred value or change it doesn't matter for the UX flow (the sparkle is gone either way). It matters for the correction log: unchanged values don't dispatch; changed values do.
6. **`inferred_fields` can only shrink.** When Recipe Edit saves, the client can remove field names (they edited, the field is no longer inferred) but cannot add new ones (they can't mark a field as newly inferred). Server enforces via `new_set ⊆ old_set`. This prevents a malicious or buggy client from synthesizing inference metadata.
7. **Flag-off is binary-clean.** Prompt reverts, guardrails skip, penalty skips, `inferred_fields` persists as `[]`. No half-state where the penalty applied but the prompt didn't. One env-var, one switch.
8. **Feedback-log is the killer feature of this epic.** The sparkle UX is nice, but the `error_logs` rows it generates are the evergreen signal that will tune prompts + weights in the next iteration. Every correction row is one data point that says "the model guessed X, the user wanted Y." Design principle: make the log comprehensive now even if we don't have the dashboard to read it yet.
9. **Recipe-Edit correction dispatch is deliberately deferred.** The badge-dismiss-on-edit is wired on Recipe Edit for UX consistency, but the `POST` round trip only fires from Review Import. Review Import is where the signal volume is — new imports every day. Recipe Edit is lower-volume (users edit less often) and needs a different endpoint shape (recipe-scoped, not import-item-scoped). Consolidate in a future dashboard epic.
10. **`json_ld` is the clean path.** Schema.org markup is authoritative; `json_ld_extractor` never infers. It emits `inferred_fields: []` and the task layer copies that through. The prompt changes do not touch `json_ld.py`. The feature flag has no effect on json_ld extractions.
11. **No retroactive enrichment.** Existing rows without `inferred_fields` render as `[]` via defensive defaults in the API response layer and the Flutter decoder. No backfill job, no migration that assumes the column existed.
12. **Eval gates are soft in v1.** Both new metrics are measured + reported, neither blocks CI. The user explicitly asked "is this a doable UX" — we need to see real numbers on real traffic before pinning thresholds. Gate-tightening is a follow-up story if / when the data supports it.
13. **Description + vibes get sparkles for real.** Vibes today are extracted freeform from source even when the source doesn't state them — which is already a form of inference, it just isn't annotated. This epic formalizes the provenance: if the source literally said "comfort food" → not inferred; if the model synthesized "comfort" from the ingredient list → inferred + sparkled. Prompt discipline enforces the distinction; eval `hallucination_rate` catches regressions.
14. **Correction dispatch is debounced + best-effort.** 1500ms debounce batches rapid edits; focus-loss fires the dispatch. Network errors log but don't block save. The user never sees a spinner or error for correction logging — it's a side channel, not a user-blocking path.
15. **Cost is an afterthought — the feature is the product.** ~350 tokens of prompt growth is $0.00005 / extraction. Not a decision gate. Measured once and forgotten.

## File Structure (anticipated)

```
libraries/utils/utils/services/recipe_extractors/
├── inference_prompt.py                         # NEW — INFERABLE_FIELDS + infer_missing_fields() + inference_rule()
├── inference_guardrails.py                     # NEW — apply_guardrails + per-field clamps
├── confidence_heuristic.py                     # MODIFIED — apply_inference_penalty helper
├── ai_extractor.py                             # MODIFIED — splice inference_rule into prompt; parse inferred_fields
├── vision_extractor.py                         # MODIFIED — same
├── text_extractor.py                           # MODIFIED — same + scope "Only if present" rule to non-inferable
├── base.py                                     # MODIFIED — ExtractedRecipe.inferred_fields field
└── json_ld.py                                  # UNTOUCHED — always emits []

libraries/utils/utils/logging/
└── inference_logging.py                        # NEW — log_inferred_field_clamp helper (AST-lint enforced)

libraries/utils/utils/tasks/import_tasks/
├── extract_recipe_task.py                      # MODIFIED — guardrails pass, penalty apply, inferred_fields persist
└── create_recipe_task.py                       # MODIFIED — copy inferred_fields to Recipe on create

libraries/utils/utils/models/
└── recipe.py                                   # MODIFIED — inferred_fields JSONB column

libraries/utils/utils/schemas/
└── recipe_extraction_schema.py                 # MODIFIED — inferred_fields: array[string] on recipe root

services/api/src/api/v1/import_item/
├── submit_correction.py                        # NEW — POST /v1/import-items/{id}/corrections
├── get_import_item.py                          # MODIFIED — hoist inferred_fields
├── list_import_items.py                        # MODIFIED — hoist inferred_fields
└── list_import_jobs.py                         # MODIFIED — hoist inferred_fields per item summary

services/api/src/api/v1/recipes/
├── get_recipe.py                               # MODIFIED — surface inferred_fields
└── update_recipe.py                            # MODIFIED — accept inferred_fields (shrink-only validation)

services/migrator/migrations/versions/
└── XXXX_add_inferred_fields_to_recipes.py      # NEW migration

services/eval/src/metrics/
├── field_inference_accuracy.py                 # NEW — per-field accuracy metric
└── hallucination_rate.py                       # NEW — anti-metric

services/eval/baselines/
└── field_inference_baseline.json               # NEW — post-first-run baseline

services/eval/
└── eval.config.yaml                            # MODIFIED — register new metrics

app/lib/features/recipes/add_recipe/widgets/
└── inferred_field_badge.dart                   # NEW — ✨ sparkle badge

app/lib/features/recipes/add_recipe/
└── import_item_review_screen.dart              # MODIFIED — badge wiring on 9 fields + correction dispatch

app/lib/features/recipes/
└── edit_recipe_screen.dart                     # MODIFIED — badge wiring on 9 fields (no dispatch v1)

app/lib/core/constants/
└── inferable_fields.dart                       # NEW — kInferableFields set (mirrors backend)

app/lib/core/api_client/
└── api_client.dart                             # MODIFIED — submitImportCorrection method

app/lib/features/recipes/add_recipe/models/
└── import_item.dart                            # MODIFIED — inferredFields field

app/lib/features/recipes/models/
└── recipe.dart                                 # MODIFIED — inferredFields field
```

## Story Map

| # | Story | Priority | Est. Effort | Dependencies |
|---|-------|----------|-------------|--------------|
| efi-1 | Backend — `INFERABLE_FIELDS` + `EXTRACTOR_INFER_MISSING_FIELDS` flag + `inference_prompt.py` + `inference_guardrails.py` + `apply_inference_penalty` helper + `log_inferred_field_clamp` helper (no live wiring yet) | 🔴 P0 | 0.75 d | None |
| efi-2 | Backend — extractor prompt rewrites (ai, vision, text) + `ExtractedRecipe.inferred_fields` + per-extractor parsing + schema update | 🔴 P0 | 1 d | efi-1 |
| efi-3 | Backend — `extract_recipe_task` wiring (guardrails + penalty + persist) + `recipes.inferred_fields` migration + `create_recipe_task` copy + `GetRecipe` / `UpdateRecipe` surface with shrink-only validation | 🔴 P0 | 1 d | efi-2 |
| efi-4 | Backend — `inferred_fields` hoist on import-item responses + `POST /v1/import-items/{id}/corrections` endpoint + tests | 🔴 P0 | 0.75 d | efi-3 |
| efi-5 | Flutter — `InferredFieldBadge` widget + `kInferableFields` constant + `submitImportCorrection` client method + model decoders (`ImportItem.inferredFields`, `Recipe.inferredFields`) | 🔴 P0 | 0.75 d | efi-4 |
| efi-6 | Flutter — Review Import wiring (badge on 9 fields + dismiss-on-edit + debounced correction dispatch) | 🔴 P0 | 1 d | efi-5 |
| efi-7 | Flutter — Recipe Edit wiring (badge on 9 fields + dismiss-on-edit, no dispatch v1) + UpdateRecipe round-trip sends shrunken `inferred_fields` | 🟡 P1 | 0.5 d | efi-5 |
| efi-8 | Eval — `field_inference_accuracy` + `hallucination_rate` metrics + `eval.config.yaml` wiring + baseline + per-extractor run + report | 🟡 P1 | 0.75 d | efi-3 |

**Total estimated effort: 6.5 days**

**Parallel tracks:**
- Track A (backend spine): efi-1 → efi-2 → efi-3 → efi-4 (serial)
- Track B (eval): efi-8 parallel with efi-4 after efi-3 lands
- Track C (frontend): efi-5 → efi-6 → efi-7 (serial, blocked on efi-4)

---

## Story efi-1: Backend — `INFERABLE_FIELDS` + flag + `inference_prompt` + `inference_guardrails` + `apply_inference_penalty` + `log_inferred_field_clamp`

As the extractor pipeline,
I want a flag-gated inference-rule generator, per-field guardrails, a confidence-penalty helper, and a sanctioned logging helper — all testable in isolation before any prompt or task is wired,
so each piece is verified end-to-end before the prompt rewrites or persistence layer depend on them.

### Acceptance Criteria

1. `libraries/utils/utils/services/recipe_extractors/inference_prompt.py` exports `INFERABLE_FIELDS: tuple[str, ...]` exactly matching the 9-field allow-list; `infer_missing_fields() -> bool` reads `EXTRACTOR_INFER_MISSING_FIELDS` via `os.environ.get(..., "true")` at call time (not startup); `inference_rule() -> str` returns the prompt fragment (or empty string when flag is off).
2. `inference_rule()` fragment includes: (a) the exact 9-field list by schema name, (b) instruction to produce plausible values based on visible recipe signals (step count, ingredient complexity, implied pan / serving size, etc.), (c) instruction to always emit `inferred_fields` as an array (empty when nothing inferred), (d) one worked example of an inferred `cook_time_minutes`.
3. `libraries/utils/utils/services/recipe_extractors/inference_guardrails.py` exposes `apply_guardrails(recipe: ExtractedRecipe, import_item_id: str | None) -> ExtractedRecipe` that iterates `recipe.inferred_fields`, applies per-field clamp/truncate/validate rules (ranges per FR-EFI-5), mutates the recipe in place (or returns a new copy — pick one, document it), and removes failed-validation fields (e.g., invalid vibe) from `inferred_fields`.
4. Each clamp/drop event writes one `error_logs` row via the sanctioned helper `log_inferred_field_clamp(import_item_id, field, raw, clamped_or_dropped, reason)` in `libraries/utils/utils/logging/inference_logging.py`: `service="audit"`, `error_type="InferredFieldClamped"`, `metadata={"field", "raw", "clamped_or_dropped", "reason"}`.
5. **AST-lint enforcement test** `libraries/utils/tests/logging/test_inference_log_enforcement.py` scans all `.py` files under `libraries/utils/` + `services/api/src/` and asserts no call site writes `error_type='InferredFieldClamped'` outside of `log_inferred_field_clamp` (mirrors the `riip-*` + `irrd-*` AST-lint precedent). Fails CI on bare log calls.
6. `libraries/utils/utils/services/recipe_extractors/confidence_heuristic.py` gets `apply_inference_penalty(score: float, inferred_count: int) -> float` — subtract `0.05 × min(inferred_count, 5)`, clamp to [0, 1].
7. Unit tests (isolated — no DB, no live extractor):
    - `infer_missing_fields()`: default on; false when `EXTRACTOR_INFER_MISSING_FIELDS=false`; off for `0`/`no`/`off` variants.
    - `inference_rule()`: returns non-empty when on, empty string when off.
    - `INFERABLE_FIELDS` has exactly 9 names, all schema-valid.
    - `apply_guardrails`: input cook_time=1000 → clamped to 720 + one audit row written (mock the logger); input primary_vibe="bogus" → dropped to None AND removed from `inferred_fields`; input description of 500 chars → truncated to 240 + audit row; input all-valid → no audit rows, recipe unchanged.
    - `apply_inference_penalty`: 6 inferred → penalty capped at 0.25; 2 inferred → 0.10 penalty; 0 inferred → no-op.
8. No extractor, task, schema, or API code is modified in this story. `ExtractedRecipe.inferred_fields` is referenced by type hint only (forward ref or `Any`-typed for now); story efi-2 adds the real field.

### Key Files

- Create: `libraries/utils/utils/services/recipe_extractors/inference_prompt.py`
- Create: `libraries/utils/utils/services/recipe_extractors/inference_guardrails.py`
- Create: `libraries/utils/utils/logging/inference_logging.py`
- Modify: `libraries/utils/utils/services/recipe_extractors/confidence_heuristic.py`
- Tests: `libraries/utils/tests/services/recipe_extractors/test_inference_prompt.py`, `test_inference_guardrails.py`, `test_confidence_penalty.py`, `libraries/utils/tests/logging/test_inference_log_enforcement.py`

---

## Story efi-2: Backend — extractor prompt rewrites + `ExtractedRecipe.inferred_fields` + parsing + schema

As each LLM-based extractor,
I want my prompt to tell the model to infer specific missing fields and self-report which ones were inferred, and my parsing to surface the `inferred_fields` array on the dataclass,
so the pipeline downstream can apply guardrails + penalty + persistence without extractors carrying that logic.

### Acceptance Criteria

1. `base.py` — `ExtractedRecipe` gains `inferred_fields: list[str] = field(default_factory=list)`. Field is positioned after `confidence_source`, before `raw_data`.
2. `ai_extractor.py` — prompt splices `inference_rule()` after `confidence_rule()`. The existing "Only include fields you can find" rule is rewritten to apply only when flag is off; when flag is on, it's replaced with "Only include non-inferable fields you can find in the content (see Inference Rule above)." `_parse_ai_response` reads `data.get("inferred_fields") or []`, filters to `INFERABLE_FIELDS`, dedupes, assigns to the recipe.
3. `vision_extractor.py` — same prompt splice + parse behaviour. The existing "infer from context when characters are unclear" instruction stays (it's about OCR disambiguation, not field inference); the new inference rule adds a parallel instruction for field-level inference.
4. `text_extractor.py` — same prompt splice + parse behaviour. The `"Set missing fields to null rather than guessing"` line is scoped to non-inferable fields when flag on, kept verbatim when flag off.
5. `json_ld.py` — no changes. Its `_parse_recipe_data` ensures `ExtractedRecipe.inferred_fields` is `[]` (default factory does this; document with a comment).
6. `libraries/utils/utils/schemas/recipe_extraction_schema.py` — `inferred_fields` added to the recipe-root schema as `{"type": "array", "items": {"type": "string"}}`. Optional (not in `required`). Schema is permissive; no new `additionalProperties: false`.
7. Feature-flag contract tests per extractor:
    - Flag on: prompt contains "inferred_fields" and the 9-field list by schema name.
    - Flag off: prompt does not mention "inferred_fields" or "infer"; prior "Only include present" phrasing is intact.
8. Parsing tests per extractor (mock LLM output):
    - Model emits `inferred_fields: ["cook_time_minutes", "servings"]` → recipe has that list.
    - Model emits `inferred_fields: ["cook_time_minutes", "bogus_field"]` → recipe has `["cook_time_minutes"]` (filtered).
    - Model emits no `inferred_fields` key → recipe has `[]`.
    - Model emits `inferred_fields: null` → recipe has `[]`.
    - Model emits duplicates → deduped.
9. **No live wiring of guardrails, penalty, or API surface in this story.** The dataclass has the field, the prompts have the instructions, the parsers populate the field. Downstream consumers come in efi-3 / efi-4.
10. Regression: existing extractor tests continue to pass without modification (the `inferred_fields` field just defaults to `[]`).

### Key Files

- Modify: `libraries/utils/utils/services/recipe_extractors/base.py`
- Modify: `libraries/utils/utils/services/recipe_extractors/ai_extractor.py`
- Modify: `libraries/utils/utils/services/recipe_extractors/vision_extractor.py`
- Modify: `libraries/utils/utils/services/recipe_extractors/text_extractor.py`
- Modify: `libraries/utils/utils/services/recipe_extractors/json_ld.py` (add comment only)
- Modify: `libraries/utils/utils/schemas/recipe_extraction_schema.py`
- Tests: per-extractor prompt + parsing tests; schema validation tests

---

## Story efi-3: Backend — `extract_recipe_task` wires guardrails + penalty + persist; `recipes.inferred_fields` migration + `create_recipe_task` copy; `GetRecipe` / `UpdateRecipe` surface with shrink-only

As the import-and-recipe persistence layer,
I want `inferred_fields` to flow from the extractor through guardrails, the confidence penalty, and the recipes table end-to-end, with `UpdateRecipe` enforcing that `inferred_fields` can only shrink,
so the field's lifecycle is fully server-authoritative and the Flutter client cannot forge or expand provenance.

### Acceptance Criteria

1. `extract_recipe_task.py` sequence after extraction: call `apply_guardrails(recipe, import_item.id)` first, then persist `parsed_recipe.inferred_fields = recipe.inferred_fields` (top-level key on `parsed_recipe` JSONB), then `resolve_confidence()`, then `apply_inference_penalty(score, len(recipe.inferred_fields))`, then persist penalized score.
2. Migration `services/migrator/migrations/versions/XXXX_add_inferred_fields_to_recipes.py` adds `ALTER TABLE recipes ADD COLUMN inferred_fields JSONB NOT NULL DEFAULT '[]'::jsonb;`. Down-migration drops cleanly. Historical rows get `[]` via the default.
3. `libraries/utils/utils/models/recipe.py` — SQLAlchemy column declaration added (`inferred_fields` as `mutable_json` / `JSONB` with default `list`).
4. `create_recipe_task.py` — when constructing the new `Recipe` from an approved import-item, set `Recipe.inferred_fields = [f for f in import_item.parsed_recipe.get("inferred_fields", []) if f in INFERABLE_FIELDS]`. Filter enforces allow-list defensively.
5. `GetRecipe` response includes `inferred_fields: list[str]` at response root. Empty list for legacy rows (column default handles it).
6. `UpdateRecipe` accepts optional `inferred_fields: list[str]` in body. Validation: (a) subset of `INFERABLE_FIELDS`; (b) **strict subset of current stored value** (shrink-only) — return 400 with `{"error": "inferred_fields can only be reduced, not expanded", "allowed": <current-stored-set>}` if new set contains anything not in the stored set. Successful update persists the new (smaller or equal) list.
7. Integration test: full-path extraction with mocked AI extractor emitting 3 inferred fields + out-of-range cook_time + bogus vibe → persisted `parsed_recipe.inferred_fields` has the two valid fields (cook_time clamped, vibe dropped) + persisted confidence = base − `0.05 × 2` (inferred_count after dropped-vibe removal = 2).
8. Integration test: `GET /v1/recipes/{id}` returns `inferred_fields` populated from the recipes column.
9. Integration test: `PUT /v1/recipes/{id}` with shrunken `inferred_fields` → persists OK, response returns the new list. Same PUT but with an expansion → 400, stored value unchanged.
10. `services/api` coverage stays at 100% (new endpoint handlers + branches).

### Key Files

- Create: `services/migrator/migrations/versions/XXXX_add_inferred_fields_to_recipes.py`
- Modify: `libraries/utils/utils/models/recipe.py`
- Modify: `libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py`
- Modify: `libraries/utils/utils/tasks/import_tasks/create_recipe_task.py`
- Modify: `services/api/src/api/v1/recipes/get_recipe.py`
- Modify: `services/api/src/api/v1/recipes/update_recipe.py`
- Tests: per-path integration tests

---

## Story efi-4: Backend — hoist `inferred_fields` on import responses + `POST /v1/import-items/{id}/corrections` + tests

As the Flutter client,
I want `inferred_fields` at the response root on every import-item surface and a dedicated endpoint to dispatch user corrections,
so the badge renders without digging into `parsed_recipe` and every user override becomes a durable audit row.

### Acceptance Criteria

1. `GetImportItem`, `list_import_items`, `list_import_jobs` — response schemas gain `inferred_fields: list[str]` at the item-object root. Hoisted from `parsed_recipe.inferred_fields` using the existing `confidence_score` hoist pattern. Legacy rows (`parsed_recipe` without the key) return `[]`. Never null; always list.
2. New endpoint `POST /v1/import-items/{id}/corrections` at `services/api/src/api/v1/import_item/submit_correction.py`:
    - Body: `{field: str, corrected: Any}`.
    - Auth: 401 unauth; 403 if `item.user_id != caller.id`.
    - 404 if import-item not found.
    - 400 if `field not in INFERABLE_FIELDS` with `{"error": "field not inferable", "allowed": list(INFERABLE_FIELDS)}`.
    - Server reads `original = parsed_recipe.get(field)` and `was_inferred = field in parsed_recipe.get("inferred_fields", [])`.
    - Writes one `error_logs` row: `service="audit"`, `error_type="InferredFieldCorrected"`, `import_item_id = item.id`, `user_id = caller.id`, `metadata = {"field", "original", "corrected", "was_inferred"}`.
    - Response: 204 No Content on success; response time P95 < 150ms on a warm cache.
3. Endpoint does NOT mutate `parsed_recipe` — this is a logging endpoint, not a persistence endpoint. The actual user edits flow through the existing `approve_import_item` path at save time.
4. Integration tests:
    - Happy path: POST with `{field: "cook_time_minutes", corrected: 45}` on an item with `parsed_recipe.cook_time_minutes = 30` and `inferred_fields = ["cook_time_minutes"]` → 204 + `error_logs` row with `original: 30, corrected: 45, was_inferred: true`.
    - Was-not-inferred path: same but `inferred_fields = []` → 204 + row with `was_inferred: false` (still logged — correction data is valuable regardless of provenance).
    - Field not in allow-list: `{field: "name", corrected: "foo"}` → 400 with the allow-list in the response.
    - Wrong user: 403.
    - Missing item: 404.
5. `services/api` coverage stays at 100% on all branches.
6. No new indexes on `error_logs`; existing `(service, created_at)` index (from prior epics) covers query patterns.

### Key Files

- Create: `services/api/src/api/v1/import_item/submit_correction.py`
- Modify: `services/api/src/api/v1/import_item/get_import_item.py`
- Modify: `services/api/src/api/v1/import_item/list_import_items.py`
- Modify: `services/api/src/api/v1/import_item/list_import_jobs.py`
- Wire endpoint into import router.
- Tests: integration tests per endpoint + per error path.

---

## Story efi-5: Flutter — `InferredFieldBadge` widget + `kInferableFields` + client method + model decoders

As Leo,
I want a tiny sparkle icon I can tap to learn what it means, backed by a model that knows which fields were inferred,
so the Review Import and Recipe Edit screens can render the badge consistently without duplicated knowledge of the allow-list.

### Acceptance Criteria

1. `app/lib/features/recipes/add_recipe/widgets/inferred_field_badge.dart` — stateless widget. Optional `onTap` (defaults to showing a bottom-sheet with the explainer copy). Renders `Icon(Icons.auto_awesome, size: 14, color: Theme.of(context).colorScheme.tertiary)` inside a 40pt-tap-target `InkWell`. `Semantics(label: "AI-inferred value, tap for details", button: true)`.
2. Explainer bottom-sheet: `showModalBottomSheet` with title *"AI guess"* and body *"This value was inferred from the recipe. Verify or edit it below — your correction helps the extractor learn."* Dismiss on tap outside or swipe-down.
3. `app/lib/core/constants/inferable_fields.dart` — `const Set<String> kInferableFields = {...}` mirroring backend `INFERABLE_FIELDS` exactly (9 entries). A contract test reads the set and asserts length + presence of each expected field; a separate check asserts the set is identical to the `allowed` array the server returns in a 400 error from `submit_correction` (the endpoint test is test-double-aware but the shape is pinned).
4. `ApiClient.submitImportCorrection({required String itemId, required String field, required dynamic corrected})` — wraps `POST /v1/import-items/{itemId}/corrections`. Handles 204, logs warn on 4xx/5xx (no user-facing error). Accepts `dynamic` for `corrected` (int for times/servings, string for the rest).
5. `ImportItem` model (`app/lib/features/recipes/add_recipe/models/import_item.dart` or equivalent) — adds `inferredFields: Set<String>` decoded from response root. Legacy responses without the key decode to empty set.
6. `Recipe` model (`app/lib/features/recipes/models/recipe.dart`) — same: `inferredFields: Set<String>`. Round-trips through `toJson` / `fromJson`.
7. Widget test: badge renders with correct icon + color; tap opens the sheet; accessibility tree has the semantic label.
8. No Review Import or Recipe Edit wiring in this story.

### Key Files

- Create: `app/lib/features/recipes/add_recipe/widgets/inferred_field_badge.dart`
- Create: `app/lib/core/constants/inferable_fields.dart`
- Modify: `app/lib/core/api_client/api_client.dart`
- Modify: `app/lib/features/recipes/add_recipe/models/import_item.dart`
- Modify: `app/lib/features/recipes/models/recipe.dart`
- Tests: widget test for badge; contract test for `kInferableFields`; API-client test for `submitImportCorrection`.

---

## Story efi-6: Flutter — Review Import wiring (badge on 9 fields + dismiss-on-edit + debounced dispatch)

As Leo,
I want every inferred field on Review Import to show a sparkle, disappear the moment I edit it, and send my correction to the backend quietly in the background,
so the page reads as "here are the guesses, verify or correct" without any explicit accept/reject step.

### Acceptance Criteria

1. `import_item_review_screen.dart` loads an `ImportItem`; reads `item.inferredFields` into local mutable state `_inferredFields: Set<String>`.
2. For each of the 9 inferable-field labels rendered on the screen, the label row conditionally includes `InferredFieldBadge` when `_inferredFields.contains(<field_name>)`. Concretely: "Prep (min)", "Cook (min)", "Total (min)" (if rendered), "Servings", description-section header, "Cuisine", "Category", primary-vibe chip, secondary-vibe chip.
3. Each of the 9 fields' `onChanged` callback: if the field name is in `_inferredFields` AND the new value differs from the originally-loaded value, mutate `setState(() => _inferredFields.remove(<field_name>))`. Schedule a debounced correction dispatch (1500ms) to fire on focus-loss with the latest `corrected` value.
4. Correction dispatch: calls `ApiClient.submitImportCorrection(itemId: item.id, field: <name>, corrected: <current_value>)`. Network errors: log `service="app"` debug, do NOT surface user-facing error. Does not block save.
5. Reverting the field to the original inferred value BEFORE save still counts as dismissal (the user interacted with the field; the badge stays gone; no new dispatch fires because value now equals original).
6. Save flow (existing `approve_import_item`) is unchanged by this story — the user's final field values flow through as usual. `inferred_fields` persisted by `create_recipe_task` is derived from `parsed_recipe.inferred_fields` MINUS fields the user edited in Review Import. This is already handled by story efi-3 / efi-7's UpdateRecipe contract, but the Review Import path is an additive requirement: **the import-approval payload includes the mutated `_inferredFields` set so the created recipe has an accurate starting state.**
7. Integration test: render a review screen with 3 badged fields; tap the ✨ on cook_time → sheet opens; edit cook_time → sheet gone, badge gone, dispatch fires on focus-loss; edit description → same; save → approved import-item has only remaining badged field's name in `inferred_fields`.
8. Regression: existing Review Import behaviour (ingredient rows, swipe actions, debounced save) is unchanged.

### Key Files

- Modify: `app/lib/features/recipes/add_recipe/import_item_review_screen.dart`
- Modify: `app/lib/features/recipes/add_recipe/approve_import_item_request.dart` (or equivalent — extend payload shape to include the mutated `inferred_fields`)
- Tests: widget/integration test for the screen's dismiss-on-edit + dispatch behaviour.

---

## Story efi-7: Flutter — Recipe Edit wiring (badge + dismiss-on-edit, UpdateRecipe round-trip sends shrunken `inferred_fields`; NO correction dispatch)

As Leo,
I want the sparkle badges to persist into Recipe Edit so I can notice inferred fields weeks after import, and I want editing those fields to update the recipe's inferred_fields list on save,
so the provenance stays honest across time and the allow-list shrinks as I touch each field.

### Acceptance Criteria

1. `edit_recipe_screen.dart` loads a `Recipe`; reads `recipe.inferredFields` into local mutable state `_inferredFields: Set<String>`.
2. Same badge-on-label rendering as Review Import for all 9 fields.
3. Same dismiss-on-edit rule: value change on a badged field removes the field from `_inferredFields` and updates setState.
4. **No correction dispatch** — explicitly deferred (design principle 9). Badge dismissal is local-only.
5. On save, the `UpdateRecipe` request body includes `inferred_fields: _inferredFields.toList()` (shrunken set). The backend's shrink-only validation in efi-3 guarantees this can only reduce the stored list — a buggy client trying to add fields gets a 400.
6. Integration test: load a recipe with 3 badged fields → edit one → save → `UpdateRecipe` call body has the 2 remaining fields → next load shows only 2 badges.
7. Accessibility: badges carry the same Semantics label; screen-reader announcement when focus moves to a badged field.

### Key Files

- Modify: `app/lib/features/recipes/edit_recipe_screen.dart`
- Modify: API-client `updateRecipe` method signature to accept optional `inferredFields: Set<String>` → serialized to JSON list in the body.
- Tests: widget/integration test for the screen's dismiss-on-edit + save round-trip.

---

## Story efi-8: Eval — `field_inference_accuracy` + `hallucination_rate` metrics + baseline + per-extractor run

As the extractor evaluation suite,
I want two new metrics measuring how close inferred values land to ground truth and how often the model guesses when the source already had an answer,
so we can calibrate prompts and confidence penalty weights post-ship without flying blind.

### Acceptance Criteria

1. `services/eval/src/metrics/field_inference_accuracy.py` — iterates fixtures; for each with ground-truth on an inferable field AND the extractor-output's `inferred_fields` contains that field, scores:
    - Numeric (times, servings): 1.0 if within ±20%; 0.0 otherwise (servings tolerance floor: ±1).
    - Vibes / cuisine / category: 1.0 if case-insensitive exact match; 0.0 otherwise.
    - Description: Levenshtein similarity on first 200 chars; 1.0 if ≥ 0.6, raw similarity otherwise.
    - Emits per-field means + overall mean.
2. `services/eval/src/metrics/hallucination_rate.py` — for each fixture × inferable field with ground-truth present, if the extractor marked the field in `inferred_fields` (= the model guessed when the source had the answer), count as hallucination. Rate = hallucinations / (extractable field × fixture count). Soft-gate threshold ≤ 0.15 (reported, not enforced).
3. Both metrics register into `services/eval/eval.config.yaml` under a new `field_inference` section.
4. Metric runner produces a per-extractor breakdown (ai, vision, text separately). `json_ld` always scores 0 hallucinations (never infers); exclude from the rate denominator.
5. A baseline JSON is committed to `services/eval/baselines/field_inference_baseline.json` after the first run. Contains per-field accuracy means + hallucination_rate.
6. Eval runner output in `services/eval/results/` includes the new metrics in its JSON payload.
7. Both metrics have unit tests using a small synthetic fixture (no live extractor call): a mock `ExtractionResult` with known `inferred_fields` and known ground truth → known score.
8. No CI enforcement in v1 (soft gate only). Document in the eval README's threshold section that these are measure-only until post-ship data tunes them.

### Key Files

- Create: `services/eval/src/metrics/field_inference_accuracy.py`
- Create: `services/eval/src/metrics/hallucination_rate.py`
- Create: `services/eval/baselines/field_inference_baseline.json`
- Modify: `services/eval/eval.config.yaml`
- Modify: `services/eval/README.md` (new metric section)
- Tests: per-metric unit tests.

---

## Dependencies

- **Cross-epic:** Independent of currently in-flight epics. Does not collide with:
  - `epic-ingredients-string-simplification` (2026-04-20 — different code surface; the deleted `IngredientRowStateBadge` is gone before this epic's badge lands, so no conflict; this epic's badge is a new widget with a new name).
  - `epic-review-import-ingredient-polish` (backlog — its rescoped-stories touch ingredient rows; this epic touches recipe-level field labels on the same screen. Merge sequencing: either order works; at implementation time, coordinate in Review Import edits if both are in-flight simultaneously).
  - `epic-cook-mode-timers` (backlog — touches extraction schema too; `ExtractedStep.timers` is additive; this epic's `inferred_fields` is also additive; no collision).
  - `epic-import-row-rich-detail` (done — its `ConfidenceBadge` is reusable in the activity hub; this epic's `InferredFieldBadge` is a separate, recipe-screen widget).
- **Cross-cutting:** Touches extractors + extract_recipe_task + confidence_heuristic, which are also touched by `epic-cook-mode-timers` (cmt-1, cmt-2) and `epic-review-import-ingredient-polish` (riip-3 prompt changes). Coordinate merge order when two of these are open — a combined PR is acceptable if they all touch `ai_extractor.py`'s prompt simultaneously.
- **Feature-flag coordination:** This epic's `EXTRACTOR_INFER_MISSING_FIELDS` flips LAST relative to `EXTRACTOR_EMIT_CONFIDENCE` and `EXTRACTOR_EMIT_CANONICAL_UNITS` (the penalty depends on confidence being live).

## Open Questions for the User

None outstanding — all UX and scope questions resolved in the 2026-04-20 planning session:

- **Q1 (scope):** Recipe-level only (per-ingredient deferred to a follow-up epic).
- **Q2 (fields):** All 9 recipe-level inferable fields (times, servings, description, cuisine, category, vibes).
- **Q3 (UI marker):** Sparkle badge (`Icons.auto_awesome`), reusing the visual vocabulary of the retired `IngredientRowStateBadge`.
- **Q4 (feedback loop):** `error_logs` with `service="audit"`, `error_type="InferredFieldCorrected"` — cheapest path, no new table.
- **Defaults confirmed:** Clamp ranges (cook 1–720, prep 1–240, total 1–960, servings 1–24, description 240 chars, cuisine/category 40 chars, vibes via `validate_vibe`); feature flag default-on; correction dispatch debounced 1500ms; Recipe-Edit correction round-trip deferred.

Any follow-up decisions fall out of post-ship correction-log data (e.g., weight tuning, per-ingredient epic scoping) and are not blockers for this epic.

## Definition of Done (Epic Level)

- `EXTRACTOR_INFER_MISSING_FIELDS` flag is live; default on; flippable via ECS task-def without redeploy.
- All three LLM extractors (ai, vision, text) emit `inferred_fields` alongside `confidence_score`; `json_ld` emits `inferred_fields: []`.
- Clamp-and-log guardrails fire for every inferred value; all clamps/drops log through `log_inferred_field_clamp`; AST-lint test is green.
- `confidence_score` carries the inference penalty; persisted penalized score is what the UI renders.
- `recipes.inferred_fields` column is live; migration is reversible; `create_recipe_task` copies the field through; `GetRecipe` / `UpdateRecipe` surface and accept it; shrink-only validation is enforced.
- `GetImportItem`, `list_import_items`, `list_import_jobs` hoist `inferred_fields` at response root.
- `POST /v1/import-items/{id}/corrections` endpoint is live, returns 204 on success, writes one `error_logs` row per call; P95 < 150ms.
- Flutter `InferredFieldBadge` is live on Review Import and Recipe Edit for all 9 inferable fields; badge disappears immediately on first edit; Review Import dispatches the correction endpoint on focus-loss debounced 1500ms; Recipe Edit shrinks `inferred_fields` on save via `UpdateRecipe`.
- Eval metrics `field_inference_accuracy` and `hallucination_rate` are wired; per-extractor breakdown in the report; baseline committed; no hard CI gate in v1.
- `services/api` coverage stays at 100%.
- End-to-end smoke on a real device: photo-import a cookbook page with no printed cook time → Review Import shows a sparkle on cook_time with a plausible value → edit it → sparkle disappears → save → recipe lands with `inferred_fields` reflecting the remaining inferred fields → open Recipe Edit, same sparkles visible, one edit shrinks the list on save.
- Zero regressions on `epic-review-import-ingredient-polish`'s one-line ingredient row layout, `epic-import-row-rich-detail`'s ConfidenceBadge + stage timeline, or `epic-cook-mode-timers`' extraction schema (if already landed).
