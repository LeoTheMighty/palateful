---
hash: fbloop1
type: dev
created: 2026-09-22T23:30:00-06:00
title: App feedback loop — scope only; the loop exists, the machine-readable half does not
from: null
status: ready
owner: null
branch: docs/fbloop1-scope
---

## Goal

Scope Leo's question: *"Do we have a feedback loop from the app itself? A way
to input feedback that we can then read from our coordinator/devx
periodically?"*

**Scoping only — no code.** Options with costs, for Leo to choose from.

## Headline: the loop already exists, end to end, and it already notifies him

This is the finding that should change the decision. Every measured, with
file:line.

| piece | where | state |
|---|---|---|
| User-facing entry point | `app/lib/features/profile/profile_screen.dart:155` → `_openFeedbackSheet()` → `widgets/feedback_sheet.dart` | **shipped** |
| Offline queue | `app/lib/features/profile/services/feedback_cache_service.dart` | **shipped** |
| Client call | `app/lib/core/services/api_client.dart:851` → `POST /v1/users/me/feedback` | **shipped** |
| Endpoint | `services/api/src/routers/v1/user_router.py:214` | **shipped** |
| Storage | `libraries/utils/utils/models/user_feedback.py:21` — table `user_feedbacks` (`body`, `category`, `context` JSONB, `status`) | **shipped** |
| **Push to every admin** | `services/api/src/api/v1/user/create_user_feedback.py:131` dispatches `notify_admins_new_feedback`; task fans out FCM with `force=True` (bypasses quiet hours), deep-link `/admin/feedback` | **shipped** |
| Admin inbox in-app | `app/lib/features/admin/admin_feedback_screen.dart` | **shipped** |
| Admin HTTP API | `GET /v1/admin/feedback`, `PUT /v1/admin/feedback/{id}/status` (`admin_router.py:171,189`) | **shipped** |
| Offline export | `services/api/scripts/fetch_feedback.py` | **shipped** |

So the answer to the first half is **yes, and it already pushes to him**. The
second half — *readable by a devx tab on a schedule* — is the only part
missing.

⚠️ **Cheap thing to check first, which I could not:** the push fans out to
users with `is_admin = true AND archived_at IS NULL`. Whether Leo's own
account has `is_admin` set is **not verifiable from outside the VPC**. If it
is false, the loop above is silent for him today and has been all along —
and that, not a new feature, would be the actual gap. `promote_admin.py`
sets it. **Check before building anything.**

## User-initiated vs automatic — they answer different halves

- **User-initiated (what Leo asked for):** the feedback sheet above. This is
  the only one. It carries free-text `body` plus a `context` envelope
  (app_version, platform, route, recipe_id).
- **Automatic (already exists, answers a different question):** the client
  error mirror to `/v1/client-errors` → `error_logs`; Crashlytics (iOS only;
  `authrep1` is widening what reaches it); the `BootSmokeTest` canary. These
  report *what broke*, never *"this screen is confusing"*. No amount of
  automatic telemetry answers the second, which is why the feedback sheet
  exists and why it is the right primitive to build the read side on.

## What actually blocks the periodic read

Two read paths exist and **neither is usable by an unattended tab today**:

1. **`fetch_feedback.py` (DB-direct).** [M] Prod RDS is
   `PubliclyAccessible: false`, in `vpc-0cd5ba0bcbb65bc91`. So this runs only
   from **inside the VPC** — an ECS task or a bastion. Not from a laptop, not
   from GitHub Actions.
2. **`GET /v1/admin/feedback` (HTTP).** Reachable from anywhere via
   `api.palateful.app`. But auth is `require_admin_async` — an **Auth0 user
   JWT** with the admin flag. There is no machine-to-machine credential path,
   so a scheduled job has no way to obtain a token unattended.

**That is the whole gap.** Not storage, not capture, not notification —
just an unattended reader credential-or-location problem.

## Options, ranked by cost

**None require an App Store build.** That is the main finding for sequencing:
the app half is done, so the long TestFlight pole does not apply to any option
below.

### A. Scheduled ECS task running the existing script — *fastest, no new surface*
Run `fetch_feedback.py` as an EventBridge-scheduled ECS task inside the VPC,
writing results somewhere a tab can read. Reuses a script that already exists,
already has `--since/--status/--format`, and already writes an audit row.
- **Cost:** Terraform only (schedule + task definition). No app release, no new
  endpoint, no new auth.
- **Risk:** needs a destination a tab can reach — see "the read side" below.

### B. Machine credential for the existing admin endpoint — *most reusable*
Give the API a way to authenticate a non-human caller (Auth0 client-credentials
grant, or a scoped API key), then any tab can `GET /v1/admin/feedback`.
- **Cost:** server change + Auth0 config. Larger blast radius (a new auth path
  into an admin endpoint) and deserves its own security review.
- **Value:** unlocks every other admin endpoint for automation, not just
  feedback. If more of this is coming, this is the one that compounds.

### C. Reuse the client-error mirror with a `user_feedback` kind — **not recommended**
Cost is deceptively low but it merges a **user-initiated** signal into an
**automatic** one, and the mirror's own path is what `absal1` exists to watch
(0 hits in 30d). Feedback would inherit a channel already known to be silent,
and the two need different retention, different privacy handling and different
read cadence.

### D. GitHub issue created from the app — **not recommended, blocked by a constraint**
Public repo. Feedback `body` is free-text user content, so it cannot go into a
public issue. It also needs an app release, unlike A and B.

## The read side, and today's lesson applied

Whatever reads it must satisfy the constraints already established today:

- **No user content in GitHub Actions logs.** Public repo, public logs. A
  scheduled workflow may print *counts* — "3 unread since last run" — never
  bodies. The bodies stay in the app's admin inbox, which already renders them
  and which Leo already has.
- **Do not build a second alert channel.** SNS email is the one Leo reads. A
  feedback notifier should use it or nothing.
- **A red run notifies nobody.** [M] Leo has GitHub Actions email
  notifications off — that is why `deploy-freshness` failed 52 times against 2
  successes for over a month unnoticed. So a scheduled reader **cannot** report
  its own failure by failing. Same shape as `absal1`: it needs its verdict to
  leave GitHub, and its silence to be detectable from outside itself.
- **Prefer count-and-pointer over content.** The richest, cheapest design is a
  reader that emits "N unread, oldest 3 days" and a deep link, and leaves the
  content where it already lives. That satisfies the privacy constraint for
  free and keeps the tab's job small.

## What I did not establish

- Whether Leo's account is an admin (needs VPC or app access) — see the
  warning above. **This is the highest-value check and it is not mine to run.**
- Whether any feedback rows exist in prod today. Same blocker. If the table is
  empty, the "read it periodically" problem is theoretical until the app is in
  more hands, and option A's schedule can be very slow.
- Whether Auth0 is licensed/configured for client-credentials, which decides
  whether option B is a config change or a bigger piece of work.

## Recommendation

**Check the `is_admin` flag first.** If it is false, setting it may close
Leo's loop entirely with no work at all, and the rest of this becomes an
automation nicety rather than a gap.

If it is true and he still wants a tab reading it: **option A**, with a
count-and-pointer reader. It needs no app release, no new auth surface and no
new alert channel, and it reuses a script that already exists and is already
audited.

## Status log

- 2026-09-22T23:30 — scoped at Leo's request, relayed by the coordinator.
  Scoping only, no code, nothing on main. Every claim in the table above
  carries a file:line and was read on `main`, not recalled.
