---
hash: logconn1
type: dev
created: 2026-09-22T18:30:00-06:00
title: Enable log_connections so the rsh102 health probe is observable in prod
from: dev/dev-rsh102-2026-07-27T12:31-credential-aware-health-probe.md
status: in-progress
owner: null
branch: feat/dev-logconn1
---

## Goal

Make rsh102's core property measurable in production. rsh102 deployed a
health probe whose whole claim is that it opens a **fresh** connection each
time. A pooled connection stays authenticated across an RDS-managed secret
rotation, so it cannot see one — measured against a live Postgres on
2026-09-22. But its post-deploy verification could only *infer* that the
deployed probe really opens fresh connections, because RDS does not log
successful connections: `log_connections` was unset, and the RDS log held 0
`connection authorized` lines. Approved by Leo (relayed by the coordinator).

## Acceptance criteria

- [x] `log_connections = 1` added to `aws_db_parameter_group.perf`
      (`terraform/modules/rds/parameter_group.tf`) — in Terraform, not the
      console, so the next gated apply does not revert it as drift.
- [x] Confirmed **dynamic** on postgres16 before choosing `apply_method`:
      `describe-engine-default-parameters` → `ApplyType=dynamic`,
      `IsModifiable=True`. No reboot; applies to new connections only.
- [x] Instance confirmed `ParameterApplyStatus: in-sync`,
      `PendingModifiedValues: {}` — no queued reboot for this to ride along
      with.
- [x] `terraform plan` reviewed under the state-writing CLI version (see status log).
- [ ] After merge (tfgate1 auto-applies terraform-only changes): the
      parameter shows `log_connections=1` live, and the RDS log shows
      `connection authorized` lines from the API task at roughly the
      `DB_PROBE_TTL_S` (60s) cadence — converting rsh102's point 6 from
      inferred to measured.

## Technical notes

- **Merging this is the prod apply.** tfgate1 (#36, `faf35fa1`) applies
  terraform-only changes merged to main. Safe here only because the change is
  dynamic.
- **Merging applies exactly 1 change** — this parameter. *An earlier version
  of this spec said "7 changes, not 1", describing six tag-only diffs as
  pre-existing, benign, and never-converging. That was wrong: see the
  2026-09-22T19:30 status-log entry. They were phantoms produced by an
  outdated local Terraform CLI, not drift.*
- Logs user, database and host — never the password.
- Volume: two lines per connection. The probe adds ~2,880 lines/day/task;
  pooled app traffic very few. Trivial CloudWatch cost.
- **Not included, deliberately:** `log_disconnections`. It would add each
  connection's lifetime, which proves the probe's connections are single-use
  as well as new. But only `log_connections` was approved, and it alone
  distinguishes the two cases (a pooled probe produces no new authorizations
  at all). Worth a separate decision if the stronger proof is wanted.

## Status log

- 2026-09-22T18:30 — filed and implemented from rsh102's deploy
  verification. `terraform plan` against prod, all four image tags pinned to
  the deployed `8d6b1329`:

      + parameter { apply_method = "immediate", name = "log_connections", value = "1" }
      Plan: 0 to add, 7 to change, 0 to destroy.

  The six non-parameter changes are the long-standing tag-only diffs. No
  `instance_class`, `apply_immediately`, `engine_version`,
  `allocated_storage`, or any `forces replacement` in the RDS instance block.
  Main was frozen for pushes (coordinator's sequenced window), so this spec
  ships inside the PR rather than as a separate main write.
- 2026-09-22T19:30 — **correction: the six "tag-only perpetual diffs" were a
  CLI-version artifact, not drift, and I described them wrongly.** The
  18:30 entry's plan ran on a local **Terraform 1.4.2**. The raw S3 state
  was written by **1.16.3** (read from the object directly —
  `terraform state pull` re-stamps the local CLI's version, so it cannot
  identify the writer), and CI's `setup-terraform@v3` is unpinned, i.e.
  latest. Twelve minor versions of skew. palateful-0e and palateful-4f found
  this today; the coordinator relayed it.

  Re-planned under **1.16.3**, checksum-verified against HashiCorp's
  official `SHA256SUMS` (fetched independently over TLS — not trusted from
  the file sitting next to a copy another session had downloaded), with a
  **fresh `TF_DATA_DIR`** so nothing cached by 1.4.2 could leak in, at the
  live `8d6b1329` tags:

      + parameter { apply_method = "immediate", name = "log_connections", value = "1" }
      Plan: 0 to add, 1 to change, 0 to destroy.

  **Why the wrong version mattered more than the wrong number.** The PR
  description told reviewers the six diffs were "pre-existing and benign"
  and "never converge". That is not a harmless miscount — it teaches a
  reviewer to *wave through* six real-looking changes as known noise. The
  next time a genuine drift lands among them, that lesson hides it. It was
  also an inference presented as fact: I had seen the diffs on two plans and
  concluded "never converge" without ever checking the CLI version.
