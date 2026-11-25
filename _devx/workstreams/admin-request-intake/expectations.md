# Expectations — Admin Request Intake

<!-- Gate 1 input. Minimum 3 E-blocks (config: engine.expectations_min).
     Every business goal (G-) must be covered by at least one expectation;
     every Covers: ID must resolve in prd/agent.md. EARS regex enforced by
     `devx gate prd`: "When .+, the system SHALL .+". A P0 with a vague
     Verified-by target fails the gate. `Measure:` is the command
     `devx outcome score --run` executes weeks later to score a numeric G-.

     Ordering is deliberate: E-1 is a request travelling the whole path.
     Component expectations follow it, widening expectations come last. -->

## E-1: A request travels the whole path

- **Priority:** P0
- **Covers:** `G-1, UC-1, UC-2, UC-4, CAP-1, CAP-3, CAP-5, FR-1, FR-3, FR-5, FR-6, FR-7, FR-8, FR-11`
- **Trigger:** An admin creates a request through `POST /v1/admin/dev-requests`; then a reference bridge that follows FR-13 drives
  the real `bin/prod-script` (with `aws` replaced by a local shim that
  reproduces the ECS-exec stream: banner lines, CRLF, keepalive escapes)
  through `poll`, `transition … received`, `adopt` and `transition … accepted` against a real Postgres.
- **Expectation (EARS):** When an admin submits a request and the bridge
  polls, acknowledges and then adopts it through the operator channel, the
  system SHALL move the row from `submitted` to `received` to `accepted`,
  hand its text over only in the `adopt` record, and return content whose
  hash equals the hash given at submission.
- **Threshold:** 1 request reaches `accepted` in 4 channel calls, each run
  ending in exactly 1 `end` record with `ok: true`; the `adopt` record's
  recomputed hash equals the create response's `content_sha256`; exactly 2
  `DevRequestTransition` audit rows; 0 rows written by anything other than
  the endpoint and the write script; a no-argument `bin/prod-script` call
  still runs (FR-5 backward compatibility).
- **Measure:** `bin/prod-script services/api/scripts/dev_requests_read.py metrics` · window: 2026-11-24 → 2026-12-31 (G-1: `by_status.accepted` ≥ 1)
- **Verified by:** `_devx/workstreams/admin-request-intake/evals/E-1_full_path.sh`

## E-2: No submitter text before adoption

- **Priority:** P0
- **Covers:** `G-3, UC-2, CAP-4, FR-6, FR-7, FR-10, FR-11`
- **Trigger:** A request whose title, body and done-when each carry a
  distinct canary token is created, then every pre-adoption channel call
  the bridge may make (`poll`, `metrics`, `transition … received`, and the
  refused calls `adopt` with a wrong hash and `transition` with a bad
  argument) runs through `bin/prod-script`.
- **Expectation (EARS):** When the bridge makes any channel call other than
  a successful `adopt`, the system SHALL return output in which none of the
  request's title, body or done-when text occurs, on stdout or stderr.
- **Threshold:** 0 occurrences of any of the 3 canaries across all
  pre-adoption calls; negative control: the same detector finds all 3
  canaries in the output of one successful `adopt` (it must, or the check
  is blind) and fails on a record deliberately built with a canary.
- **Measure:** `bash _devx/workstreams/admin-request-intake/evals/E-2_containment_canary.sh` · window: every CI run through 2027-02-28 (G-3: 0 failures)
- **Verified by:** `_devx/workstreams/admin-request-intake/evals/E-2_containment_canary.sh`

## E-3: Only the operator can adopt

- **Priority:** P0
- **Covers:** `G-4, UC-1, CAP-2, CAP-3, FR-3, FR-12`
- **Trigger:** Calls to the API as an admin and as a non-admin, including
  create payloads that try to set `status`, `submitter_id` or a pipeline
  field, plus an enumeration of the app's registered routes.
- **Expectation (EARS):** When any HTTP caller tries to create or move a
  request, the system SHALL store new requests only as `submitted` for the
  calling admin and SHALL expose no route that writes a status the bridge
  owns.
- **Threshold:** admin create → 201 with `status: submitted`; non-admin → 403
  and 0 rows; each of 3 smuggled fields → 422 and 0 rows; the create route
  exists (the check can see); 0 routes touching `dev-requests` outside the
  FR-3/FR-15 allowlist.
- **Measure:** `bin/prod-script services/api/scripts/dev_requests_read.py metrics` · window: through 2027-02-28 (G-4: `accepted_without_audit` = 0)
- **Verified by:** `_devx/workstreams/admin-request-intake/evals/E-3_operator_only.sh`

## E-4: Transitions are validated, compare-and-set and audited

- **Priority:** P0
- **Covers:** `G-4, UC-4, UC-5, UC-6, CAP-5, FR-11, FR-12`
- **Trigger:** `dev_requests_write.py transition` calls against a real
  Postgres: every slice edge, a sample of illegal and widening edges, stale
  `from` values, repeats, bad arguments, a wrong `--sha`, and an adopt after
  the submitter lost admin.
