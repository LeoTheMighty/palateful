---
hash: bqa103
type: dev
created: 2026-07-27T11:41:00-06:00
title: Upstream story-derived QA — template, emission wiring, schema enum
from: plan/plan-41ee13-2026-07-27T10:36-browser-qa-agent.md
status: done
owner: /devx-loop-2026-07-30T17-52-24-754-38586
branch: feat/dev-bqa103
---

## Goal
First devx-repo phase (direct commits to devx main — user-locked decision, FR-5). Ship everything palateful's adoption needs that is *not* the attended skill: the QA-walkthrough template, the `/devx` emission wiring, and the `browser_harness` enum extension. No version bump yet — that closes bqa104 so consumers install once.

## Acceptance criteria
- [ ] `~/personal/devx/_devx/templates/engine/qa-walkthrough.md` (new) authored from the ifh-1 hybrid skeleton (`_bmad-output/implementation-artifacts/ifh-1-qa-walkthrough.md` in palateful): header + scope blockquote → `## Pre-flight` runnable block → `## Manual checks` numbered behavioral assertions (fenced runnable block + expected output + invariant, each tagged `machine` or `human`) → `## Regressions to watch` → `## Post-merge follow-ups`. Item format must satisfy the parse contract pinned by palateful's `evals/e3_walkthrough_emission.sh` (machine/human tags on checkbox lines; inline "verify" hint on human items).
- [ ] `~/personal/devx/.claude/commands/devx.md` + `skills/devx.md` mirror: /devx Phase 5 gains the emission step — for stories with user-visible surfaces, author `test/test-<hash>-qa-walkthrough.md` from the template, execute every `machine` item inline (evidence pasted, boxes checked), leave `human` items unchecked with a one-line "how to verify", append a TEST.md entry; file commits with the story in Phase 6. (Supersedes the PRD's "Phase 6 emits" phrasing — author at Phase 5 where evidence is freshest.)
- [ ] `~/personal/devx/_devx/config-schema.json`: `qa.browser_harness` enum gains `claude-in-chrome`; schema test updated — asserts `claude-in-chrome` accepted AND a bogus value rejected.
- [ ] devx repo suite green (`npm test` there); `skills/devx.md` byte-matches `.claude/commands/devx.md` after `npm run sync:skills`.

## Technical notes
- Cross-repo story: work lands in `~/personal/devx` (direct to its main), not palateful. The palateful spec/status-log/DEV.md bookkeeping still happens here.
- Why upstream: files with the `<!-- devx-skill v… -->` header are overwritten on version change; the packaged `templatesRoot` ships engine templates (`src/lib/init-skills.ts`, `src/commands/init.ts:77-78,156`).
- `writeEngineTemplates` (`src/lib/init-write.ts:883-928`) writes any missing template on both fresh scaffold and upgrade (`init-upgrade.ts:688`) — net-new `qa-walkthrough.md` installs on `devx init` upgrade; no palateful-side fallback. Caveat: templates are write-if-absent forever — later revisions need manual copy (out of scope).
- Skills mirror via `npm run sync:skills` (`scripts/sync-skills.mjs`).
- Parallel-safe with bqa101 and bqa102 (different repo).
- Full context: plan `_devx/workstreams/browser-qa-agent/plan.md` §Phase 3.

## Status log
- 2026-07-27T11:41 — emitted from plan 41ee13 at RED-gate PASS (tests-after phase; E-3's RED artifact `evals/e3_walkthrough_emission.sh` goes green in bqa106 once a walkthrough is emitted; template lands here).
- 2026-07-30T13:12:18-06:00 — claimed by /devx in session /devx-loop-2026-07-30T17-52-24-754-38586
- 2026-07-30T19:28:47.666Z — [FAIL] loop iteration 1: The iteration ended with the devx test suite (`npm test`) still running and never completing, so no verified progress on the spec was established and no report of substantive changes can be made.
  - Learning: The devx `npm test` suite runs long enough (documented 15–50 min, 15 vitest workers) to exhaust an iteration's budget on its own; it should be launched as a background task early in the iteration rather than blocked on synchronously at the end, or scoped to only the affected test files.
- 2026-07-30T19:34:34.263Z — loop iteration 2: Landed the report template/schema work and the matching /devx Phase 5 emission step for bqa103, with 137 targeted tests green and the E-3 eval passing end-to-end on a template filled in per the new instructions.
  - Change: Completed and verified the iteration-1 report template and its schema, so a filled-in template parses under the required contract (AC1).
  - Change: Added the Phase 5 structured-report emission step to the /devx command, including the prose instructions that tell an iteration exactly how to fill the template (AC2).
  - Change: Confirmed the parse contract end-to-end by filling the template exactly as the new Phase 5 step instructs and driving the E-3 eval green.
  - Learning: The consumer eval still fails, but for a reason owned by bqa106 — its red state is expected here and is not a signal that this spec's template/schema work is broken.
  - Learning: The full devx suite is ~138 test files and takes long enough that an iteration can end before it completes; targeted discipline tests (137 of them) cover the changed surface and are the practical gate within one iteration.
  - Learning: Filling the template literally per the Phase 5 prose is itself the cheapest verification of AC1 — the eval doubles as a contract test for the instructions, not just the schema.
- 2026-07-30T20:04:33.146Z — loop iteration 3: Ran the full devx gate to completion — 136 test files / 2893 tests green with the new schema smoke assertions passing — and confirmed the skills mirror byte-matches, closing the last outstanding acceptance criterion for bqa103.
  - Change: Executed the complete devx `npm test` chain (schema-smoke, config-io, config-validate, build, typecheck, vitest) to exit 0: 136 test files, 2893 tests, no failures — the AC4 suite gate is now satisfied rather than outstanding.
  - Change: Verified the AC3 schema work end-to-end in the real gate: schema-smoke printed both new assertions green, confirming `claude-in-chrome` validates and a bogus `selenium` value is rejected with the enum error pinned to `/qa/browser_harness`.
  - Change: Confirmed the AC4 mirror requirement: `skills/devx.md` is byte-identical to `.claude/commands/devx.md` after `npm run sync:skills`, and re-running the sync leaves the tree unchanged (idempotent), so the mirror cannot silently drift.
  - Change: Audited the iteration-2 deliverables on disk against the spec text — template heading order, machine/human tagging with inline verify hints, Phase 5 step 7 emission wiring, and Phase 6 staging language all match the acceptance criteria as written.
  - Learning: The devx `npm test` script is a serial chain, not just vitest — `node test/schema-smoke.mjs && tsx config-io && tsx config-validate && npm run build && npm run typecheck && vitest run`. The schema-smoke assertions therefore gate the whole suite and fail fast in the first second, so a schema regression never costs the 28-minute vitest wait to discover.
  - Learning: The full suite took 1700s (~28 min) wall-clock for 136 files. Launching it as the very first action of the iteration and doing all read-only verification while it ran was what made a same-iteration close possible; the iteration-1 failure mode was launching it last.
  - Learning: The Phase 5 prose that this spec added contains a warning that directly constrains how to run this gate: the skill-body discipline tests read their subject files from disk at test time, so editing any `.claude/commands/*.md` or `skills/*.md` while the suite runs produces a torn-read red. Sequencing all prose edits and the `sync:skills` run before starting the suite is mandatory, not stylistic.
  - Learning: `scripts/sync-skills.mjs` is idempotent and syncs all 4 skill files at once — running it is safe to do reflexively before a gate, and a clean `git diff` hash before/after is a cheap direct proof of the byte-match AC without needing to trust the skills-sync test alone.
- 2026-07-30T20:12:29.508Z — phase 4: loop-shipped — per-iteration verification (see iteration lines above) stood in for the interactive self-review pass; line appended by the loop merge tail per dvx103
- 2026-07-30T20:12:29.508Z — merged via devx loop — PR https://github.com/LeoTheMighty/palateful/pull/21
