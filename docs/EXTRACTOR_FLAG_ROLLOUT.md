# Extractor Flag Rollout Runbook — epic-extractor-richer-ingredients

Owned by story **eri-6**. Defines the production flip order, staging
verification, observability, and rollback drill for the three
epic-ERI flags.

## Flags in play

| env var | default | purpose |
|---|---|---|
| `EXTRACTOR_SOFTEN_UNIT_RULE` | `"true"` | Turn on the softened unit rule (eri-1) — LLM may emit `clove`, `stalk`, etc. |
| `EXTRACTOR_JSON_LD_INGREDIENT_PARSE` | `"true"` | Turn on the JSON-LD parse-pass (eri-3a) — text-only JSON-LD ingredients get structured via gpt-4o-mini. |
| `EXTRACTOR_EMIT_CANONICAL_UNITS` | `"true"` | Legacy riip-3 flag — retired once SOFTEN is stable in prod. |

Precedence (call-time resolved): `SOFTEN → CANONICAL → freeform`.

## 4-step production flip

**Pre-flight on each step:** run the post-flip verification (below) for
~30 minutes before advancing to the next step.

### Step 1 — Migrations land

```bash
# Confirm heads are the two eri migrations.
cd services/migrator && poetry run alembic heads
# Expect: erifraliases01 (head)

# Apply.
DATABASE_URL=<prod> poetry run alembic upgrade head
```

Expect 15 rows inserted into `units` (eri-4a) + 16 alias rows +
2 alias row deletions (eri-4b).

### Step 2 — `EXTRACTOR_SOFTEN_UNIT_RULE=true` on

In ECS task-def env vars for the api / worker / parser services:

```
EXTRACTOR_SOFTEN_UNIT_RULE=true
EXTRACTOR_JSON_LD_INGREDIENT_PARSE=false   # still off
EXTRACTOR_EMIT_CANONICAL_UNITS=true
```

Redeploy. First import with softened rule takes effect on the next
`extract_recipe_task` invocation.

**Verify:** any photo-import with `"1 clove garlic, minced"` produces
`{unit: "clove", name: "garlic", notes: "minced"}` (was: `{name:
"[clove of garlic]"}` pre-flip). Check via `services/api/scripts/audit_errors.py --drill api:` and manual inspection of the Review
Import screen.

### Step 3 — `EXTRACTOR_JSON_LD_INGREDIENT_PARSE=true` on

```
EXTRACTOR_SOFTEN_UNIT_RULE=true
EXTRACTOR_JSON_LD_INGREDIENT_PARSE=true   # NEW
EXTRACTOR_EMIT_CANONICAL_UNITS=true
```

Redeploy. Parse pass fires on the next URL import whose JSON-LD has
text-only ingredients.

**Verify:**
1. Import a URL with Schema.org JSON-LD (NYT Cooking, Serious Eats)
   whose ingredients are plain strings. Review Import shows fully
   structured rows.
2. `services/api/scripts/audit_errors.py --window 1h` — expect
   `IngredientFieldCoverage` rows with `source="json_ld_parse_pass"`.
3. No new `IngredientParseFailure` rows (a few transient failures
   over 24-48h are acceptable — investigate if >10/hour).
4. OpenAI cost delta is ~$0.0001 per URL import. Check the
   `ai_cost_cents` trend on new imports.

### Step 4 — retire `EXTRACTOR_EMIT_CANONICAL_UNITS`

After **7 days of clean eri-5 metric data** (overall ≥ 0.85 + 0
`IngredientParseFailure` in last 48h + no new `UnitAliasMiss` tied to
the 15 eri-4a seeds), flip the legacy riip-3 flag off:

```
EXTRACTOR_SOFTEN_UNIT_RULE=true
EXTRACTOR_JSON_LD_INGREDIENT_PARSE=true
EXTRACTOR_EMIT_CANONICAL_UNITS=false   # retired
```

Softened rule takes precedence regardless of the canonical flag, but
flipping canonical off cleans up the fallback chain. Once confirmed
stable (24 h), open a PR to remove `_CANONICAL_RULE` + the canonical
flag entirely (`emit_canonical_units()`), leaving only SOFTEN as the
live path.

## Observability

