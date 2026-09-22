---
hash: ncfgverdict1
type: dev
created: 2026-09-22T22:10:00-06:00
title: NOT_CONFIGURED must be loud for the worker, and must cover the passwordless-URL case
from: dev/dev-selfheal1-2026-09-20T11:45-503-only-when-a-restart-can-fix-it.md
status: ready
owner: null
branch: null
---

## Correction to this spec's first draft

The first draft asked for a `NOT_CONFIGURED` verdict to be **created**.
[M] It already exists — selfheal1 (#52) shipped it: `ProbeVerdict.
NOT_CONFIGURED` (`db_probe.py:154`), returned at `:401`, rendered by
`health_router.py` as `{"status": "degraded"}` rather than `ok`, and the
CLI's exit-0 choice is already argued in `main()`'s docstring. The draft
was written from a message thread without reading the merged source, and
it was wrong. What follows is the real remaining gap.

## Goal

Two things the merged verdict does not yet do, both of which bite at
rsh107:

1. **It is silent where it matters.** [M, 0a] The CLI exits `0` for
   `NOT_CONFIGURED` — deliberately, and the reasoning is right: ECS
   treats any non-zero exit as unhealthy, so a distinct code would
   replace the worker over exactly the condition this verdict was
   invented to stop replacing tasks over. But rsh107 makes that CLI the
   worker's container health check, and `/v1/health`'s `degraded` has no
   worker equivalent. So a worker with no DB credential reports
   **HEALTHY forever** while being structurally unable to do its job.
   That is the silent-void shape, arrived at by correct reasoning about
   503s.
2. **It does not cover the passwordless-URL case.** [M]
   `_downgrade_passwordless_auth_failure` (`db_probe.py:350`) classifies
   a connection that *was* attempted and rejected against a URL carrying
   no password, and returns `UNREACHABLE` — "may clear by itself" — for
   a condition that never clears by itself.

## Acceptance criteria

- [ ] **The spec decides the worker's answer, because rsh107 must consume
      it and will otherwise pick one by accident.** Proposed: keep exit
      `0` (a replacement cannot conjure a credential, and
      `deployment_minimum_healthy_percent = 0` means a drain loop) **and**
      make the condition alarm — the worker analogue of `degraded`. Not
      a 503; not silence either. 0a raised this; it needs 41's ranking
      against rsh107's own ACs before implementation.
- [ ] The passwordless-URL case classifies `NOT_CONFIGURED` rather than
      `UNREACHABLE`.
- [ ] ~~Never emitted for a connection that was attempted and failed.~~
      **Softened** [0a]: not emitted for a connection that failed for any
      reason *other than* an absent credential. The original "never"
      is violated by the only sane implementation — with a provider
      registered, an empty resolved password is knowable only **at**
      connect time, so a pre-connect check cannot cover the FR-5 case.
- [ ] The check inspects **the URL actually being connected with** —
      never `DB_PASSWORD` or any other env var directly. `DATABASE_URL`
      can carry no password while `DB_PASSWORD` is populated, and vice
      versa; a pre-connect check that asks the env var is a tidier-looking
      instance of the wrong-path mistake that produced this workstream.
- [ ] `NOT_CONFIGURED` stays **distinguishable from `UNREACHABLE` AND
      keeps the shared `failing open` phrase** [M, 0a]. It has it today
      (`db_probe.py:399`). 0e's G11 metric filter keys on that exact
      string across all four fail-open branches and nothing enforces it,
      so a future edit giving this verdict a more specific message —
      which "distinguishable" actively invites — would silently drop it
      out of the alarm with every test still green. The two requirements
      collide unless the AC says both.
- [ ] A test pinning the asyncpg case: a blank-password URL classifies
      via the URL check, **not** via the error.

## Technical notes

- **The distinction cannot come from the driver error.** [M, 0a, against
  an isolated pg16] On asyncpg a *missing* password is byte-identical to
  a *wrong* one: `InvalidPasswordError`, `sqlstate='28P01'`,
  `password authentication failed`. libpq's `no password supplied` — what
  `is_missing_password` matches — is something asyncpg never emits.
- **Interaction with rsh105/rsh106, and it cuts both ways.** Once FR-5 is
  wired, "the URL carries no password" is the *normal* state of a healthy
  rotating-credential task, so a naive URL check reports
  `NOT_CONFIGURED` for a perfectly fine worker. The same precondition is
  already flagged from the other side in
  `_downgrade_passwordless_auth_failure`'s docstring: if anyone drops
  `DB_PASSWORD` from the task definition — the natural end state of
  "the secret is resolved at connect time" — **every real rotation
  rejection silently downgrades and the self-heal is deleted.** Any
  change here must consult the listener's resolved credential, not the
  URL.
- Land with or before rsh107; after it, a misconfigured worker fails open
  silently in production.

## Status log

- 2026-09-22T23:05 — draft corrected by palateful-98 after reading the
  merged source: the verdict already exists, so the spec is re-scoped to
  the loudness gap and the passwordless-URL case. 0a's review supplied
  the worker-silence gap, the "never" softening, and the phrase
  collision; its finding that FR-5 makes a passwordless URL normal is
  folded into the technical notes.
- 2026-09-22T22:10 — filed by palateful-98 at the coordinator's request.
  Distinction identified by palateful-0a.