- **Expectation (EARS):** When the write script is asked for a status
  change, the system SHALL apply it only if FR-12 gives that edge to the
  bridge and the row is in the stated `from` status, SHALL treat a repeat as
  a no-op, SHALL refuse everything else with a named error, and SHALL write
  exactly one audit row per applied change.
- **Threshold:** 7 of 7 slice edges (`submitted`→`received`, and
  `submitted`/`received` → `accepted`/`declined`/`withdrawn`) applied with 1
  audit row each; 6 of 6
  sampled illegal or widening edges → `illegal_transition`; stale `from` →
  `conflict`; repeat → `changed: false` and 0 new audit rows; 4 of 4 bad
  arguments → `invalid_argument`; wrong `--sha` → `sha_mismatch`; revoked
  submitter → `submitter_revoked`; 0 status changes on any refusal.
- **Verified by:** `_devx/workstreams/admin-request-intake/evals/E-4_transitions.sh`

## E-5: What Leo reads is what an agent reads

- **Priority:** P0
- **Covers:** `CAP-1, FR-2, FR-3, FR-8`
- **Trigger:** Create calls whose fields carry zero-width, bidi-override and
  other `Cc`/`Cf` characters, NFKC-foldable characters, surrounding
  whitespace, and over-length or blank-after-normalization values.
- **Expectation (EARS):** When an admin submits text containing invisible or
  foldable characters, the system SHALL store the normalized text and a
  `content_sha256` computed over it exactly as FR-2 defines, and SHALL
  reject a field that is blank after normalization or over its limit.
- **Threshold:** 0 `Cc`/`Cf` characters other than `\n`/`\t` in any stored
  field; stored text equals the reference normalization in 8 of 8 cases;
  stored hash equals the reference hash in 8 of 8; title > 120, body > 4000,
  done-when > 1000 and blank-after-normalization each → 422.
- **Verified by:** `_devx/workstreams/admin-request-intake/evals/E-5_normalization.sh`

## E-6: Submission is rate-limited

- **Priority:** P1
- **Covers:** `CAP-2, FR-4`
- **Trigger:** Six creates by one admin inside an hour.
- **Expectation (EARS):** When an admin exceeds 5 creates in a rolling hour,
  the system SHALL answer 429 with `retry_after_s` and create no row.
- **Threshold:** calls 1–5 → 201; call 6 → 429 with `retry_after_s` ≥ 1; a
  second admin is unaffected (1 of 1 → 201).
- **Verified by:** `services/api/tests/test_dev_requests_rate_limit.py`

## E-7: An admin can file a request from the panel

- **Priority:** P1
- **Covers:** `UC-1, FR-14`
- **Trigger:** An admin opens the dashboard's "Request a change" entry and
  submits the form; a non-admin opens the dashboard.
- **Expectation (EARS):** When an admin submits the panel form, the system
  SHALL send one create call and show the returned id8, and SHALL not offer
  the entry to a non-admin.
- **Threshold:** 1 create call per submit; id8 shown; 403/422/429 each
  rendered as their message; 0 entries rendered for a non-admin.
- **Verified by:** `app/test/features/admin/admin_dev_request_new_screen_test.dart`

## E-8: The live path works in production

- **Priority:** P1
- **Covers:** `G-1, G-2, UC-1, UC-2, UC-3, UC-4, UC-5, FR-13, FR-14`
- **Trigger:** After the slice phases are deployed and the bridge (external
  gate) is installed, Leo files one request from the production panel,
  reads it with `show`, and adopts it; then files and declines a second.
- **Expectation (EARS):** When Leo files a request in production with the
  bridge running, the system SHALL put the decision question in front of him
  within 10 minutes, and after he adopts it SHALL show the row as `accepted`
  with the quarantine file's hash equal to the row's.
