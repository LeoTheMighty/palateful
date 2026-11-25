---
hash: obsgap1
type: dev
created: 2026-09-22T16:00:00-06:00
spawned:
  - dev/dev-alrt1-2026-09-22T19:00-alert-topic-push-channel.md
  - dev/dev-rdsal1-2026-09-22T19:00-rds-auth-failure-alarm.md
  - dev/dev-authrep1-2026-09-22T19:00-auth-path-error-reporting.md
  - dev/dev-prsal1-2026-09-22T19:00-client-parse-failure-alert.md
  - dev/dev-dfrcp1-2026-09-22T19:00-deploy-freshness-and-failopen-alerts.md
  - dev/dev-absal1-2026-09-22T19:00-absence-alert-expected-telemetry.md
  - dev/dev-tfgate1-2026-09-22T19:00-terraform-only-changes-never-apply.md
title: Server-side production detection — what exists, what works, what would have caught Leo's complaints
from: coordinator dispatch (leonidbelyi-41), 2026-09-22 — "harden palateful so production issues get detected"
status: done
owner: null
branch: feat/dev-obsgap1
---

## Scope

**Server and infrastructure half only.** Split by the coordinator on
2026-09-22: this spec owns backend + infra detection (`error_logs`
api/worker, `/v1/health`, CloudWatch, RDS, ECS/ALB, deploy-freshness,
credential rotation, `cldb01`). **palateful-4f** owns the client side
(Crashlytics, `/v1/client-errors`, Flutter capture) and whether anyone is
told. The gap ranking at the end is written to be merged with 4f's, not to
compete with it.

Every claim is marked **[M] measured** — read from prod or the live AWS
account on 2026-09-22 with read-only tooling — or **[I] inferred**. All prod
queries ran inside `SET TRANSACTION READ ONLY`, so Postgres itself rejected
any write; nothing was mutated. No secret values were read (Secrets Manager
access was `list-secrets` metadata only).

## Headline

