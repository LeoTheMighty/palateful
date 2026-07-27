# Palateful AI/OCR Evaluation Suite

Ad-hoc evaluation suite for testing Palateful's AI and OCR features against configurable test datasets with reproducible metrics.

## Quick Start

```bash
# Install dependencies
npx nx run eval:install

# Copy and configure environment
cp .env.eval.example .env.eval
# Edit .env.eval with your API keys

# Run all evaluations
npx nx run eval:run

# Run specific suite
npx nx run eval:run-ocr
npx nx run eval:run-recipe
npx nx run eval:run-matching

# Generate HTML report
npx nx run eval:report -- --format html --open
```

## Features

- **Direct Production Code Testing**: Imports actual prompts and functions from `utils` library
- **Easy Q/A Pairs**: YAML-based test cases with expected outputs
- **Configurable Metrics**: Character accuracy, BLEU scores, field accuracy, and more
- **Mock/Cache Mode**: Fast iteration without GPU or API costs
- **Multiple Reporters**: Console, JSON, and HTML dashboard outputs

## Evaluation Suites

### OCR (`npx nx run eval:run-ocr`)

Tests image-to-text extraction using the HunyuanOCR model.

| Metric | Description |
|--------|-------------|
| `character_accuracy` | Percentage of characters correctly extracted |
| `word_accuracy` | Percentage of words matching expected output |
| `levenshtein_distance` | Edit distance from expected text |
| `bleu_score` | N-gram overlap score |

### Recipe Extraction (`npx nx run eval:run-recipe`)

Tests HTML-to-recipe conversion using JSON-LD and AI extractors.

| Metric | Description |
|--------|-------------|
| `field_accuracy` | Percentage of recipe fields correctly extracted |
| `recipe_count_accuracy` | Fraction of cases where extractor returned the right *number* of recipes (FR88 multi-recipe fan-out). 1.0 per exact match / 0.0 otherwise. Gated at 0.80 on `multi_recipe`-tagged cases. |
| `ingredient_count_accuracy` | Accuracy of ingredient list extraction |
| `instruction_similarity` | Text similarity of instructions |
| `cost_cents` | AI API cost tracking |
| `latency_ms` | Response time |

Multi-recipe expected files use `{"recipes": [recipe_a, recipe_b, ...]}`. Single-recipe expected files keep the legacy bare-recipe shape; the evaluator wraps both transparently, pair-wise aligns expected-vs-actual in source order, and grades accordingly.

### Ingredient Matching (`npx nx run eval:run-matching`)

Tests ingredient text matching to database ingredients.

| Metric | Description |
|--------|-------------|
| `exact_match_rate` | Percentage of exact ID matches |
| `fuzzy_match_rate` | Percentage of fuzzy matches above threshold |
| `false_positive_rate` | Incorrect match rate |
| `confidence_calibration` | Confidence score accuracy |

## Configuration

### Environment Variables (`.env.eval`)

```bash
# API Keys
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql://...

# Evaluation modes
EVAL_OCR_MODE=local        # local | batch | mock
EVAL_MOCK_AI=false         # Use cached responses
EVAL_CACHE_RESPONSES=true  # Save responses for mock mode
EVAL_PARALLEL_WORKERS=4    # Parallel execution
```

### Metrics Configuration (`eval.config.yaml`)

```yaml
thresholds:
  ocr_character_accuracy: 0.95  # Pass/fail threshold
  recipe_field_accuracy: 0.90
  ingredient_match_rate: 0.85
  field_inference_accuracy_min: 0.60  # efi-8 soft gate
  hallucination_rate_max: 0.15        # efi-8 soft gate
```

### Field inference metrics (efi-8, soft gate)

Two post-ship calibration metrics for the
`EXTRACTOR_INFER_MISSING_FIELDS` pipeline:

- `field_inference_accuracy` — for every (fixture × inferable-field)
  pair where the extractor marked the field in `inferred_fields` AND
  ground truth has a value, score how close the inferred value landed
  to truth. Numeric fields use ±20% tolerance (servings also has a ±1
  floor). Enum-ish fields (cuisine, category, vibes) require exact
  case-insensitive match. Description uses Levenshtein similarity on
  the first 200 chars (pass ≥ 0.6, raw ratio otherwise).
