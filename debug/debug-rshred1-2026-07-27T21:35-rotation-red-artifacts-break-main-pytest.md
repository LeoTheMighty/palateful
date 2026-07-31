---
hash: rshred1
type: debug
created: 2026-07-27T21:35:00-06:00
title: rotation-self-heal RED artifacts break the `test` job on main
from: dev/dev-bqa101-2026-07-27T11:39-config-truth-qa-flip.md
status: in-progress
owner: /devx-loop-2026-07-27T21-15-34-312-36147
---

## Goal
`ci.yml / test` (the Python/pytest job) is green on `main`, so the `/devx`
merge gate reflects real breakage instead of standing red.

## Repro

Pre-existing and unrelated to bqa101/imptab1/dvxci1. The `test` job on
`main` flipped `success` → `failure` at commit `5a6174d`
("plan: rotation-self-heal — red stage") and has failed on every `main`
run since:

| main commit | run | `test` job |
|---|---|---|
| `2f4b699` | 30293754580 | **success** (last green) |
| `5a6174d` | — | *(RED-stage merge — the flip)* |
| `879f47a` | 30295039381 | failure |
| `266de9c` | 30295775409 | failure |
| `dddcb58` | 30296449693 | failure |
| `640987e` | 30306176710 | failure |

Local: `npx nx run api:test`

## Root cause (established, not hypothesis)

```
E   ModuleNotFoundError: No module named 'utils.services.db_credentials'
libraries/utils/test/test_db_credential_provider.py:120: ModuleNotFoundError
```

Every failure is `ERROR at setup` — collection-time import failure, not an
assertion. Two RED-stage test files landed on `main` via `5a6174d`:

- `libraries/utils/test/test_db_credential_provider.py`
- `libraries/utils/test/test_rotation_redeploy_handler.py`

They import modules that do not exist yet **by design** — that is what a
tests-first RED artifact is. The implementing stories are still open
(`rsh105` secrets-manager-password-provider, `rsh103`
rotation-redeploy-lambda-handler). So this is not a bug in the tests; it is
a **process gap**: RED artifacts were merged to `main` where the default
pytest collection picks them up, which turns the shared merge gate red for
every unrelated PR in the repo until the whole rotation-self-heal
workstream lands.

## Acceptance criteria
- [ ] Decide the policy: RED artifacts must either (a) not merge to `main`
      until their implementation lands, or (b) be excluded from default
      collection until then (e.g. a `red` marker deselected in `ci.yml`, or
      staged under a not-collected path). **This is the load-bearing
      decision — the fix follows from it.**
- [ ] `ci.yml / test` green on `main`.
- [ ] Whichever mechanism is chosen is documented so the next `/devx-plan`
      RED stage doesn't reintroduce it.

## Technical notes
- **Ownership caution:** `rsh101` is actively claimed by another session
  (worktree `.worktrees/dev-rsh101` live at time of filing). Do NOT edit
  the rotation-self-heal test files or specs from a different session —
  coordinate first, or scope any fix to `ci.yml` collection config only.
- This resolves itself once `rsh103` + `rsh105` land, so option (a) may be
  "wait". But `main` stays red until then, which is exactly the standing-red
  condition that made imptab1 and dvxci1 hard to attribute — two agents
  independently had to verify "is this red mine?" against main before
  trusting CI. That cost is recurring and is the argument for option (b).
- Filed from bqa101's post-merge verification, per the /devx rule to file
  rather than expand scope.

## Status log
- 2026-07-27T21:35 — filed from /devx bqa101 Phase 8 post-merge check.
  Root cause established from run 30306176710 logs (ModuleNotFoundError at
  collection). Attribution to `5a6174d` established by walking the `test`
  job conclusion across the last 8 `main` runs — green at `2f4b699`, red on
  everything after the RED-stage merge. Not root-caused further because the
  fix is a policy decision, not a code defect.
