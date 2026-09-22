---
hash: ncfgverdict1
type: dev
created: 2026-09-22T22:10:00-06:00
title: NOT_CONFIGURED is not UNREACHABLE — a missing credential must not read as a transient outage
from: dev/dev-selfheal1-2026-09-20T11:45-503-only-when-a-restart-can-fix-it.md
status: ready
owner: null
branch: null
---

## Goal

Give the probe a verdict that says "this task has no credential to
connect with" and keep it distinct from "the database did not answer".
Today both collapse into `UNREACHABLE`, which is cosmetic while nothing
acts on the verdict — and stops being cosmetic at rsh107, where the
worker health check does.

`UNREACHABLE` means *try again, this may clear by itself*. A missing or
passwordless `DATABASE_URL` never clears by itself. A worker sitting
fail-open forever on a credential it was never given is the silent-void
shape wearing a new label: the check reports a condition it cannot
distinguish from a blip, nobody is paged, and the task is not doing its
job.

## Acceptance criteria

- [ ] A distinct `NOT_CONFIGURED` verdict exists, emitted when the
      connection cannot be attempted for want of a credential (no URL, or
      a URL carrying no password), and is never emitted for a connection
      that was attempted and failed.
- [ ] The check inspects **the URL actually being connected with** — never
      `DB_PASSWORD` or any other env var directly. `DATABASE_URL` can carry
      no password while `DB_PASSWORD` is populated, and vice versa; a
      pre-connect check that asks the env var is a tidier-looking instance
      of the wrong-path mistake that produced this whole workstream.
      (0a's caveat against its own suggestion; 3b has it in the ACs too.)
- [ ] `NOT_CONFIGURED` does **not** produce a 503. A restart cannot supply
      a credential the task definition never had — the selfheal1 principle
      applies unchanged.
- [ ] `NOT_CONFIGURED` **is** distinguishable in logs/telemetry from
      `UNREACHABLE`, so "this task is misconfigured" is a queryable state
      rather than a silence. Fail-open without a signal is the failure mode
      this spec exists to remove, not the fix.
- [ ] A test pinning the asyncpg case below: a blank-password URL must
      classify `NOT_CONFIGURED` via the URL check, **not** via the error.

## Technical notes

- **The distinction cannot come from the driver error.** [M, measured by
  0a against an isolated pg16] On asyncpg a *missing* password is
  byte-identical to a *wrong* one: `InvalidPasswordError`,
  `sqlstate='28P01'`, `password authentication failed`. libpq's
  `no password supplied` string — which `is_missing_password`
  (`db_credentials.py`, added by 3b in #52) matches — is something asyncpg
  never emits. So the async path has to detect the condition from the URL
  before connecting; `db_probe._url_password_is_blank` is the existing
  seam.
- Interaction with rsh105 (#45): the `do_connect` listener resolves the
  password at connect time when `DB_PASSWORD_SECRET_ARN` is set, so "the
  URL carries no password" is not by itself a misconfiguration once FR-5
  is wired (rsh106). The check must account for a provider being
  registered on the engine, or it will report `NOT_CONFIGURED` for a
  perfectly healthy rotating-credential task.
- Land with or before rsh107; after it, a misconfigured worker fails open
  silently in production.

## Status log

- 2026-09-22T22:10 — filed by palateful-98 at the coordinator's request
  (41: "a spec written by the implementer beats one transcribed from a
  message"). Distinction identified by palateful-0a; URL-not-env-var
  constraint from 0a and 3b. Not yet reviewed by either — draft sent to
  both for the shape before implementation starts.