- `hallucination_rate` — anti-metric. For every (fixture ×
  inferable-field) pair where GT has a value AND the extractor marked
  it as inferred, count a hallucination (the model guessed when the
  source had the answer). Lower is better. Rate =
  `hallucinations / extractable_pairs`.

Both metrics are **soft-gate in v1** — reported in the results payload,
never CI-blocking. Baseline at `baselines/field_inference_baseline.json`.
Gate tightening is a follow-up story once real traffic accumulates in
`error_logs(service="audit", error_type="InferredFieldCorrected")` and
we can tune from correction data.

### Confidence gates (irrd-3a, opt-in)

Two gates over the fixture set in `fixtures/`, wired together in
`src/confidence_gates.py`:

| Gate | Metric | Rule | Enforcement |
|---|---|---|---|
| Confidence calibration | `mean(abs(confidence_score - overall_f1))` | MAE ≤ 0.30 | hard |
| Title regression | `title_extraction_f1` (token-level F1 vs the ground-truth title) | no more than a 5% relative drop vs `baselines/extraction_baseline.json` | soft (blocking for irrd-3a) |

Both run the **real** extractors, so the command needs `OPENAI_API_KEY`
and takes roughly ten minutes over the checked-in fixtures. It is
deliberately **opt-in** — invoked explicitly, never part of the fast CI
path. The deterministic half (metric math, threshold comparison,
baseline load/compare, report rendering) is unit-tested without network
in `tests/test_confidence_calibration.py`,
`tests/test_title_extraction.py`, and `tests/test_confidence_gates.py`.

```bash
# Run both gates against the current baselines. Exit 1 if either fails.
npx nx run eval:confidence-gate

# Save the full report (per-fixture errors, correlations, worst offenders).
npx nx run eval:confidence-gate -- --output results/confidence_gates.json

# Capture the PRE-confidence title baseline, then compare with the flag on.
EXTRACTOR_EMIT_CONFIDENCE=false npx nx run eval:confidence-gate -- --write-baseline
EXTRACTOR_EMIT_CONFIDENCE=true  npx nx run eval:confidence-gate
```

### Pay for the run once: `--save-run` / `--from-run`

```bash
# Pay the ten minutes once, keeping the raw payloads.
npx nx run eval:confidence-gate -- --save-run /tmp/irrd3a-run.json

# ...edit the weights in confidence_heuristic.py, then re-gate for free.
npx nx run eval:confidence-gate -- --from-run /tmp/irrd3a-run.json
```

`--from-run` needs no `OPENAI_API_KEY` and no network. It recomputes every
**heuristic-sourced** confidence from its saved extraction under the
weights currently in `confidence_heuristic.py` — identical to what a fresh
run would produce, because the heuristic is a pure function of the
extracted recipe and extraction itself doesn't depend on the weights.
**Model-sourced** scores are replayed verbatim; they are exactly the
samples a retune cannot move, and the replay line reports how many of each
there were. Add `--as-recorded` to skip the recompute and re-read the
original run's verdict unchanged.

So AC9's "retune until MAE ≤ 0.3" loop costs one API run, not one per
candidate: propose (the report computes it), edit, `--from-run`, confirm.
The saved run is a debugging record, not a baseline — write it somewhere
untracked.

`--write-baseline` rewrites both `baselines/confidence_calibration_baseline.json`
and `baselines/extraction_baseline.json` from the run (stamping the
timestamp and commit, and mirroring the live heuristic weights), merging
into the existing files so their explanatory comments survive. Review the
diff and commit the baselines together with the change that produced them.

A run that measured nothing — no key, no network, every fixture errored —
is **refused**: the write would stamp a real timestamp, commit, and
`_emit_confidence` onto all-null numbers, producing a file that reads as a
captured baseline and only reveals itself as empty on the *next* run.
Fix the run and re-capture; `--force-baseline` records it anyway if you
really mean to.

### Is the title gate actually answering AC11?

