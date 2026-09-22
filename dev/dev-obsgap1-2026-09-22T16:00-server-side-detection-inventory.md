---
hash: obsgap1
type: dev
created: 2026-09-22T16:00:00-06:00
title: Server-side production detection — what exists, what works, what would have caught Leo's complaints
from: coordinator dispatch (leonidbelyi-41), 2026-09-22 — "harden palateful so production issues get detected"
status: ready
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

**Palateful's database could not authenticate its own application for six
weeks — 238,258 failed logins between 2026-06-17 and 2026-07-31 — and not
one mechanism told a human.** [M] It ended because a deploy on 07-31 happened
to pick up the current credential, not because anything noticed. It is
**scheduled to be able to recur on 2026-10-29**, the next credential
rotation. [M for the date; I for the recurrence — see §4.]

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
| **RDS Postgres log → CloudWatch** | ✅ live, 160 MB, **retention: never expires** | 2026-07-31 17:11 — last of 238,258 auth failures [M] | ❌ no filter, no alarm [M] | **Works, unread.** The *only* surviving record of the outage |
| **`/ecs/palateful-api-prod` stdout** | ✅ 26 MB, 30 d retention | today; access log complete (172,802 health lines ≈ 172,800 in DB) [M] | ❌ [M] | Works, unread |
| **`request_latencies`** | ✅ 176k rows, ~30 d | today [M] | ❌ pull-only | Works, but see defects below |
| **`error_logs` `service=api`** | ✅ | 2026-09-20 19:40 — **1 row in the entire 30 d window** (a 400) [M] | ❌ pull-only | Works; genuinely quiet (cross-checked: stdout shows **0** 5xx in 30 d) [M] |
| **`error_logs` `service=worker`** | ✅ 60 rows | nightly 03:00 [M] | ❌ | **Noise, not failures** — `advance_recurrence_windows` audit rows mislabelled `service='worker'`; convention is `service='audit'` (4f measured: `per_rule_failures 0`) |
| **`/v1/health` DB probe** | ✅ deployed in `848311af` | never fired a failure — `health check db probe failed`: **0** in 30 d [M] | indirectly (ECS replaces task) | Present but **not proven to catch rotation** — pooled `SELECT 1` [I, per rsh102] |
| **`deploy-freshness.yml`** | ✅ daily | **today** — `Gap: 52 day(s); threshold: 7` → red, for the right reason [M] | ❌ red workflow, no notification path | **Works correctly, into a void.** 56 of 58 runs red [M] |
| **`bin/prod-status`** | on demand | today — correctly shows 52 d stale image [M] | human-pulled | Works; requires someone to run it |
| **ALB target health** | ✅ `/v1/health`, 60 s, threshold 3 [M] | n/a | ❌ no alarm | Only as good as `/v1/health` |
| **CloudWatch alarms** | ❌ **none exist** [M] | — | — | **Not present** |
| **SNS / EventBridge / metric filters / Chatbot** | ❌ **none** [M] | — | — | **Not present** |
| **`cleanup_error_logs`** | ✅ | prunes `error_logs` at 30 d [M] | — | Works — and erases history (§5) |

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

**Window:** 2026-06-17 05:32 UTC → 2026-07-31 17:11 UTC. **238,258**
`password authentication failed for user "palateful"` lines in the RDS log;
**every FATAL in the 90-day window is one of them.** Peak ≈ 8,000/day — one
every ~11 s, around the clock. **Zero since 2026-07-31.**

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
cadence" — was written **six weeks before the outage began**. It sat
undeployed behind the April freeze. Its infra half (rotation) is applied
independently of app deploys; its app half (the probe) is not. **The
rotation it configured took effect; the guard it wrote did not.** [M for
the commit and freeze; I that the rotation half was the part in force]

### Can this surface to a user as "login failed"? — Yes, and it fits "random"

