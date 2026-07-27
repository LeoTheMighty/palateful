---
hash: irrd3a
type: dev
created: 2026-07-27T17:09:00-06:00
title: Confidence eval metric module plus heuristic calibration and soft eval regression gates
from: _bmad-output/planning-artifacts/epic-import-row-rich-detail.md
status: in-progress
owner: /devx-loop-2026-07-27T21-15-34-312-36147
branch: feat/dev-irrd3a
---

## Goal
Land the eval-side work deferred out of irrd-3 (ACs 8, 9, 11): a confidence-calibration metric module, a heuristic-weight calibration pass gated on MAE <= 0.3, and a soft regression gate protecting title-extraction quality from the new confidence-emitting prompts. irrd-3 shipped confidence_score end-to-end with a heuristic fallback; this story proves the scores are calibrated and that the prompt changes didn't regress extraction quality. Requires real LLM API calls (~10 min runtime), which is why it was split out so irrd-4..7 weren't blocked.

## Acceptance criteria
- [ ] (irrd-3 AC8) New metric module `services/eval/metrics/confidence_calibration.py` computes `mean(abs(confidence - ground_truth_f1))` across the eval fixtures; gate wiring runs against `services/eval/fixtures/expected/*.json` (per sprint-status comment; see note on the fixture-path discrepancy below).
- [ ] (irrd-3 AC8) Baseline written to `services/eval/baselines/confidence_calibration_baseline.json` and checked into the repo.
- [ ] (irrd-3 AC9) Calibration gate: run the eval suite; if MAE > 0.3 vs fixture ground-truth F1s, retune the heuristic weights in `libraries/utils/utils/services/recipe_extractors/confidence_heuristic.py` (shift proportionally toward whichever factor correlates most) until MAE <= 0.3. Calibrated weights land in this story's PR. Initial weights: `0.4 * min(ingredient_matched_rate, 1.0) + 0.3 * (1.0 if title else 0.0) + 0.3 * min(step_count / 3.0, 1.0)`.
- [ ] (irrd-3 AC11) Soft eval regression gate: the confidence-emitting prompts must not drop `title_extraction_f1` (or the suite's equivalent title-focused metric) by more than 5% vs the prior baseline at `services/eval/baselines/extraction_baseline.json`. On regression, the gate blocks and prompts are retuned before this story completes. Baseline is updated post-merge.
- [ ] Eval runs requiring real LLM API calls (~10 min) are opt-in — invoked explicitly (documented command), not wired into the default fast CI path; deterministic gate-wiring logic (metric math, threshold comparison, baseline load/compare) is unit-tested without network.
- [ ] Both gates emit a clear pass/fail summary (metric value, baseline value, threshold) so a regression is diagnosable from the run output alone.

## Technical notes
- The epic file has no dedicated irrd-3a section — the story exists only as a sprint-status.yaml comment: "Spawned by irrd-3 dev loop 2026-04-18. AC8/AC9/AC11 (eval metric module + heuristic calibration gate + soft eval regression gate) require real LLM API calls + ~10min runtime — deferred so irrd-4..7 aren't blocked. Gate wiring runs against eval fixtures at services/eval/fixtures/expected/*.json; baseline file goes in services/eval/baselines/ when the gate lands." Goal/ACs above are synthesized from irrd-3 ACs 8, 9, 11 in the epic plus that comment.
- Fixture-path discrepancy: epic irrd-3 AC8 says fixtures live at `tests/fixtures/extractor_eval/*.json`, but the later sprint-status comment (which reflects the post-irrd-3 dev-loop reality) says `services/eval/fixtures/expected/*.json`. Treat the sprint-status path as authoritative; verify on disk before wiring and note the outcome in the Status log.
- The eval suite is "epic 13.5" per the epic; check `services/eval/` (and `docs/` eval doc) for the existing runner and where `title_extraction_f1` (or its equivalent) is computed before adding the metric module.
- Heuristic and extractors under `libraries/utils/utils/services/recipe_extractors/` (`confidence_heuristic.py`, `ai_extractor.py`, `vision_extractor.py`, `text_extractor.py`, `json_ld_extractor.py`); the `EXTRACTOR_EMIT_CONFIDENCE` flag from irrd-3 AC10 controls prompt emission if a retune requires comparing flag states.
- Budget note: full run needs `OPENAI_API_KEY` and ~10 minutes; keep fixture count fixed so MAE/baseline comparisons stay apples-to-apples.
- Original BMAD story key: irrd-3a-confidence-eval-calibration-gate.

## Status log
- 2026-07-27T17:09 — imported from BMAD (epic file + sprint-status.yaml) during BMAD→devx migration
- 2026-07-27T16:27:05-06:00 — claimed by /devx in session /devx-loop-2026-07-27T21-15-34-312-36147
- 2026-07-27T22:31:44.053Z — loop iteration 1: Landed the confidence-calibration metric module (MAE + gate + summary + retune correlations), its checked-in baseline placeholder, and 31 network-free unit tests — all 157 eval tests and ruff pass.
  - Change: Added services/eval/src/metrics/confidence_calibration.py: MAE of |confidence - ground_truth_f1|, MAE<=0.3 gate that fails closed on empty runs, per-source (model/heuristic) breakdown, worst-offender ranking, and per-signal Pearson correlation vs ground-truth F1 to drive the AC9 weight retune
  - Change: Added services/eval/baselines/confidence_calibration_baseline.json with null placeholders following the existing field_inference_baseline.json convention, mirroring the live heuristic weights and the 0.3 threshold
  - Change: Added 31 deterministic unit tests covering MAE math, input coercion from runner dict shapes, NaN/inf/bool rejection, correlation of the dominant signal, gate threshold/baseline handling, summary rendering, and drift guards binding the baseline file to confidence_heuristic.py's weight constants
  - Change: Verified the fixture-path discrepancy called out in the spec: services/eval/fixtures/expected/*.json exists (8 fixtures); the epic's tests/fixtures/extractor_eval/ path does not
  - Learning: No OPENAI_API_KEY is set and services/eval/.env.eval does not exist in this worktree, so AC9's real retune run and AC11's regression comparison cannot be executed by the loop — full acs_met is blocked on a provisioned key or a MANUAL.md handoff. All deterministic wiring can still be finished offline.
  - Learning: AC8's stated module path services/eval/metrics/confidence_calibration.py does not match the repo layout; the real package is services/eval/src/metrics/ (and confidence_heuristic.py's own docstring already points at src/metrics/). Used the real path.
  - Learning: npx nx run eval:test is broken pre-existing: pyproject addopts includes --html=... but pytest-html is not in the dev dependencies, so bare `poetry run pytest` errors out. Must run with -o addopts="" (or add pytest-html) — worth fixing before relying on CI for this service.
  - Learning: There is no title_extraction_f1 metric anywhere in the suite. scoring.py only has metadata_accuracy, which blends title + prep/cook time + servings into one number, so AC11 needs a brand-new dedicated title-focused metric — it cannot reuse an existing one.
  - Learning: services/eval/baselines/extraction_baseline.json (required by AC11) does not exist yet and must be created alongside the title metric.
  - Learning: services/eval/tests/ has 4 pre-existing ruff violations (unused imports, unsorted imports); the project's lint target only scans src/ so they don't block, but a broadened lint scope would fail.
- 2026-07-27T22:35:55.320Z — loop iteration 2: Landed AC11's title-extraction metric (token F1), its checked-in extraction baseline, the 5%-relative-drop regression gate with diagnosable summary output, and 42 network-free unit tests — eval lint clean and 199 tests pass.
  - Change: Added services/eval/src/metrics/title_extraction.py: title_extraction_f1 as bag-of-tokens precision/recall/F1 per fixture (multiset-bounded overlap, case/punctuation/whitespace insensitive, unicode-safe), averaged across fixtures, with exact-match rate and worst-offender ranking
  - Change: Added check_title_regression_gate: relative >5%-drop-vs-baseline gate that fails closed on an empty run, passes with baseline_missing on the null placeholder, and treats a 0.0 baseline as unregressable; plus format_title_regression_summary emitting value/baseline/threshold/min-allowed/actual-drop on the headline lines
  - Change: Added services/eval/baselines/extraction_baseline.json with null placeholders per the sibling-baseline convention, carrying the title section, the fixture_runner aggregate means for diagnostic context, and the 0.05 threshold
  - Change: Added 42 deterministic unit tests covering token-F1 math, input coercion from four call shapes, skip-vs-zero semantics, all gate branches and boundary conditions, baseline payload parsing, summary rendering, and drift guards binding the baseline file to the module constant
  - Learning: Multi-recipe fixtures (multi_recipe_*.json) use the {"recipes": [...]} envelope rather than a bare recipe dict, so any fixture-level metric must unwrap both shapes; all 8 checked-in fixtures do have a ground-truth title, which the new sweep test now pins.
  - Learning: ruff's eval:lint target only scans services/eval/src/ — the new tests directory is unlinted, consistent with iteration 1's note about 4 pre-existing violations there. An f-string-without-placeholders (F541) in the summary formatter was the only lint hit and is easy to reintroduce when building these multi-line report blocks.
  - Learning: The confidence-calibration gate and this one now share a shape (compute -> check -> format, fail-closed on empty), which makes the natural next unit a single opt-in entry point that runs both against fixture_runner output and prints both summaries under one documented command.