- **`IngredientFieldCoverage`** (`service="audit"`) — once per
  successful extraction. Metadata: `{total, qty_present, unit_present,
  name_present, notes_present, source, url_host}`.
  `source` ∈ {`json_ld`, `json_ld_parse_pass`, `ai_extractor`}.

  ```bash
  python services/api/scripts/audit_errors.py \
      --drill audit:IngredientFieldCoverage --window 24h --format json
  ```

- **`IngredientParseFailure`** (`service="audit"`) — one per failed
  batch. Metadata: `{error_class, batch_size, url_sample}`. Expected
  volume: near-zero. Alert on >10/hour.

  ```bash
  python services/api/scripts/audit_errors.py \
      --drill audit:IngredientParseFailure --window 1h
  ```

- **`IngredientParsePathological`** (`service="audit"`) — one per
  import that exceeded 200 ingredients. Metadata: `{total, max_total,
  overflow, url_sample}`. Expected volume: effectively zero — this
  signals a spice-catalog-sized URL, not a real recipe.

- **`UnitAliasMiss`** (`service="audit"`) — riip-1 legacy; watch for
  new misses tied to the eri-softened vocabulary. If `stalk`, `bunch`,
  etc. start appearing here, the migration hasn't run or the cache
  hasn't reloaded.

## Rollback drill (verified in staging)

### Scenario: parse pass is misbehaving — disable without redeploy

1. ECS task-def env update:
   ```
   EXTRACTOR_JSON_LD_INGREDIENT_PARSE=false
   ```
2. Redeploy (rolling — no downtime).
3. Next import uses JSON-LD text-only fallback — Review Import shows
   unstructured rows (same as pre-ERI). User can edit manually. No
   failures, no data loss.

### Scenario: softened prompt regressed — full rollback to riip-3

1. ECS task-def env update:
   ```
   EXTRACTOR_SOFTEN_UNIT_RULE=false
   EXTRACTOR_JSON_LD_INGREDIENT_PARSE=false
   EXTRACTOR_EMIT_CANONICAL_UNITS=true
   ```
2. Redeploy. Prompt reverts to the 19-token canonical rule.
3. Migrations stay applied — the 15 freeform rows + 16 aliases are
   harmless when the prompt doesn't emit freeform words. Leave them.

### Scenario: migrations must be rolled back

```bash
cd services/migrator && poetry run alembic downgrade erifrunits01
# (drops the 16 freeform aliases, restores piece/pieces→each)
cd services/migrator && poetry run alembic downgrade schdrem001
# (drops the 15 freeform units — ERRORS OUT if aliases still reference them)
```

Follow the error message's instruction: downgrade the alias migration
first. This is a deliberate guard in the downgrade — we never silently
orphan FK deps.

## Staging verification (required before step 2 in prod)

Run against a non-prod ECS task def with the staging DB:

1. Apply migrations to staging DB.
2. Flip `EXTRACTOR_SOFTEN_UNIT_RULE=true`, leave parse-pass off.
3. Import a recipe photo containing "1 clove garlic, minced" — confirm
   structured output.
4. Flip `EXTRACTOR_JSON_LD_INGREDIENT_PARSE=true`.
5. Import a URL with Schema.org JSON-LD (text-only ingredients) —
   confirm `source="json_ld_parse_pass"` audit row.
6. Rehearse the two rollback scenarios above (flip flags off, confirm
   no user-visible error).

Sign-off log (append as you go):

```
[ ] Step 1 — migrations applied to staging      (operator/date)
[ ] Step 2 — soften flag on staging verified   (operator/date)
[ ] Step 3 — parse-pass on staging verified    (operator/date)
[ ] Rollback drills rehearsed                  (operator/date)
[ ] Production step 1 — migrations             (operator/date)
[ ] Production step 2 — soften on              (operator/date)
[ ] Production step 3 — parse-pass on          (operator/date)
[ ] Production step 4 — retire canonical flag  (after 7 days clean)
```

## Related

- Epic: [`_bmad-output/planning-artifacts/epic-extractor-richer-ingredients.md`](../_bmad-output/planning-artifacts/epic-extractor-richer-ingredients.md)
- Metric + baseline: `services/eval/baselines/ingredient_field_completeness_baseline.json`
- Ops script: `services/api/scripts/audit_errors.py`