- Any request needing a *new* DB connection fails with a 500 during the
  window. The app's first authenticated call after sign-in, `GET
  /v1/users/me`, needs the DB to resolve the user. [M for the dependency]
- **The pattern matches "random".** Working after an incidental restart,
  broken within a week at the next rotation, working again after the next
  restart — from the outside, logins fail on some days and not others with
  no visible cause. [I]
- **What I cannot establish server-side:** whether Leo's specific failures
  fell inside the window. The API cannot attribute requests to users
  (`user_id` NULL, above), and the outage's own requests could not be
  recorded (structural blindness). Needs his timestamps, or 2d's Auth0-side
  view. [gap, not a finding]
- **Since 2026-07-31 the API has recorded zero 401s and zero 5xx.** [M] So
  any "login failed" *after* 07-31 is **not** this — it is either Auth0-side
  or client-side. → **2d.**

## 3. Leo's complaints vs. the server-side detectors

| Complaint | What happened server-side | Would any server detector have caught it? |
|---|---|---|
| **"Random login failed"** | Likely the credential outage above, **within 06-17 → 07-31**. After 07-31: zero 401/5xx — not server-side. [M/I as marked] | **The data existed** — 238k FATALs in the RDS log. **Nothing read it.** Collected-but-unread |
| **Credentials don't hold as long as they should** | No server evidence either way; the API recorded zero auth rejections in 30 d [M]. Plausibly Auth0 session/refresh config [I] — **2d's track**. Possibly also downstream of the outage if the app clears auth on a failed `/users/me` [I, 4f can confirm] | Not collected server-side — auth sessions live in Auth0 |
| **Shopping cart broken for months** | `GET /v1/shopping-lists/{id}` returns **200**; the client crashes parsing `quantity` (Decimal serialized as a string). [M, cc] | **No — by construction.** The server did nothing wrong by its own lights. Zero 5xx, zero `error_logs`. The server-side answer to "was the API even called?" is **yes, and it succeeded**. The only server-visible symptom is **zero writes for weeks while reads continue** — see gap G5 |

**The cart and the credential outage fail differently, and that matters for
the fix:** the credential outage was *collected but unread* — a loud signal
nobody watched. The cart was *not collectable server-side at all* — a quiet
contract break the server cannot see. One needs alerting; the other needs a
contract test and a client-side detector (4f).

## 4. Forward risk — 2026-10-29

**The next scheduled rotation is 2026-10-29.** [M, `NextRotationDate`]

Deployed `848311af` has the DB probe, so this is not a repeat of the
`c85e350` blind spot. But the probe runs `SELECT 1` through the connection
pool, and a pooled connection authenticated before a rotation stays valid —
Postgres checks the password only at connect time. **rsh102 (PR #29, open,
being landed by 0a) exists precisely because the pooled probe can pass while
new connections fail.** [I — this is rsh102's analysis, which I have not
independently reproduced]

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
| **G9** | Unauthenticated route sweeps unexamined | 2026-09-11 and 09-14: ~65 routes each in seconds, including admin routes (405/422, all rejected) [M] | Security question, not detection — flag, don't build yet. Nothing got through |

### Retention — the gap that decides whether you can investigate at all

App-side tables prune at **30 days** (`cleanup_error_logs.py`; the others
match) [M]. The credential outage ended 53 days ago, so **every app-side
record of it is gone.** It is reconstructable **only** because the RDS log
group happens to have no expiry. The API log group expires at 30 d. Had the
RDS group matched, the outage would be unrecoverable and this section would
read "unknown". Keep RDS logs indefinitely; consider a longer window for
API stdout.

## 6. Recommended order

**G1 first, because it is a multiplier:** without a push channel, every other
gap closes into the same void deploy-freshness already fires into. Then
**G2** (catches the outage class, and the log already exists), **G3** (the
detector already works), **G5** (catches the cart server-side at zero client
cost). G6 is being built by cc. G7 before anyone needs per-user forensics.

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
- **palateful-2d (auth):** the credential outage window is **06-17 → 07-31**;
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
