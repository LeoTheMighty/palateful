---
hash: e2eprod1
type: dev
created: 2026-09-24T21:00:00-06:00
title: E2E_MODE must make a production base URL impossible, not merely overridden
from: dev/dev-e2echat1-2026-09-23T00:10-e2e-flag-without-an-environment-guard.md
status: ready
owner: null
branch: null
---

## Goal

**A Flutter bundle built with `E2E_MODE=true` and no `API_BASE_URL` override
talks to production with a working auth bypass.** Nothing fails, nothing
warns. Make that combination impossible to build or impossible to run.

## The mechanism, verified from source

Two independent facts that are individually reasonable and jointly dangerous:

1. **Production is the default.** `app/lib/core/config/environment.dart:9-12`
   — `API_BASE_URL` has `defaultValue: 'https://api.palateful.app'`. The
   file's own header says *"Values default to production."* `AUTH0_AUDIENCE`
   defaults the same way.
2. **`E2E_MODE` has no environment condition.** Line 37 is
   `const bool kE2EMode = bool.fromEnvironment('E2E_MODE');` — a bare flag.
   Its own docstring: *"When true, Auth0 is skipped and a fixed test token is
   used instead."* It is consumed at **nine sites in `main.dart`** (46, 71,
   95, 135, 142, 214, 417, 436, 535), gating auth init, `getMe()`, lifecycle
   handling and error reporting.

So `E2E_MODE=true` alone yields: **auth bypassed, fixed test token, and
`https://api.palateful.app` as the base URL.**

**This is not hypothetical — the mitigation exists because it already
happened.** `services/e2e/scripts/run_all.sh:26-29`, written by whoever fixed
it (bqa102, `c992552e`, 2026-09-20):

> *"The Flutter build defaults API_BASE_URL to https://api.palateful.app
> (app/lib/core/config/environment.dart). Without this define a 'local' e2e
> run compiles a bundle that talks to PRODUCTION with the fixed e2e token.
> Every browser build launched from this repo pins it to localhost."*

**The safety is one `--dart-define` deep, in a shell script.** Any path that
does not go through `run_all.sh` — `flutter test integration_test` run
directly, an IDE run configuration, a new script, a refactor of the existing
one — produces a prod-talking bundle with the bypass armed. And the tests it
runs are not read-only: they create recipe books and drive a recipe wizard.

## Why a check in the script is worth nothing

`run_all.sh` already pins `API_BASE_URL`. Adding another assertion **inside
the script that already gets it right** protects only the path that is
already safe. The whole defect is the paths that bypass it. **Any fix whose
enforcement lives in the launcher is not a fix.**

## Design decisions to settle in implementation

**1. The predicate. Use "not local", not a production allowlist.**
A hostname denylist/allowlist of known prod hosts is brittle: it fails open
for a host nobody listed — staging, a preview deploy, a new domain — which
is the same failure shape as an unlisted case elsewhere in this codebase.
**Invert it: enumerate what is permitted and reject everything else.**
Proposed permitted set, to confirm during implementation:
`localhost`, `127.0.0.1`, `[::1]`, `10.0.2.2` (Android emulator host loopback),
and `host.docker.internal`. Anything else with `E2E_MODE=true` is a failure.
Fails **closed**: a new legitimate local host must be added deliberately.

**2. `assert` is the wrong tool — it is stripped in release builds.**
Dart removes `assert` in release mode, so an assert-based guard protects
debug and profile and silently vanishes from exactly the build most likely to
be pointed somewhere real. **The check must be an unconditional
`throw`/abort**, not an assert.

**3. Where it lives: beside the flag, not beside the caller.**
The check belongs in `environment.dart` (or a function it exposes, invoked as
the first statement of `main()` before any dependency setup or network call)
so that **every** bundle carrying `kE2EMode == true` executes it. Build-time
failure is better still if achievable; runtime abort at startup is the
minimum. Either way the property to preserve is: **no launch path can opt
out.**

## Acceptance criteria

- [ ] **A bundle with `E2E_MODE=true` and a non-permitted `API_BASE_URL`
      fails** — at build time if achievable, otherwise aborting at startup
      before any network call and before the bypass arms.
- [ ] **The guard is not an `assert`** and is proven to survive a release
      build. A test or documented manual check must demonstrate it firing in
      release mode; otherwise the guard protects only the safe builds.
- [ ] **Enforcement lives in the app, not in `run_all.sh`.** Proven by
      invoking a launch path that bypasses the script entirely (e.g.
      `flutter test integration_test` with `E2E_MODE=true` and no
      `API_BASE_URL`) and observing the failure.
- [ ] **Negative control: the guard is shown to fire.** Construct the unsafe
      combination deliberately and assert it is rejected. A guard that has
      never been observed refusing anything is indistinguishable from one
      that cannot.
- [ ] **The permitted-host set is explicit, fails closed, and is stated in a
      comment with its reasoning** — including why an allowlist of *local*
      hosts beats a denylist of *production* ones.
- [ ] **The legitimate path still works**: `npx nx run e2e:test` is unaffected.
- [ ] Consider whether `AUTH0_AUDIENCE`/`AUTH0_DOMAIN` need the same
      treatment, and record the decision either way.

## Technical notes

- **Sibling instance, same class:** `e2echat1` (#67, merged `82d27127`) — *an
  e2e flag with no environment guard*, at
  `services/api/src/api/v1/chat/agent_loop.py:58`, branching on
  `settings.e2e_test_mode` alone. **That is the server-side instance; this is
  the client-side one.** Two instances make it a pattern: **an e2e flag is a
  privilege, and a privilege with no environment predicate is a defect
  regardless of how carefully its callers behave.**
- e2echat1 also records why the envspell1 CI gate cannot catch either:
  `tools/environment-gate-check.sh` greps for *comparisons against*
  `ENVIRONMENT`, so it is blind to sites that **omit** the check rather than
  misspell it. **Whatever guard this spec adds should be checkable by
  something that can see an absence** — otherwise it joins the same blind
  spot.
- The blast radius here is larger than e2echat1's. That one returns a canned
  chat string to a real user. This one runs a recipe-creation suite against
  production data with authentication bypassed.

## Status log
- 2026-09-24T21:00 — filed at palateful-41's request after the E2E-suite
  investigation surfaced `run_all.sh:26-29`. The comment is a warning written
  by someone who understood the hazard and mitigated it in the only place
  they controlled; the default it warns about is still in `environment.dart`.
  Cross-referenced to `e2echat1` as the second instance of the class.
