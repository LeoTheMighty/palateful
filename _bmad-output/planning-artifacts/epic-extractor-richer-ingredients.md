<!-- refined via party-mode 2026-04-22 -->
# Epic: Extractor Richer Ingredient Extraction — Softened Units, JSON-LD Parse Pass, Convertible-Unit Bias

## Overview

Dogfood surfaced two concrete ingredient-extraction bugs that share a root cause: **ingredient-level extraction fidelity is too conservative**.

1. **"1 clove garlic" loses the `clove` unit.** Even though `clove` is in the 19-token canonical enum that `riip-3` pinned into the prompt (`unit_prompt.py`), the rigid *"use EXACTLY one of these tokens… Do not write out full words"* framing combined with "only include what's clearly there" causes the LLM to fold `clove` into the ingredient `name` field. Review Import shows `[ ] [ ] [clove of garlic]`.
2. **"300 gram of vinegar" loses BOTH quantity and unit on URL imports.** Root cause: `libraries/utils/utils/services/recipe_extractors/json_ld.py:141-145` emits `ExtractedIngredient(text=ing_text.strip(), quantity=None, unit=None, name=None)` for every entry in the Schema.org `recipeIngredient` array — the spec defines that field as a plain-string list, not structured, so JSON-LD has nothing to pull from. Those `None`s ride through to `parsed_recipe.ingredients[]`; the Flutter review screen falls back to putting the full raw string into the name field (`ingredient_edits_mapping.dart:22-26`). User sees one big unstructured string instead of `[300] [g] [vinegar]`.

This epic ships a cohesive fix across three slices:

1. **Soften the canonical-units prompt rule.** The 19-token prompt-token list (`CANONICAL_UNIT_TOKENS`) stays as the *preferred* hint; the prompt now allows freeform unit words (stalk, bunch, packet, sprig, head, can, sheet…) when the source uses them literally, AND biases toward convertible units (cup/tbsp/tsp/ml/l/g/kg/oz/lb/fl oz) when ambiguous — future-proofing a later US↔metric conversion feature. Both `ai_extractor`, `vision_extractor`, and `text_extractor` get aggressive qty/unit/notes capture instructions plus worked examples for the historically-broken cases. Flag-gated (`EXTRACTOR_SOFTEN_UNIT_RULE`, default on).
2. **JSON-LD ingredient-parse-only AI pass — on the text-only subset.** When `JsonLdExtractor` yields a mix of structured + text-only ingredients, run a focused AI pass against the *text-only subset only* — not the full AI extractor, just ingredients-in / structured-ingredients-out via gpt-4o-mini with a strict JSON-schema response format. Results splice back in original order. Recipe-level fields (name, times, servings, source) still come from JSON-LD as authoritative. Flag-gated (`EXTRACTOR_JSON_LD_INGREDIENT_PARSE`, default on). One extra OpenAI call per URL import with text-only ingredients (~$0.0001).
3. **Expanded `units` table + alias-table seeds, eval fixtures, flag rollout runbook.** Seed 15 new *freeform-canonical* rows in `units` (stalk, bunch, sprig, head, can, packet, stick, sheet, strip, piece, sachet, jar, bottle, bar, [one more per actual migration]) so `unit_aliases.canonical_unit` FK stays intact; seed ~15 plural→singular aliases (`stalks`→`stalk`, `cans`→`can`, etc.). Seven eval fixtures (three happy-path + four negative-case) anchor the clove/gram/stalk/notes-null/substring/range cases; a new `ingredient_field_completeness` metric measures {quantity, unit, name, notes} presence vs. ground truth. Production observability via a once-per-import `IngredientFieldCoverage` audit row so the 0.55 → 0.85 metric charts against real traffic. A 4-step production flip runbook owns the rollout.

**No Flutter changes required for ingredient-row UI.** Research confirmed the row already renders freeform units; `UnitInput` `SessionAliasMap.coerce` handles non-canonical units on blur. The whole slice is backend-only — **except** one small pin: verify `SessionAliasMap` invalidation picks up the 15 new alias seeds without requiring app reinstall (covered in `eri-4b`).

**No parser-service changes.** User confirmed "Maybe just the extractor honestly." The URL → HTML fetch path in `services/parser/` is unchanged; only the downstream JSON-LD handling inside `libraries/utils/.../recipe_extractors/` is touched.

## Goal

A user pastes a recipe URL into the app. The URL has Schema.org JSON-LD markup with `recipeIngredient: ["1 clove garlic, minced", "300 gram of vinegar", "2 stalks celery, chopped", ...]` (plain strings — the Schema.org default). Backend runs the pipeline:

