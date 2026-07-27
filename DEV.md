# DEV — Features to build

Backlog for `/devx` to pick up. Each entry points at a spec file under `dev/`. All entries below were imported from the BMAD backlog on 2026-07-27 after reconciling both stale trackers against git main — see `_devx/import-2026-07-27.md` for the evidence table. The legacy epic checklist that used to live here is preserved in git history; every epic it listed is done except the remnants below.

Conventions: `[ ]` ready · `[/]` in-progress · `[-]` blocked · `[x]` done · `~~strikethrough~~` deleted. Status field on each entry is the source of truth; checkbox is the glanceable mirror.

---

## Epic — import-flow-hardening (active; ifh-1/2 already on main)

- [ ] `dev/dev-ifh3-2026-07-27T17:00-ios-share-extension-failure-state.md` — iOS Share Extension — persist failure state + system notification on permanent failures. Status: ready. Blocked-by: —. Parallel-safe with ifh4 (disjoint files: Swift vs Dart).
- [ ] `dev/dev-ifh4-2026-07-27T17:01-reconciler-backoff-permanent-failure-ux.md` — Dart Reconciler — exponential backoff + permanent-failure UX. Status: ready. Blocked-by: —. Parallel-safe with ifh3.
- [ ] `dev/dev-ifh5-2026-07-27T17:02-failed-imports-banner-and-sheet.md` — Frontend — FailedImportsBanner + FailedImportsSheet wired into Import Activity Hub. Status: ready. Blocked-by: ifh3, ifh4 (consumes their `failed: true` App Group records + attempt_count reset).
- [ ] `dev/dev-ifh6-2026-07-27T17:03-regression-sweep-and-e2e.md` — Regression sweep + e2e. Status: ready. Blocked-by: ifh3, ifh4, ifh5. One AC needs a staging deploy that includes ifh-1 (already on main).

## Loose ends from executed epics (independent, parallel-safe)

- [-] `dev/dev-mvp1-2026-07-27T17:04-multi-image-group-index-fix.md` — Fix multi-image group_index so one upload session yields one recipe. Status: blocked (awaiting diagnostic info from Leo — initial one-line client-fix hypothesis invalidated in review; see spec status log). From: epic-mvp-finalization.
- [ ] `dev/dev-bugsimppho7-2026-07-27T17:06-vision-extraction-eval-suite.md` — Vision-extraction eval suite with image fixtures and recipe-count gate. Status: ready. Blocked-by: —. From: epic-bugs-import-photo-pipeline (pho-1..6 done).
- ~~`dev/dev-bugscal3b-2026-07-27T17:07-backend-recurrence-expansion.md` — Backend server-side recurrence expansion in ListMealEvents.~~ Status: superseded (2026-07-27 verification: recurring-meals epics deliver this via slot-rule + materialization; residual resurrection bug filed as debug rcres1; the deferred bugs-cal-3 recurrence UI is no longer blocked).
- [x] `dev/dev-bugsact2a-2026-07-27T17:08-backend-fields-addendum.md` — Backend fields addendum for import-item detail (last_successful_stage, last_retry_at, confidence_score). Status: done (2026-07-27 verification: all three fields already landed via irrd-1/irrd-3 incl. tests — see spec status log).
- [ ] `dev/dev-irrd3a-2026-07-27T17:09-confidence-eval-calibration-gate.md` — Confidence eval metric module plus heuristic calibration and soft eval regression gates. Status: ready. Blocked-by: —. Needs real LLM API calls (~10 min runtime).
- [ ] `dev/dev-sru4-2026-07-27T17:10-presigned-upload-in-receive-screen.md` — Presigned upload path for PDF / audio / video in the receiving screen. Status: ready. Blocked-by: —. From: epic-share-receiving-ux (sru-1/2/3/5 done).
- [ ] `dev/dev-msa4-2026-07-27T17:11-create-meal-event-mcp-meal-id-and-evals.md` — create_meal_event MCP tool accepts meal_id plus 7 CI-gated eval fixtures. Status: ready. Blocked-by: —. From: epic-meals-sharing-and-ai (msa-1..3 done).

## Epic — api-async-migration (Phases 4–6 close-out; 20+ stories already on main)

Critical path: aam7 / aam8 / aam22 / aam23 in parallel → aam24 cutover → aam25 + aam27 in parallel → aam26 last (needs 7-day post-cutover soak). Scope re-verified against main 2026-07-27; each spec's Technical notes record what already landed.

