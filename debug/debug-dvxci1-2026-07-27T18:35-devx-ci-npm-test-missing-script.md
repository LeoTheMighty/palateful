---
hash: dvxci1
type: debug
created: 2026-07-27T18:35:00-06:00
title: devx-ci `test` job red on every run — `npm test` with no `test` script
from: dev/dev-bqa101-2026-07-27T11:39-config-truth-qa-flip.md
status: done
branch: feat/dev-bqa101
---

## Goal
`devx-ci` should be green on this repo (or honestly reflect a real suite),
so the `/devx` merge gate can distinguish "this PR broke something" from
"this workflow has never passed."

## Repro

Committed repro is the CI history itself — every `devx-ci` run, on every
branch including `push` to `main`, has concluded `failure`:

```
$ gh run list --workflow=devx-ci.yml --limit 10 --json headBranch,conclusion,event
failure  push          main
failure  push          main
failure  pull_request  feat/debug-btri01
failure  push          main
failure  pull_request  feat/debug-rbv101
... (no success in the retained history)
```

Local repro of the exact failing command:

```
$ npm test --silent   # from repo root
$ echo $?
1
```

`package.json` declares 14 scripts (`dev`, `dev:build`, `flutter:*`, …) and
no `test`. npm exits 1 on a missing script.

## Root cause

`.github/workflows/devx-ci.yml:43` ran `npm test --silent`. Its two sibling
jobs in the same generated file guard with `--if-present`
(`npm run lint --if-present`:31, `npm run coverage --if-present`:55); the
`test` job omitted it. On a repo with no `test` script the job therefore
fails unconditionally.

The workflow is the `/devx-init`-generated **TypeScript / JavaScript** CI
(its own header line 1 says so). Palateful's real suites are pytest +
`flutter test`, run by `ci.yml` — which passes. So `devx-ci` was never
testing anything here; it was only ever a red light.

Hypothesis → check → result:
- Hypothesis: the failure is caused by bqa101's config change. → Checked
  `gh run list` for runs predating the branch. → **Refuted** — `main`
  pushes fail identically.
- Hypothesis: `npm ci` install step fails. → Checked `--log-failed`
  output. → **Refuted** — the only failing step is `Run npm test --silent`;
  `lint` and `coverage` jobs pass on the same install.
- Hypothesis: missing `test` script. → Checked `package.json` scripts. →
  **Confirmed** — no `test` key.

## Fix applied (in bqa101's PR #3)

`.github/workflows/devx-ci.yml:43` → `npm run test --if-present`, matching
the sibling jobs. Edit is between the `>>> devx` / `<<< devx` markers,
which the file header states are the preserved-edit region.

## Open question for the user (not decided here)

The applied fix makes the `test` job a **no-op** on this repo — honest, but
it means `devx-ci` contributes no real signal. The alternative is to wire
`devx-ci` to the actual runners (`npx nx run api:test`, `flutter test`, or
the `projects:` table in `devx.config.yaml`) — but that duplicates `ci.yml`,
which already runs them. Worth deciding whether `devx-ci` should exist in a
Python/Flutter repo at all, or be removed in favour of `ci.yml`.

## Status log
- 2026-07-27T18:35 — filed from /devx bqa101 Phase 7 after remote CI came
  back `failure` on run 30293935751. Confirmed pre-existing and unrelated to
  bqa101 (main pushes fail identically). Root-caused to the missing
  `--if-present` guard; one-line fix applied on bqa101's branch per the
  skill's "fix the root cause in a new commit on the branch" rule. The
  should-devx-ci-exist-here question is left open above for the user.
- 2026-07-27T19:15 — the one-line fix was ported byte-identically onto
  `feat/debug-imptab1` and merged first via PR #6 (squash → 640987e),
  because imptab1 and dvxci1 were a mutual block: PR #6 needed this fix to
  go green, PR #3 needed PR #6's imports-tab fix to go green. Porting the
  identical content avoided a merge-gate override; when `origin/main` was
  merged back into `feat/dev-bqa101` the file resolved with no conflict and
  now matches main exactly. This spec + the DEBUG.md row still ship with
  PR #3. The open question (should devx-ci exist at all in a Python/Flutter
  repo) is unresolved and deliberately left for a separate decision.
