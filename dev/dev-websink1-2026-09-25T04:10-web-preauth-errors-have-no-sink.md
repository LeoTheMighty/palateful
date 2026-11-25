---
hash: websink1
type: dev
created: 2026-09-25T04:10:00-06:00
title: Pre-auth errors on web report to a place nobody looks
from: dev/dev-deluser1-2026-09-23T03-10-delete-user-script.md
status: ready
owner: null
branch: null
---

## Goal

Give web pre-auth failures somewhere to land. Today they reach the
browser console and nothing else, which means **the class of bug Leo has
been reporting by hand for months is invisible to every dashboard we
have.**

## Measured

[M] `ErrorReporter._reportingDisabled` includes `kIsWeb`
(`error_reporter.dart:90`) because `firebase_crashlytics` has no web
platform implementation — calling it throws `MissingPluginException` at
startup. So **Crashlytics receives nothing from web, ever.**

[M] `reportPreAuth` also skips the backend `error_logs` mirror. That is
deliberate and correct: the mirror POST needs a signed-in user, and in a
pre-auth failure there is none — a plain `report` would collect a 401 and
drop the event.

Net: on web, `ErrorReporter.reportPreAuth(...)` is a `debugPrint`. The
call sites are right; there is no sink behind them.

## Why this is structural, not an oversight

**The failures that matter most are the ones that cannot authenticate a
report of themselves.** Mirroring requires a session; the user has no
session *because of* the error being reported. That is a loop, not a bug,
and it cannot be closed by choosing a different call site.

It is the same shape as `audit4xx1`: the 4xx audit writer never sees a
dependency-raised auth failure, so the table under-reports exactly the
auth class. Two subsystems, same hole, same cause.

## What is currently lost

- `web.onLoad.callbackError` — an Auth0 Action deny, a rejected callback
  URL, a blocked user (`auth_service_web.dart:46`).
- `web.onLoad.storedCredentials` — the user authenticated and we still
  ended with no session (`:88`).
- `web.onLoad.silentAuthDeclined` / `sessionLost` — the silent logout,
  added by the session-persistence fix. **The detector for Leo's oldest
  complaint reports nowhere.**
- `initializeWeb` — the web redirect callback failing
  (`auth_service.dart:265`).
- `webSessionMarker.read` / `.write` — storage unavailable, so session
  persistence is degraded and a later loss looks like a first visit.

## Acceptance criteria

- [ ] Web pre-auth failures reach a queryable destination. Options, in
      rough order of cost — the decision belongs to whoever owns
      observability spend, not to the implementer:
  - An **unauthenticated ingest endpoint** taking a narrow, rate-limited
    error shape. Closes the loop properly; needs abuse thinking, because
    unauthenticated write endpoints attract exactly that.
  - **`sentry_flutter`** or similar, which does support web. New vendor,
    new cost, duplicated telemetry.
  - **Deferred send**: buffer pre-auth events and mirror them after the
    *next* successful login. Cheap, and loses anyone who never gets in —
    which is the population this exists to observe.
- [ ] Whatever lands, `reportPreAuth`'s doc says plainly where a web
      pre-auth error goes. Its current comment says Crashlytics is
      disabled on web and the call "is still the right call site"; that
      is true and reads as "handled".
- [ ] A test that the chosen sink receives a web pre-auth event, driven
      through `reportPreAuth` rather than asserting on the sink directly.

## Technical notes

- Do **not** widen `reportPreAuth` to mirror pre-auth events to the
  existing backend endpoint: it needs a session, and the 401 would be
  collected and dropped, which is worse than silence because it looks
  like coverage.
- Interaction with the session-persistence fix: `WebSessionMarker`
  reports a loss exactly once per occurrence. If a sink appears, that
  event is the one to route first — it is the direct evidence for "sessions
  not holding", which has so far only ever been a user report.
- Until this ships, any web auth retest has to **read the browser
  console**; no dashboard will show the failure.

## Status log

- 2026-09-25T04:10 — filed by palateful-98 while fixing web session
  persistence (PR #106). Found by correcting my own PR body: I had written
  that a session loss is "reported (Crashlytics via `reportPreAuth`)",
  which is false on the only platform where the bug occurs. The detector
  works; it reports to a place nobody will ever look.