- [ ] `dev/dev-aam7-2026-07-27T17:12-openai-async.md` — Swap sync OpenAI client to AsyncOpenAI at all API callsites and drop the threadpool bridge. Status: ready. Blocked-by: —.
- [ ] `dev/dev-aam8-2026-07-27T17:13-firebase-threadpool-wrap.md` — Firebase messaging.send threadpool wrap — async-safe push send variant plus sync-on-loop audit. Status: ready. Blocked-by: —. Mostly done via notify_via_threadpool; remaining scope in spec.
- [ ] `dev/dev-aam22-2026-07-27T17:14-error-tracking-middleware-async.md` — Error-tracking middleware — bridge the sync error-log write off the event loop via threadpool and the dedicated error-log sub-pool. Status: ready. Blocked-by: —.
- [ ] `dev/dev-aam23-2026-07-27T17:15-lifespan-and-pre-warm.md` — Lifespan pre-warm — warm every async pool connection before healthcheck flips green. Status: ready. Blocked-by: —.
- [ ] `dev/dev-aam24-2026-07-27T17:16-cutover-and-shim-removal.md` — Cutover — flip last sync holdouts (WS auth, chat SSE), remove sync shims, shrink sync pool. Status: ready. Blocked-by: aam7, aam8, aam22, aam23.
- [ ] `dev/dev-aam25-2026-07-27T17:17-sync-in-async-startup-guard.md` — Sync-in-async startup guard — fail fast if API handler code imports the sync Database. Status: ready. Blocked-by: aam24.
- [ ] `dev/dev-aam27-2026-07-27T17:19-concurrent-load-integration-test.md` — Concurrent-load integration test — CI-enforced proof the event loop is never held. Status: ready. Blocked-by: aam24.
- [ ] `dev/dev-aam26-2026-07-27T17:18-latency-baseline-snapshot.md` — Latency baseline snapshot — tabulate pre-vs-post-migration p95 deltas and gate the epic's win. Status: ready. Blocked-by: aam24 (+ 7-day soak).

### Epic — browser-qa-agent (workstream 41ee13; RED gate passed 2026-07-27)

Dependency shape: bqa101 ∥ bqa102 ∥ bqa103 (disjoint files/repos) → bqa104 after bqa103 (same devx repo; single version bump) → bqa105 after all four → bqa106 (attended, needs Leo) → bqa107 (attended, needs Leo). bqa103/bqa104/bqa107 land work in `~/personal/devx` (direct to its main — user-locked FR-5). Eval artifacts were authored at RED — stories re-run them, never re-author.

- [ ] `dev/dev-bqa101-2026-07-27T11:39-config-truth-qa-flip.md` — Config truth — qa flip to installed tools, runner resolution green (E-1). Status: ready. Blocked-by: —. Parallel-safe with bqa102/bqa103.
- [ ] `dev/dev-bqa102-2026-07-27T11:40-e2e-revival-one-command.md` — E2E revival — one-command green with lifecycle wrapper + 3 latent-defect fixes (E-2). Status: ready. Blocked-by: —. Parallel-safe with bqa101/bqa103.
- [ ] `dev/dev-bqa103-2026-07-27T11:41-upstream-walkthrough-template.md` — Upstream story-derived QA — template, emission wiring, schema enum. Status: ready. Blocked-by: —. Cross-repo (devx main). Parallel-safe with bqa101/bqa102.
- [ ] `dev/dev-bqa104-2026-07-27T11:42-upstream-devx-test-skill.md` — Upstream attended layer — /devx-test skill, routing, QA.md carve-out, version bump. Status: ready. Blocked-by: bqa103. Cross-repo (devx main).
- [ ] `dev/dev-bqa105-2026-07-27T11:43-palateful-adoption-eval-convention.md` — Palateful adoption — install, qa flip to claude-in-chrome, browser-flow eval convention (E-5). Status: ready. Blocked-by: bqa101, bqa102, bqa103, bqa104.
- [ ] `dev/dev-bqa106-2026-07-27T11:44-first-attended-pass.md` — First attended pass — walkthrough emission + recipe-import journey (E-3, E-4). Status: ready. Blocked-by: bqa105. Needs Leo attended.
- [ ] `dev/dev-bqa107-2026-07-27T11:45-persona-seeded-passes.md` — Persona-seeded passes — --persona flag + one seeded pass (E-6). Status: ready. Blocked-by: bqa106. Needs Leo attended; cross-repo skill change.
- [ ] `dev/dev-bqaret-2026-07-27T11:41-retro-browser-qa-agent.md` — Retro + LEARN.md updates (interim retro discipline). Status: ready. Blocked-by: bqa101, bqa102, bqa103, bqa104, bqa105, bqa106, bqa107.
