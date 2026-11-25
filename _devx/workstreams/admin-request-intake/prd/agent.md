# PRD — Admin Request Intake

<!-- Stage: PRD. Gate: `devx gate prd 1e84ad`. Every concrete item gets a
     stable ID (G-/UC-/CAP-/FR-). IDs are never renumbered. Traceability is
     by ID, not by prose. -->

<!-- Seed: docs/admin-request-pipeline.md on branch
     docs/admin-request-pipeline (PR #124, head 53cb59a4). Leo accepted its
     four recommendations and changed one thing: a thin vertical slice
     first, then widen along the design's six-phase shape.
     Revised 2026-11-24 (`devx revise 1e84ad --touched prd`): Leo added a
     second intake (faults reported by the running system) and routing
     (fit / create / split / combine), relayed by the orchestrator tab. -->

## Problem

Palateful's admins have no way to ask for a change to Palateful that turns
into devx work. Today a request arrives by message, and Leo re-types it into
a workstream by hand. The design in PR #124 proposes a pipeline: an admin
files a request in the panel, a listener on Leo's laptop sees it, Leo adopts
it, and devx scopes and builds it. Leo's priority, in his words: "literally
just want this working".

The pipeline crosses two repos. Palateful holds the request (a database row,
an admin endpoint, two operator scripts and a panel screen). The listener
("the bridge") lives in `~/.claude/orchestrator`. devx's single-repo
invariant (O-5, `devx:v2/07-decisions.md:390`) keeps one workstream inside
one repo, so **this workstream is Palateful's half only**. The bridge is an
external dependency, and this PRD pins the contract between the two halves
(§ Bridge contract) precisely enough that the bridge can be built against it
without reopening this document.

A request is **untrusted text**. Until Leo adopts it from his laptop, no
session that can write may read it, and none of it may reach a surface the
orchestrator reads. The devx gates cannot enforce that: Gate 1 checks
structure, and a malicious request written in EARS passes it. The laundering
step is Leo's adoption, not a gate.

**A second intake: faults.** Leo wants the running system to report what
is broken, so that a fault can become an investigation the same way a
request becomes work. Palateful already records server errors in
`error_logs`. A fault differs from a request in two ways that set this
PRD's shape:

- **Machine-written, but not trustworthy.** Exception messages, stack
  traces and request paths echo whatever the caller sent, and `client` rows
  are written through a user endpoint
  (`services/api/src/api/v1/user/record_client_error.py:63`). So a fault
  signal carries only fields that server code chose: never a message, a
  trace's text or a raw path.
- **Unbounded volume.** One admin types a few requests a month; one bad
  deploy writes thousands of rows an hour. Deduplication into signatures
  and a hard cap on what one poll returns matter more here than laundering
  does.

**Routing.** Leo does not want one workstream per item: "see if it can fit
into a similar workstream … and then when it's different enough … split
workstreams". Four operations are first-class: **fit** an item into an open
workstream, **create** one when nothing fits, **split** one that has grown
incoherent, **combine** two that turned out to be the same. devx has a
primitive only for create. Split and combine are devx engine work, and the
routing decision is orchestrator work; both are other repos (O-5). This PRD
specifies the signals Palateful supplies and the row bookkeeping routing
needs, and names the rest as external gates.

**Premise changed twice since the design was written.** The design's §11.1
found that the `production` environment had no protection rules. At the
start of this session it had a required reviewer; by the revision it had
none again: Leo removed it and chose automatic deployment on merge (0
protection rules, checked with
`gh api repos/LeoTheMighty/palateful/environments/production`). So the
merge is literally the deploy, with nothing behind it, and MERGE is the
only human checkpoint between agent work and production.

**The backend is quiet.** The last commit touching `services/`,
`libraries/` or `terraform/` is `cd6a3c3e` (2026-09-24); none of the 14
commits on `main` since then touched them. A fault intake will mostly
report on code that has not changed in two months, so it is sized for a
trickle of new signatures, not for a busy deploy pipeline.

## Goals

- **G-1** (slice works): By 2026-12-31, at least 1 request submitted from
  the production admin panel has reached `accepted` through the bridge, with
  0 hand edits to its `dev_requests` row.
- **G-2** (prompt latency): From the first production request through
  2027-02-28, 100% of requests reach `received` within 10 minutes of their
  `created_at`.
- **G-3** (containment): Through 2027-02-28, 0 occurrences of
  submitter-written text in the output of any channel call the bridge makes
  before adoption. The containment eval (E-2) fails 0 times on `main`.
- **G-4** (operator-only adoption): Through 2027-02-28, 100% of rows that
  reached `accepted` carry a matching operator-channel audit row, and 0 HTTP
  routes can set a bridge-owned status.
- **G-5** (widening — visible state): By 2027-02-28, 0 requests sit in
  `submitted` or `received` for more than 7 days, and 100% of requests filed
  after the panel list lands show their current state in the panel.
- **G-6** (slice 2 — faults): By 2027-04-30, 100% of new server-side error
  signatures reach the bridge as exactly 1 signal within 10 minutes of
  their first occurrence, and 0 fault signals carry message, trace or
  raw-path text.
- **G-7** (routing): By 2027-05-31, at least 1 adopted item has been routed
  into an existing workstream by fit, and 0 fault signatures are attached
  to more than 1 open workstream.

## Non-goals

- **Building the bridge.** It lives in `~/.claude/orchestrator` and is an
  external gate of this plan (O-5). This workstream creates no artifact in
  that repo and edits nothing there.
- **Auto-adopt, auto-merge, panel approval.** The two human checkpoints are
  ADOPT and MERGE (Decision 1). With no deploy approval left, the merge is
  the deploy, so any future auto-merge proposal carries production on its
  own.
- **Building the router, or split and combine.** The routing decision runs
  in the orchestrator, and split / combine are devx engine primitives. Both
  are external gates. This workstream supplies signals and row bookkeeping.
- **AWS-side fault sources** (CloudWatch alarms, the `palateful-prod-alerts`
  SNS topic, ECS events). The laptop reads them with its own AWS
  credentials, so collecting them is the bridge's work. Palateful supplies
  the database-side source.
- **Client-reported errors as fault signals.** `client` rows are written
  through a user endpoint, so their fields are user-controlled. Slice 2
  uses server-emitted rows only.
- **Routing by classifying text.** An LLM reading unadopted text breaks
  containment, and admin or stack-trace text is the weakest signal there
  is (FR-21).
- **The design's slices 2 and 3:** the CI `request-guard`, the request-tab
  environment scrub and hook, identity separation, feedback-to-request
  promotion. They bound autonomy that slice 1 does not grant.
- **An LLM pre-scoping pass.** It duplicates `/devx prd` and weakens what
  Leo reads (design §4.3).
- **Reusing `user_feedbacks` or `Suggestion`.** `user_feedbacks` is user
  feedback with CHECK-constrained statuses and an admin push fan-out;
  `Suggestion` is AI meal suggestions. Requests get their own table
  (Decision 3).
- **Push notifications about requests.** Leo hears through the bridge;
  admins read state in the panel.
- **Any change inside devx.** D-10 holds: devx never learns that a request
  came from Palateful.
- **Targets other than Palateful.** `target` has one value.

## Users

- **Primary — submitting admin**: one of the handful of known Palateful
  admins. Files a request from the panel and later watches its state. Any
  admin may submit, because submitting grants nothing (Decision 4).
- **Primary — the operator (Leo, at the laptop)**: reads a request outside
  any LLM session, then adopts or declines it through an orchestrator
  question. Only the operator may adopt (Decision 4).
- **Secondary — the bridge**: a non-LLM launchd program in the orchestrator
  repo. It reads and writes rows only through the operator channel, under
  the contract below.
- **Secondary — the running system**: the API, worker and push services,
  whose server-side errors in `error_logs` become fault signals.
- **Secondary — the router**: orchestrator logic (external) that decides
  fit / create / split / combine from the signals this workstream supplies,
  with Leo confirming at adoption.
- **Anti-persona**: non-admin users; any LLM session before adoption; anyone
  holding a stolen admin session (Leo's included). None of them may cause
  agent work.

## Use cases

Tags: **[slice]** is the thin vertical slice that proves the whole path;
**[widening]** follows once the slice works live; **[slice 2]** is the fault
intake, after the widening; **[routing]** is the row bookkeeping routing
needs, alongside slice 2.

- **UC-1** [slice]: An admin files a request (title, body, optional
  done-when) from the panel and gets back its id.
- **UC-2** [slice]: The bridge notices a new request and acknowledges it
  (`received`) without receiving any of its text, then prompts Leo.
- **UC-3** [slice]: Leo reads the request's text in a plain terminal or (once
  it exists) the panel — never inside an LLM session — and decides.
- **UC-4** [slice]: Leo adopts the request. The bridge fetches its content
  once, checks it against the hash taken at submission, quarantines it on
  the laptop and marks the row `accepted`.
- **UC-5** [slice]: Leo declines the request with a reason, and nothing is
  created in any repo.
- **UC-6** [slice]: A submitter who loses admin before adoption has the
  request withdrawn, and it is never adopted.
- **UC-7** [widening]: An admin sees their requests and each one's state in
  the panel, and can cancel one before adoption.
- **UC-8** [widening]: The bridge reflects pipeline progress (scoping …
  shipped, waiting on Leo) onto the row, and the panel shows it.
- **UC-9** [slice 2]: A new server-side error signature appears, and the
  bridge receives one collapsed signal for it (service, error type, route
  template, code locations, count) with no message or trace text.
- **UC-10** [slice 2]: Leo adopts a fault. Its sample messages and traces
  cross to the laptop once, into quarantine, and it becomes a tracked row
  like a request.
- **UC-11** [routing]: When Leo adopts an item, the router proposes fit
  (with the overlapping workstream and the shared files) or create, and Leo
  confirms.
- **UC-12** [routing]: When a workstream is split or two are combined, each
  affected row follows its work, so the panel and the signature index
  still say where every item lives.

## Capabilities

- **CAP-1**: Durable request storage whose text is normalized at submission
  and never changes afterwards, with a content hash over everything an agent
  will later read.
- **CAP-2**: Admin-only submission over the API, rate-limited per admin.
- **CAP-3**: An operator-only channel (`bin/prod-script`, which needs the
  laptop's AWS credentials) for reading and transitioning requests. No HTTP
  route can adopt.
- **CAP-4**: Containment: every channel call the bridge makes before
  adoption returns no submitter-written text.
- **CAP-5**: A validated status state machine, compare-and-set, with one
  audit row per applied change.
- **CAP-6** [widening]: Panel visibility of requests and their state, with a
  staleness hint when the listener is quiet.
- **CAP-7** [slice 2]: Bounded, deduplicated fault signals built only from
  fields server code chose.
- **CAP-8** [routing]: Routing signals (code locations, signatures, the
  workstream each row belongs to) and a validated way to move a row
  between workstreams.

## Feature requirements

### FR-1: `dev_requests` storage [slice]

A new table `dev_requests`, created by one migration, holding:

| Group | Columns |
|---|---|
| Identity | `id` (UUID PK), `submitter_id` (FK `users.id`, `ON DELETE SET NULL`; for an admin row, null reads as revoked) |
| Source | `source` (CHECK `admin`/`fault`, default `admin`), `fault_signature` (64 hex; CHECK: present exactly when `source = 'fault'`) |
| Submitter-written, immutable | `title` (1–120 chars), `body` (1–4000), `done_when` (null or 1–1000) |
| Integrity | `content_sha256` (64 lowercase hex, FR-2) |
| Labels | `target` (CHECK `= 'palateful'`), `priority` (null or `low`/`normal`/`high`, advisory) |
| Pipeline | `status` (CHECK over the full FR-12 enum from day one), `status_detail` (null; written only by FR-17), `workstream`, `spec_hash`, `pr_urls` (JSONB list, default `[]`) |
| Timestamps | `created_at`, `updated_at`, `adopted_at`, `synced_at` |

The status CHECK carries every status in FR-12, and the source columns
exist, from the first migration, so neither the widening nor slice 2 needs
a second migration. Slice 1 writes only `source = 'admin'`. Length limits are CHECK constraints
as well as API validation.

### FR-2: Normalization and content hash [slice]

At submission the server, not the client, normalizes `title`, `body` and
`done_when`: Unicode NFKC, then removal of every character in categories
`Cc` and `Cf` except `\n` and `\t` (this drops zero-width and bidi-override
characters), then trimming of leading and trailing whitespace. A field that
is empty after normalization is rejected (422).

`content_sha256` is the lowercase hex SHA-256 of the UTF-8 bytes of
`json.dumps({"title": t, "body": b, "done_when": d}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))` over the normalized values (`d` is
JSON `null` when absent). The hash covers every submitter-written field,
because the PRD agent reads all three. This widens the design's
`body_sha256`.

### FR-3: Create endpoint [slice]

`POST /v1/admin/dev-requests`, behind `require_admin_async`.

- Body: `title`, `body`, optional `done_when`, optional `priority`. Unknown
  keys → 422 (`extra="forbid"`), so a client cannot send `status`,
  `submitter_id` or any pipeline field.
- The row is always created with `status = 'submitted'`, `target = 'palateful'` and `submitter_id` = the caller.
- Response 201: `{id, id8, status, content_sha256, created_at}`, where `id8`
  is the first 8 hex characters of the id.
- Non-admin → 403. Over-length or blank-after-normalization → 422.
- No push fan-out and no Celery task. Leo hears through the bridge.

### FR-4: Rate limit [slice]

At most 5 creates per admin per rolling hour, using the in-memory pattern of
`services/api/src/api/v1/user/create_user_feedback.py:41-56`. The 6th call
returns 429 with `retry_after_s` and creates no row.

### FR-5: `bin/prod-script` forwards arguments [slice]

`bin/prod-script <script.py> [args…]` sets `sys.argv` inside the ECS task to
`[<script.py>, args…]` before the script runs. Today it forwards nothing
(`bin/prod-script:14`, `SCRIPT="${1:-}"`), so a parameterized script cannot
be reached at all. A call with no extra arguments behaves exactly as today.
Arguments travel inside the base64 payload, never through shell
interpolation.

### FR-6: Record framing [slice]

`bin/prod-script` returns the task's stdout and stderr merged through a TTY,
with CRLF line ends, keepalive escape codes (`\x1b[0C`, every 0.5 s,
`bin/prod-script:85-95`) and the runner's own banner lines. So every
machine-readable line the two scripts print is:

- the literal prefix `DEVREQ1 ` followed by one JSON object, serialized with
  `ensure_ascii=True, sort_keys=True, separators=(",", ":")`, so the line is
  pure ASCII;
- written with one `write` call and flushed.

Every run ends with exactly one `end` record:
`{"kind":"end","v":1,"ok":<bool>,"count":<n>,"error":<code|null>}`, where
`count` is the number of non-`end` records in the run.

A consumer strips CSI sequences (`\x1b\[[0-?]*[ -/]*[@-~]`) and trailing
`\r`, keeps only lines matching `^DEVREQ1 (\{.*\})$`, and treats the run as
**failed** if there is no `end` record, more than one, a `count` mismatch,
`ok: false`, or any record whose `v` it does not know. It makes no state
change on a failed run. The process exit code is not part of the contract.

Error codes are enums, never exception text, because an exception message
can carry row data.

### FR-7: Read script — `poll` [slice]

`services/api/scripts/dev_requests_read.py poll` (read-only, no audit row,
no write of any kind) emits one record per row whose status is not terminal
(FR-12), ordered by `created_at`:

`{"kind":"request","v":1,"id","id8","source","fault_signature","status","content_sha256","submitter_id","submitter_is_admin","created_at","updated_at","adopted_at","workstream","spec_hash","pr_urls"}`

`submitter_is_admin` is `false` when `submitter_id` is null. Timestamps are
ISO-8601 UTC. The record carries **no** `title`, `body`, `done_when`,
submitter email or name, and neither stdout nor stderr carries any of them
anywhere in this mode.

Both scripts read `DATABASE_URL` and build their own engine, as
`services/api/scripts/inspect_user_push.py` does, so they run the same way
standalone and under `bin/prod-script`.

### FR-8: Read script — `adopt` [slice]

`dev_requests_read.py adopt <id> <expected_sha256>` is read-only. It emits
one record

`{"kind":"adopt","v":1,"id","id8","content_sha256","submitter_id","title","body","done_when"}`

only when all of these hold: the row exists; its status is `submitted` or
`received`; its stored hash, the hash recomputed from its stored text (FR-2)
and `expected_sha256` are equal; its submitter is non-null and currently an
admin. Otherwise it emits no `adopt` record and ends with `ok: false` and
`error` ∈ {`invalid_argument`, `not_found`, `wrong_status`, `sha_mismatch`,
`submitter_revoked`}. Adopting is a separate write (FR-11).

### FR-9: Read script — `show` [slice]

`dev_requests_read.py show <id>` prints one request's title, body,
done-when, status and hash as plain text for a human, under a banner saying
it must not be run inside an LLM session. It is how Leo reads a request in
the slice, before the panel detail screen exists (FR-16). The bridge never
calls it (FR-13).

### FR-10: Read script — `metrics` [slice]

`dev_requests_read.py metrics` emits one record
`{"kind":"metrics","v":1,"total","by_status","received_lag_s_p50","received_lag_s_max","stale_undecided","accepted_without_audit"}`.
The lags run from `created_at` to the `received` audit row;
`stale_undecided` counts rows in `submitted` or `received` older than 7
days; `accepted_without_audit` counts rows that reached `accepted` with no
matching audit row. It is the measure for G-1, G-2, G-4 and G-5.

### FR-11: Write script — `transition` [slice]

`services/api/scripts/dev_requests_write.py transition <id> <from> <to> [--sha <hex64>] [--reason <code>]` applies one status change.

- **No free text.** Every argument is validated: `id` a UUID; `from`/`to` in
  the FR-12 enum; `--sha` 64 lowercase hex; `--reason` in {`duplicate`,
  `wont_do`, `unclear`, `unsafe`, `submitter_revoked`}. Anything else →
  `invalid_argument`, nothing written.
- **Compare-and-set, idempotent.** In one transaction, with the row locked:
  if the current status equals `to`, report `changed: false` and write
  nothing; if it equals `from` and `(from, to)` is an edge FR-12 gives the
  bridge, apply it; if the edge exists but the current status is something
  else → `conflict`; if the edge does not exist → `illegal_transition`.
- **`→ accepted`** also requires `--sha` and re-checks it as FR-8 does
  (`sha_mismatch`, `submitter_revoked`), and stamps `adopted_at`.
- **`→ declined`** requires a decline reason; **`→ withdrawn`** requires
  `submitter_revoked`.
- **Audit.** Each applied change writes exactly one `error_logs` row
  (`service="audit"`, `error_type="DevRequestTransition"`) in the same
  transaction, with a message composed only of the id8, the two statuses and
  the reason code. A no-op writes none.
- Every applied change stamps `updated_at` and `synced_at`.
- Output: `{"kind":"transition","v":1,"id","id8","from","to","changed"}`
  then `end`. Refusals end `ok: false` with `error` ∈ {`invalid_argument`,
  `not_found`, `conflict`, `illegal_transition`, `sha_mismatch`,
  `submitter_revoked`, `db_error`}.

### FR-12: Status set and who may move it

Status enum: `submitted`, `received`, `accepted`, `declined`, `withdrawn`,
`scoping`, `designing`, `planning`, `building`, `waiting_on_leo`, `shipped`,
`stopped`, `reverted`.

Terminal (left out of `poll`): `declined`, `withdrawn`, `shipped`,
`stopped`, `reverted`. `shipped` may still move to `reverted`.

| Edge | Made by | Arguments | Phase |
|---|---|---|---|
| (new) → `submitted` | API create (FR-3) | — | slice |
| `submitted` → `received` | bridge | — | slice |
| `submitted`/`received` → `accepted` | bridge, on Leo's adopt | `--sha` | slice |
| `submitted`/`received` → `declined` | bridge, on Leo's decline | decline reason | slice |
| `submitted`/`received` → `withdrawn` | bridge, on revocation | `submitter_revoked` | slice |
| `submitted`/`received` → `withdrawn` | API cancel, submitter only (FR-15) | — | widening |
| `accepted` → `scoping` → `designing` → `planning` → `building` (forward skips allowed) | bridge | FR-17 fields | widening |
| any of `accepted`…`building` ⇄ `waiting_on_leo` | bridge | FR-17 detail code | widening |
| `building`/`waiting_on_leo` → `shipped` | bridge | — | widening |
| any of `accepted`…`waiting_on_leo` → `stopped` | bridge | — | widening |
| `shipped` → `reverted` | bridge | — | widening |

No HTTP route sets any status the bridge owns. Only `bin/prod-script`
reaches the write script, and only a machine holding the AWS credentials can
run it. That is what "only the operator may adopt" means mechanically.
Until FR-17 lands, the write script refuses the widening edges with
`illegal_transition`.

### FR-13: Bridge obligations (external — the orchestrator half)

Palateful cannot test these; the bridge must meet them, and its own repo
tests them. The bridge:

1. Runs only the `origin/main` copies of `bin/prod-script`,
   `dev_requests_read.py` and `dev_requests_write.py`, taken with
   `git fetch` + `git show` into a private directory. It never runs them
   from a working tree, so no branch or uncommitted edit can change what
   writes to production.
2. Calls only `poll`, `adopt`, `metrics` and `transition`. Never `show`.
3. Polls at most once every 300 s, with a lock so runs cannot overlap.
4. Parses output exactly as FR-6 says, and changes no state on a failed run.
5. On first sight of a `submitted` row: `transition <id> submitted received`, then emits one event `palateful_request event=received request=<id8> submitter=<alias>`, where `alias` comes from Leo's local
   config keyed by `submitter_id`, and is `unlisted` when unmapped.
6. Puts only enums, the id8 and the alias into events, the ledger, TODO,
   INTERVIEW, its logs and its state file. Its state file holds `{id, content_sha256, status}` per row. No title, body or done-when, ever.
7. Adopts in this order: `adopt <id> <sha>`; write the quarantine file
   (outside every repo and worktree, mode 0600, a header with the adoption
   time and the hash); recompute the hash from the written fields; then
   `transition <id> <current> accepted --sha <sha>`. If the transition is
   refused, it deletes the quarantine file.
8. Declines with `transition <id> <current> declined --reason <code>`.
9. Withdraws a `submitted`/`received` row whose `submitter_is_admin` is
   `false` with `transition … withdrawn --reason submitter_revoked`.
10. Treats an unknown record version or `DEVREQ` prefix as a failed run. A
    breaking change to this contract moves both sides to `DEVREQ2`.

### FR-14: Minimal panel submit screen [slice]

The admin dashboard gains a "Request a change" entry, visible to admins
only, that opens a form (title, body, optional done-when) and calls FR-3.
On success it shows the returned id8 and the line "Leo will be asked about
it on his laptop." Errors (403, 422, 429) render as their messages. The
slice has no list screen.

### FR-15: List and cancel endpoints [widening]

`GET /v1/admin/dev-requests` (admin; status filter; newest first; each item
carries id, id8, title, status, status_detail, the submitter's display name,
created_at, synced_at) and `POST /v1/admin/dev-requests/{id}/cancel`
(submitter only; `submitted`/`received` → `withdrawn`; any other state →
409). These are the only other routes that touch `dev_requests`.

### FR-16: Panel list and detail [widening]

A list screen with a status chip per request, and a detail screen showing
the text as plain `Text` (as the feedback inbox does), `status_detail`, and
two staleness hints: "Not picked up yet — the listener may be offline" for
a row still `submitted` 15 minutes after `created_at`; `Last update from the listener: <age>` from `synced_at` for every other row. The detail screen
becomes Leo's reading surface, replacing FR-9 in day-to-day use.

### FR-17: Pipeline reflection fields [widening]

The write script gains the widening edges of FR-12 and the arguments they
carry: `--workstream` (a devx slug, `^[a-z0-9][a-z0-9-]{0,49}$`, since
fit routes items into workstreams with ordinary names), `--spec-hash`
(`^[a-z0-9]{6}$`), `--pr` (`^https://github\.com/LeoTheMighty/palateful/pull/[1-9][0-9]*$`,
appended to `pr_urls` without duplicates), and `--detail <code>` with
`--gate` and `--count`. The script composes `status_detail` itself from a
fixed template per code (`pr_held`, `gate_fail`, `gate_concerns`,
`blocking_question`, `plan_review`, `submitter_revoked`, `stalled`). No
argument carries free text.

### FR-18: Fault signals — `faults` [slice 2]

`dev_requests_read.py faults <window>` (`window` ∈ {`1h`, `24h`, `7d`};
read-only, no audit row) groups `error_logs` rows from the server-emitted
services (`api`, `worker`, `push_notifications`; never `audit` or
`client`) inside the window by **signature**, and emits at most 50 `fault`
records, highest count first:

`{"kind":"fault","v":1,"signature","sig8","service","error_type","status_code","method","route","frames","count","first_seen","last_seen"}`

- `route` is the API route template the request path matched, or
  `unmatched`. Never the raw path.
- `frames` is up to 3 in-repo stack frames, innermost first, each
  `<repo-relative path>:<function>`. Frames outside `services/` and
  `libraries/` are dropped. Line numbers are not included.
- `error_type` is emitted only when it is a Python identifier path of at
  most 80 characters, otherwise `other`.
- `signature` is the SHA-256 of `service`, `error_type`, `status_code`,
  `method`, `route` and the innermost frame, so it survives edits that move
  lines.
- No `error_message`, no `stack_trace` text, no raw `path`, no
  `request_id`, no `user_id`.

When more than 50 signatures exist, the 51st onward are summed into one
`{"kind":"fault_overflow","v":1,"signatures","count"}` record, so the bridge
knows it saw a cap and not the whole picture.

### FR-19: Fault detail at adoption — `fault-adopt` [slice 2]

`dev_requests_read.py fault-adopt <signature>` (read-only) emits one
`fault_detail` record carrying the signature's fields plus up to 3 of its
most recent rows' `error_message` and `stack_trace`. It is the only call
that moves fault text to the laptop, and the bridge calls it only after Leo
adopts the fault. An unknown signature ends `ok: false`, `error:
not_found`.

### FR-20: An adopted fault becomes a row [slice 2]

`dev_requests_write.py open-fault <signature> <window>` re-derives the
signature from `error_logs` and inserts one `dev_requests` row with
`source = 'fault'`, `status = 'accepted'`, `submitter_id` null, and a title
and body the script composes from the signature's validated fields (no
error text). If an open row already holds the signature, it reports that
row with `changed: false` and inserts nothing. One audit row per insert.
From there the row follows FR-12 like any request, and `metrics` (FR-10)
gains `faults_open` and `signatures_multi_workstream`.

### FR-21: Routing signals [routing]

The router routes from code locations, never from text:

- **Fault**: its `frames` paths and its `signature`.
- **Request**: nothing before adoption, since all it has is text. Leo
  routes it at adoption (create, or fit into a workstream he names); after
  the PRD and design stages, the files they cite become its code locations
  for later combine proposals.
- **Overlap rule (the recommendation)**: an item fits an open workstream
  when it shares at least 1 non-hub file with that workstream's plan
  `Files:` lists, or its signature is already attached to that workstream.
  Hub files (touched by 3 or more open workstreams, plus a fixed list:
  `services/api/src/dependencies.py`, `services/api/src/main.py`,
  `services/api/tests/conftest.py`) never count, so one shared module
  cannot pull everything into one workstream.

What it costs when wrong:

| Error | Cost | Recovery |
|---|---|---|
| Wrong fit | An unrelated item revises a workstream's PRD; `devx revise` resets all 4 gates and its next PR mixes concerns | Leo confirms every fit at adoption; split |
| Wrong create | Duplicate workstreams for one cause — the bloat Leo named | Combine, proposed when two workstreams' files overlap |
| Accretion | A hub file makes everything overlap, so one workstream absorbs all | Hub exclusion; split |

The router consumes `poll` (each row's `workstream`, `source`,
`fault_signature`), `faults`, and devx's own plan files at `origin/main`.

### FR-22: Routing operations and their owners [routing]

| Operation | Exists today? | Decided by | Palateful's part |
|---|---|---|---|
| Create | yes: `devx workstream new` | router proposes, Leo confirms | `--workstream` on `accepted` → `scoping` (FR-17) |
| Fit | in parts: `devx revise <hash> --touched prd` plus a PRD amendment | router proposes, Leo confirms | same as create |
| Split | **no devx primitive** (external gate) | router proposes, Leo decides | `move` (below) for each row that changes workstream |
| Combine | **no devx primitive** (external gate) | router proposes, Leo decides | `move` for each row of the absorbed workstream |

`dev_requests_write.py move <id> <from_workstream> <to_workstream>` is
compare-and-set on `workstream` (`conflict` when the row is elsewhere),
validates both slugs, leaves `status` alone, and writes one audit row. It
is the only write routing needs from Palateful.

## Bridge contract

The orchestrator half is built against FR-5 to FR-13 and nothing else.
Summary of what crosses the boundary:

| Direction | Call | Carries submitter text? |
|---|---|---|
| bridge → Palateful (read) | `bin/prod-script …/dev_requests_read.py poll` | **no** (FR-7) |
| bridge → Palateful (read) | `… dev_requests_read.py adopt <id> <sha>` | yes, once, at adoption (FR-8) |
| bridge → Palateful (read) | `… dev_requests_read.py metrics` | no (FR-10) |
| bridge → Palateful (write) | `bin/prod-script …/dev_requests_write.py transition …` | no; every argument is an enum, UUID, hash or validated slug (FR-11) |
| bridge → Palateful (read) | `… dev_requests_read.py faults <window>` | no; server-chosen fields only (FR-18) |
| bridge → Palateful (read) | `… dev_requests_read.py fault-adopt <signature>` | yes, once, at fault adoption (FR-19) |
| bridge → Palateful (write) | `… dev_requests_write.py open-fault …` / `move …` | no (FR-20, FR-22) |
| human → Palateful (read) | `… dev_requests_read.py show <id>`, in a plain terminal | yes, to Leo only (FR-9) |

The write path carries no free text, and the read path carries text only
inside `adopt` and `fault-adopt`, after Leo has chosen to adopt. FR-13's
bridge obligations apply to every call here; `faults`, `fault-adopt`,
`open-fault` and `move` join the list of calls the bridge may make (FR-13.2)
when slice 2 and routing land.

## Evals seed

Promoted to `expectations.md` E-1 … E-11. The first expectations are about a
request travelling the whole path, not about any one component being
complete.

## Open questions

None of these blocks Gate 1. Each has a recommended default that this PRD
already uses.

- **Where the slice line falls.** Default: slice 1 stays the admin-request
  path only (Leo's "literally just want this working"); faults are slice 2
  and routing ships with it, after slice 1 works live. Folding faults into
  slice 1 would roughly double it. — owner: user
- Should an adopted fault become a `dev_requests` row (FR-20), or stay
  bridge-side? Default: a row, so faults share the states, panel and
  signature index. — owner: user
- The hub-file list and the threshold of 3 workstreams (FR-21) are guesses
  until the router has run on real items. — owner: research (revisit at
  slice 2)

- Leo reads a request in the slice with `show` in a plain terminal (FR-9),
  because the panel detail screen is widening. Acceptable until FR-16
  lands? Default: yes. — owner: user
- Should requests Leo submits himself auto-adopt? Design §6 recommends not
  in slice 1 (a stolen Leo session would then be enough). Default: no
  auto-adopt. — owner: user
- The hash covers title, body and done-when, not only the body (FR-2).
  Default: all three. — owner: research (settled at design)

## Reference links

- Spec: `plan/plan-1e84ad-2026-11-24T22:51-admin-request-intake.md`
- Design input: `docs/admin-request-pipeline.md` on
  `docs/admin-request-pipeline` (PR #124, head `53cb59a4`)
- Patterns reused: `services/api/src/api/v1/user/create_user_feedback.py`
  (rate limit, strict Pydantic), `services/api/scripts/inspect_user_push.py`
  (read-only script, own engine), `services/api/scripts/promote_admin.py`
  (audit row), `bin/prod-script` (operator channel),
  `app/lib/features/admin/admin_feedback_screen.dart` (panel)
- External gate parser: `~/.claude/orchestrator/lib/orchlib/harness_phases.py`
  `parse_external_gates`