**Palateful's database refused its own application's logins for about 100
days: 573,039 failed logins, first recorded 2026-04-22, last on
2026-07-31. Not one mechanism told a human.** [M] (Corrected from "six weeks /
238,258": the first query covered too short a window. See §2.) It ended because a deploy on 07-31 happened
to pick up the current credential, not because anything noticed. It is
**scheduled to be able to recur on 2026-10-29**, the next credential
rotation. [M for the date. The mechanism is measured too: the probe deployed
today passes straight through a password change (§4). Only the recurrence
itself is a prediction — it depends on rsh102 being *deployed* first.]

Three structural facts made it invisible, and each generalises:

1. **Nothing in the AWS account pushes to a human.** Zero CloudWatch
   alarms, zero composite alarms, zero EventBridge rules, zero log metric
   filters, no Chatbot; the one SNS topic has zero subscribers. [M, live
   account — agrees with 4f's terraform reading and extends it to
   console-created resources.]
2. **The app's own observability lives in the database it observes.**
   `error_logs` and `request_latencies` are rows in the same Postgres. When
   the DB rejects auth, the request that failed cannot record its own
   failure. The DB-backed stack is structurally blind to exactly the
   outage that happened. [M for the mechanism; the outage is recoverable
   only from the RDS log, below.]
3. **The health check said "ok" throughout.** The image live during the
   outage returned `{"status":"ok"}` unconditionally. [M]

## 1. What exists — verified working, not merely configured

"Last fired on something real" means the most recent time the mechanism
recorded a genuine event, as opposed to existing or being scheduled.

| Mechanism | Collecting? | Last fired on something real | Anyone told? | Verdict |
|---|---|---|---|---|
| **RDS Postgres log → CloudWatch** | ✅ live, 160 MB, **retention: never expires** | 2026-07-31 17:11 — last of 573,039 auth failures [M] | ❌ no filter, no alarm [M] | **Works, unread.** The *only* surviving record of the outage |
| **`/ecs/palateful-api-prod` stdout** | ✅ 26 MB, 30 d retention | today; access log complete (172,802 health lines ≈ 172,800 in DB) [M] | ❌ [M] | Works, unread |
| **`request_latencies`** | ✅ 176k rows, ~30 d | today [M] | ❌ pull-only | Works, but see defects below |
| **`error_logs` `service=api`** | ✅ | 2026-09-20 19:40 — **1 row in the entire 30 d window** (a 400) [M] | ❌ pull-only | Works; genuinely quiet (cross-checked: stdout shows **0** 5xx in 30 d) [M] |
| **`error_logs` `service=worker`** | ✅ 60 rows | nightly 03:00 [M] | ❌ | **Noise, not failures** — `advance_recurrence_windows` audit rows mislabelled `service='worker'`; convention is `service='audit'` (4f measured: `per_rule_failures 0`) |
| **`/v1/health` DB probe** | ✅ deployed in `848311af` | never fired a failure — `health check db probe failed`: **0** in 30 d [M] | indirectly (ECS replaces task) | **Present and demonstrably blind to rotation** — pooled `SELECT 1` passes through a password change (§4) [M, 0a] |
| **`deploy-freshness.yml`** | ✅ daily | **today** — `Gap: 52 day(s); threshold: 7` → red, for the right reason [M] | ❌ red workflow, no notification path | **Works since 2026-09-20, into a void.** Only **4** scheduled runs have ever produced a verdict; the **49** before them died at `configure-aws-credentials` and measured nothing (see §1a) [M] |
| **`bin/prod-status`** | on demand | today — correctly shows 52 d stale image [M] | human-pulled | Works; requires someone to run it |
| **ALB target health** | ✅ `/v1/health`, 60 s, threshold 3 [M] | n/a | ❌ no alarm | Only as good as `/v1/health` |
| **CloudWatch alarms** | ❌ **none exist** [M] | — | — | **Not present** |
| **SNS / EventBridge / metric filters / Chatbot** | ❌ **none** [M] | — | — | **Not present** |
| **`cleanup_error_logs`** | ✅ | prunes `error_logs` at 30 d [M] | — | Works — and erases history (§5) |

### 1a. deploy-freshness — a red is not a verdict (corrected)

The first draft said "56 of 58 runs red, for the right reason". **That
generalised one run's log to 56 runs** — the same proxy error as reading a
red as a verdict. Classified every run by its failing step [M]:

| Runs | Event | Failed at | Meaning |
|---|---|---|---|
| **49** | schedule, 08-01 → 09-19 | `configure-aws-credentials` | **Died before measuring.** No verdict |
| **4** | schedule, 09-20 → 09-22 | Measure gap | **Correct verdict**: 52 d stale |
| 2 | manual, 07-31 | — (success) | Fix-branch runs |
| 1 | manual, 07-31 | Measure gap | Fix-branch run |
| 1 | manual, 07-31 | `configure-aws-credentials` | Fix-branch run |
| 1 | schedule, 08-06 | no failed step recorded | Unclassified |

So the detector **started working on 2026-09-20** (when #25 fixed its
credentials) and has correctly reported a stale prod four times since, to
no one. For its first seven weeks, every red meant "the check died", and
was indistinguishable from "prod is stale" unless someone opened the log.
(Credit: palateful-4f caught this; its count was 52 at credentials, mine
is 49 scheduled + 1 manual — the finding is the same either way.)

### Defects found in the collectors themselves

- **`request_latencies.user_id` is never populated** — NULL on all 173,143
  rows in 30 d, including authenticated endpoints like `/v1/users/me`. [M]
  No request can be attributed to a user, so "did Leo's request fail?" is
  unanswerable from this table. (4f independently hit the same wall.)
- **99.8% of `request_latencies` is the health check** — 172,800 of 173,143
  rows, exactly one per 15 s. [M] Real traffic is ~343 requests / 30 d. Any
  volume-based detector must exclude `/v1/health` or it measures nothing.
- **4xx never reaches `error_logs`** — 405/422/429/400 all appear in
  `request_latencies`, only one reached `error_logs`. [M, 4f concurs]

## 2. The DB-credential outage (`cldb01`) — full reconstruction

All [M] unless marked.

**Window:** first recorded **2026-04-22 02:31 UTC**, last **2026-07-31 17:11 UTC**.
**573,039** `password authentication failed for user "palateful"` lines in
the RDS log, all for that user. Peak ≈ 8,000/day, one every ~11 s, around the
clock. **Zero since 2026-07-31.** [M]

**Six episodes**, split on silences over 60 minutes (palateful-4f; the total
and the endpoints re-verified here):

| Episode | Duration |
|---|---|
| 04-22 02:30 → 04-22 03:45 | 1.2 h |
| 04-29 03:00 → 06-11 22:00 | **1,051 h (44 days)** |
| 06-17 05:30 → 06-21 06:40 | 97 h |
| 06-24 02:35 → 07-16 11:40 | 537 h |
| 07-22 03:45 → 07-27 16:50 | 133 h |
| 07-29 00:50 → 07-31 17:10 | 64 h |

**How the first draft got this wrong.** It reported "six weeks, 238,258,
starting 06-17". That count was correct for the window queried. The window
began about 06-14, which falls inside the silent gap between the second and
third episodes. So the query saw a clean-looking onset that wasn't one: a
correct number over a truncated window. That is the same class as the G3
count error. 4f caught it by querying the log group's whole retention.

**Caveat on "first recorded".** The RDS log group was **created 2026-04-21
14:50 UTC** [M], so the first failure it holds comes about 12 hours after log
export began. **04-22 is the earliest point that can be observed, not a
proven start.** Failures before 04-21 would not have been exported, so the
outage may be older.

**The outage predates the freeze.** The first recorded failure is four days
before prod froze on `c85e350` (2026-04-26). The freeze did not cause the
outage. It is why the outage kept going.

**Positive control, because an empty result is not a reading:** the same
Logs Insights query form returned 13 for `Connection reset by peer` (a
string visible in the raw tail) before its zero for `password
authentication failed` in the last 30 d was accepted. A first attempt using
a `parse` regex matched nothing at all and was **discarded**, not reported.

**Mechanism:**

1. **Weekly rotation.** CloudTrail shows the RDS-managed secret rotated by
   the RDS service role (`SLRSession`) on **07-01, 07-07, 07-15, 07-21,
   07-28** — weekly, the RDS-managed default. Today the rule reads 90 d; it
   was changed by `palateful-github-actions` (`RotateSecret`) on
   **2026-07-31**. [M]
2. **A running ECS task keeps the credential it started with.** New DB
   connections after a rotation fail auth.
3. **Rotations line up with failure onsets to the minute.** Failures had
   stopped on 07-27 16:52 and resumed **07-29 00:50 UTC — 19 minutes after
   the 07-29 00:31 rotation**. Earlier, they resumed **07-22 03:46 — 17
   minutes after the 07-22 03:29 rotation**. [M]
4. **Gaps are incidental restarts.** Failures stop (06-21, 07-16, 07-27)
   then return at the next rotation. [I — consistent with every gap; the ECS
   event history that would prove each restart has aged out]
5. **The health check could not notice.** Prod was frozen on `c85e350`
   (2026-04-26), whose `/v1/health` is literally `return {"status": "ok"}` —
   no DB access. [M]

**The part worth remembering:** the fix for exactly this failure —
`e74303f3`, 2026-05-03, "db probe in `/v1/health` + 90d password rotation
cadence" — was written **eleven days into the outage**, during its longest
episode. It sat undeployed behind the April freeze, and the outage continued
for another three months with the fix already on `main`. (The first draft
said "written six weeks *before* the outage began". That came from the
truncated window above and is wrong.) Its infra half (rotation) is applied
independently of app deploys; its app half (the probe) is not. **The
rotation it configured took effect; the guard it wrote did not.** [M for
the commit and freeze; I that the rotation half was the part in force]

### Can this surface to a user as "login failed"? — **No. Retracted.**

The first draft answered "yes, and it fits 'random'". **That was wrong**,
and it had been relayed toward Leo before it was caught. palateful-2d
refuted it from code; I verified each point before retracting [M]:

- **"Login failed. Please try again." is set in exactly one place** —
  `app/lib/features/auth/login_screen.dart:65` — and only when
  `AuthService.login()` returns `false`.
- **`AuthService.login()` makes no palateful API call.** It uses Auth0 web
  auth and on-device secure storage only. A database that cannot
  authenticate the app has no path into that code.
- **A 500 on `/v1/users/me` after sign-in lets the user in.**
  `_fetchUserAndCheckOnboarding()` swallows its error and routes to `/`.
- **A 500 never clears credentials either.** `_isAuthError`
  (`app/lib/main.dart:366`) is 401/403 only, so the outage did not look like
  a logout. (2d; rules out my second inference too.)

**What the outage *would* have looked like:** broken after login — data
failing to load, screens erroring. Leo might loosely remember that as
"login didn't work", but it **cannot** have produced the literal message.

**The error that caused this:** I reasoned from "the first authenticated call
needs the DB" to "login fails" without reading where the message comes from.
The server-side dependency was real; the jump across the client boundary was
not measured. 2d measured it.

**What still holds, and sharpens the auth track:** since 2026-07-31 the API
has recorded **zero 401s and zero 5xx** [M, cross-checked against stdout]. So
if Leo has seen "Login failed" since August, it is **definitively** not this
outage — it is the Auth0/client path 2d traced. When he last saw it is the
question that settles it.

## 3. Leo's complaints vs. the server-side detectors

| Complaint | What happened server-side | Would any server detector have caught it? |
|---|---|---|
| **"Random login failed"** | **Not the credential outage** — the message has no path to the API (§2, retracted). After 07-31: zero 401/5xx [M]. It is Auth0/client-side → **2d** (account-linking `api.access.deny()` is the prime suspect) | **Not collected anywhere.** `auth_service.dart` and `login_screen.dart` have no error reporting; `login()` swallows every exception into one string (4f, 2d) |
| **Credentials don't hold as long as they should** | Zero auth rejections server-side in 30 d [M]. **Not downstream of the outage** — a 500 never clears credentials (§2). 2d's root cause: `tryRestoreCredentials` wiped saved credentials on `RENEW_FAILED`, which the SDK raises for *any* failed renewal including a flaky network at launch — so a good refresh token was destroyed with no request and no 401 | **Not collected.** The restore catch does `debugPrint` and wipes the session |
| **Shopping cart broken for months** | `GET /v1/shopping-lists/{id}` returns **200**; the client crashes parsing `quantity` (Decimal serialized as a string). [M, cc] | **No — by construction.** The server did nothing wrong by its own lights. Zero 5xx, zero `error_logs`. The server-side answer to "was the API even called?" is **yes, and it succeeded**. The only server-visible symptom is **zero writes for weeks while reads continue** — see gap G5 |

**The cart and the credential outage fail differently, and that matters for
the fix:** the credential outage was *collected but unread* — a loud signal
nobody watched. The cart was *not collectable server-side at all* — a quiet
contract break the server cannot see. One needs alerting; the other needs a
contract test and a client-side detector (4f).

## 4. Forward risk — 2026-10-29

**The next scheduled rotation is 2026-10-29.** [M, `NextRotationDate`]

Deployed `848311af` has the DB probe, so this is not a repeat of the
`c85e350` blind spot. **But the pooled probe does not survive a rotation —
now measured.** [M, palateful-0a, 2026-09-22, live pg16 using the real async
pooled-engine shape `848311af` uses; `ALTER ROLE … PASSWORD` standing in for
the rotation]:

```
before rotation : pooled SELECT 1 -> OK (pool warmed)
ROTATED         : ALTER ROLE ... PASSWORD <new>
after rotation  : OLD pooled probe -> OK            <- stale task reports HEALTHY
after rotation  : new conn, start-time password -> InvalidPasswordError 28P01
after rotation  : NEW rsh102 probe -> AUTH_FAILED
```

PostgreSQL authenticates once at session start, and changing a role's
password does not terminate established sessions. So **the probe deployed
today would answer healthy through the 10-29 rotation** while the pool's next
fresh connection is rejected. The first draft cited this only as rsh102's
analysis; it was untested by anyone until 0a ran it.

A possible explanation for a detail of §2 — **[I], and explicitly unmeasured**:
the **17- and 19-minute** delays between rotation and first failure are about
what a pool cycling its connections would produce before it has to open a
fresh one. 0a's experiment showed that a pooled connection survives a password
change; it did **not** measure any pool's cycle time, and nothing rules out
other causes of the delay: connection lifetime limits, traffic-driven
checkouts, `pool_recycle`, or RDS-side behaviour. It stays inferred until
someone checks prod's actual pool recycle interval against those gaps. (0a
flagged its own first framing of this as overstated.)

