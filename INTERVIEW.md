# INTERVIEW — Questions for you

## (imported from BUGS.md) RDS Performance Insights — keep paying or switch off? Decide before 2026-10-08

Performance Insights on `palateful-db-prod` exits its free tier around 2026-10-08 (day 170).

**Options:**
- Keep it (~$2/mo, stays under NFR29's $50 cap) — retains the query-level perf history that `analyze_latency.py` baselines complement.
- Toggle `performance_insights_enabled=false` in `terraform/modules/rds/main.tf` before the date — zero cost, lose PI dashboards.

**Recommendation:** keep it; $2/mo is well inside the cost cap and the perf epics lean on query-level visibility.

- [ ] Decide keep vs disable before 2026-10-08.


## (from /devx-init) Stack: which language for the first dev story?

Empty repo — no stack file detected. The first slice's spec needs a primary
language so language_runners + lint/test commands can be wired up.

**Options:** TypeScript / Python / Rust / Go / Flutter / other.
**Recommendation:** TypeScript (default for the first dev story unless you
say otherwise — broadest tooling, fastest iteration).

- [ ] Pick a primary language for the first dev story.

## (from /devx-init) CI: when should GitHub Actions run?

`.github/workflows/devx-ci.yml` was just scaffolded. It needs trigger filters.

**Options:**
- on PR + push to main (default, runs every change before merge)
- on push only (cheaper; PRs go through review without CI)
- on schedule + on PR (nightly + per-PR)

**Recommendation:** on PR + push to main.

- [ ] Confirm CI trigger filters.

## (from /devx-init) Browser harness — Playwright, Cypress, or none?

If the first slice has any UI, this gates Layer-1 (scripted) browser tests.
If it's pure CLI / API, pick none — devx will skip browser harness setup.

**Options:** Playwright (default) / Cypress / none.
**Recommendation:** Playwright (covers Chromium + WebKit + Firefox in one run).

- [ ] Pick a browser harness (or `none`).

## (from devx init) Init halt bypassed non-interactively: uncommitted-changes <!-- devx:init-defaults:halt-uncommitted-changes -->

Non-interactive scaffold took a default: proceeded anyway (non-interactive runs can't answer the interactive menu).
Why it needs you: uncommitted changes detected — choose how to handle them before init proceeds.

- [ ] Confirm or replace this default.

## (from devx init) First slice — what's the smallest demo that matters? <!-- devx:init-defaults:n2 -->

Non-interactive scaffold took a default: placeholder ("Scaffolded non-interactively — pick the smallest demo that matters (see INTERVIEW.md).").
Why it needs you: the first slice is a product decision no repo probe can make.

- [ ] Confirm or replace this default.

## (from devx init) Who's it for? <!-- devx:init-defaults:n3 -->

Non-interactive scaffold took a default: "you propose" — devx drafted the persona panel under focus-group/.
Why it needs you: audience is a product decision; review the proposed panel.

- [ ] Confirm or replace this default.

## (from devx init) Project shape — empty-dream, bootstrapped-rewriting, mature-refactor-and-add, mature-yolo-rewrites, or production-careful? <!-- devx:init-defaults:n6 -->

Non-interactive scaffold took a default: mature-refactor-and-add.
Why it needs you: repo state was ambiguous (no tests+tags signal); confirm the project shape.

- [ ] Confirm or replace this default.

## (from devx init) Real users today, or pre-launch? <!-- devx:init-defaults:n7 -->

Non-interactive scaffold took a default: YOLO.
Why it needs you: no real-user signal detected; YOLO is the pre-launch default — bump the mode when users arrive.

- [ ] Confirm or replace this default.
