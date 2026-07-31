---
hash: 7c5cf2
type: dev
created: 2026-07-31T10:24:06-06:00
title: "rsh108 follow-up: run the E-7 observation protocol against live prod"
from: dev/dev-rsh108-2026-07-27T12:37-deploy-freeze-visibility.md
status: ready
blocked_by: [rsh108]
branch: feat/dev-7c5cf2
owner: null
---

## Goal

Continue rsh108: remaining acceptance criteria split out by devx split (merge-first).

## Acceptance criteria

- [ ] workflow_dispatch run against current prod reports the true gap, cross-checked against bin/prod-status and git log
- [ ] Synthetic gap > 7 days fails the run and < 7 days passes, via the synthetic-gap-days dispatch input
- [ ] Registering a newer ACTIVE task-definition revision without deploying it does not change the reported gap
- [ ] The scheduled 09:00 MDT trigger fires unattended with no approval prompt, confirmed the next morning after merge
- [ ] Actuals recorded in _devx/workstreams/rotation-self-heal/evals/E-7_deploy-freeze-visibility.md

## Carried forward

### State to trust

- parent dev/dev-rsh108-2026-07-27T12:37-deploy-freeze-visibility.md shipped its committed portion at reduced scope through the normal PR/CI/merge tail

### Gotchas (save time — don't rediscover)

- All remaining ACs require the workflow merged to main plus live AWS access and a next-morning check, so they are human-observation work, not loop-iteration work

### Do NOT

- Do not redo ACs already shipped by the parent — audit its PR diff first

## Status log

- 2026-07-31T10:24:06-06:00 — created by devx split from `dev/dev-rsh108-2026-07-27T12:37-deploy-freeze-visibility.md` (merge-first)
