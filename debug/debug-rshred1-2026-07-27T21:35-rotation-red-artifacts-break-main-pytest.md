---
hash: rshred1
type: debug
created: 2026-07-27T21:35:00-06:00
title: rotation-self-heal RED artifacts break the `test` job on main
from: dev/dev-bqa101-2026-07-27T11:39-config-truth-qa-flip.md
status: ready
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
