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
