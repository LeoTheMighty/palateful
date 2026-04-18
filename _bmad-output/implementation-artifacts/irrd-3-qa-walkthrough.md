# irrd-3 QA walkthrough — confidence score end-to-end

Backend-only story. No UI yet — the Flutter caret consumes these values
in irrd-4/5/6.

## 1. Flag sanity — default on, rollback is quiet

- [ ] `EXTRACTOR_EMIT_CONFIDENCE` unset → `emit_confidence()` returns
      True. The AI/text/vision prompts include the
      "emit `confidence_score` + `confidence_source`" bullet.
- [ ] `EXTRACTOR_EMIT_CONFIDENCE=false` → prompts OMIT the instruction
      AND even if the model speculatively emits the keys,
      `resolve_confidence` forces `confidence_source = "heuristic"`.

Verify with:
```
EXTRACTOR_EMIT_CONFIDENCE=false npx nx run utils:test -- -k confidence
```
(all tests pass both ways; the flag-on/flag-off fixtures already cover this.)

## 2. Extractor behavior — each path pointed at a pre-baked response

- [ ] `AIExtractor._parse_ai_response` with a dict carrying
      `confidence_score=0.91, confidence_source="model"` → returns a
      recipe with `confidence_score == 0.91, confidence_source == "model"`.
- [ ] Same method with no confidence keys → `confidence_source ==
      "heuristic"`, score in [0, 1].
- [ ] `text_extractor._parse_response` with `confidence_score=0.62 +
      model` → returns 0.62 / "model".
- [ ] `vision_extractor._parse_response` with `confidence_score=1.5` →
      falls back to heuristic (out-of-range).
- [ ] `JsonLdExtractor.extract` on a full Schema.org Recipe → score
      1.0 / source "model" (deterministic, no LLM).
- [ ] `JsonLdExtractor.extract` on a title-only Recipe → score ~0.33
      (floor protects against 0), source "model".

## 3. Persistence — parsed_recipe carries both keys

- [ ] `_serialize_recipe(recipe, extractor, session)` now emits
      `confidence_score` and `confidence_source` at the top level of
      the returned dict — verified by the existing unit tests in
      `test_unit_normalize_write_paths.py` that still pass (they use
      `SimpleNamespace` mocks; the `getattr(recipe, "confidence_score",
      None)` fallback handles them).

## 4. API shape — the two new hoisted fields

- [ ] `GET /v1/import-items/{id}` response now carries
      `confidence_score: float | null` and `confidence_source: string
      | null` at the root.
- [ ] `GET /v1/import-jobs/{job_id}/items` returns per-item summaries
      that include both fields.
- [ ] Malformed values in persisted `parsed_recipe` (legacy rows,
      out-of-range scores, bogus source literals) → API returns
      `null` for both rather than leaking garbage to the UI.

## 5. Regression — unchanged surfaces stay unchanged

- [ ] `ListImportJobs` (GET /v1/import-jobs) still returns
      job-level summaries only (no item-level hoist — follows the
      irrd-1 decision).
- [ ] Existing tests `test_get_import_item_success`,
      `test_list_import_items_with_parsed_recipe`, etc. all continue
      to pass (the new fields are additive).
- [ ] AST-lint test `test_stage_transition_enforcement.py` still
      passes — the new `confidence_*` modules do NOT contain stage log
      calls, so they're neutral to that gate.

## 6. Deferred gate awareness

- [ ] Sprint-status carries `irrd-3a-confidence-eval-calibration-gate:
      backlog` — a reminder that AC8/AC9/AC11 still owe the eval
      calibration (MAE ≤ 0.3 vs ground-truth F1) and soft regression
      gate (≤ 5% drop in `title_extraction_f1`). Kick off with a real
      OPENAI_API_KEY and ~10 min runtime when ready.

## Commands used

```
npx nx run utils:test                               # 239 passed
npx nx run api:test -- -k "TestGetImportItem or TestListImportItems"   # 32 passed
npx nx run utils:lint                               # clean
npx nx run api:lint                                 # clean
```
