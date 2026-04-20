# efi-1 — QA walkthrough

Pure-module story — no DB, no endpoints, no UI. Verification is done by
running the four new test modules and spot-reading the generated
prompt text.

## Local checks

```bash
# Unit tests — all four new modules.
cd libraries/utils && poetry run pytest \
    test/test_inference_prompt.py \
    test/test_inference_guardrails.py \
    test/test_confidence_inference_penalty.py \
    test/test_inference_log_enforcement.py

# Lint.
npx nx run utils:lint

# Full utils suite (no regressions expected).
cd libraries/utils && poetry run pytest test/
```

Expected: 66 new tests green, 339 total utils tests green, lint clean.

## Sanity — read the generated prompt

```bash
cd libraries/utils && EXTRACTOR_INFER_MISSING_FIELDS=true poetry run python -c \
    "from utils.services.recipe_extractors.inference_prompt import inference_rule; print(inference_rule())"
```

Expected: a paragraph listing all 9 inferable fields by schema name,
forbidding inference of `name` / `ingredients` / `steps`, mandating
`inferred_fields` as an always-present array (even when empty), and
including a worked `cook_time_minutes: 27` example.

```bash
EXTRACTOR_INFER_MISSING_FIELDS=false poetry run python -c \
    "from utils.services.recipe_extractors.inference_prompt import inference_rule; print(repr(inference_rule()))"
```

Expected: `''` (empty string — flag off, rule suppressed).

## Sanity — flag values

```bash
cd libraries/utils && for v in true false 0 off No; do
    EXTRACTOR_INFER_MISSING_FIELDS="$v" poetry run python -c \
        "from utils.services.recipe_extractors.inference_prompt import infer_missing_fields; print('$v', '->', infer_missing_fields())"
done
```

Expected:
- `true -> True`
- `false -> False`
- `0 -> False`
- `off -> False`
- `No -> False`

## Regression checks

- `apply_inference_penalty(0.72, 0) == 0.72` — zero inferred fields is a no-op.
- `apply_inference_penalty(0.72, 5) == 0.47` — five fields hit the 0.25 cap.
- `apply_inference_penalty(0.72, 9) == 0.47` — six+ inferred fields stay capped.
- `apply_inference_penalty(float("nan"), 2) == 0.0` — NaN coerces to 0 before the clamp, downstream JSON / Postgres can't see non-finite.

## Not verified in this story

- End-to-end path from extractor → task → DB — that lands in efi-3.
- The AST-lint test fails loudly when a violating literal appears — verified by dry-running the scan; no offenders today.
- The `ExtractedRecipe.inferred_fields` dataclass field — efi-2 adds it. Guardrails currently use getattr/setattr to round-trip; tests stamp the value with `setattr(recipe, "inferred_fields", [...])`.
