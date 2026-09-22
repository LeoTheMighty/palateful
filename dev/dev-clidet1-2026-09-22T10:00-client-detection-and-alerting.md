---
hash: clidet1
type: dev
created: 2026-09-22T10:00:00-06:00
title: Client-side detection and alerting — what works, what would have caught Leo's three failures, ranked gaps
from: leonidbelyi-41 production-detection push (client half; server/infra half is palateful-0e)
status: ready
owner: null
branch: null
---

## Goal

Make production failures on the client reach a human automatically. Leo hit
three failures: a random "login failed", credentials that don't hold, and a
shopping cart that was dead for months. None of them was raised with anyone.
This spec records what the client-side detection stack actually does (measured,
not configured), whether it would have caught each failure, and a ranked list
of gaps.

Gaps are split into **not collected** (no signal exists) and **collected but
unread** (the signal exists and no human is told). They need different fixes.

## Headline

1. **Nothing in palateful pushes to a human. Ever.** Every detector is
   pull-only. Confirmed in terraform [C] **and in the live AWS account** by
   palateful-0e: zero metric or composite alarms, EventBridge rules, log metric
   filters or Chatbot, and one SNS topic with 0 subscriptions. The one possible
   exception is Crashlytics' built-in email alerts, which only the console can
   show (see §5).
2. **The cart failure was collected — in May and again on 2026-09-20 — and
   nobody was told.** Someone saw it in May and wrote a fix. The fix went into a
   module nothing imports, it has been deployed in prod since before the freeze,
   and it does nothing. The failure kept firing for four months after that.
3. **Both auth failures are not collected anywhere.** The credential-restore
   path wipes the session and only calls `debugPrint`. The auth code has no
   `ErrorReporter` calls at all, and the only server-side sink needs a valid
   token to accept a report.

## Evidence key

**[M]** = measured (a read-only prod query or an executed command, 2026-09-22).
**[C]** = verified by reading the code at `main` `0b8a5f50`.
**[I]** = inferred; says what would settle it.

Prod queries ran through `bin/prod-script` inside `SET TRANSACTION READ ONLY`
and were rolled back. `error_logs` keeps 30 days (`cleanup_error_logs`), so the
observable window is 2026-08-23 → 2026-09-22.

---

## 1. What exists, and whether it works

| Mechanism | Wired | Last fired on something real | Verdict |
|---|---|---|---|
| `FlutterError.onError` / `PlatformDispatcher.onError` → Crashlytics (fatal) | iOS + Android [C] `error_reporter.dart:167-171`. **Not web**: `initialize()` returns early on `kIsWeb`. | Unknown — no read API [I] | Configured; unverified |
| `ErrorReporter.report` → Crashlytics (non-fatal) | iOS + Android [C]; no-op on web, debug and E2E | Unknown [I] | Configured; unverified |
| `ErrorReporter.report` → `/v1/users/me/client-errors` mirror → `error_logs` (`service='client'`) | All platforms incl. web [C]; off in debug/E2E | **2026-09-20 20:06** — the cart `_TypeError` [M] | **Works, but only since 2026-09-20** [M] |
| `ErrorReporter.log` breadcrumbs → mirror (`ClientLog`) | Same [C]; `nav.*` excluded | 2026-09-22 15:24 [M] | Works since 09-20 |
| Dio interceptor auto-report | **5xx only** [C] `api_client.dart:~94`. 4xx and connectivity failures are skipped ("Phase 1 scope") | Never in the window: zero 5xx in 30 days [M] | Works; covers nothing that happened |
| `BootSmokeTest` canary | Cold boot, only when credentials restore [C] `main.dart:180-199` | 2026-09-21 15:18 — **once in 30 days** [M] | Fires; **nobody watches for its absence** |
| `tools/no-silent-catch-check.sh` | CI; scope `app/lib/features/**/services/` [C] | Passes today (exit 0) [M] | **Misses the auth path and has false negatives** (§4) |
| iOS dSYM upload | **Absent**: `GoogleService-Info.plist` is present, but `project.pbxproj` has zero Crashlytics references [C] | n/a | Native iOS crashes arrive unsymbolicated [I] |
| Android Crashlytics Gradle plugin | Present [C] `build.gradle.kts:5,82` | Unknown [I] | Configured |

