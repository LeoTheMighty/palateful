---
hash: 3a50ae
type: dev
created: 2026-07-31T12:33:25-06:00
title: "E-7 follow-up: confirm the scheduled deploy-freshness run fires after merge"
from: dev/dev-af8309-2026-07-31T11:38-continue-7c5cf2-rsh108-follow-up-run-the-e-7-obser.md
status: ready
blocked_by: [af8309]
branch: feat/dev-3a50ae
owner: null
---

## Goal

Continue af8309: remaining acceptance criteria split out by devx split (merge-first).

## Acceptance criteria

- [ ] Registering a newer ACTIVE task-definition revision without deploying it does not change the reported gap (the literal prod registration; measurement already discharged by simulation with ECS semantics verified read-only)
- [ ] The scheduled 09:00 MDT trigger fires unattended with no approval prompt, confirmed the next morning after merge, recording the actual UTC time the run lands

## Carried forward

### State to trust

- parent dev/dev-af8309-2026-07-31T11:38-continue-7c5cf2-rsh108-follow-up-run-the-e-7-obser.md shipped its committed portion at reduced scope through the normal PR/CI/merge tail

### Gotchas (save time — don't rediscover)

- Merging is a precondition for the remaining observation: main's copy of deploy-freshness.yml still predates the environment: production fix, so a scheduled run before the merge dies in configure-aws-credentials (still a half-witness that the cron fired)
- This repo's scheduler does not track cron expressions as written (54 firings against a cron predicting zero), so record the actual UTC time rather than confirming it ran at 09:00; E-7's threshold is about frequency, which is already measured at a 3.4h longest silence
- Both remaining items have filed commands in MANUAL.md; the prod registration is not discriminating while prod is fresh, since the family-shortcut trap only produces a visible gap difference against a stale running image

### Do NOT

- Do not redo ACs already shipped by the parent — audit its PR diff first

## Status log

- 2026-07-31T12:33:25-06:00 — created by devx split from `dev/dev-af8309-2026-07-31T11:38-continue-7c5cf2-rsh108-follow-up-run-the-e-7-obser.md` (merge-first)