- **Threshold:** question within 600 s of `created_at`; row `accepted`;
  quarantine hash equal; second request `declined` with its reason; 0 hand
  edits to either row; 0 request text in `events.ndjson`, the ledger or
  TODO (grep for the request's canary word returns 0 lines).
- **Measure:** `bin/prod-script services/api/scripts/dev_requests_read.py metrics` · window: first production request → 2027-02-28 (G-2: `received_lag_s_max` ≤ 600)
- **Verified by:** `_devx/workstreams/admin-request-intake/evals/E-8_live_walkthrough.md`

## E-9: Admins can list and cancel their requests

- **Priority:** P2
- **Covers:** `UC-7, CAP-6, FR-15, FR-12`
- **Trigger:** List calls with and without a status filter; cancel calls by
  the submitter before and after adoption, and by another admin.
- **Expectation (EARS):** When the submitter cancels a request before it is
  accepted, the system SHALL move it to `withdrawn`, and SHALL refuse a
  cancel after acceptance or by anyone else.
- **Threshold:** list returns 100% of matching rows newest first with no
  `body` field; pre-adoption cancel → `withdrawn`; post-adoption cancel →
  409; other admin's cancel → 403.
- **Verified by:** `services/api/tests/test_dev_requests_list_cancel.py`

## E-10: The panel shows each request's state

- **Priority:** P2
- **Covers:** `G-5, UC-7, UC-8, CAP-6, FR-16`
- **Trigger:** The list and detail screens rendered for rows in each status,
  including a `submitted` row 16 minutes old and an `accepted` row whose
  `synced_at` is 3 hours old.
- **Expectation (EARS):** When an admin opens their requests, the system
  SHALL show every request with its status chip and detail, and SHALL show a
  staleness hint when the listener has gone quiet.
- **Threshold:** 13 of 13 statuses render a chip; "Not picked up yet" shown
  for the 16-minute row and not for a 14-minute one; "Last update from the
  listener: 3 h ago" shown for the stale row.
- **Measure:** `bin/prod-script services/api/scripts/dev_requests_read.py metrics` · window: widening landed → 2027-02-28 (G-5: `stale_undecided` = 0)
- **Verified by:** `app/test/features/admin/admin_dev_requests_list_screen_test.dart`

## E-11: Pipeline progress is reflected without free text

- **Priority:** P2
- **Covers:** `UC-8, FR-12, FR-17`
- **Trigger:** The widening edges of FR-12 with their FR-17 arguments,
  including a PR URL for another repo and a workstream slug that does not
  match the template.
- **Expectation (EARS):** When the bridge reports pipeline progress, the
  system SHALL apply the widening edges, compose `status_detail` from its
  fixed templates, and refuse any argument outside its pattern.
- **Threshold:** every widening edge applied with 1 audit row; 7 of 7 detail
  codes render their template; foreign PR URL and bad slug →
  `invalid_argument`; a repeated PR URL is stored once.
- **Verified by:** `services/api/tests/test_dev_requests_pipeline_fields.py`

## E-12: Fault signals carry no caller-written text and are bounded

- **Priority:** P1
- **Covers:** `G-6, UC-9, CAP-7, FR-18`
- **Trigger:** `error_logs` seeded with server rows whose `error_message`,
  `stack_trace` and `path` each carry a canary, `client` rows carrying a
  canary in every field, and 60 distinct signatures in one window.
- **Expectation (EARS):** When the bridge asks for fault signals, the
  system SHALL return one record per server-side signature, at most 50 plus
  one overflow record, containing none of the rows' message, trace or path
  text and nothing from `client` rows.
- **Threshold:** 0 canary occurrences in `faults` output; 50 `fault` records
  plus 1 `fault_overflow` with `signatures` = 10; 0 records with `service`
  = `client` or `audit`; negative control: `fault-adopt` on one signature
  returns its canary.
- **Measure:** `bin/prod-script services/api/scripts/dev_requests_read.py metrics` · window: slice 2 live → 2027-04-30 (G-6: `faults_open` tracked; leak count 0 from this eval on every CI run)
- **Verified by:** `services/api/tests/test_dev_requests_faults.py`

## E-13: A fault's signature is stable and its signals are code-derived

- **Priority:** P2
- **Covers:** `UC-9, CAP-8, FR-18, FR-21`
- **Trigger:** The same exception raised from the same function before and
  after an edit that moves its line; request paths with UUID and integer
  segments, and a path matching no route.
- **Expectation (EARS):** When the same fault recurs after its code moves,
  the system SHALL report the same signature, with routes reduced to
  registered templates and frames reduced to repo-relative paths.
- **Threshold:** 1 signature across the line move; 3 of 3 parameterized
  paths → their template; unknown path → `unmatched`; 0 frames outside
  `services/` or `libraries/`; 0 line numbers in `frames`.
- **Verified by:** `services/api/tests/test_dev_requests_fault_signature.py`

## E-14: Routing writes keep every row pointing at its work

- **Priority:** P2
- **Covers:** `G-7, UC-10, UC-11, UC-12, CAP-8, FR-20, FR-22`
- **Trigger:** `open-fault` twice for one signature; `move` with the right
  and a stale `from_workstream`; `move` with a slug outside the devx
  pattern.
- **Expectation (EARS):** When the bridge opens a fault or moves a row
  between workstreams, the system SHALL keep one open row per signature and
  apply a move only from the workstream the row is in.
- **Threshold:** second `open-fault` → `changed: false`, 0 new rows; good
  `move` → 1 audit row and `status` unchanged; stale `from` → `conflict`;
  bad slug → `invalid_argument`.
- **Measure:** `bin/prod-script services/api/scripts/dev_requests_read.py metrics` · window: router live → 2027-05-31 (G-7: `signatures_multi_workstream` = 0)
- **Verified by:** `services/api/tests/test_dev_requests_routing_writes.py`
