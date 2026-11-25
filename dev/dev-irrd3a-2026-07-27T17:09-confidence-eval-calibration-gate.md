---
hash: irrd3a
type: dev
created: 2026-07-27T17:09:00-06:00
title: Confidence eval metric module plus heuristic calibration and soft eval regression gates
from: _bmad-output/planning-artifacts/epic-import-row-rich-detail.md
status: blocked
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
- 2026-07-27T23:20:12.046Z — [FAIL] loop abandoned irrd3a: iteration budget exhausted (8 iterations without acs_met); worktree preserved at .worktrees/dev-irrd3a
