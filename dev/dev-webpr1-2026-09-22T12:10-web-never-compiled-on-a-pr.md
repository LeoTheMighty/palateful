---
hash: webpr1
type: dev
created: 2026-09-22T12:10:00-06:00
title: Web is never compiled on a PR — a web-only break first shows as a failed prod deploy
from: leonidbelyi-41 (found by palateful-79, verified by palateful-4f)
status: in-progress
owner: palateful-30
branch: fix/webpr1-pr-web-compile
---

## Goal

Compile Flutter web on pull requests that touch `app/`, so a web-only
compile failure is caught by the PR that introduces it instead of by the
prod deploy that ships it.

## Problem

`flutter build web --release` appears exactly once in `.github/workflows/ci.yml`,
in `deploy-web` (`:510`), gated on `github.ref == 'refs/heads/main' && github.event_name == 'push'`.
PR CI runs `flutter analyze` and `flutter test` (`flutter-test` job) and never
compiles for the web. A web-only break therefore passes every PR check,
merges, and surfaces as a red `deploy-web` on `main` — detection after the
fact, which is the failure class this initiative exists to remove.

**The gap is not "analyze is weak", it is conditional-import substitution.**
`auth_service.dart:11-12` imports `auth_service_stub.dart`, or
`auth_service_web.dart` when `dart.library.html` is present. The analyzer
resolves the **stub**, so a signature that drifts between stub and web
implementation type-checks on a PR and only fails when the web compile
substitutes the real file. (Hypothesis from palateful-79; measured below
rather than assumed.)

**Measured, this machine, Flutter 3.41.7:** add a third required positional
parameter to `onLoad` in `auth_service_web.dart` and not in
`auth_service_stub.dart`:

    flutter analyze --no-fatal-warnings --no-fatal-infos   → exit 0
    flutter build web --release                            → exit 1
        Error: Too few positional arguments: 3 required, 2 given.
        Error: Failed to compile application for the Web.

Nobody has hit this in the wild yet — palateful-79's real web build was
green. The break above is deliberate and was reverted.

## Acceptance criteria

- [x] PR CI compiles Flutter web when a PR touches `app/`, and skips the
      compile when it does not.
- [x] The step uses the same command as the deploy (`flutter build web --release`),
      so a PR-green web build means the deploy's build is green.
- [x] `deploy-web` pins the same Flutter version as `flutter-test`
      (`3.41.7`). Today it pins only `channel: stable`, so the version that
      compiles the deploy can differ from the version CI tested with — the
      same class of gap this story closes.
- [x] Added minutes are measured and recorded here, not estimated.
- [x] The guard is proven to fail on the conditional-import break above and
      pass without it.

## Technical notes

- **Placement**: inside the existing `flutter-test` job, appended at the end,
  so it reuses that job's Flutter install and pub cache. Appending (rather
  than inserting mid-job) also keeps it out of the way of palateful-79's
  authrep1 PR, which adds a step after `No silent catches` in the same job.
  Coordinated with 79 — whoever merges second rebases.
- **`fetch-depth: 0`** is required on the `flutter-test` checkout: the
  change detection diffs against `github.event.pull_request.base.sha`, which
  is not present in a depth-1 checkout.
- **Cost, measured locally (warm cache, Flutter 3.41.7):** `--release` 61s,
  `--debug` 46s. The debug build catches this failure too, but only saves
  ~15s and does not compile the same way the deploy does, so `--release`
  wins. Runner timings are recorded in the status log.
- **Known property of the change detection** (state it, don't rediscover it):
  the step diffs the PR's **net** change against `base.sha`, so it skips
  whenever the merged tree leaves `app/` untouched — including a PR that
  breaks `app/` in one commit and reverts it in another, or whose app changes
  cancel out across commits while an intermediate state is broken. That is
  correct for a merge gate, where only the merged state ships, but it means
  the step is not a per-commit check and won't catch a broken intermediate
  state. Observed live: #50's revert commit skipped the step.
- **Not doing**: running the web build on `main` pushes. `deploy-web`
  already compiles there; duplicating it would add minutes and catch
  nothing new.

## Status log

- 2026-09-22T12:10 — filed by palateful-30, assigned via leonidbelyi-41.
  Claim is carried in this PR rather than committed to `main` (serialized
  deploy lane).
- 2026-09-22T12:55 — guard proven in CI, both directions, on throwaway PR #50
  (draft, DO NOT MERGE, closed and deleted after this measurement).
  - Deliberate stub/web signature drift (`64ca5abd`): step **ran and failed**
    in 65s — `Too few positional arguments: 3 required, 2 given.` /
    `Failed to compile application for the Web.`
  - Benign `app/` edit (`5388ce8e`): step **ran and passed** in 63s.
  - PR #49 itself, which touches no `app/` file: step **skipped**, job green.
  - **Added cost: ~65s of runner time, and only on PRs that touch `app/`.**
    `flutter-test` job wall-clock: 7m54s with the step skipped, 9m54s with it
    passing — the delta is larger than the step because the two runs queued
    differently; the step's own duration is the honest number.
  - Note on the detection logic: it diffs the PR's **net** change against
    `base.sha`, so a break-and-revert pair nets to zero `app/` diff and
    correctly skips. Observed when #50's revert commit skipped the step.