1. `JsonLdExtractor` extracts recipe-level fields (name, description, times, servings, source) from JSON-LD.
2. `JsonLdExtractor` emits the ingredient list with qty/unit/name nulls (text-only subset).
3. `extract_recipe_from_html` filters to the text-only *subset* (works even when JSON-LD has a few structured rows mixed in) and invokes `parse_ingredient_strings(["1 clove garlic, minced", "300 gram of vinegar", ...])` against `gpt-4o-mini` with a strict JSON-schema response format.
4. The parse pass returns `[{q:1, u:"clove", n:"garlic", notes:"minced"}, {q:300, u:"gram", n:"vinegar"}, {q:2, u:"stalks", n:"celery", notes:"chopped"}]`, spliced back in original order.
5. `normalize_unit_display` runs (riip-2): `gram`→`g`, `stalks`→`stalk`. Persisted: `[{q:1, u:"clove", n:"garlic", notes:"minced"}, {q:300, u:"g", n:"vinegar"}, {q:2, u:"stalk", n:"celery", notes:"chopped"}]`.
6. One `error_logs service="audit" error_type="IngredientFieldCoverage"` row is written with `{total, qty_present, unit_present, notes_present, source="json_ld_parse_pass"}` for production trend observability.
7. Review Import renders three rich rows: `[1] [clove] [garlic]` with notes "minced" auto-expanded; `[300] [g] [vinegar]` clean; `[2] [stalk] [celery]` with notes "chopped" auto-expanded. **Confidence stays at JSON-LD's score (1.0) — we explicitly do NOT penalize confidence for parse-pass-origin ingredients** (ingredients are review-editable anyway; confidence reflects recipe-level structure).
8. Leo taps Save. Recipe lands with clean structured ingredients.

Same user photo-imports a cookbook page with `"1 clove garlic, minced"` in the ingredient list. AI extractor (softened prompt) correctly emits `{q:1, u:"clove", n:"garlic", notes:"minced"}` — `clove` is no longer folded into the name.

Same user imports a URL with no JSON-LD: `JsonLdExtractor.can_extract()` returns False → falls through to `AIExtractor` (softened prompt) running directly on raw HTML. No second parse pass (the AI extractor already emits structured ingredients; a duplicate pass would waste cost). Same rich extraction.

## End-User Flow

1. Leo copies a recipe URL from a cookbook site with Schema.org JSON-LD (NYT Cooking, Serious Eats, BBC Good Food — most modern sites).
2. Leo opens Palateful → Add Recipe → URL → pastes → Import.
3. Backend runs the import pipeline: `parse_source_task` fetches HTML → `extract_recipe_task` → `RecipeExtractorRegistry.extract()`.
4. `JsonLdExtractor.can_extract()` finds the `<script type="application/ld+json">` block → returns True. `extract()` parses JSON-LD into recipe-level fields + an ingredient list.
5. **NEW:** `extract_recipe_from_html` computes the text-only subset (ingredients where `quantity IS None AND unit IS None AND name IS None`). If the subset is non-empty AND `EXTRACTOR_JSON_LD_INGREDIENT_PARSE` is on, it invokes `parse_ingredient_strings()` on that subset. Structured ingredients (from JSON-LD itself) are passed through untouched. Parse results splice back into the original list at their original indices.
6. Parse pass sends one focused prompt to `gpt-4o-mini`, temperature 0, with `response_format={"type": "json_schema", ...}` pinning a strict array-of-objects schema. Returns a structured list.
7. `extract_recipe_task` persists. `normalize_unit_display` runs on every ingredient's unit. Inference guardrails for recipe-level fields (efi) still apply untouched.
8. One `IngredientFieldCoverage` audit row per import (whether or not parse pass fired) captures qty/unit/notes/name presence counts so prod trend is visible in `error_logs`.
9. Leo opens Review Import. Every ingredient row is fully structured. Notes auto-expand where present.
10. Leo taps Save. Recipe lands.