**What rsh102 deliberately does *not* detect** — it fails open with 200 on
each, by design [M, from 0a's scope statement]:

- **A broken serving pool** (exhausted, or dead sockets after failover). The
  fresh probe passes while real requests fail. The old pooled check *did*
  catch this; rsh102's AC required removing it. **rsh102 trades seeing a
  broken pool for seeing a rotation** — the right trade for this story, not a
  free one.
- **DB unreachable** (timeout, refused, DNS, SG change, AZ loss). By design —
  but with G1 absent, **a total database outage reads `{"status":"ok"}`**.
- pg_hba rejection / missing role / login denied (`28000` with no auth
  message) — a restart cannot fix them.
- No DB configured at all (`selfheal1` Case 2); the worker (rsh107); secrets
  other than the RDS master.

The first two become gaps G10 and G11 below.

So whether 10-29 repeats the outage depends on rsh102 **deploying** before
then — and prod has not deployed in 52 days. **The guard landing on `main`
is not the guard being live**; that distinction is the whole of §2.

## 5. Gaps, ranked by what they would have caught

"Cheapest mechanism" means the smallest change that closes the gap, not the
ideal design. Split into the two kinds the coordinator asked for, because
they need different fixes.

### Collected but unread — the data exists; nothing tells a human

| # | Gap | Would have caught | Cheapest mechanism |
|---|---|---|---|
| **G1** | **No push channel exists anywhere** | Everything below. This is the multiplier | One SNS topic + one email/Slack subscription. Every other alert routes here. ~10 lines of terraform |
| **G2** | RDS log FATALs unread | **The six-week credential outage**, on its first minute. 238k lines | Log metric filter on `password authentication failed` (or any `:FATAL:`) → alarm at ≥1 → G1. The log already exists and never expires |
| **G3** | deploy-freshness red into a void | The 52-day freeze — and by extension the undeployed probe fix | Add a failure-notification step to the workflow, or have it push to G1. **The detector already works**; it needs a recipient |
| **G4** | API 5xx unread | Any server error. (0 in 30 d, so nothing missed recently [M]) | Metric filter on `" 5[0-9][0-9]` in API stdout → alarm → G1 |

### Not collected at all — needs new instrumentation

| # | Gap | Would have caught | Cheapest mechanism |
|---|---|---|---|
| **G5** | **No "write endpoint went silent" signal** | **The cart**, from the server side, without client instrumentation: reads on 09-14 and 09-20, zero writes since April. (cc's framing) | Scheduled query over `request_latencies`: a user-facing write endpoint with 0 writes in N weeks while its read endpoint is hit. Excludes `/v1/health` |
| **G6** | **No response-contract test** | **The cart**, and the May no-op fix (`a5c84386` patched a schema class no endpoint uses; its test tested the class, not the endpoint) | Contract test on the real endpoint's JSON asserting `quantity` is a number. cc is building it |
| **G7** | `request_latencies.user_id` never populated | "Did *Leo's* request fail?" — unanswerable today | Populate it in the latency middleware |
| **G8** | Observability shares fate with the DB | Any DB-auth or DB-down event recorded by the app itself | Structural. G2 is the cheap mitigation: the RDS log does not depend on app→DB auth |

**The failure class G8 belongs to is wider than the DB** — 4f's framing,
which I'd make the headline lesson: **the recorder depends on the thing that
broke, so the failure produces silence instead of a signal.** `error_logs`
lives in the DB that was rejecting auth. The client mirror needs a valid
token, and delivered **zero rows for four weeks** (08-23 → 09-19) with nobody
noticing. G2 catches the DB instance; U3 catches the class.
| **N1** | **Auth path reports nothing** (4f) | **Both of Leo's auth complaints.** `auth_service.dart` / `login_screen.dart` have no `ErrorReporter` calls; the restore catch wipes the session with a `debugPrint` | A handful of catch blocks → Crashlytics. (The `error_logs` mirror needs a token, so it can't take pre-auth failures.) **No fix is in flight for auth** |
| **U3** | **No absence alert** (4f) | Silence as a failure mode — the class *both* this outage and the client mirror belong to (below) | Alert when expected telemetry (`service='client'` rows, or the `BootSmokeTest` canary) is absent for N days while `/v1/health` reports the API up |
| **G10** | **Broken serving pool undetected after rsh102** (0a) | Pool exhaustion / dead sockets after failover | A separate pooled-path check, or a metric on request-level DB errors — not a health-probe change |
| **G11** | **DB unreachable reads `ok`** (0a) | A total database outage | **No new code.** rsh102 already logs every fail-open branch; add one CloudWatch metric filter on the phrase **`failing open`** → alarm → G1. Verified on `feat/dev-rsh102`, four branches all use it: `db probe: database unreachable, failing open` (`db_probe.py:270`, WARNING), `db probe: unclassified failure, failing open` (`:277`), `db probe: classifier raised … failing open` (`:252`), `health check: probe raised — failing open` (`health_router.py:41`). **One filter on the shared phrase covers all four**, including failure modes nobody has named yet. Can't be wired until rsh102 deploys. rsh102 can't close this itself without contradicting itself: making UNREACHABLE fail the health check *is* the outage (0a) **The filter turns the phrase into a contract, and nothing enforces it** (0a): if a message is later reworded to "falling back" or "degraded", that failure mode silently drops out of the alarm while every test still passes, since tests assert verdicts rather than log text. **Wiring the filter must ship with a test asserting every fail-open branch emits `failing open`**, placed beside the filter it protects. That test belongs to G11, not rsh102. (A fifth grep hit, `db_probe.py:238`, is a docstring and is never emitted. `probe_sync` goes through the same `_classify`, so the worker path hits the same lines once rsh107 uses it — 0a, verified on its branch.) |
| **G12** | **Silent-catch CI guard can't see auth** (4f's N5 — same finding, one entry) | The swallowed exceptions in N1 | `tools/no-silent-catch-check.sh` scans only `app/lib/features/**/services/` (line 29, 82); `auth_service.dart` is in `app/lib/core/`. Widen the scan. Same shape as a devx guard that checks only `dev/` specs |
| **G9** | Unauthenticated route sweeps unexamined | 2026-09-11 and 09-14: ~65 routes each in seconds, including admin routes (405/422, all rejected) [M] | Security question, not detection — flag, don't build yet. Nothing got through |