### The four-week gap in the mirror [M]

From 2026-08-23 to 2026-09-19, `error_logs` held **zero `service='client'`
rows** and **zero real error rows of any kind**. The only rows were two
`advance_recurrence_windows` audit breadcrumbs a night, logged as
`service='worker'`. Client rows start at **2026-09-20 19:40**. That's the day
the iOS deploy path was revived (#30 `tfship1`, then #33 bumping to
`1.0.64+90`); it had been dead since 2026-04-26.

Two things this does **not** show, because I checked:
- It does not show the app was in heavy use and silently failing to report.
  **176,075 of 176,408** `request_latencies` rows are `/v1/health` [M].
  Non-health traffic was single or double digits a week until September.
- The build on the device can't be read from the `BootSmokeTest` row. Its
  `1.0.36+49` is a hardcoded literal (`main.dart:192`, unchanged since
  2026-04-21) [C].

**What this means:** before 09-20 there's no evidence the client could report
at all. After 09-20 it can. [I] The likely cause is an old build on the device
until the iOS path was revived. ASC ran eleven builds ahead of committed
`pubspec` (#33's commit message), so git can't confirm which build was
installed. **Either way, nothing noticed that four weeks of client telemetry
were missing.** The canary built for exactly this ("if this row is also
missing, the binary doesn't have the new Dart code") has no absence alert.

---

## 2. Would it have caught Leo's three failures?

### (a) Cart dead for months — **collected, read once, misfixed, then unread**

- **Root cause** [C][M], converged independently with palateful-cc:
  `get_shopping_list.py:139,144` declares a local `ItemResponse` with
  `quantity: Decimal | None`. Pydantic v2 emits `Decimal` as a JSON **string**.
  `shopping_list_item.dart:56` does `json['quantity'] as num?` and throws
  `_TypeError: type 'String' is not a subtype of type 'num?'`. Any list with a
  non-null quantity fails to load.
- **Prod timeline, 2026-09-20** [M]: `GET /v1/shopping-lists/{list_id}` → **200**
  at 20:06:13.49 and 20:06:14.41; client `_TypeError` rows at 20:06:13.59 and
  20:06:14.62 (`shopping.cart` / `loadList`, list `ee31f0c4…`). Server 200,
  client parse failure ~100 ms later, twice.
- **The May fix** [C][M]: `a5c84386` (2026-05-03) added a
  `field_serializer` to `services/api/src/schemas/shopping_list.py:52`. Its
  comment quotes this exact error signature. **None of that module's 9 classes
  is imported anywhere.** The commit changed only the dead module and
  `tests/test_schemas.py`, which tests the dead module and passes. The fix **is**
  deployed: `a5c84386` is an ancestor of prod's `848311af` [M]. Prod has been
  running a fix that does nothing.
- **Client captured it?** Yes, by the mirror (09-20) [M] and by Crashlytics on
  iOS [I]. It was clearly seen in May, since the fix quotes it.
- **Server captured it?** **No, and it never could.** The server returned 200
  [M]. Zero 5xx and zero cart `error_logs` rows in 30 days [M]. This class of
  failure is only visible client-side.
- **Was anyone told?** No. Nothing alerts on a recurring signature, and nothing
  re-checked the May fix against the live endpoint.
- **What would have caught it:** a recurrence alert on the client signature,
  plus a contract test on the live endpoint's JSON (cc is adding one).

### (b) Random "login failed" — **not collected**

- `auth_service.dart:196` (login error), `:151` (web init), and
  `login_screen.dart:69,95,122` all `debugPrint` or `setState` only [C].
  **Neither file contains an `ErrorReporter` call** [C]. So nothing reaches
  Crashlytics or `error_logs`.
- The auto-report interceptor skips all 4xx [C], so an auth 4xx wouldn't be
  reported either.
- **Server side:** zero 401s in 30 days [M]. `get_current_user_async` takes
  `authorization: Annotated[str, Header()]` (`dependencies.py:306`): a
  **missing** header gets FastAPI's 422 and only an **invalid** token gets 401
  [C]. So no request carrying a rejected token reached the API. The login
  failure happens on-device, before any API call [I, strongly supported].
- **Anyone told?** No. There was nothing to tell them with.

### (c) Credentials not holding — **not collected, and the session is wiped silently**

- `auth_service.dart:56-61` (`tryRestoreCredentials`): on
  `CredentialsManagerException` with `isTokenRenewFailed ||
  isNoRefreshTokenFound || isNoCredentialsFound`, it calls
  `credentialsManager.clearCredentials()` and `debugPrint`s [C]. **This is the
  failure itself:** a failed renewal quietly deletes the session and the user
  lands on login. `:62` and `:293` (token refresh) are `debugPrint` only too [C].
- **Structurally unreportable to `error_logs`**: the mirror is
  `POST /v1/users/me/client-errors`, gated by `get_current_user_async` [C]. A
  user who has just lost their credentials can't authenticate the report.
  `_postMirror`'s `catch (_) {}` drops the 401 [C]. Crashlytics needs no token,
  so it is the only viable sink for this class.
- **Circumstantial** [M]: the cold-boot `BootSmokeTest`, which fires only when
  credentials restore, landed **once** in 30 days. That's consistent with
  restore failing on cold boot. [I] Low usage could also explain it; nothing in
  prod can separate the two, because the failure is swallowed on the device.

---

## 3. Ranked gaps

### Merged ranking, client + server (agreed with palateful-0e, 2026-09-22)

One ordered list for Leo. The server half, with G-numbers, lives in
[`dev/dev-obsgap1-2026-09-22T16:00-server-side-detection-inventory.md`](dev-obsgap1-2026-09-22T16:00-server-side-detection-inventory.md) §6.

| # | Item | Owner | Why it's here |
|---|---|---|---|
| 1 | **G1: a push channel exists at all** (one SNS topic + subscription) | 0e (pipe) / this spec (U1: is anyone told) | A multiplier: every other alert fires into the void without it. |
| 2 | **G2: RDS FATAL metric filter → alarm** | 0e | 238,258 Postgres auth failures, 2026-06-17 → 07-31, invisible to `error_logs` because it lives in that DB. |
| 3 | **N1: the auth path reports to Crashlytics** | this spec | Two of Leo's three complaints; zero signal today; no fix in flight. A multiplier on zero is zero. |
| 4 | **U2: client parse-failure / recurrence alert** | this spec | Catches the cart, and catches the May fix recurring. |
| 5 | **G3: deploy-freshness gets a recipient** | 0e | #25 is verified; the detector has correctly reported a 52-day-stale prod since 09-20, to nobody. |
| 6 | **U3: absence alert on expected client telemetry** | this spec | Catches the class, not just one instance (below). |
| 7 | G5: write endpoint silent while reads continue | 0e | The cart seen from the server side. |
| 8 | Contract test on real endpoint JSON | palateful-cc | In flight. |
| 9 | Promote client `area`/`operation` out of `stack_trace` | this spec | Makes client rows queryable without JSON parsing. |
| 10 | `request_latencies.user_id` population | 0e | |
| 11 | G10/G11: rsh102 fails open with 200 on a broken pool or unreachable DB, so a total DB outage reads `{"status":"ok"}` | 0e, from 0a | Needs an alarm or it's silent. **No code needed:** every fail-open branch logs `failing open` (four sites, verified on the PR branch), so one log metric filter on that phrase covers them all once rsh102 deploys. **The filter must ship *with* a test asserting every fail-open branch emits `failing open`:** the filter makes the phrase a contract nothing else enforces, so a rewording would silently drop a mode from the alarm (0a; see `dev-dfrcp1`). |
| 12 | G12 = **N5** here: the silent-catch guard can't see `app/lib/core/` | this spec (2d relayed it into obsgap1; one finding under two labels) | The file behind N1. |

Tail, lower urgency (this spec): N2 decide where pre-auth failures go · N3
uncaught errors on web · N5's borrowed-token false negative
(`shopping_cart_service.dart:358`) · N6 iOS dSYM upload · N8 stale version
literal.

**The unifying lesson (0e's §5 headline, from U3):** *the recorder depends on
the thing that broke, so the failure produces silence instead of a signal.*
The client mirror's four-week silence (it needs a valid token) and the DB's
six-week outage (`error_logs` lives in the DB) are the same class. G2 catches
one instance. U3, an alert on missing expected signal, catches the class.

### Detail by category

Ranking: how directly the gap caused one of Leo's three failures to go
unnoticed, then how cheap the fix is.

### Collected but unread — fix by telling a human

| # | Gap | Evidence | Fix |
|---|---|---|---|
| **U1** | **No push channel exists.** Terraform has 4 `aws_cloudwatch_log_group`s and zero alarms, SNS topics, subscriptions, metric filters or Chatbot. No workflow notifies anyone. Every error surface (`admin/get_errors`, `get_stats`, `get_error_detail`, `audit_errors.py`) is pull-only. | [C] | One alert path, e.g. SNS → email/push for Leo, fed by U2–U4. Everything else in this table needs it. |
| **U2** | **No recurrence alert.** The cart signature was seen in May, "fixed", and fired again for four months. | [M][C] | Alert on any `service='client'` signature that recurs after a fix, and on any new `error_type`. The query is cheap: rows are low-volume (52 client rows in 2 days). |
| **U3** | **No absence alert.** Four weeks of zero client telemetry, and a canary designed for exactly this, and nobody noticed. | [M] | Alert when there has been no `BootSmokeTest` / no `service='client'` row in N days, while `/v1/health` shows the API is up. |
| **U4** | `request_latencies` records every 4xx (405/422/429/400 all present), but no one reads it for errors. Only 1 of those 4xx reached `error_logs`. | [M] | Surface client-contract 4xx (422 above all) from latencies into the alert path. Server-side; coordinate with 0e. |
| U5 | Crashlytics alert emails: can't be verified from here. It's the only possible push channel today. Non-fatal events (everything `ErrorReporter.report` sends, including the cart `_TypeError`) may not alert by default. | [I] | **Leo, in the console:** check the last event date, open issue count, and which alert types are enabled and who receives them (new fatal / new non-fatal / regressed / velocity). "Regressed issue" is exactly U2, if the May issue had been closed. |

### Not collected — fix by reporting

| # | Gap | Evidence | Fix |
|---|---|---|---|
| **N1** | **Auth path reports nothing.** `auth_service.dart` and `login_screen.dart` have no `ErrorReporter` calls. The credential-restore catch wipes the session silently. | [C] | `ErrorReporter.report(e, st, area: 'auth', operation: …, extras: {renewFailed, noRefreshToken, noCredentials})` in every auth catch, **before** `clearCredentials()`. |
| **N2** | **The mirror can't accept pre-auth reports.** `/client-errors` needs a valid token, so auth failures, the most important class, can never reach `error_logs`. | [C] | Either an unauthenticated, rate-limited `POST /v1/client-errors` (anonymous device id), or accept that auth failures go to Crashlytics only and make U5 real. Decide explicitly; right now it's accidental. |
| **N3** | **Uncaught errors vanish on web, and skip `error_logs` everywhere.** `initialize()` returns on `kIsWeb` before installing handlers. On native, uncaught errors go to Crashlytics only and are never mirrored. | [C] | Install `FlutterError.onError` / `PlatformDispatcher.onError` on every platform, forwarding to the mirror; call Crashlytics only when it's available. |
| **N4** | **Interceptor reports 5xx only**, and there were zero 5xx in 30 days. 4xx, where contract breaks and auth show up, is skipped. | [C][M] | Report 4xx except expected ones (401 during refresh, 404 on probes); report 422 always. |
| **N5** | **Silent-catch guard scope and false negatives.** It scans `features/**/services/` only, so `core/services/auth_service.dart` and `api_client.dart`, and all screens, are out of scope. And its 40-line window accepts a safe token from a **neighbouring function**: `shopping_cart_service.dart:358` is a pure `debugPrint` swallow around the entire WS message dispatch. It passes because `ErrorReporter.report(` appears at `:388`, inside `_handleError`. The allowlist's own comment admits the cart case passes "implicitly". | [C][M] | Widen the scope to `app/lib/core/**` and screens; bound the window to the catch block's braces. Fix `:358` to report: a WS schema drift would otherwise fail every live cart update silently. |
| N6 | **iOS dSYM upload absent.** Native iOS crashes arrive unsymbolicated. Leo is on iOS. | [C] | Add the Crashlytics `upload-symbols` run-script phase, including for Xcode Cloud builds. |
| N7 | **Contract drift is silent on the client.** A server type change becomes an app-wide `_TypeError` on one screen. | [M] | Contract tests on live endpoint JSON (cc is adding them for shopping). A client-side coercion guard **must report while it tolerates** — see note. |
| N8 | **The `BootSmokeTest` version label is a stale literal**, so it can't identify the build. | [C] | Read the version from `PackageInfo`. |

**Note on N7, from palateful-cc:** a *silent* client coercion
(`num.tryParse` when a String arrives) is the same move that kept the cart
invisible. It turns a contract break into a quietly-accepted one, and the next
break produces no signal at all. If the client tolerates a type mismatch, it
must also `ErrorReporter.report(area: 'contract', …)` with the field and value.
The server-side contract test is the primary guard.

---

## 4. Also observed (hand-off, not client scope)

- **Unauthenticated route sweeps** [M], 2026-09-11 21:42 and 2026-09-14 10:02:
  ~65 endpoints each in ~5 s, all `GET`, 0–2 ms, including POST-only routes
  (405) and requests missing the `Authorization` header (422). Something is
  enumerating the public API. → palateful-0e (infra/security).
- **`request_latencies.user_id` is never populated** [M]. Even the 54
  authenticated `/client-errors` POSTs show null, so latencies can't attribute
  traffic to users. → 0e.
- **Audit breadcrumbs logged as `service='worker'`** [M]:
  `advance_recurrence_windows:start/:complete`, twice nightly. CLAUDE.md's
  convention is `service="audit"`. Because `audit_errors.py` excludes only
  `service='audit'`, these are the only "errors" in the default triage view for
  four weeks. → 0e.
- **`/v1/health` is 99.8% of latency rows** [M]. Any volume detector over
  latencies must exclude it.

## 5. Checks that need Leo (can't be done from the repo)

1. Crashlytics console: date of the last event on iOS and on Android; open issue
   count; whether the cart `_TypeError` issue exists and when it was first seen;
   which alert types are enabled and who receives them.
2. Which app build is on Leo's phone now, and which was on it before
   2026-09-20.
3. Whether any alarm or notification exists in the AWS console **outside**
   terraform (0e may have checked the live account).

## Acceptance criteria

- [ ] U1: one push path to Leo exists and is proven by a deliberate test event.
- [ ] U2: a recurring or new client `error_type` pages within a day. Proven by
      replaying the cart signature.
- [ ] U3: no client telemetry for N days while `/v1/health` is up pages. Proven
      with a synthetic gap.
- [ ] N1: every catch in `auth_service.dart` and `login_screen.dart` reports
      with `area: 'auth'`. The credential-restore catch reports **before**
      clearing credentials.
- [ ] N2: an explicit, written decision on where pre-auth failures go, and a
      test showing one arrives there.
- [ ] N3: uncaught errors on web produce a record somewhere. Proven by a thrown
      error in a web build.
- [ ] N5: the silent-catch guard covers `app/lib/core/**`, bounds its window to
      the catch block, and flags `shopping_cart_service.dart:358` until it's
      fixed.
- [ ] Each mechanism in §1 has a **last-fired date** recorded from a real
      event, not a configuration check.

## Technical notes

- Cart root cause and fix: palateful-cc (shared `JsonDecimal` type across the
  ten local response models, plus a contract assertion on the WS broadcast).
- Auth root cause: palateful-2d, sent the timing evidence above on 2026-09-22.
- Server/infra detection: palateful-0e. The gap rankings are meant to merge
  into one ordering.

## Status log

- 2026-09-22 — filed from the client-detection research (leonidbelyi-41's
  production-detection push). All prod reads went through `bin/prod-script`
  inside `SET TRANSACTION READ ONLY` and were rolled back. Two of my own
  readings were caught and reversed before filing: the nightly `worker` rows
  are audit breadcrumbs, not failures, and `request_latencies` volume is
  health checks, not app use. The cart 405/422s are a route sweep, not the
  cart.
- 2026-09-22 — ranking merged with palateful-0e (obsgap1 §6, adopted as
  proposed); 0e's live-account check confirms no push channel exists. #25
  verified by reading run 35704107068's verdict (`Gap: 52 day(s)`).
  deploy-freshness run counts use 0e's per-failing-step classification (49
  scheduled + 1 manual died at credentials, 1 unclassified); I had checked
  one run's failing step and generalised, and MANUAL.md is corrected in the
  same commit.
