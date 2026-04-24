<!-- refined via party-mode 2026-04-17 -->
# Epic: Bugs — Import Photo Pipeline (Source-Photo Hero + Multi-Recipe Per Photo)

## Overview

Two BUGS.md items live in the photo-import pipeline. The draft assumed they share the same touchpoint (`parser_batch_completion._handle_success`), but the audit shows they don't: **fan-out belongs in `extract_recipe_task._update_item_from_result`**, not in parser-batch completion. They're still bundled because both alter the photo-import end-state and the source-photo S3 key has to be preserved across both code paths.

**Bug A (FR87) — No source-image preservation.** When a photo import finalizes into a Recipe, the original photo the user took is forgotten. The recipe ends up with `image_url` only if the AI extractor populated it (rare for photo imports — photo extractors leave `image_url` null). URL imports work fine because their extractors scrape JSON-LD or AI-generated `image_url`. The user's locked decision: when no other hero is set, copy the user-uploaded source photo to a permanent location and use it as the recipe hero.

**Bug B (FR88) — One photo, one recipe.** The text and vision extractors today are explicitly single-recipe (`vision_extractor.py:30` literally says "Multiple recipes on a page: extract only the primary/largest recipe"). HunyuanOCR produces flat markdown with no recipe-boundary detection. So a cookbook page with two recipes side-by-side gets crammed into one mangled extraction. The user's locked decision: update the extractor prompts to detect distinct recipes and emit a JSON array; fan out N ImportItems server-side at extract time; the existing exception-review queue surfaces N cards with no new screen.

The two bugs are coupled by ordering: source-photo promotion must run **after** fan-out, so each child recipe gets a copy of (or reference to) the same source photo S3 key. The shared key flows from the original ImportItem's `raw_data.s3_keys` (set by `parser_batch_completion._handle_success`) into each fanned-out child ImportItem's `raw_data`, then into `create_recipe_task` for promotion.

## Goal