### Retention — the gap that decides whether you can investigate at all

App-side tables prune at **30 days** (`cleanup_error_logs.py`; the others
match) [M]. The credential outage ended 53 days ago, so **every app-side
record of it is gone.** It is reconstructable **only** because the RDS log
group happens to have no expiry. The API log group expires at 30 d. Had the
RDS group matched, the outage would be unrecoverable and this section would
read "unknown". Keep RDS logs indefinitely; consider a longer window for
API stdout.

## 6. Recommended order — merged with palateful-4f

One list, agreed with 4f, so Leo gets one ordering rather than two:

1. **G1** — a push channel exists at all. Multiplier. (Pipe: here. "Is anyone told": 4f.)
2. **G2** — RDS FATAL metric filter → alarm. Catches the six-week outage on minute one.
3. **N1** — auth path reports to Crashlytics. **A multiplier on zero is zero**: G1 can't forward a signal that doesn't exist, and two of Leo's three complaints are auth with no fix in flight.
4. Client parse-failure / recurrence alert (4f). Catches the cart, and the May no-op fix recurring.
5. **G3** — deploy-freshness gets a recipient. Working since 09-20.
6. **U3** — absence alert on expected telemetry. Catches the silence class.
7. **G5** — write endpoint silent while reads continue.
8. **G6** — contract test on real endpoint JSON (cc, in flight).
9. Promote client `area`/`operation` out of `stack_trace` (4f).
10. **G7** — populate `request_latencies.user_id`.

