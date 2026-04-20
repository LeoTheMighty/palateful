# efi-8 — QA walkthrough

Eval-only story. No backend runtime, no UI. Soft-gate metrics — reported
on every eval run, never CI-blocking in v1.

## Local checks

```bash
cd services/eval
poetry run pytest tests/test_field_inference_metrics.py --no-cov
poetry run ruff check src/metrics/field_inference_accuracy.py \
                     src/metrics/hallucination_rate.py \
                     tests/test_field_inference_metrics.py
```

Expected: 19 tests green, lint clean.

## Integration sanity

```bash
# Confirm the eval.config.yaml parses and the thresholds land:
cd services/eval
poetry run python - <<'PY'
import yaml
cfg = yaml.safe_load(open("eval.config.yaml"))
assert "field_inference" in cfg["metrics"]
assert "field_inference_accuracy_min" in cfg["thresholds"]
assert "hallucination_rate_max" in cfg["thresholds"]
print("eval.config.yaml parses and exposes the new section + thresholds")
PY
```

Expected: prints the success line.

## Baseline file

`services/eval/baselines/field_inference_baseline.json` ships with
null sentinels — every `score`, `rate`, and `overall` is `null` until
the first real eval run against an LLM populates them. Update path:

1. Run `npx nx run eval:run-recipe` with `EXTRACTOR_INFER_MISSING_FIELDS=true`.
2. Inspect `services/eval/results/latest.json` for the new
   `field_inference_accuracy` + `hallucination_rate` keys.
3. Copy per-field and overall numbers into the baseline JSON, set
   `_generated_at` and `_generated_commit` to the current state, and
   land that delta in the same PR as the initial numbers.

Post-baseline, gate tightening is a follow-up story that waits on real
traffic in `error_logs(service="audit", error_type="InferredFieldCorrected")`.