After this epic:
- A photo import → recipe always has a hero image (either the extractor's `image_url` or the user-uploaded source photo as fallback).
- A photo with multiple recipes → multiple review cards in the queue, each correctly attributed to the source photo.
- Eval suite gates extractor changes against single-recipe regression and ≥80% recipe-count accuracy on a new multi-recipe fixture set.
- The "1 photo = 1 recipe" assumption is gone from the pipeline contract, not papered over.

## End-User Flow

### Single-recipe photo (today's path, unchanged behavior + image hero)
1. User taps Add Recipe → Photo, snaps a cookbook photo, uploads, picks a recipe book, submits.
2. ParserBatch + ParserJob(s) → AWS Batch → HunyuanOCR runs → flat markdown lands in S3.
3. `parser_batch_completion._handle_success` creates one ImportJob + one ImportItem per `group_index` (the user's manual grouping). Source S3 keys are preserved on `raw_data.s3_keys`. **Unchanged.**
4. `extract_recipe_task` runs the text extractor on the OCR markdown. Extractor returns an array of length 1. `_update_item_from_result` writes `parsed_recipe` and moves the item to `matching` → `awaiting_review`. **Unchanged downstream behavior; new extractor contract.**
5. User opens the import-review queue (Activity Hub → Imports filter, or directly via `/recipes/import/review-list/{jobId}`), reviews the single card, approves.
6. **NEW:** `create_recipe_task` creates the recipe; if `recipe.image_url` is empty AND `raw_data.s3_keys` is non-empty, copies the first source photo from `palateful-parser-inputs-{env}` to a permanent location and writes that URL into `recipe.image_url`. Recipe detail and home-screen card now show the photo as the hero.

### Multi-recipe photo (cookbook facing pages, side-by-side cards)
1. User snaps one photo of two recipes on a cookbook page; uploads as a single image (group_index 0).
2. OCR + `_handle_success` create one ImportJob with `total_items=1` and one ImportItem (today's behavior).
3. `extract_recipe_task` runs the text extractor; the new prompt detects two distinct recipes; the extractor returns a list of two `ExtractedRecipe`s.
4. **NEW:** `_update_item_from_result` notices N>1 recipes. It writes the first recipe into the existing ImportItem's `parsed_recipe`, then creates N-1 sibling ImportItems on the same ImportJob, each with the same `raw_data.s3_keys` and a `recipe_index` field for traceability. ImportJob `total_items` is bumped from 1 to N atomically.
5. User opens the import-review queue and sees **two** review cards under the same job instead of one mangled item.
6. User reviews and approves each independently. Each becomes its own Recipe via `create_recipe_task`.
7. Both recipes get the same source photo as their hero (FR87 applies independently to each child, both find the same S3 key in `raw_data`).
8. If the model over- or under-splits, the user edits the cards individually with the structured editor (epic-bugs-import-structured-ingredients) — there is no manual merge/split affordance in v1. **If the model FAILS to split a multi-recipe photo, the user gets a mangled card just like today; this is a known v1 gap, surfaced via the eval gate (Open Question 1, resolved as "ship without merge/split UI; revisit on dogfood feedback").**

### URL imports
1. **Unchanged.** URL extractors continue to populate `image_url` from JSON-LD or AI; FR87's fallback never fires because `image_url` is already set. The new array-return contract still applies — single-recipe URL responses become arrays of length 1, indistinguishable downstream.

## Frontend Changes

**Audit + light copy edits.** The existing `ImportHistoryScreen` (`app/lib/features/activity/import_history_screen.dart`) already loads jobs and lists their items via `_apiClient.listImportItems(jobId)`. When fan-out creates N items on one job, the list naturally renders N cards — no UI rewrite required. Verify:

- `BatchParserService` in `batch_parser_service.dart` polls per-`ParserJob`; it does NOT track ImportItems. Fan-out happens downstream (in extract_recipe_task) so this service is unaffected. (Marcus — confirmed via code read.)
- `ImportHistoryScreen._loadAttentionView` calls `listImportItems(jobId)` and filters by `status == 'awaiting_review'`. N items per job appear naturally.
- `BatchImportStatusWidget` on the home screen shows "X recipes processed" — but the `X` here counts ParserJob successes, not ImportItems. After fan-out a single ParserJob can produce N recipes; the widget undercounts. Update its summary to say "X photos processed → check Activity for recipes" or similar. (Sally — surfaces the multi-recipe outcome instead of hiding it.)
- `ImportItemReviewScreen` renders one card per ImportItem; nothing assumes 1:1 with photo. **No code change required**, but verify with a manual end-to-end test.
- Activity-feed text generated by `create_activity` (in `extract_recipe_task` and `create_recipe_task`) currently says "Import complete!" with subtitle "X succeeded, Y need review" — already plural-friendly. No change.

This is one slim story (`bugs-imp-pho-6`) of verification + the BatchImportStatusWidget copy edit, not a redesign.

## Backend Changes

**Heavy.** Most of the epic.

- **Extractor contract change** (`libraries/utils/utils/services/recipe_extractors/`):
  - `BaseExtractor.extract()` and the module-level `extract_recipe_from_text()` / `extract_recipe_from_image()` change return type from `ExtractionResult` (singular `recipe`) to `ExtractionResult` with a new `recipes: list[ExtractedRecipe]` field. The existing `recipe` field is kept as a deprecated alias = `recipes[0] if recipes else None` for one cycle to ease the migration. **Do not remove `recipe` in this epic** — the `RecipeExtractionEvaluator` (`services/eval/src/evaluators/recipe_extraction_evaluator.py:160`) reads `result.recipe` directly. (Winston caught this — eval would break silently.)
  - All four extractors (`ai_extractor.py`, `text_extractor.py`, `vision_extractor.py`, plus `json_ld.py` for URL parity) update prompts and return shapes.
  - **`vision_extractor.py:30` must change** — the line "Multiple recipes on a page: extract only the primary/largest recipe" is directly opposite of FR88 and must be replaced with the new multi-recipe instruction. (Winston caught this; the draft missed it.)
- **Fan-out lives in `extract_recipe_task._update_item_from_result`** (`libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py:137`), NOT in `parser_batch_completion._handle_success`. The draft was wrong about the location. (Winston caught this; the parser-batch completion runs BEFORE extraction.) When the extractor returns N>1 recipes:
  1. Write the first recipe into the existing ImportItem's `parsed_recipe`, set `last_successful_stage=STAGE_EXTRACTED`, status `matching`.
  2. For recipes [1..N-1], create new ImportItem rows on the same `import_job_id` with copies of `raw_data` (including `s3_keys`) plus a `recipe_index` int (0-based, so the first item gets `recipe_index=0` too).
  3. Atomically bump `ImportJob.total_items` from 1 to N (or from M to M+N-1 in batched cases).
  4. Dispatch `match_ingredients_task` for each new item.
  5. Idempotency: dedupe on `(import_job_id, source_s3_key, recipe_index)` so a retry of the same extract call doesn't double-fan-out. Concretely: on retry, look up existing siblings by `import_job_id` + same `s3_keys` and only create rows for `recipe_index` values not yet present.
- **Source-photo promotion** (FR87, in `create_recipe_task`):
  - New helper module `libraries/utils/utils/services/recipe_image_promotion.py` exposing `promote_source_photo(aws_service, user_id, recipe_id, source_s3_key) -> str | None`.
  - The helper copies from `parser_inputs_bucket` (source) to `parser_inputs_bucket` (destination, **same bucket**) at `recipe-photos/{user_id}/{recipe_id}/source-{timestamp}.{ext}`. **Same bucket reuses the existing recipe-photos prefix convention from `get_photo_upload_url.py:70`**, which is the existing user-attached-photo flow. (Decision below; see Inherited Locked Decisions.)
  - Returns the public URL `https://{bucket}.s3.{region}.amazonaws.com/{key}`, mirroring `get_photo_upload_url.py:91`.
  - On any S3 error, returns `None` and logs warning at WARN level. Does not raise.
  - Called from `create_recipe_task.execute` AFTER `self.database.create(recipe)` succeeds. Conditions: `recipe.image_url is None or empty` AND `raw_data.get('s3_keys')` is non-empty. Uses the first key. After successful promotion, sets `recipe.image_url` and commits.
  - **AWSService instantiation:** `BaseTask` does not currently expose AWS. `create_recipe_task` must instantiate `AWSService` inline using `config.settings`, mirroring the pattern in `services/api/src/api/v1/recipe/get_photo_upload_url.py:_get_aws_service()`. (Winston flagged.)
  - **AWSService gains a new `copy_object(source_key, dest_key, source_bucket=None, dest_bucket=None) -> None` method** that wraps `boto3.client('s3').copy_object(...)`. Today there is no copy primitive. (Winston flagged.)
- **Eval fixtures + recipe-count metric** (Story 13.5 framework lives at `services/eval/src/`, fixtures at `services/eval/fixtures/`):
  - 3+ new multi-recipe text fixtures added under `services/eval/fixtures/text/` paired with `expected/` JSON whose top-level shape changes from a single recipe object to `{"recipes": [...]}` for the multi-recipe cases. Single-recipe expected shapes remain `{...recipe...}` for backwards compat — the evaluator detects the new shape and grades both lengths.
  - `RecipeExtractionEvaluator._calculate_metrics` gains a `recipe_count_accuracy` metric.
  - Eval threshold gate added in `services/eval/src/runner.py::_check_thresholds` for the `recipe_extraction` suite: fail when `recipe_count_accuracy_avg < 0.8` on multi-recipe-tagged cases.
  - The existing `field_accuracy` metric must NOT regress more than 5% from the pre-change baseline (captured in PR description).
  - **No new vision-extractor eval suite** — image fixtures + vision extractor are not covered today and adding them is its own story (`bugs-imp-pho-7`, see follow-up). Multi-recipe text fixtures cover the fan-out logic adequately for v1; vision-extractor's multi-recipe behavior is graded only on the OCR-then-text round-trip in real dogfood. **Open Question 2 below — escalated.**
- **Migration: NONE.** ImportItem already supports N items per job. `recipe_index` lives in `raw_data` JSONB. `total_items` is mutable on ImportJob. Source-photo promotion writes to existing `recipe.image_url`.

## Infrastructure Changes

**Smaller than the draft claimed — no new bucket needed.** (Infra lens.)

- **Bucket reuse decision: reuse `palateful-parser-inputs-{env}` with the `recipe-photos/` prefix.** Audit found:
  - There is no `palateful-recipe-photos-{env}` bucket. Story 2.3 (Recipe Photos) shipped without one — it piggybacks on `parser-inputs` (`get_photo_upload_url.py:70-91`).
  - The parser-inputs bucket has **no lifecycle expiration on prod** (only dev's `parser_outputs` has 30-day expiry per `terraform/modules/s3/main.tf:101-116`). Reuse is safe for permanent storage.
  - Reusing the bucket means **zero new infra**: no new Terraform module, no new IAM grants beyond what the worker task already has via `aws_iam_policy.api_service` (which already grants `PutObject`, `GetObject`, `DeleteObject` on `parser_inputs_bucket_arn/*`). The worker task role attaches this policy at `terraform/modules/iam/main.tf:476-480`.
  - **Trade-off accepted:** entangling permanent recipe images with short-lived parser inputs in one bucket is a long-term cleanliness concern, but solving it requires a wider migration of the existing recipe-photo flow. That migration is **out of scope here** and tracked as a separate concern. (Sally+Winston flagged; resolved by punting the migration as a separate epic, not a hidden defer in this one — see Open Question 3.)
- **No new IAM grant required** — `s3:CopyObject` is implicitly covered: AWS evaluates copy as a `GetObject` on source + `PutObject` on dest. Both are already granted on `parser_inputs_bucket_arn/*`. The new `copy_object` call is same-bucket, so a single bucket policy covers both sides. (Winston verified against `terraform/modules/iam/main.tf:226-275`.)
- **No CORS change** — same bucket, same existing CORS rules (`terraform/modules/s3/main.tf:52-62`).
- **No new env var** — the worker reads `parser_inputs_bucket` from existing `config.settings`, same as the API.
- **Cost impact:** ~1–4 MB per recipe import via photo. At 100 photo-imports/month = ~400 MB/month new permanent storage. Trivial S3 cost. (Quinn asked.)
- **Open follow-up (NOT this epic):** factor `palateful-recipe-photos-{env}` into a dedicated bucket and migrate both this epic's promoted images AND the existing `recipe-photos/` prefix in parser-inputs over to it. Tracked in Open Question 3.

No new ECS services, no Lambda, no API Gateway changes.

## Design Principles (refined via party-mode 2026-04-17)

1. **Fan-out is the contract; single-recipe is a length-1 array** (Bob+Winston). All extractors emit an array via `ExtractionResult.recipes`. Downstream code never special-cases N=1. This kills the "1 photo = 1 recipe" assumption at its source instead of papering over it. The deprecated `recipe` alias buys one cycle to migrate the eval framework safely.
2. **Source-photo promotion is best-effort** (Bob+Quinn). A failure to copy must not fail recipe creation. The recipe is the user's data; the hero image is a nice-to-have. Log warnings, don't crash. NFR41's 500ms budget is enforced by setting `botocore.config.Config(read_timeout=2.0, retries={'max_attempts': 2})` on the copy call, with a fail-fast fallback.
3. **No new Review UX in v1** (locked). Auto-detect ships first; manual merge/split is a follow-up only if dogfood shows the model regularly fails. Trust the model to be right most of the time and let the user edit cards individually when it isn't.
4. **One source photo, N recipes share it** (locked). If the extractor splits into 2 recipes, both get the same hero (a photo of the cookbook page). Acceptable v1 — the user can replace either recipe's hero via the existing photo-attachment flow.
5. **Eval gate is non-negotiable** (Quinn). Prompt changes that improve multi-recipe but regress single-recipe must be caught before merge. The existing eval framework (Story 13.5, at `services/eval/src/`) gets a new `recipe_count_accuracy` metric AND a regression guard on `field_accuracy` (≤5% drop from baseline).
6. **Reuse the existing bucket; defer the cleanup** (infra lens). The "permanent vs. transient" entanglement is a real concern, but solving it now means migrating the existing user-attached-photo flow too. Punted explicitly to Open Question 3, not silently inherited.
7. **Fan-out point is `extract_recipe_task`, not `parser_batch_completion`** (Winston). The draft was wrong; this is fixed in the story map below. Extraction is where recipes become recipes, so it's where N-recipe detection happens.
8. **BatchImportStatusWidget surfaces the multi-recipe outcome** (Sally). After fan-out, a single ParserJob can produce N recipes. The home-screen widget's wording shifts from "X recipes processed" (which undercounts) to "X photos processed → see Activity for recipes" so the user knows to look at the Activity Hub for the actual count.
9. **Field-render policy borrowed from Activity Hub workshop** (Quinn). When the extractor adds a new field per-recipe (`recipe_index`), it must be either rendered in the review queue or annotated in code as intentionally-not-shown. Currently `recipe_index` is `intentionally-not-shown: server-side traceability only`.

## Inherited Locked Decisions

**From the structured-ingredients workshop (carry forward verbatim):**
- Ingredient `quantity` is `float`/`Decimal | null` on the wire; fractions are parsed/formatted client-side only.
- Ingredient `unit` is a free-text string on the wire; curated dropdown is Flutter-UI only (NFR43 — Flutter constant in `ingredient_units.dart`).
- `name` (string) is an accepted alternate to `ingredient_id` on recipe-create/update endpoints with server-side find-or-create (`pending_review=True` for new ingredients).
- The structured ingredient shape (`{name, quantity, unit, notes, is_optional}`) is canonical for any client → server ingredient input. The legacy `{quantity_display, unit_display, ingredient: {canonical_name}}` shape is dead.
- Audit-log admin actions (existing pattern via `error_logs` with `service="audit"`).
- Constructive actions skip snackbar-undo; destructive actions use snackbar-undo (3s).
- Directories: shared Flutter widgets → `app/lib/features/recipes/widgets/`; shared utils → `app/lib/core/utils/`; ops scripts → `services/api/scripts/`; migrations → `services/migrator/migrations/`.

**New locked decisions from this workshop (carry forward to later epics in this run):**
- **`ExtractionResult.recipes: list[ExtractedRecipe]` is the canonical extractor return shape.** The deprecated `recipe` field is a single-cycle migration alias = `recipes[0] if recipes else None`; remove it in the next epic that touches extractors. Future extractors MUST populate `recipes`, not `recipe`.
- **Fan-out happens at extract time, not at OCR-completion time.** Any future "1 input → N outputs" pattern in the import pipeline (PDF page splitting, audio transcript splitting, future video-segment splitting) follows the same model: the extractor decides multiplicity; `_update_item_from_result` (or its sibling for that source type) does the fan-out; ImportJob's `total_items` is bumped atomically.
- **`raw_data.s3_keys` (list of strings) is the canonical carrier for source-photo provenance** on a photo-imported ImportItem, set by `parser_batch_completion._handle_success`. Children created by fan-out copy this verbatim. The first key wins for source-photo promotion.
- **`raw_data.recipe_index: int` (0-based) is the canonical fan-out ordinal** on a photo-imported ImportItem. Lives in JSONB; no schema column. Used as the dedupe key for fan-out idempotency.
- **Source-photo promotion writes to the same bucket the photo was uploaded to** (`palateful-parser-inputs-{env}`), at `recipe-photos/{user_id}/{recipe_id}/source-{timestamp}.{ext}`. The bucket-rename to a dedicated `palateful-recipe-photos-{env}` is deferred to a follow-up epic (Open Question 3).
- **Eval `recipe_count_accuracy` metric is gated at ≥0.8 on multi-recipe fixtures**; existing `field_accuracy` may not regress >5% from baseline. Both gates are CI-enforced via `services/eval/src/runner.py::_check_thresholds`.

## File Structure

```
libraries/utils/utils/services/recipe_extractors/
├── base.py                                        # MODIFIED — ExtractionResult.recipes (list); recipe (single) kept as deprecated alias for one cycle
├── ai_extractor.py                                # MODIFIED — prompt requests array of recipes; returns recipes list
├── text_extractor.py                              # MODIFIED — same; this is the photo-OCR-text path
├── vision_extractor.py                            # MODIFIED — same; ALSO remove the "extract only the primary/largest recipe" anti-instruction at line 30
└── json_ld.py                                     # MODIFIED — wrap single result in length-1 list to satisfy the new contract uniformly

libraries/utils/utils/services/
├── parser_batch_completion.py                    # UNCHANGED — _handle_success continues to set raw_data.s3_keys; the draft was wrong about needing to change it
└── recipe_image_promotion.py                     # NEW — promote_source_photo() helper (S3 same-bucket copy + URL construction + best-effort error handling)

libraries/utils/utils/services/aws.py             # MODIFIED — add copy_object(source_key, dest_key, source_bucket=None, dest_bucket=None) wrapping boto3 s3.copy_object

libraries/utils/utils/tasks/import_tasks/
├── extract_recipe_task.py                        # MODIFIED — _update_item_from_result fans out to N ImportItems when extractor returns recipes list of length >1; bumps ImportJob.total_items atomically; dispatches match_ingredients_task per child
└── create_recipe_task.py                         # MODIFIED — instantiate AWSService inline; after recipe.create(), if image_url is empty AND raw_data.s3_keys exists, call promote_source_photo; persist returned URL to recipe.image_url

services/eval/fixtures/text/
├── multi_recipe_facing_pages.txt                 # NEW — OCR text from a 2-recipe spread
├── multi_recipe_side_by_side.txt                 # NEW — OCR text from 2 side-by-side recipe cards
└── multi_recipe_three_panel.txt                  # NEW — OCR text where 3 recipes share a layout (boundary stress test)

services/eval/fixtures/expected/
├── multi_recipe_facing_pages.json                # NEW — {"recipes": [recipe1, recipe2]}
├── multi_recipe_side_by_side.json                # NEW — same shape
└── multi_recipe_three_panel.json                 # NEW — {"recipes": [r1, r2, r3]}

services/eval/src/evaluators/
└── recipe_extraction_evaluator.py                # MODIFIED — _calculate_metrics adds recipe_count_accuracy; handles both legacy single-recipe expected shape and new {"recipes": [...]} multi-recipe shape

services/eval/src/
└── runner.py                                     # MODIFIED — _check_thresholds gains recipe_count_accuracy gate (≥0.8) for multi-recipe-tagged cases; field_accuracy regression guard (≤5% from baseline) optional but logged

services/eval/src/config.py                       # MODIFIED — thresholds adds recipe_count_accuracy threshold (default 0.8)

libraries/utils/test/
├── test_extract_recipe_task_fanout.py            # NEW — extractor returns N → N ImportItems; total_items bumped; match_ingredients_task dispatched per child; retry idempotency
├── test_recipe_image_promotion.py                # NEW — copy succeeds, copy fails, image_url already set, no s3_keys
└── test_recipe_extractors_array_contract.py      # NEW — every extractor returns recipes list (length 1 or N); legacy `recipe` alias still works for one cycle

services/api/tests/
└── test_create_recipe_task_promotion.py          # NEW — end-to-end: ImportItem with s3_keys → recipe created → image_url is the new permanent URL

app/lib/features/home/widgets/
└── batch_import_status_widget.dart               # MODIFIED — copy edit: "X photos processed" + nudge to Activity instead of misleading "X recipes processed"

app/lib/features/recipes/add_recipe/
├── photo_capture_screen.dart                     # AUDIT — confirm N-from-1 polling works; no code change expected
├── batch_parser_service.dart                     # AUDIT — polls per-ParserJob; unchanged by fan-out
└── import_item_review_screen.dart                # AUDIT — renders one card per ImportItem; unchanged by fan-out

app/lib/features/activity/
├── import_history_screen.dart                    # AUDIT — listImportItems(jobId) returns N items naturally; verify counters
└── widgets/import_activity_detail.dart           # AUDIT — already field-render-policy compliant; add disposition for raw_data.recipe_index in the audit comment block
```

## Story Map

| # | Story | Priority | Est. | Dependencies |
|---|-------|----------|------|--------------|
| bugs-imp-pho-1 | Extractor multi-recipe prompt + array-return contract (recipes list + deprecated alias) | 🔴 P0 | 1 d | None |
| bugs-imp-pho-2 | Fan-out in extract_recipe_task (NOT parser_batch_completion); bump total_items atomically | 🔴 P0 | 1 d | bugs-imp-pho-1 |
| bugs-imp-pho-3 | AWSService.copy_object + recipe_image_promotion helper (no Terraform; bucket reuse decided) | 🟡 P1 | 0.5 d | None (parallel) |
| bugs-imp-pho-4 | Source-photo promotion call in create_recipe_task | 🔴 P0 | 0.5 d | bugs-imp-pho-3 |
| bugs-imp-pho-5 | Multi-recipe eval fixtures + recipe_count_accuracy gate (≥0.8) + field_accuracy regression guard | 🟡 P1 | 1 d | bugs-imp-pho-1 |
| bugs-imp-pho-6 | Flutter audit + BatchImportStatusWidget copy edit | 🟢 P2 | 0.5 d | bugs-imp-pho-2 |

**Total: ~4.5 days.** bugs-imp-pho-3 and bugs-imp-pho-1 can start in parallel.

---

## Story bugs-imp-pho-1: Extractor multi-recipe prompt + array-return contract

As a backend developer (and downstream, the user),
I want every recipe extractor to return a list of recipes (length 1 for single-recipe inputs, length N when multiple are detected),
so that the "1 photo = 1 recipe" assumption is killed at the source.

### Acceptance Criteria

1. `ExtractionResult` (in `libraries/utils/utils/services/recipe_extractors/base.py`) gains a new field `recipes: list[ExtractedRecipe] = field(default_factory=list)`. The existing `recipe: ExtractedRecipe | None` field is retained as a **deprecated alias** that resolves to `recipes[0] if recipes else None`. **A `# DEPRECATED: remove in next extractor-touching epic` comment is added.**
2. All four extractors update prompts to request an array shape:
   - `text_extractor.py` and `ai_extractor.py`: prompt now requests `{"recipes": [...]}` with each recipe matching the existing single-recipe schema. Includes 1–2 few-shot examples of multi-recipe pages.
   - `vision_extractor.py`: same as text; **also delete the line `- Multiple recipes on a page: extract only the primary/largest recipe` at line 30** and replace with `- Multiple recipes on a page: emit each as a separate object in the recipes array; do not merge them.`
   - `json_ld.py`: continues to extract a single recipe; wraps the result in a length-1 `recipes` list to satisfy the new contract uniformly.
3. The new prompts explicitly define what counts as "distinct" — a recipe with a separate title and ingredient list is distinct; a "Variation" subsection or "Substitution Notes" is the same recipe with a note. (Eval fixture `multi_recipe_three_panel.txt` exercises this boundary case.)
4. JSON-array parse failures fall back to a single-recipe parse via the existing path: if the model returns a bare recipe object instead of `{"recipes": [...]}`, treat it as `{"recipes": [bare_object]}`. Log a warning. The pipeline does not break on a model that ignores the new instruction.
5. JSON parse errors entirely (malformed JSON) continue to set `success=False` with `AI_JSON_PARSE_ERROR` exactly as today.
6. Every extractor sets BOTH `result.recipes` (canonical) and `result.recipe` (alias) on the success path.
7. Unit tests cover, per extractor: array-of-1 return on single-recipe input, array-of-N return on multi-recipe input, fallback on bare-object JSON, fallback on malformed JSON. (New test file `libraries/utils/test/test_recipe_extractors_array_contract.py`.)
8. Identify all call sites in this story's PR description. **Confirmed call sites today:** `extract_recipe_task._update_item_from_result` (changes in story 2), `services/eval/src/evaluators/recipe_extraction_evaluator.py:160` (continues to read `result.recipe` via the deprecated alias — no change in this story; eval gate updated in story 5). Search for any others in `libraries/utils/utils/` and `services/api/src/` and confirm they tolerate the new shape.

### Key Files

- Modify: `libraries/utils/utils/services/recipe_extractors/base.py`
- Modify: `libraries/utils/utils/services/recipe_extractors/ai_extractor.py`
- Modify: `libraries/utils/utils/services/recipe_extractors/text_extractor.py`
- Modify: `libraries/utils/utils/services/recipe_extractors/vision_extractor.py` (including line-30 deletion)
- Modify: `libraries/utils/utils/services/recipe_extractors/json_ld.py` (wrap single result in length-1 list)
- Test: `libraries/utils/test/test_recipe_extractors_array_contract.py` (new)

---

## Story bugs-imp-pho-2: Fan-out in extract_recipe_task (NOT parser_batch_completion)

As a user uploading a photo with multiple recipes,
I want the system to create one ImportItem per detected recipe,
so that the review queue shows them as N separate cards instead of one mangled item.

### Acceptance Criteria

1. **`extract_recipe_task._update_item_from_result`** (`libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py:137`) — NOT `parser_batch_completion._handle_success` as the draft incorrectly claimed — is modified. When `result.recipes` has length > 1:
   - The existing ImportItem absorbs `recipes[0]` into its `parsed_recipe`. `raw_data` is updated to add `recipe_index: 0`.
   - For each `recipes[i]` where `i >= 1`, a new ImportItem row is created with `import_job_id=item.import_job_id`, `source_type='photo'`, `status='matching'` (skipping `extracting`, since extraction is already done), `last_successful_stage=STAGE_EXTRACTED`, `parsed_recipe=recipes[i]_dict`, `raw_data={...item.raw_data, 'recipe_index': i}`.
2. **`ImportJob.total_items` is bumped atomically** from M to M+N-1 in the same transaction as the new ImportItem inserts. The existing `_update_job_counts` machinery picks up the new count on the next pass without further code change.
3. `match_ingredients_task` is dispatched for each new sibling ImportItem, mirroring the dispatch the existing `_dispatch_matching_task(item)` does for the original item.
4. **Idempotency on retry:** if `_update_item_from_result` runs again for the same item (e.g., Celery retry), it must NOT create duplicate siblings. Dedupe key: `(import_job_id, source_s3_keys, recipe_index)`. Implementation: before creating a sibling for `recipe_index=i`, query for an existing ImportItem on the same job with `raw_data->>'recipe_index' = i AND raw_data->'s3_keys' = original.raw_data->'s3_keys'`. Skip if present.
5. **AI cost tracking:** the entire extractor call's cost goes to the original ImportItem's `ai_cost_cents`. Sibling items have `ai_cost_cents=0`. (Avoids double-counting on the job-level `total_ai_cost_cents`.)
6. Single-recipe behavior is untouched: when `len(result.recipes) == 1`, the existing path runs unchanged.
7. Failure / no-recipes case (`success=False` or empty `recipes`) is unchanged: original item gets `status=failed`, `error_message`, `error_code`, `retry_count += 1`.
8. Unit tests:
   - extractor returns 3 → 3 ImportItems on the job (one updated, two new) with `recipe_index` 0/1/2 sharing identical `s3_keys`.
   - extractor returns 1 → 1 ImportItem updated (regression test).
   - retry of the 3-recipe extractor call → still 3 ImportItems (no duplicates).
   - extractor returns 0 / fails → original item marked failed; no siblings created.
   - `total_items` ends at expected value in all cases.
9. Integration test (existing test infra permitting): construct an ImportJob + ImportItem with mock raw OCR text, mock the extractor to return 2 recipes, run `extract_task` → assert 2 ImportItems exist on the job, `total_items=2`, both have `last_successful_stage=STAGE_EXTRACTED`.

### Key Files

- Modify: `libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py` (specifically `_update_item_from_result`)
- Test: `libraries/utils/test/test_extract_recipe_task_fanout.py` (new)

---

## Story bugs-imp-pho-3: AWSService.copy_object + recipe_image_promotion helper

As a backend developer,
I want a clean S3 same-bucket copy primitive and a focused helper for promoting a parser-input photo to a permanent recipe-photo key,
so that source-photo promotion (story 4) is one function call with predictable failure semantics.

### Acceptance Criteria

1. **`AWSService.copy_object(source_key: str, dest_key: str, source_bucket: str | None = None, dest_bucket: str | None = None) -> None`** is added to `libraries/utils/utils/services/aws.py`. Wraps `boto3.client('s3').copy_object(...)` with `CopySource={'Bucket': source_bucket or self.parser_inputs_bucket, 'Key': source_key}`. Both bucket params default to `parser_inputs_bucket` so same-bucket copies need no overrides. Boto3 client uses the existing `Config(read_timeout=2.0, retries={'max_attempts': 2})` to enforce NFR41's 500ms-ish budget.
2. **`libraries/utils/utils/services/recipe_image_promotion.py` is created** with a single public function `promote_source_photo(aws: AWSService, user_id: UUID | str, recipe_id: UUID | str, source_s3_key: str, region: str, bucket: str) -> str | None`:
   - Generates a deterministic dest key: `recipe-photos/{user_id}/{recipe_id}/source-{utc_iso_compact}.{ext}` where `ext` is parsed from `source_s3_key` (default `jpg`).
   - Calls `aws.copy_object(source_key=source_s3_key, dest_key=dest_key)` (same bucket, both default to `parser_inputs_bucket`).
   - On success, returns `f"https://{bucket}.s3.{region}.amazonaws.com/{dest_key}"` (mirrors `get_photo_upload_url.py:91` URL construction).
   - On any `botocore.exceptions.ClientError` or other exception, logs at WARN level with the source key and exception type, returns `None`. Does not raise.
3. **No Terraform changes.** The existing worker IAM policy (`aws_iam_policy.api_service` attached at `terraform/modules/iam/main.tf:476-480`) already grants `PutObject`+`GetObject` on `parser_inputs_bucket_arn/*`, which collectively covers `s3:CopyObject` for the same-bucket case. Document the rationale in the PR description.
4. **No new env var.** The bucket name is read from the existing `config.settings.parser_inputs_bucket` at the worker side.
5. **Idempotency:** the deterministic dest key includes a UTC-iso-compact timestamp at function-call time, so a retry produces a NEW dest key. This is intentional — we don't want a half-copied object to be silently reused. The orphan from the failed first attempt is caught by a future cleanup pass; in the meantime, S3 cost is negligible.
6. Unit tests in `libraries/utils/test/test_recipe_image_promotion.py`:
   - happy path: mocked `aws.copy_object` returns OK → URL returned; URL has the right shape; key has the right user_id/recipe_id segment.
   - copy raises `ClientError` → returns `None`, log line emitted at WARN.
   - non-ClientError exception (e.g., `KeyError` from a malformed source key) → returns `None`, log emitted, no raise.
   - No `source_s3_key` extension → defaults to `.jpg` in dest key.
7. Helper has no SQLAlchemy or task-framework dependencies — pure function over `AWSService`. Easy to call from any context with an AWS client.

### Key Files

- Modify: `libraries/utils/utils/services/aws.py` (add `copy_object` method)
- Create: `libraries/utils/utils/services/recipe_image_promotion.py`
- Test: `libraries/utils/test/test_recipe_image_promotion.py`

---

## Story bugs-imp-pho-4: Source-photo promotion call in create_recipe_task

As a user importing a recipe by photo,
I want the photo I uploaded to become the recipe's hero image when no other hero is set,
so that my recipe collection looks like recipes (not titles on a blank card).

### Acceptance Criteria

1. `create_recipe_task.execute` (in `libraries/utils/utils/tasks/import_tasks/create_recipe_task.py`) is modified to call `promote_source_photo` AFTER the recipe row is created and committed (i.e., after `self.database.create(recipe)` and `self.database.db.refresh(recipe)`), only if:
   - `recipe.image_url` is `None` or empty string, AND
   - `item.raw_data.get('s3_keys')` is a non-empty list.
2. **AWSService instantiation in the worker:** since `BaseTask` does not currently expose an AWS client, `create_recipe_task` instantiates `AWSService` lazily via the same singleton pattern as `services/api/src/api/v1/recipe/get_photo_upload_url.py:_get_aws_service()`. Pull region + parser_inputs_bucket + parser_outputs_bucket + batch_job_queue + batch_job_definition from `config.settings`. (For the worker, `config.settings` lives in `services/worker/src/config.py` — verify during implementation; mirror what other worker tasks already do for AWS access if any precedent exists.)
3. The first key in `raw_data['s3_keys']` is used as the source. Multi-page recipes (multiple keys for one recipe) get only their first page promoted as hero. **This is acceptable v1** per locked decision #4. (Sally — flagged as future polish if multi-page imports become common.)
4. `promote_source_photo` is called with the worker's `user_id` (= `self.user_id` if available, else fall back to `job.user_id` looked up from `ImportJob`). The recipe_id is `recipe.id`.
5. If `promote_source_photo` returns a URL, `recipe.image_url = url`; commit. Activity-log this as INFO with the source key + dest URL.
6. If `promote_source_photo` returns `None`, leave `recipe.image_url = None`. **Recipe creation does NOT fail** (NFR41).
7. **NFR41 latency budget**: the boto3 copy call uses `Config(read_timeout=2.0, retries={'max_attempts': 2})` (set on the `AWSService._s3` client — story 3 covers this). Verify in a single integration test that adds a happy-path-with-real-S3-mock measurement: total `create_recipe_task.execute` time delta with vs. without promotion is < 500ms at P95 across 5 runs. (If this can't be measured cleanly without real S3, log `time.perf_counter()` deltas in the test and assert the in-process portion of promotion is < 50ms; trust the boto3 timeout to enforce the rest.)
8. URL imports remain unaffected — `recipe.image_url` is set by the extractor, the `image_url is empty` condition is false, promotion is a no-op.
9. **Multi-recipe fan-out (from story 2):** each sibling ImportItem inherits the same `raw_data['s3_keys']`. When each is approved, each child recipe gets its own promotion call → each child gets the same source-photo URL (the dest key includes `recipe_id` so they're distinct objects in S3, both copied from the same source). **The user can later attach a different hero photo to either recipe via the existing `get_photo_upload_url` flow; that overrides the auto-promoted one.**
10. **Idempotency**: re-running `create_recipe_task` for the same item (currently allowed when `item.status in ('approved', 'awaiting_review')`) — if the recipe already exists with `image_url` set, the conditions in AC1 are false and promotion no-ops. If it doesn't (race), a fresh dest key (different timestamp) is written; harmless duplicate in S3.
11. Unit tests in `services/api/tests/test_create_recipe_task_promotion.py`:
   - `image_url` empty + `s3_keys` non-empty + mocked successful copy → `recipe.image_url` set to the dest URL.
   - `image_url` empty + `s3_keys` non-empty + mocked failed copy → `recipe.image_url` stays None, recipe still created, warning logged.
   - `image_url` already set by extractor → promotion skipped, `image_url` unchanged.
   - `s3_keys` missing or empty (e.g., URL import) → promotion skipped, `image_url` unchanged.
   - Multi-recipe: two ImportItems (created via fan-out in story 2) both approved → both recipes get promoted URLs with the same source bucket key but distinct dest keys.

### Key Files

- Modify: `libraries/utils/utils/tasks/import_tasks/create_recipe_task.py`
- Test: `services/api/tests/test_create_recipe_task_promotion.py` (new)

---

## Story bugs-imp-pho-5: Multi-recipe eval fixtures + recipe_count_accuracy gate

As a backend developer,
I want the existing eval suite extended with multi-recipe fixtures and a recipe-count accuracy metric,
so that prompt changes can't quietly regress single-recipe extraction or under-perform on the new multi-recipe path (NFR42).

### Acceptance Criteria

1. Add at least 3 new fixture pairs under `services/eval/fixtures/text/` and `services/eval/fixtures/expected/`:
   - `multi_recipe_facing_pages.{txt,json}` — OCR text representing a 2-recipe spread (e.g., a real cookbook page transcribed). Expected JSON has shape `{"recipes": [{...}, {...}]}`.
   - `multi_recipe_side_by_side.{txt,json}` — 2 side-by-side recipe cards. Same expected shape.
   - `multi_recipe_three_panel.{txt,json}` — 3 recipes on one layout (boundary test for the "Variation vs distinct recipe" prompt heuristic).
2. The eval manifest (whichever YAML/JSON drives `RecipeExtractionEvaluator.load_cases`) tags these new cases with `"multi_recipe"` so the threshold can be applied selectively.
3. **`RecipeExtractionEvaluator._calculate_metrics`** in `services/eval/src/evaluators/recipe_extraction_evaluator.py` is updated to:
   - Detect the expected shape: if `expected_data` has key `"recipes"`, treat as multi-recipe; else legacy single-recipe (wrap implicitly in a length-1 list).
   - Detect the actual shape similarly: if `actual_output` has key `"recipes"`, use `actual["recipes"]`; else wrap as single. (The deprecated `result.recipe` alias means legacy actuals still work.)
   - Compute `recipe_count_accuracy`: `1.0` if `len(actual) == len(expected)`, else `0.0` per case. Aggregate across the suite as a mean.
   - **Per-recipe field metrics (`field_accuracy`, etc.) compute on ALL pairs via order-based alignment** (resolved Workshop Question 4): pair `expected[i]` with `actual[i]` for `i in range(min(len(expected), len(actual)))`. Unpaired expected recipes contribute 0 to field accuracy (missed); unpaired actual recipes contribute 0 (hallucinated). Aggregate as the mean over all paired field-comparisons. **Document the alignment heuristic in a code comment** so a future contributor understands order-based is intentional, not an oversight.
   - Add an alignment-fallback log line when `len(actual) != len(expected)` so eval failures are diagnosable: `"alignment: expected N=X actual N=Y; field metrics computed on first min(X,Y) pairs"`.
4. **Threshold gate added** in `services/eval/src/runner.py::_check_thresholds` for the `recipe_extraction` suite: append `recipe_count_accuracy_avg >= thresholds.recipe_count_accuracy` (default 0.8) to the existing `field_accuracy_avg >= thresholds.recipe_field_accuracy` check. Both must pass for the suite to pass.
5. `services/eval/src/config.py` adds a new threshold field `recipe_count_accuracy: float = 0.8` to the `EvalThresholds` dataclass.
6. Existing single-recipe fixtures (`chocolate_chip_cookies`, `chicken_tikka_masala`, `simple_pasta`, `banana_bread`, `potato_quiche`) continue to pass without modification. Their expected JSONs stay in single-recipe shape; the evaluator wraps them implicitly.
7. Baseline run: in the PR description, capture the pre-change scores for `field_accuracy_avg` and (if any baseline runs were stored) `recipe_count_accuracy_avg`. Fail the merge if `field_accuracy_avg` regresses by more than 5% from the captured baseline. (This guard can be enforced manually in the PR review if there's no automated baseline diff yet.)
8. Document the new gate in `services/eval/README.md` (or wherever eval docs live) — what it measures, the 0.8 threshold, how to add new fixtures.
9. **No vision-extractor multi-recipe fixtures in this story.** Image-based eval is not covered today and adding it is its own follow-up (`bugs-imp-pho-7`). Multi-recipe text fixtures cover the fan-out logic; the vision extractor uses the same prompt-shape change and is graded only on real-world dogfood for now. (Open Question 2 escalated.)

### Key Files

- Create: `services/eval/fixtures/text/multi_recipe_{facing_pages,side_by_side,three_panel}.txt`
- Create: `services/eval/fixtures/expected/multi_recipe_{facing_pages,side_by_side,three_panel}.json`
- Modify: `services/eval/src/evaluators/recipe_extraction_evaluator.py`
- Modify: `services/eval/src/runner.py`
- Modify: `services/eval/src/config.py`
- Modify: manifest file driving `RecipeExtractionEvaluator.load_cases` (locate during implementation; likely `services/eval/fixtures/recipe_extraction.yaml` or similar)
- Modify: `services/eval/README.md`

---

## Story bugs-imp-pho-6: Flutter audit + BatchImportStatusWidget copy edit

As a user uploading a single photo that contains multiple recipes,
I want the existing import-review queue to surface N cards correctly and the home screen to nudge me to the Activity Hub for accurate counts,
so that my mental model ("review what came back") still works after the backend fan-out.

### Acceptance Criteria

1. **Audit (no code change expected for these):**
   - `app/lib/features/recipes/add_recipe/photo_capture_screen.dart` — submits a parser batch; lands user back on home via `context.pop(true)`. Fan-out happens after this point. **Confirm: no UI assumes 1:1 photo→ImportItem.**
   - `app/lib/features/recipes/add_recipe/batch_parser_service.dart` — polls per-`ParserJob` for OCR completion, NOT per-ImportItem. Fan-out happens downstream of this service. **Confirm unchanged.**
   - `app/lib/features/activity/import_history_screen.dart::_loadAttentionView` — calls `listImportItems(jobId)` per job; if the job has 2 ImportItems with `awaiting_review`, both render. **Confirm via manual test on real backend after stories 1+2 land.**
   - `app/lib/features/recipes/add_recipe/import_item_review_screen.dart` — renders one card per item; nothing 1:1 with photos. **Confirm unchanged.**
   - `app/lib/features/activity/widgets/import_activity_detail.dart` — extend the audit comment block at the top of the file to add `raw_data.recipe_index → annotated-not-shown: server-side traceability only` per the field-render policy. (One-line edit; not a behavior change.)
2. **BatchImportStatusWidget copy edit** (`app/lib/features/home/widgets/batch_import_status_widget.dart`):
   - Today's strings `"$succeeded recipe${succeeded == 1 ? '' : 's'} processed"` and `"Processing $processing photo${processing == 1 ? '' : 's'}..."` are misleading after fan-out (a "processed" photo can yield more than 1 recipe).
   - Change "$X recipes processed" → "$X photos processed — see Activity for details" (or equivalently terse). The processing string ("Processing X photos...") stays as-is — it's accurately about photos.
   - Tap target unchanged: still navigates to Activity / Import History.
3. **End-to-end manual test** (with backend fan-out enabled): upload a real multi-recipe cookbook photo → verify Activity / Import History shows N cards under the same job → approve each → verify N recipes appear in the user's collection, each with the source photo as hero (regression for FR87).
4. **Single-recipe regression test:** upload a single-recipe photo → verify exactly 1 review card → approve → verify 1 recipe with hero set. (Catches accidental double-fan-out.)
5. **No new Flutter code for fan-out detection.** The N-from-1 outcome is rendered by the existing list-of-items rendering. Document this in the PR description so reviewers know the audit is the deliverable, not silence.

### Key Files

- Audit (no code change unless the audit finds an issue): `app/lib/features/recipes/add_recipe/photo_capture_screen.dart`, `batch_parser_service.dart`, `import_item_review_screen.dart`
- Audit (one-line comment update): `app/lib/features/activity/widgets/import_activity_detail.dart`
- Modify: `app/lib/features/home/widgets/batch_import_status_widget.dart` (copy edit only)

---

## Dependencies

**Within epic:**
- bugs-imp-pho-1 → bugs-imp-pho-2 (fan-out consumes the new `recipes` list)
- bugs-imp-pho-1 → bugs-imp-pho-5 (eval needs the new prompt to grade)
- bugs-imp-pho-3 → bugs-imp-pho-4 (promotion needs the helper + AWSService.copy_object)
- bugs-imp-pho-2 → bugs-imp-pho-6 (audit needs N-card behavior live to verify)

**Cross-epic:**
- None against `epic-bugs-import-structured-ingredients`. Both can ship independently. The structured-ingredient editor consumes whatever ingredient shape the extractor emits, regardless of how many recipes came from one photo.

## Resolved Workshop Questions (answered 2026-04-17)

1. **Multi-recipe model failure mode:** **Ship as-is, rely on dogfood.** No merge/split UI in v1. Eval gate (`recipe_count_accuracy ≥ 0.8`) is the safety net. Revisit only if dogfood proves the failure mode is common enough to warrant the UI.
2. **Vision-extractor multi-recipe eval coverage:** **Ship + file `bugs-imp-pho-7` as follow-up.** Vision path is graded only on real-world dogfood for now. The follow-up epic will add image fixtures + a `VisionExtractionEvaluator`.
3. **Bucket cleanup:** **Punt to a future epic.** A placeholder backlog entry `epic-bugs-recipe-images-bucket-migration` is filed in sprint-status. This epic continues piggybacking on `palateful-parser-inputs-{env}` with the `recipe-photos/` prefix; bucket rename is deferred.
4. **Per-recipe field-accuracy in multi-recipe eval cases:** **Do proper N-to-N alignment NOW.** Story 5 expands to include alignment logic. **Alignment heuristic chosen (sensible default, not asked):** **order-based pairing** — `expected[i]` aligns to `actual[i]`. The extractor prompt instructs the model to emit recipes in source order; expected fixtures are authored in the same order. This is the simplest correct alignment and matches how multi-page recipe layouts read top-to-bottom, left-to-right. If fixture growth surfaces alignment failures (e.g., the model swaps order), upgrade to a name-similarity heuristic in a follow-up.

## Open Questions for the User

None. All workshop-spawned questions resolved.

## Definition of Done (Epic Level)

- A photo import → recipe always has a hero (extractor-supplied or auto-promoted source photo).
- A 2-recipe cookbook photo → 2 review cards under the same ImportJob, each independently approvable, each yielding a recipe with the same source photo as hero.
- Eval CI fails on prompt regressions: `recipe_count_accuracy_avg < 0.8` on multi-recipe fixtures, OR `field_accuracy_avg` regresses >5% from the captured baseline.
- All four extractors (`ai`, `text`, `vision`, `json_ld`) return `result.recipes: list[ExtractedRecipe]`. The `result.recipe` alias is in place with a deprecation comment, callable for one cycle.
- Worker has `AWSService.copy_object` and the `recipe_image_promotion` helper. `create_recipe_task` calls them best-effort.
- No new Terraform. No new env vars. No DB migration.
- Flutter audit complete; one copy edit on `BatchImportStatusWidget`. No other UI changes.