Then G10, G11, G12. Tail items are in 4f's spec.

**Crashlytics is the only possible push channel left in the system** now that
the live AWS account is ruled out, and nobody can verify from here whether its
non-fatal alerts are on (no read API). It decides whether the cart
`_TypeError` ever emailed anyone. On Leo's checklist via 4f.

**And land + deploy rsh102 before 2026-10-29.** That is a date, not a
priority.

## Measurement caveats

- **`Connection reset by peer` lines in the RDS log are almost certainly
  self-inflicted.** They cluster at 15:24–15:39 UTC today, matching my own
  `bin/prod-script` (ECS Exec) sessions opening and closing DB connections.
  **Not a prod finding.** Recorded so nobody chases them.
- The ECS service event history is short (it shows only 6-hourly
  steady-state events), so each restart behind each outage gap is inferred,
  not proven.
- `request_latencies` and `error_logs` cover only ~30 d. Any conclusion about
  *absence* is bounded to that window.

## Hand-offs

- **palateful-4f (client + alerting):** agree on G1 — live account confirms
  your terraform finding, and adds that nothing was created in the console
  either. 4xx→`error_logs` gap and audit-row mislabelling are yours as
  measured; I've reused them with credit.
- **palateful-2d (auth):** the credential outage spans **first recorded 04-22 → 07-31** (not 06-17, corrected);
  "login failed" inside it has a server-side cause. **After 07-31 the API
  recorded zero 401s and zero 5xx** — any later login failure is Auth0- or
  client-side.