**Failure fallback:** If the parse pass raises (rate limit, malformed JSON that even the strict schema can't salvage, OpenAI 5xx, timeout of 10s per batch), log `service="audit", error_type="IngredientParseFailure"` with the failing subset + error class, and return the text-only ingredient list unchanged. User sees pre-ERI behavior — the full raw string in the name field — but the Review screen still lets them edit manually. **No user-visible error.** This is explicit: Review Import NEVER degrades below today's behavior, even when the parse pass fails.

## Frontend Changes

**One small verification, no UI changes.**

- `StructuredIngredientRow`, `UnitInput`, `ingredient_edits_mapping.dart` — verified by research to already render freeform units and all five structured fields (`structured_ingredient_row.dart:331-340`, `unit_input.dart:91-114`). No widget changes.
- **Verification gate in `eri-4b`:** confirm `SessionAliasMap` invalidates / refreshes so the 15 new alias seeds land for already-logged-in users without reinstall. Check `app/lib/features/recipes/add_recipe/providers/session_alias_map_provider.dart` — whatever cache refresh pattern exists, ensure a fresh cold-start of the app picks up the new aliases. If the cache is keyed by anything other than "current session", add a trivial version-bump pattern.
- **Round-trip drift note (documented, not a bug):** user types "stalks" + blur → Flutter's client-side `SessionAliasMap.coerce` may or may not snap (depends on whether server response with new aliases has been fetched). Save → backend `normalize_unit_display` normalizes to "stalk" → API response returns "stalk" → Flutter re-renders. User may see their "stalks" silently change to "stalk" on save round-trip. This is desired behavior (plural→singular normalization); just documented so nobody is surprised.
- **Explicit AC on `eri-1`:** a grep in Flutter code confirms no client-side enum validation rejects non-canonical units on save. If any check fails `unit IN kCuratedUnits`, remove it. (Research found none; this AC is a belt-and-suspenders guard.)

## Backend Changes

**Required — medium.** Five modules touched: extractor prompts (soften + aggressive capture), `unit_prompt.py` (flag precedence), new `ingredient_parse.py`, `__init__.py` (parse-pass invocation), `units` + `unit_aliases` seed migrations. Plus eval + observability.

### `unit_prompt.py` — softened rule + coded flag precedence

- Rewrite to support THREE flag states with a pinned precedence order:
  ```python
  def unit_rule(*, freeform_fallback: str) -> str:
      """Precedence: SOFTEN wins; else CANONICAL; else freeform legacy."""
      if soften_unit_rule():
          return _SOFTENED_RULE
      if emit_canonical_units():
          return _CANONICAL_RULE
      return freeform_fallback
  ```
- `soften_unit_rule()` reads `EXTRACTOR_SOFTEN_UNIT_RULE` env var at call time (default `"true"`).
- `emit_canonical_units()` keeps its current shape (default `"true"` — but in production after rollout it flips to `"false"` so the riip-3 path retires cleanly).
- `_SOFTENED_RULE` text:
  > - "unit": prefer one of these tokens where applicable — `tsp`, `tbsp`, `cup`, `fl oz`, `ml`, `l`, `g`, `kg`, `oz`, `lb`, `each`, `pinch`, `dash`, `clove`, `slice`, `mg`, `gallon`, `quart`, `pint`. If the source uses a more accurate freeform unit word that isn't in this list (e.g., `stalk`, `bunch`, `sprig`, `head`, `can`, `packet`, `stick`, `sheet`, `strip`, `piece`, `sachet`, `jar`, `bottle`, `bar`), emit that word literally in lowercase singular form. **When the source is ambiguous between a convertible unit (cup, tbsp, tsp, ml, l, g, kg, oz, lb, fl oz) and a count unit, prefer the convertible one** — it lets us convert later. Use null for count-of-item when the item itself is uncountable (`"salt to taste"` → unit: null). Never include the number or ingredient name here.
- `_CANONICAL_RULE` preserved verbatim for rollback.
- **Four-case matrix test** (`libraries/utils/tests/services/recipe_extractors/test_unit_prompt_precedence.py`) covers the cross-product of both flags, asserting rule text matches expectation in each quadrant.

### Extractor prompts — aggressive qty/unit/notes capture + worked examples

- `ai_extractor.py`, `vision_extractor.py`, `text_extractor.py` each get their ingredients section amended:
  > For every ingredient line, always extract `quantity`, `unit`, and `notes` when they appear in the source, even if the quantity is a fraction, a range, or implied by context. Notes capture preparation hints: "minced", "melted", "room temperature", "to taste". **If the source gives a range like "1–2 cups" or "1 to 2 cups", emit `quantity` as the first value and capture the full range in `notes` (e.g., `{quantity: 1, notes: "to 2 cups"}`).** Respect word boundaries for units: "a pinchful" is NOT "pinch" (unit: null).
- Worked examples (added to each extractor's ingredients section):
  - `"1 clove garlic, minced"` → `{"quantity": 1, "unit": "clove", "name": "garlic", "notes": "minced"}`
  - `"300 gram of vinegar"` → `{"quantity": 300, "unit": "g", "name": "vinegar", "notes": null}` (backend post-normalize)
  - `"2 stalks celery, chopped"` → `{"quantity": 2, "unit": "stalk", "name": "celery", "notes": "chopped"}`
  - `"Salt, to taste"` → `{"quantity": null, "unit": null, "name": "salt", "notes": "to taste"}`
  - `"1/2 cup olive oil"` → `{"quantity": 0.5, "unit": "cup", "name": "olive oil", "notes": null}`
  - `"1–2 cups water"` → `{"quantity": 1, "unit": "cup", "name": "water", "notes": "to 2 cups"}`
  - `"a pinchful of salt"` → `{"quantity": null, "unit": null, "name": "salt", "notes": "pinchful"}` (substring ambiguity)
  - `"2 cups flour"` → `{"quantity": 2, "unit": "cup", "name": "flour", "notes": null}` (no hallucinated notes)

### `ingredient_parse.py` — new parse-only AI pass

- New module `libraries/utils/utils/services/recipe_extractors/ingredient_parse.py`:
  ```python
  async def parse_ingredient_strings(
      strings: list[str],
      openai_client,
      *,
      batch_size: int = 25,
      max_total: int = 200,
      timeout_seconds: float = 10.0,
  ) -> list[ExtractedIngredient]:
      ...
  ```
- `gpt-4o-mini`, temperature 0, `response_format={"type": "json_schema", "json_schema": {...strict array-of-objects...}}` with required fields `{quantity: number|null, unit: string|null, name: string, notes: string|null}`. Strict schema removes the class of "wrapped in {ingredients: [...]}" and "dict instead of list" failures.
- Prompt is short + ingredients-only — splices in `unit_rule(freeform_fallback=...)` from `unit_prompt.py` so there is ONE source of truth for the soften rule.
- Batch size: **fixed batches of 25 (not 50-then-remainder)** for deterministic prompt-order stability. Sequential batching above 25. Cap at `max_total=200`; anything beyond gets dumped back as text-only with a `service="audit" error_type="IngredientParsePathological"` audit row (including the URL and the overflow count) so we see the edge case if it ever fires.
- Failure modes: OpenAI rate limit / 5xx / JSON-schema violation / timeout (10s per batch) → log `service="audit", error_type="IngredientParseFailure"` with `{batch_size, error_class, url_sample}` and return text-only inputs unchanged for THAT batch (partial success across batches is fine — earlier batches that succeeded are kept).
- Per-call token counts logged into the audit row for cost true-up over the first week.

### `extract_recipe_from_html` — parse-pass invocation (subset filter + splice)

- In `libraries/utils/utils/services/recipe_extractors/__init__.py`, after JSON-LD extraction succeeds:
  ```python
  if _json_ld_parse_enabled() and recipe and recipe.ingredients:
      text_only_indices = [i for i, ing in enumerate(recipe.ingredients)
                           if ing.quantity is None
                           and ing.unit is None
                           and ing.name is None
                           and ing.text]
      if text_only_indices:
          strings = [recipe.ingredients[i].text for i in text_only_indices]
          parsed = await parse_ingredient_strings(strings, openai_client)
          for i, ing in zip(text_only_indices, parsed):
              recipe.ingredients[i] = ing  # splice back in-order
  ```
- `_json_ld_parse_enabled()` reads `EXTRACTOR_JSON_LD_INGREDIENT_PARSE` env var at call time, default `"true"`.
- Structured ingredients from JSON-LD itself are passed through unchanged — mixed-structure sites work correctly.
- If `text_only_indices` is empty (all-structured JSON-LD), the pass doesn't fire — no cost.
- An `IngredientFieldCoverage` audit row is written regardless of whether the pass fired: `{service="audit", error_type="IngredientFieldCoverage", metadata={total, qty_present, unit_present, notes_present, name_present, source: "json_ld" | "json_ld_parse_pass" | "ai_extractor", url_host}}`. Production field-completeness trend is queryable via the existing `audit_errors.py` script.

### `units` + `unit_aliases` seed migrations

**Design principle 1 (refined):** separate *prompt vocabulary* (`CANONICAL_UNIT_TOKENS` — 19 items, untouched) from *data-model vocabulary* (`units` table — grows by 15). They are not the same thing.

- **Migration A — `XXXX_seed_freeform_units.py`:** Insert 15 rows into `units` with `type="other"`, `to_base_factor="1"`, `base_unit=<self>` — matching the established pattern for `pinch`/`dash`/`clove`/`slice` already seeded in `20260418040000_create_unit_aliases.py:58-63`. Names: `stalk`, `bunch`, `sprig`, `head`, `can`, `packet`, `stick`, `sheet`, `strip`, `piece`, `sachet`, `jar`, `bottle`, `bar`, `drop` (15 total; drop added as a common freeform count). Idempotent via `INSERT ... ON CONFLICT DO NOTHING`.
- **Migration B — `XXXX_seed_freeform_unit_aliases.py`:** Insert 15 plural→singular alias rows: `stalks`→`stalk`, `bunches`→`bunch`, `sprigs`→`sprig`, `heads`→`head`, `cans`→`can`, `packets`→`packet`, `packs`→`packet`, `sticks`→`stick`, `sheets`→`sheet`, `strips`→`strip`, `pieces`→`piece`, `sachets`→`sachet`, `jars`→`jar`, `bottles`→`bottle`, `bars`→`bar`, `drops`→`drop`. FK to `units.name` is intact (15 new `units` rows from Migration A satisfy it).
- **FK is preserved.** Dropping the FK would silently allow typos in future alias seeds; preserving it catches them at migration time.
- Down-migration for A removes the 15 `units` rows (only if no `recipe_ingredients.unit_display` or `unit_aliases.canonical_unit` still references them — otherwise errors out, operator intervention required). Down-migration for B removes just the 15 alias rows.
- Regression test: `normalize_unit_display("stalks")` → `"stalk"` post-migration. `normalize_unit_display("drops")` → `"drop"`.

### `normalize_unit_display` + confidence interaction

- **`normalize_unit_display` — no code change required.** Existing behavior is already correct: input in canonical set → pass; alias hit → canonical; miss → pass + log. After the new `units` + alias seeds land, `stalk`, `bunch`, etc. are in the canonical set (`units.name`); plurals coerce to singulars via aliases. Existing audit-log miss path catches anything else.
- **Confidence is NOT inflated or penalized by the parse pass.** `JsonLdExtractor` sets `confidence_score=1.0, confidence_source="model"` when name+ingredients+instructions present (`json_ld.py:187-202`). Post-parse-pass, ingredients are technically AI-generated, but we **explicitly do not re-score**. Rationale: (a) ingredients are review-editable, so the user can fix anything; (b) confidence is a recipe-level-structure signal, not an ingredient-level one; (c) re-scoring would require arbitrary calibration without data. Lock this decision in a comment at the parse-pass invocation site so a future reader doesn't "fix" it. Confidence handling untouched.

### Eval — `ingredient_field_completeness` metric + 7 fixtures

- `services/eval/src/metrics/ingredient_field_completeness.py`:
  - Iterates fixtures with ground-truth ingredients. For each ingredient × each of {quantity, unit, name, notes}, score 1.0 if the extracted field matches ground truth (case-insensitive for unit/name/notes; ±5% tolerance for quantity), 0.0 otherwise.
  - Denominator: extractable-field count (fields the source genuinely has). A ground-truth-null field with extracted-null counts as correct; ground-truth-null with extracted-non-null counts as hallucination (score 0; captured separately as `ingredient_hallucination_rate`).
  - Reports per-field means, per-extractor means, overall mean per fixture, aggregate across fixtures.
  - Target: overall ≥ 0.85.
- Seven fixtures total (three happy-path + four negative-case, per QA lens):
  1. `1_clove_garlic_jsonld.yaml` — JSON-LD source with `recipeIngredient: ["1 clove garlic, minced", "2 tbsp olive oil", "1/2 tsp salt"]`. Ground truth: three structured. Exercises parse pass + softened prompt.
  2. `300_gram_vinegar_jsonld.yaml` — JSON-LD source with metric units. Exercises parse pass + `normalize_unit_display("gram")`.
  3. `2_stalks_celery_text.yaml` — plain-text for text_extractor. Exercises softened prompt + alias plural→singular.
  4. `no_notes_simple_text.yaml` — `"2 cups flour"` → no-notes. Exercises "don't hallucinate notes".
  5. `pinchful_substring_text.yaml` — `"a pinchful of salt"` → unit:null. Exercises substring-ambiguity.
  6. `range_quantity_jsonld.yaml` — `"1–2 cups water"` → `{q:1, notes:"to 2 cups"}`. Exercises range rule.
  7. `mixed_structure_jsonld.yaml` — JSON-LD with 2 structured + 3 text-only ingredients. Exercises subset-filter + splice-in-order.
- Register in `services/eval/eval.config.yaml` under a new `ingredient_fidelity` section.
- Baseline at `services/eval/baselines/ingredient_field_completeness_baseline.json` committed post-first-run.
- **Eval is soft-gate in v1.** Hard-gate promotion trigger locked as: **(a) ≥7 days of post-ship eval-run data with `ingredient_field_completeness ≥ 0.85` AND (b) 0 `IngredientParseFailure` audit rows in the last 48h AND (c) `UnitAliasMiss` count tied to the 15 new seeds is zero.** Until all three hold, the metric runs + logs but doesn't block CI. A follow-up story (`eri-hard-gate`) will own the promotion when criteria are met.
- **Regression pinning:** eri-5 AC explicitly lists every pre-ERI fixture under `services/eval/fixtures/`; every one must still pass post-merge. Baselines snapshotted before merge.

## Infrastructure Changes

**None in the resource sense; two new env-var flags.**

- Two Alembic migrations (freeform units + alias seeds).
- Two new feature-flag env vars (`EXTRACTOR_SOFTEN_UNIT_RULE`, `EXTRACTOR_JSON_LD_INGREDIENT_PARSE`), flippable via ECS task-def; no Terraform.
- One production runbook owned by `eri-6` — documented in `docs/EXTRACTOR_FLAG_ROLLOUT.md` (or inline in the epic if shorter).
- No new AWS resources, no new IAM, no CI/CD changes.
- OpenAI usage: ~$0.0001 per URL import that hits the parse pass (text-only JSON-LD subset). At ~10 URL imports/day dogfood volume, ~$0.001/day. Token counts logged for a week to validate.

## Design Principles (refined via party-mode 2026-04-22)

1. **Prompt vocabulary ≠ data-model vocabulary.** The 19-token `CANONICAL_UNIT_TOKENS` (prompt hint list) stays frozen. The `units` table grows by 15 freeform rows (`stalk`, `bunch`, etc.) so `unit_aliases.canonical_unit` FK stays intact. Conflating the two is a scope error — the draft conflated them; this epic doesn't.
2. **Parse pass runs on the text-only *subset*, not all-or-nothing.** Mixed-structure JSON-LD (common in the wild) gets the best of both: structured rows pass through untouched; text-only rows get the AI pass; results splice back in original order. `_ingredients_are_text_only` short-circuit from the draft is rejected.
3. **Flag precedence is coded, not implied.** `unit_rule()` checks `SOFTEN_UNIT_RULE` → `EMIT_CANONICAL_UNITS` → freeform fallback, in that order. Four-case matrix test pins the behavior. Implicit precedence is a regression vector.
4. **Parse-pass output uses OpenAI `json_schema` response_format with a strict array schema.** Temperature 0 alone is not enough — pin the schema to eliminate wrapped-dict / reordered-key / dict-instead-of-list failures. Graceful fallback (log + return text-only) remains the backstop for hard failures.
5. **Confidence stays at JSON-LD's score — no inflation, no penalty.** Post-parse-pass ingredients ARE AI-generated, but confidence reflects recipe-level structure, not ingredient-level. Ingredients are review-editable anyway. Explicit locked decision so a future reader doesn't "fix" it.
6. **Flag-off parity is gated by a pinned test.** One test runs a fixture with `SOFTEN_UNIT_RULE=false, JSON_LD_INGREDIENT_PARSE=false, EMIT_CANONICAL_UNITS=true` and asserts byte-for-byte equality with a pre-ERI golden output. Rollback safety net.
7. **Review Import NEVER degrades below today's behavior.** Parse-pass failure → text-only row — same as pre-ERI. User can always edit manually. Explicit AC.
8. **Normalize-on-write is the backstop.** Prompt may emit `gram`, `cloves`, `stalks`, `Tablespoon`, `Tbsp.` — `normalize_unit_display` catches all via the alias table. Every miss logs for alias-seed growth. LLM is not trusted; the alias table is.
9. **Batch determinism: 25 per batch, cap at 200 total.** Fixed 25 (not 50-then-remainder) for predictability. Pathological >200 dumps back as text-only + audit row — the only case where a recipe has 200+ ingredients is a data error or a spice catalog, not a cooking recipe.
10. **Production observability is cheap and mandatory.** One `IngredientFieldCoverage` audit row per import captures per-field presence counts so the 0.55 → 0.85 metric charts against real traffic, not just eval.
11. **No ingredient-level inference yet.** This epic captures what's THERE. "Best-guess when not specified" (efi pattern for ingredients) stays deferred.
12. **No Flutter churn for UI; one small verification for alias-cache refresh.** Frontend is already correct for the new freeform units; we just need `SessionAliasMap` to pick up 15 new aliases on app restart. Handled by a grep-level check in eri-4b, not a UI change.

## Inherited Locked Decisions (carry forward to later epics)

- **Prompt token list vs. data-model units table are separate vocabularies** — don't conflate.
- **Confidence score reflects recipe-level structure, not AI-generated ingredient rows** — don't re-score ingredients.
- **Parse-pass failures degrade to text-only, never to error** — Review Import is always a valid recovery path.
- **OpenAI structured-output path uses `json_schema` response_format** (not free JSON) — sets a precedent for any future LLM call that emits structured data.
- **Feature flags flip on a documented runbook** — not ad hoc.

## File Structure (anticipated)

```
libraries/utils/utils/services/recipe_extractors/
├── unit_prompt.py                              # MODIFIED — add _SOFTENED_RULE + EXTRACTOR_SOFTEN_UNIT_RULE flag + coded precedence (SOFTEN > CANONICAL > freeform)
├── ai_extractor.py                             # MODIFIED — aggressive qty/unit/notes + worked examples (incl. range rule + substring rule)
├── vision_extractor.py                         # MODIFIED — same
├── text_extractor.py                           # MODIFIED — same
├── json_ld.py                                  # UNCHANGED — still emits text-only ingredients; parse-pass invocation lives in __init__.py
├── ingredient_parse.py                         # NEW — parse_ingredient_strings(...) via gpt-4o-mini + strict json_schema response_format + batch 25 + cap 200
└── __init__.py                                 # MODIFIED — subset-filter parse-pass invocation after JSON-LD + IngredientFieldCoverage audit emit

libraries/utils/utils/services/units/
└── normalize.py                                # UNCHANGED — grows via seeds, not code

services/migrator/migrations/versions/
├── XXXX_seed_freeform_units.py                 # NEW — 15 freeform units in units table (preserves FK)
└── XXXX_seed_freeform_unit_aliases.py          # NEW — 15 plural→singular alias rows

services/eval/src/metrics/
└── ingredient_field_completeness.py            # NEW — per-field + overall fidelity + hallucination sub-metric

services/eval/fixtures/
├── 1_clove_garlic_jsonld.yaml                  # NEW — clove regression
├── 300_gram_vinegar_jsonld.yaml                # NEW — URL-import gram regression
├── 2_stalks_celery_text.yaml                   # NEW — freeform + alias plural→singular
├── no_notes_simple_text.yaml                   # NEW — no-hallucinated-notes negative case
├── pinchful_substring_text.yaml                # NEW — substring-ambiguity negative case
├── range_quantity_jsonld.yaml                  # NEW — range rule
└── mixed_structure_jsonld.yaml                 # NEW — subset-filter + splice-in-order

services/eval/baselines/
└── ingredient_field_completeness_baseline.json # NEW — post-first-run baseline

services/eval/
└── eval.config.yaml                            # MODIFIED — register new metric + fixtures

docs/
└── EXTRACTOR_FLAG_ROLLOUT.md                   # NEW — 4-step flip runbook + rollback drill (owned by eri-6)

libraries/utils/tests/services/recipe_extractors/
├── test_unit_prompt_precedence.py              # NEW — 4-case matrix for both flags
├── test_ingredient_parse.py                    # NEW — happy path + failure fallback + batching + cap + schema violation
├── test_extract_recipe_from_html.py            # MODIFIED — subset filter + splice + mixed structure + all-structured short-circuit
└── test_flag_off_parity.py                     # NEW — byte-for-byte parity golden vs. pre-ERI

app/lib/features/recipes/add_recipe/providers/
└── session_alias_map_provider.dart             # VERIFIED (may get a trivial tweak if cache doesn't refresh cold-start)
```

## Story Map

| # | Story | Priority | Est. | Dependencies |
|---|-------|----------|------|--------------|
| eri-1 | Backend — `_SOFTENED_RULE` + `EXTRACTOR_SOFTEN_UNIT_RULE` flag in `unit_prompt.py` + coded flag precedence (SOFTEN > CANONICAL > freeform) + 4-case matrix test + per-extractor aggressive-capture prompt rewrites with worked examples (incl. range + substring rules) + Flutter client-side enum-validation grep check | 🔴 P0 | 0.5 d | None |
| eri-2 | Backend — `ingredient_parse.py` module (`parse_ingredient_strings`) with gpt-4o-mini + strict `json_schema` response_format + batch 25 + cap 200 + graceful failure + per-call token logging; unit tests with mocked OpenAI covering happy path, schema-violation fallback, rate-limit fallback, 10s timeout, pathological 200+ | 🔴 P0 | 0.75 d | eri-1 (reuses `unit_rule`) |
| eri-3a | Backend — `extract_recipe_from_html` invokes parse pass on text-only subset after JSON-LD + splice-back-in-order + `EXTRACTOR_JSON_LD_INGREDIENT_PARSE` flag + `IngredientFieldCoverage` audit row per import; integration test against the 3 new JSON-LD fixtures (clove, gram, range) | 🔴 P0 | 0.5 d | eri-2 |
| eri-3b | Backend — mixed-structure handling (run only on text-only subset; pass structured rows through untouched); integration test against `mixed_structure_jsonld.yaml` + stress case with 2-structured/3-text-only shuffled | 🔴 P0 | 0.25 d | eri-3a |
| eri-4a | Backend — `XXXX_seed_freeform_units.py` migration (15 rows in `units` table, `type="other"`, `to_base_factor=1`, self-referential `base_unit`); regression test confirms FK-intact + pattern-match with `pinch`/`dash`/`clove`/`slice` | 🔴 P0 | 0.25 d | None (parallel with eri-1..3) |
| eri-4b | Backend — `XXXX_seed_freeform_unit_aliases.py` migration (15 plural→singular alias rows) + regression on `normalize_unit_display("stalks")` etc.; Flutter `SessionAliasMap` cold-start cache-refresh verification | 🔴 P0 | 0.25 d | eri-4a |
| eri-5 | Eval — `ingredient_field_completeness` metric + 7 fixtures (3 happy + 4 negative) + `ingredient_hallucination_rate` sub-metric + baseline + eval-config registration + pre-ERI regression pinning | 🟡 P1 | 1 d | eri-3b, eri-4b |
| eri-6 | Docs + ops — `EXTRACTOR_FLAG_ROLLOUT.md` (4-step flip + rollback drill + observability pointers) + staging flip-on/flip-off verification + production flip (owns the rollout) | 🟡 P1 | 0.5 d | eri-5 |

**Total estimated effort: ~4 days**

**Parallel tracks:**
- Track A (prompt + parse pass): eri-1 → eri-2 → eri-3a → eri-3b (serial)
- Track B (migrations): eri-4a → eri-4b parallel with Track A
- Track C (eval + ops): eri-5 → eri-6 after A+B

## Open Questions for the User

**None outstanding.** All three draft open questions resolved in Phase 6:

1. **`unit_aliases.canonical_unit` FK decision →** add 15 freeform rows to `units` table, keep FK intact. Matches the `pinch`/`dash`/`clove`/`slice` pattern already in place.
2. **Parse pass on non-JSON-LD path →** no. AI extractor already emits structured ingredients; a duplicate pass would waste cost.
3. **Eval hard-gate threshold →** soft-gate in v1 with an explicit promotion trigger (7 days clean + 0 `IngredientParseFailure` + no new `UnitAliasMiss` spikes).

**Locked defaults for edge cases surfaced in Phase 6:**
- Range quantity (`"1–2 cups"`) → `quantity=1, notes="to 2 cups"`. First value is safe; full range in notes preserves intent.
- Substring ambiguity (`"a pinchful"`) → `unit=null`, notes captures the original word. Explicit prompt rule.
- No-notes cases (`"2 cups flour"`) → `notes=null`. Anti-hallucination rule in prompt + negative-case fixture.
- Non-English sources → explicitly deferred. English-only extraction in v1; tracked separately.

## Definition of Done (Epic Level)

- `EXTRACTOR_SOFTEN_UNIT_RULE` flag is live; default on; flippable via ECS task-def; flag precedence coded and matrix-tested.
- `EXTRACTOR_JSON_LD_INGREDIENT_PARSE` flag is live; default on; same flippability.
- `unit_prompt.py` emits `_SOFTENED_RULE` by default across `ai_extractor`, `vision_extractor`, `text_extractor`. `_CANONICAL_RULE` preserved for flag-off rollback.
- `ingredient_parse.py` parses text-only ingredient lists via `gpt-4o-mini` with strict JSON-schema response format; temperature 0; batches of 25 (cap 200); graceful failure (text-only + audit log on any failure class).
- `extract_recipe_from_html` invokes the parse pass on the text-only *subset* after JSON-LD succeeds; structured ingredients are passed through untouched; results splice back in original order. Mixed-structure sites work.
- `IngredientFieldCoverage` audit row written per import with per-field presence counts.
- `units` table has 15 new freeform rows (FK intact); `unit_aliases` has 15 new plural→singular seeds; `normalize_unit_display("stalks")` → `"stalk"`; `normalize_unit_display("cans")` → `"can"`.
- Flutter `SessionAliasMap` cold-start cache-refresh verified (new aliases appear without reinstall).
- `ingredient_field_completeness` metric + 7 fixtures + baseline + `ingredient_hallucination_rate` sub-metric registered in eval config. Pre-ERI fixtures still pass (regression pinned).
- End-to-end smoke: Leo imports a URL with JSON-LD text-only ingredients → Review Import shows structured rows with qty/unit/name/notes all populated → `gram`→`g` via alias table → saves cleanly.
- Photo-import smoke: `"1 clove garlic, minced"` extracts to `{q:1, u:"clove", n:"garlic", notes:"minced"}` — no name-folding.
- Mixed-structure smoke: URL with 2 structured + 3 text-only ingredients → all 5 end up structured; order preserved.
- Flag-off parity test passes: byte-for-byte equality with pre-ERI golden output when all three flags off.
- Production 4-step flip runbook executed per `eri-6`; 48h of clean `IngredientParseFailure` observation; `EXTRACTOR_EMIT_CANONICAL_UNITS` retired.
- `services/api` coverage stays at 100%; `libraries/utils` coverage not reduced.
- Zero regression on riip-1..6, efi, `epic-bugs-import-structured-ingredients`, or existing eval fixtures.
