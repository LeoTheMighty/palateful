---
hash: bugsimppho7
type: dev
created: 2026-07-27T17:06:00-06:00
title: Vision-extraction eval suite with image fixtures and recipe-count gate
from: _bmad-output/planning-artifacts/epic-bugs-import-photo-pipeline.md
status: in-progress
owner: /devx-loop-2026-07-27T21-15-34-312-36147
branch: feat/dev-bugsimppho7
---

## Goal
Stories bugs-imp-pho-1..6 shipped multi-recipe fan-out and eval gating, but only for the text path — the vision extractor (`extract_recipe_from_image`, gpt-4o-mini) ships with zero eval coverage and is graded only on dogfood. This story (spawned from the epic's resolved Workshop Question 2) adds image-based eval: image fixtures, a VisionExtractionEvaluator, and the same ≥0.8 `recipe_count_accuracy` gate the text suite already enforces.

## Acceptance criteria
- [ ] Image fixture pairs exist under `services/eval/fixtures/images/` with expected JSON under `services/eval/fixtures/expected/`, covering at least: single-recipe photo(s) and multi-recipe photo(s) (e.g., cookbook facing pages / side-by-side cards), with multi-recipe cases tagged `multi_recipe` in the manifest.
- [ ] A `VisionExtractionEvaluator` (in `services/eval/src/evaluators/`) runs the vision extractor (`extract_recipe_from_image`) against the image fixtures and computes the same metrics as the text suite, including `recipe_count_accuracy` and per-recipe field metrics via the existing order-based alignment.
- [ ] The vision suite is graded at the same bar as text: `recipe_count_accuracy_avg >= 0.8` on multi-recipe-tagged cases, enforced via `services/eval/src/runner.py::_check_thresholds`.
- [ ] Existing text-suite fixtures, thresholds, and results are unchanged; a baseline vision-suite run is captured (PR description) for future `field_accuracy` regression comparison.
- [ ] Eval docs (`services/eval/fixtures/README.md` or the eval README) document the new suite: what it measures, the 0.8 threshold, how to add image fixtures.

## Technical notes
- Story has no dedicated BMAD story file; ACs above are derived from the epic (`epic-bugs-import-photo-pipeline.md`: Story Map row bugs-imp-pho-7, story-5 AC 9, Resolved Workshop Question 2) and the sprint-status.yaml comment: "image fixtures + VisionExtractionEvaluator. Vision path ships under text-only eval coverage; this story adds image-based eval graded at the same ≥0.8 recipe_count_accuracy bar."
- Prerequisites are all on main: `recipe_count_accuracy` threshold exists in `services/eval/src/config.py` (default 0.80, lines 22/135) and the gate in `services/eval/src/runner.py` (~line 274). Reuse — don't duplicate — the metric/alignment logic in `services/eval/src/evaluators/recipe_extraction_evaluator.py` (order-based pairing, alignment-fallback log line).
- Existing evaluator scaffolding to mirror: `services/eval/src/evaluators/` already has `base.py`, `recipe_extraction_evaluator.py`, `ocr_evaluator.py`; `services/eval/fixtures/images/` directory already exists.
- Extractor entry point: `libraries/utils/utils/services/recipe_extractors/vision_extractor.py` / `extract_recipe_from_image` — post pho-1 it returns `ExtractionResult.recipes: list[ExtractedRecipe]` (the `recipe` field is a deprecated alias; use `recipes`).
- Vision calls cost real OpenAI money per run — follow whatever live-call/caching convention the existing suites use in `services/eval/src/runner.py` / `fixture_runner.py`; keep the fixture set small.
- Epic dependency note: sprint-status snapshot listed pho-1..6 as backlog, but they are done on main — this story has no remaining in-repo blockers.
- Original BMAD story key: bugs-imp-pho-7-vision-extraction-eval-suite.

## Status log
- 2026-07-27T17:06 — imported from BMAD (epic file + sprint-status.yaml) during BMAD→devx migration
- 2026-07-27T17:06 — verified prerequisites on main: recipe_count_accuracy gate (config.py:22, runner.py:274) and fixtures/images/ dir already exist; stories pho-1..6 confirmed done despite stale backlog markers in sprint-status.yaml
- 2026-07-27T15:15:34-06:00 — claimed by /devx in session /devx-loop-2026-07-27T21-15-34-312-36147
- 2026-07-27T21:23:03.506Z — loop iteration 1: Added the vision-eval image fixture layer: a reproducible PNG generator, five committed image fixtures (2 single + 3 multi-recipe), the tagged vision_extraction manifest, 24 dataset-consistency tests, and fixture docs.
  - Change: Added services/eval/scripts/generate_image_fixtures.py, which renders the existing text fixtures into page-like PNGs (page / facing_pages / cards_row / panels_row layouts) so image fixtures share ground truth with their text twins and are regenerable from source
  - Change: Generated and committed 5 image fixtures under services/eval/fixtures/images/: banana_bread + simple_pasta (single-recipe), multi_recipe_facing_pages + multi_recipe_side_by_side (N=2), multi_recipe_three_panel (N=3), all reusing the existing fixtures/expected/*.json ground truth
  - Change: Added datasets/vision_extraction/manifest.yaml wiring the 5 cases with multi_recipe / single_recipe / image tags, ready for the recipe_count_accuracy gate
  - Change: Added a hard glyph-coverage guard to the generator that aborts rather than rendering tofu boxes, after the bundled Pillow font silently corrupted 'jalapeño' into 'jalape□o'
  - Change: Added tests/test_vision_fixtures.py (24 tests, no live API calls) asserting manifest/filesystem consistency, image readability and size, no orphan PNGs, tag-vs-expected-recipe-count agreement, regenerability of every case, and the glyph guard's behaviour
  - Change: Documented the image-fixture convention, layout table, font guard, cost caveat, and add-a-fixture procedure in services/eval/fixtures/README.md
  - Learning: Pillow's bundled default font (Aileron) lacks 'ñ', which the three_panel and other fixtures contain ('jalapeño'). Rendering with it silently produces tofu boxes that would desync the image from its expected JSON and read as a model accuracy miss. The generator now resolves a system face from FONT_CANDIDATES and hard-fails on missing glyphs; regenerating fixtures on a machine without Arial/DejaVu/Liberation will error rather than corrupt.
  - Learning: The eval service had no poetry venv in this worktree — `poetry install` is required first (pulls torch/transformers, takes several minutes).
  - Learning: `poetry run pytest` fails out of the box locally: pyproject addopts includes `--html=...` but pytest-html is not in the dev dependencies. Run with `-o addopts=""` locally. This is pre-existing, not introduced here.
  - Learning: Four pre-existing ruff violations live in tests/ (test_fixture_runner.py F401 x2, test_recipe_extraction_timers.py and test_scoring.py I001). CI does not catch them because the nx `lint` target only checks `src/`.
  - Learning: The recipe_extraction manifest uses a `text:` key, but RecipeExtractionEvaluator.load_cases only reads `case_data.get("html", ...)` — so those three multi-recipe text cases resolve to a non-existent datasets/recipe_extraction/html/*.html and would error. Worth confirming before wiring the vision evaluator, since copying that load_cases shape would inherit the bug.
  - Learning: Loading the generator script in tests needs the module registered in sys.modules *before* exec_module — dataclasses resolves annotations via sys.modules[cls.__module__] and raises AttributeError otherwise.