- 2026-07-27T16:13:10-06:00 — claimed by /devx in session /devx-loop-2026-07-27T21-15-34-312-36147
- 2026-07-27T22:18:44.826Z — loop iteration 1: Decided and implemented the RED-artifact policy (registry-driven exclusion from default pytest collection), turning the utils test suite green locally (608 passed) without touching any rotation-self-heal-owned file.
  - Change: Added tools/red-artifacts.txt — a registry of tests-first RED artifacts merged to main ahead of their implementation, in the same path:hash:rationale format as the existing silent-catch allowlist, with the full policy (register on merge, delete entry on GREEN) in its header.
  - Change: Added libraries/utils/test/conftest.py, which reads the registry into collect_ignore, hard-errors on a registered path that does not exist, and honours PYTEST_RUN_RED=1 as the opt-in for directory runs.
  - Change: Registered the two rotation-self-heal RED files against their implementing stories (rsh105, rsh103), taking the utils suite from 5 failed / 23 errors to 608 passed.
  - Change: Documented the mechanism in CLAUDE.md Key References so the next /devx-plan RED stage registers rather than reintroducing the standing red.
  - Learning: The spec's root cause is slightly off: the missing-module imports are inside pytest fixtures (test_db_credential_provider.py:120, test_rotation_redeploy_handler.py:129), not at module scope. The modules import fine — the failures are ERROR-at-setup, not collection errors. A marker-based deselection would therefore have worked too; the spec's 'collection-time import failure' framing would have ruled that option out incorrectly.
  - Learning: collect_ignore does NOT suppress a file named explicitly on the command line — only directory recursion. That is a feature here: the implementing story can run its own RED artifact with a plain path and no env var, while the CI directory run stays clean.
  - Learning: Blast radius is naturally contained: every other Python test target (api, worker, parser, agent, migrator) is scoped to its own testpaths or an explicit path, so none of them can ever collect libraries/utils. Only the utils target and a bare root-level pytest were ever affected.
  - Learning: This worktree has no libraries/agent venv, so `npx nx run agent:test` fails locally with 'unrecognized arguments: --cov'. Pre-existing environment gap, unrelated to this spec — future iterations should not chase it as a regression.
  - Learning: Local api tests are unrunnable in this worktree (Docker daemon down, so no Postgres); AC #2 can only be closed by CI on main.
- 2026-07-31 — iteration 2 (manual, outside the loop): completed the fix. Iteration 1
  registered only the two `libraries/utils` RED artifacts and left `main` red, because
  the api suite was unrunnable in that worktree (its own last Learning) — so the third
  RED artifact, `services/api/tests/test_health.py`, was never seen. Postgres was up
  this time; the api suite runs.
  - Change: Split `services/api/tests/test_health.py`. The RED stage (`5a6174d`) rewrote
    that file *in place*, replacing three passing tests, so it could not simply be
    registered: `services/api` pins `fail_under = 100` and excluding the file drops
    `health_router.py` coverage, leaving the gate red either way. The pre-RED baseline is
    restored at `test_health.py` (recovered from `5a6174d^`) and the RED content moved to
    `services/api/tests/test_health_credential_probe.py`.
  - Change: Registered `test_health_credential_probe.py` against rsh102 (Phase 2 / FR-2,
    the story that implements `utils/services/db_probe.py`).
  - Change: Extracted the iteration-1 conftest loader into `utils.testing.red_registry`
    so each test root opts in with two lines rather than a copied 60-line loader; both
    `libraries/utils/test/conftest.py` and `services/api/tests/conftest.py` now use it.
  - Change: Added the authoring caveat to the registry header — a RED artifact MUST be a
    new file, never an in-place rewrite of an existing one, or it cannot be registered.
  - Verified: api suite 2570 passed, coverage 100.00%. utils suite 595 passed with both
    registered artifacts excluded. `PYTEST_RUN_RED=1` collects 19 items from the api RED
    file; default collection collects 0. `tests/conftest.py` ruff count unchanged at 8.
  - Learning: 12 failures in `test_freeform_units_seed.py` / `test_freeform_unit_aliases_seed.py`
    are pre-existing on `main` (confirmed by running them at `origin/main`) and are NOT
    part of this spec. They are not RED artifacts — do not register them; they need their
    own debug spec.
  - Learning: In `services/api/tests/conftest.py` the `collect_ignore` assignment must sit
    *below* the `sys.path`/`os.environ` preamble. Ruff tolerates that preamble before a
    module-level import, but a plain assignment ahead of it tips
    `from fastapi.testclient import TestClient` into a new E402.
  - Note for rsh102: its GREEN commit must delete the registry entry AND fold the two
    baseline tests out of `test_health.py` — they pin the old contract and both become
    wrong when FR-2 ships. Called out in the header of both files.
