---
hash: tfval1
type: dev
created: 2026-09-22T21:30:00-06:00
title: PR CI validates Terraform only for the dev root, so prod-only files are never checked before merge
from: dev/dev-tfgate1-2026-09-22T19:00-terraform-only-changes-never-apply.md
status: ready
owner: null
branch: null
---

## Goal

The `terraform` CI job runs `fmt -check -recursive` on all of `terraform/`, but
**`init -backend=false` and `validate` only in `terraform/environments/dev`**
(`ci.yml:464-469`, measured). Files that exist only in the prod root, such as
`alerts.tf` and every `alarm_*.tf`, are formatted but **never validated before
merge.** After tfgate1, a broken prod file merges and then fails the
unattended apply on `main`. **This affects every alarm PR in flight.**
Found by palateful-4f.

## Acceptance criteria

- [ ] Run `init -backend=false` and `validate` for `terraform/environments/prod`
      in PR CI. It needs no credentials: `-backend=false` doesn't touch state.
- [ ] Proven by a deliberately invalid prod-only file failing PR CI.
- [ ] **Guard against plaintext secrets in task definitions** (palateful-4f).
      `container_definitions` is plaintext, so a secret put in a task's
      `environment` (a `value`) instead of `secrets` (`valueFrom`) would print
      in the **public** Actions log on every deploy. Today nothing leaks: all
      **7** secret-shaped names in `terraform/modules/ecs/main.tf` are
      `valueFrom` references (measured). 4f also scanned the 07-31
      `terraform-prod` log and found no secret-shaped strings.
      **Match a secret-shaped name *paired with* `value =`, not the name
      alone.** A name-only grep for `KEY|SECRET|TOKEN|PASSWORD|CREDENTIAL`
      matches all 7 legitimate `valueFrom` lines (`DB_PASSWORD`,
      `OPENAI_API_KEY`, `FIREBASE_CREDENTIALS_JSON`, …) on day one. A guard
      that fails on its first run gets disabled. Prove it both ways: it must
      pass on today's tree and fail on a planted `{ name = "X_TOKEN", value =
      "…" }`.
      **A proven implementation already exists: `feat/dev-tfenvguard`**
      (`a28dbb03`, palateful-4f): `tools/tf-env-secret-check.py` and its
      `.suite.py`. **Start from it; don't rebuild it.** It isn't wired into CI
      yet, and that wiring is this spec's job. Its scoping rule is to check
      **list elements only**: container env entries are `{ name, value }`
      objects in a list, while RDS `parameter { name, value }` and SSM
      parameters are HCL *blocks*, so a whole-tree check would flag real
      settings like `password_encryption`. It also flags `value` inside a
      `secrets` list. Re-run independently by palateful-0e on 2026-09-22:
      suite **exit 0** ("ALL AS EXPECTED", 17 cases + coverage), checker on
      today's tree **exit 0** (18 files, 0 violations). Both exit codes were
      read directly, not through a pipe. **Known limits, by design:** a secret
      behind a non-secret-shaped name (`{ name = "CONFIG_BLOB", value = var.k }`)
      and secrets in `jsonencode()` of a map rather than a list are not
      caught. It catches a break in the naming convention, not every possible
      leak. The suite's coverage expectation is pinned to today's 58 entries
      and 7 secret-shaped names, so it's a proof artifact, not a CI gate.
- [ ] Optionally, a read-only `terraform plan` in PR CI against prod state,
      which needs credentials, so weigh it against envprot1/ciiam1. The
      alarm PRs have been doing this by hand.

## Technical notes

- Cheapest item here and the most immediately useful: land before the alarm
  PRs if possible.

## Status log
- 2026-09-22T21:30 — filed as tfgate1 follow-up ("merge now, then harden", Leo). Found
  while building tfgate1; each finding measured live, not read from config.
- 2026-09-22T22:00 — added the plaintext-secret guard AC (palateful-4f). The
  baseline was measured on the repo side: 7 secret-shaped names, all
  `valueFrom`. The AC requires matching name + plaintext `value`, because a
  name-only check fails on all 7 legitimate entries.
- 2026-09-22T22:30 — the guard exists: `feat/dev-tfenvguard` (4f). Re-ran it
  independently: suite and checker both exit 0. Its coverage check caught three
  bugs before any planted case ran, and each of them would otherwise have
  shipped as a green guard that never fires.