- **palateful-cc (cart):** server side agrees with you exactly — 200, zero
  server signal. G5 is your point 4 formalised.
- **palateful-0a (rsh102):** 2026-10-29 is the date it needs to be *deployed*
  by, not merged by.

## Status log
- 2026-09-22T16:00 — research complete. All prod reads under `SET
  TRANSACTION READ ONLY`; Secrets Manager metadata only. One reading was
  discarded as invalid (a `parse`-regex query that matched nothing) and
  replaced with a positive-controlled query before any conclusion was drawn
  from it. One inference was retracted mid-research: a burst of "4xx = 2"
  across ~10 authenticated endpoints looked like two failed logins until the
  status codes were read — they were 405/422 from a scripted route sweep.
  The API recorded zero 401s in the window.
- 2026-09-22T17:30 — **corrections, before merge.** (1) **Retracted** "the
  outage can surface as 'login failed'": 2d showed from code that the message
  has no path to the API, and a 500 neither blocks login nor clears
  credentials. Verified each point before retracting. The inference crossed
  the client boundary without measuring it. (2) **Corrected G3's "56 of 58
  runs correctly red"** — it generalised one log to 56 runs; classified all 58
  by failing step: 49 died at credentials, only 4 are verdicts. 4f caught it.
  (3) **Upgraded §4 from inferred to measured** — 0a demonstrated on live pg16
  that the pooled probe passes through a password change while fresh
  connections get 28P01. (4) Added N1, U3 (4f), G10, G11 (0a), G12 (2d) and
  adopted the merged order. Three of those four corrections came from peers
  checking claims I had marked as findings; the fourth came from one I had
  correctly marked as unverified.