The title gate compares one number against another; it cannot tell on its
own whether that comparison is the before/after AC11 asked for. So the
run records `_emit_confidence` in each baseline it writes, and every
report classifies the pairing:

| Baseline | Run | Verdict |
|---|---|---|
| flag off | flag on | valid AC11 before/after |
| same state on both sides | | drift check — a pass proves nothing about the confidence prompts |
| flag on | flag off | inverted — re-capture the baseline |
| either side unrecorded | | cannot be shown to be a before/after |

Anything but the first prints a `WARNING:` line under the title block.
This matters because the failure mode is silent: capture the baseline
with `EXTRACTOR_EMIT_CONFIDENCE` left on, and every later comparison is
confidence-on vs confidence-on, which passes without testing anything.
The post-merge baseline refresh is legitimately a confidence-on run, so
the classification is reported rather than enforced.

On failure the report names the next step.

A **calibration failure** does not just point at a signal — it computes
the retune. Because the heuristic is a pure function of three signals the
run already recorded, candidate weight vectors are replayed offline
against those samples, so the report prints the smallest shift that
reaches MAE ≤ 0.3, the MAE it projects, and the literal constants to
paste into
`libraries/utils/utils/services/recipe_extractors/confidence_heuristic.py`.
Apply them and re-run to confirm — no second API bill is needed to *find*
the weights, only to verify them.

Two cases the report calls out rather than papering over:

- **Every score came from the model.** No weight vector can move the MAE;
  the fix is the prompts, not the heuristic. Reported as "not applicable"
  with the dominant signal kept as evidence.
- **No vector reaches the threshold.** The best-effort weights are still
  printed with `still fails`, along with how many samples were
  model-sourced and therefore immovable.

A **title failure** points at the confidence-emitting prompts
(`EXTRACTOR_EMIT_CONFIDENCE`).

## Adding Test Cases

### Manual Method

1. Add input files to the appropriate `datasets/` subdirectory
2. Add expected output files to `expected/` subdirectory
3. Update the manifest file

### Using CLI

```bash
# Add OCR test case
npx nx run eval:add-case -- --suite ocr --input path/to/image.jpg --expected path/to/expected.md --tags handwritten,recipe

# Add recipe extraction test case
npx nx run eval:add-case -- --suite recipe_extraction --input path/to/page.html --expected path/to/expected.json
```

## Dataset Structure

```
datasets/
├── ocr/
│   ├── manifest.yaml        # Test case index
│   ├── images/              # Input images
│   ├── expected/            # Expected markdown outputs
│   └── cache/               # Cached OCR responses
├── recipe_extraction/
│   ├── manifest.yaml
│   ├── html/                # Input HTML files
│   ├── expected/            # Expected JSON outputs
│   └── cache/               # Cached extraction responses
└── ingredient_matching/
    └── cases.yaml           # Input → expected match pairs
```

## Running Evaluations

```bash
# Run all suites
npx nx run eval:run

# Run with tag filter
npx nx run eval:run -- --suite ocr --tags handwritten --verbose

# Compare with baseline
npx nx run eval:run -- --compare results/baseline.json

# Save to specific output
npx nx run eval:run -- --output results/my_run.json
```

## Generating Reports

```bash
# HTML dashboard (opens in browser)
npx nx run eval:report -- --format html --open

# JSON output
npx nx run eval:report -- --format json --output results/report.json

# Console output
npx nx run eval:report -- --format console
```

## Mock Mode

For fast iteration without GPU or API costs:

```bash
# First run: Cache responses
EVAL_CACHE_RESPONSES=true npx nx run eval:run

# Subsequent runs: Use cached responses
EVAL_MOCK_AI=true npx nx run eval:run
```

Cache files are stored in `datasets/*/cache/` and keyed by input content hash.

## CI Integration

Exit codes:
- `0`: All suites passed thresholds
- `1`: One or more suites failed thresholds

```yaml
# Example GitHub Actions
- name: Run AI Evaluations
  run: npx nx run eval:run
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
    DATABASE_URL: ${{ secrets.DATABASE_URL }}
```

## Development

```bash
# Lint
npx nx run eval:lint

# Run tests
npx nx run eval:test

# Generate lock file
npx nx run eval:lock
```
