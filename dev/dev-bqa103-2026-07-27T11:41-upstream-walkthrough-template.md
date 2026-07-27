---
hash: bqa103
type: dev
created: 2026-07-27T11:41:00-06:00
title: Upstream story-derived QA — template, emission wiring, schema enum
from: plan/plan-41ee13-2026-07-27T10:36-browser-qa-agent.md
status: ready
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