- 2026-09-22T18:10 — G11 made concrete: no new code needed. Every fail-open
  branch in rsh102 logs the phrase `failing open` (four sites, verified on the
  PR branch), so one metric filter covers them all. Nearly recorded the
  opposite: my first two searches missed `db_probe.py:270`. The first only
  covered `services/api/src`; the second found the line but my `log|warn`
  filter dropped it, because the message string and the `logger.warning(`
  call are on different lines. 0a's quote was exact. Pool-cycle reading kept
  at [I] with 0a's alternative explanations listed.
- 2026-09-22T18:20 — attribution fix: G12 is **palateful-4f's** (its N5), not
  2d's. 2d relayed it and says so. It is one finding under two labels, so it
  is not double-counted in the merged list. It is measured, not relayed: the
  scan root (`no-silent-catch-check.sh:29`) and walk (`:82`) were read before
  it was added.
- 2026-09-22T18:40 — G11 amended (0a): the metric filter makes `failing open`
  a contract with no enforcement, so the change that wires the filter must
  include a test pinning the phrase on every fail-open branch. Otherwise a
  harmless-looking rewording silently removes a failure mode from the alarm,
  which is the same shape as every detector this spec found.
- 2026-09-22T19:00 — **research complete; marked `done`** (was `ready`, which made a
  research artifact claimable as a single implementable story). Top gaps
  filed as individually claimable specs: alrt1, rdsal1, authrep1, prsal1, dfrcp1, absal1, tfgate1. `tfgate1` is new,
  found while starting alrt1: Terraform-only changes merged to main are never
  applied.
- 2026-09-22T20:30 — **headline corrected: about 100 days, not six weeks.**
  palateful-4f queried the RDS log group's whole retention and found 573,039
  failures, first recorded 2026-04-22 02:31 UTC, in six episodes. I
  re-verified the total and the endpoints. The first draft's 238,258 / 06-17
  was a correct count over a truncated window: it started inside the gap
  between the second and third episodes. Two knock-on corrections: (a) the
  probe fix `e74303f3` was written *eleven days into* the outage, not "six
  weeks before" it; (b) the outage **predates** the 04-26 freeze, which
  prolonged it but did not cause it. One caveat added from verification: the
  log group was created 2026-04-21 14:50, so 04-22 is the observable floor,
  not a proven start.
