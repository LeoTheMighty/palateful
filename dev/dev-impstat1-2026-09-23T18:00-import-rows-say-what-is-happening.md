---
hash: impstat1
type: dev
created: 2026-09-23T18:00:00-06:00
title: import rows say what is actually happening, and expand to per-photo detail
from: debug/debug-impprog1-2026-09-22T23:00-blue-rows-always-say-zero-processed.md
status: in-progress
owner: /devx-c2872fff
branch: feat/dev-impstat1
---

## Goal

Leo, verbatim: *"Let's also update the import page to give a lot more
information on the statuses. They're not clickable or expandable so I don't
have any input into what's happening except that the import isn't working."*

Said while an import had been queued **85+ minutes with zero attempts**. The
app could tell him nothing beyond a spinner, so he spent the evening asking
a human for status the app already had the data to give.

**The data is already on the wire.** `GET /v1/parser/batches` returns each
batch with `jobs[]` — one `ParserJob` per photo, carrying `status`,
`group_index`, `input_s3_key`, `extracted_text`, `error_message`
(`services/api/src/api/v1/parser/get_parser_batch.py:55-61`). The Flutter
model parses all of it (`import_batch.dart`) and the UI renders **none** of
it: `jobs[]` is read nowhere. This story is almost entirely "show what we
already have".

**But the queued-vs-parsing distinction does NOT survive to the database.**
`aws.py:330-339` maps `SUBMITTED | PENDING | RUNNABLE → submitted` and
`STARTING | RUNNING → running` — and then
`parser_batch_completion.py:87-89` declines to persist anything
non-terminal, logging *"leaving untouched"*. So `running` is computed and
thrown away: a job stays `submitted` for its entire GPU run and flips
straight to `succeeded` / `failed`.

What the client can therefore say honestly today is **"accepted, not
finished"** plus how long that has been true, and — past the watcher's
budget — that nothing is watching any more. "Parsing" is not available
until the server persists it (`impstat2`).

Client-only. No new endpoint, no deploy — ships in the next build.

## Acceptance criteria

- [x] A batch whose jobs are all `submitted` reads **"Waiting for a parser
      machine"** with the elapsed time since `batch.createdAt`
      (e.g. "queued 85 min"), not a bare spinner.
- [x] **NOT "Parsing N of M photos" — that state is unreachable today.**
      `parser_batch_completion.py:87-89` writes only on terminal
      (`TERMINAL_STATUSES = ("succeeded", "failed", "partial")`, `:28`); a
      non-terminal poll logs *"leaving untouched"* and returns. So
      `parser_job.status` **never moves `submitted → running`** — it stays
      `submitted` through the whole GPU run and jumps straight to terminal
      (measured by palateful-4f, verified here).

      Building that copy now would ship a branch production can never
      enter, provable only by a test fabricating a status the server never
      writes — the same shape as the fixtures that invented
      `processed_items` and hid "Importing 0 of N" for months. **Do not
      render it until the server writes it** (`impstat2` gains that AC).
      The honest states are: queued, stuck, done, failed.
- [x] **The stuck state.** Past the watcher's budget the batch is not
      "still queued" — nothing is watching it any more
      (`watch_parser_batch_task.py:38-39`: `POLL_INTERVAL_SECONDS = 30` ×
      `MAX_POLL_ATTEMPTS = 180` = 90 min). The row must say so — closer to
      *"This import seems stuck"* with a retry affordance than a minute
      counter that keeps climbing. Leo will hit this tonight. **No retry
      button** — see Technical notes; nothing can resubmit a batch.
- [x] **The threshold is not a hardcoded 90 in the UI.** Either read the
      server constant, or declare in one named client constant that it
      duplicates `MAX_POLL_ATTEMPTS × POLL_INTERVAL_SECONDS`, with a test
      pinning the two together. A UI that says "stuck" at the wrong
      threshold is its own false verdict.
- [x] **Tapping a batch row expands it in place** — listing each photo with
      its status and, where present, its `error_message`. Expansion, not
      navigation: there is no ImportJob behind a pre-fan-out batch, which
      is why these rows are currently inert (impvis1 made them
      non-openable after a synthetic id 500'd against a UUID route). Reuse
      `_ExpandableRow` / `ImportRowExpansion`, which already do this for
      item rows.
- [x] **Where the app cannot know, it says so.** No invented numbers. This
      is the rule that produced "Importing 0 of N" — a label that was
      always wrong and looked authoritative — and it must not produce its
      successor. "Waiting for a parser machine" is true and useful;
      "Importing 0 of N" was worse than nothing.
- [x] **The stuck state is recoverable — and recovery is stuck → DONE,
      not stuck → running.** With no intermediate status ever written, a
      batch that reports stuck and is then picked up shows nothing new for
      the whole run and then completes. Pin that transition; asserting
      stuck → running would be asserting something that cannot happen.
- [x] Tests cover: all-`submitted` copy with elapsed time, the stuck
      threshold on both sides, stuck → complete recovery, expansion
      rendering per-photo rows, and a failed photo showing its error.
      **No test may fabricate a `running` parser-job status** while the
      server cannot produce one.

## Technical notes

- `batch_import_status_widget.dart` shows an in-memory upload count from
  `BatchParserService`, which is a different thing — it is about the upload,
  not the parse. Leave it; this story is the Activity tab's row.
- Per-photo *timing* is not available: `JobInfo` carries no timestamps and
  `ParserJob` has no `started_at`. Filed as `impstat2` (wire) and
  `impstat3` (column). This story shows batch-level elapsed only, which is
  honest — and worth stating in the UI copy rather than implying per-photo
  precision.
- `impprog1`'s "Importing 0 of N" is the same surface. Its fix is
  server-side and lives in `impstat2`; once a batch row says "waiting for a
  parser machine", that label is no longer the first thing Leo sees.
- **No retry button.** [M, palateful-4f, verified in the router] The
  parser surface has eight endpoints — upload-url, jobs, jobs/batch, GET
  job, batches, GET batches, GET batch, and the completion callback — and
  **none resubmits**. `retry_import_item` is downstream of the parse and
  useless when the parse produced nothing. The only recovery today is
  creating a new import, which makes a new batch and strands the old one as
  another zero-ImportJob orphan of the kind `parsercap1` measured. So the
  row states the fact and offers nothing: *"This import stopped responding.
  It hasn't been picked up by a parser machine."* A retry needs an endpoint
  built first, and it must supersede the old batch rather than strand it —
  its own story.

## What this story deliberately does not do

- No "Parsing…" state (unreachable — see the AC).
- No retry button (nothing to wire it to).
- No per-photo timing (`JobInfo` carries no timestamps — `impstat2`).

Each is absent because the data or the endpoint does not exist, not because
it was forgotten. Rendering any of them would mean inventing a fact, which
is the failure this surface keeps producing.

## Status log
- 2026-09-23T18:00 — filed from Leo's request, scoped against what the wire already carries; ranked with leonidbelyi-41, Leo chose all three stories. Blocked-by: —.
- 2026-09-23T18:35 — claimed for /devx. Client-only, so it ships in the next build independently of impstat2's deploy; base 9bbc3461. Retry-affordance copy is blocked on whether a resubmit path exists (asked palateful-4f); the other ACs proceed meanwhile.
- 2026-09-23T18:50 — ACs revised on measurement from palateful-4f, verified here: (1) no resubmit endpoint exists, so the stuck row offers no button; (2) `parser_job.status` never passes through `running` — `parser_batch_completion.py:87-89` writes only on terminal — so the "Parsing N of M" state I had specified is **unreachable in production** and is cut. Recovery is stuck → complete. Leo's batch at the time: ~115 minutes, still RUNNABLE, zero attempts.
- 2026-09-23T19:40 — phase 3+5. Client-only as scoped. The batch row now reads "Waiting for a parser machine · queued 1 h 25 min" (coarse formatting on purpose — a queue wait does not warrant seconds, and false precision is the habit this surface is breaking); past the watcher's budget it reads "This import stopped responding. It hasn't been picked up by a parser machine" with no retry button, because no endpoint can resubmit a batch. Both batch rows expand in place to per-photo detail from `jobs[]` — data the API has always sent and no UI had ever rendered — including each photo's error. The old 2h `preFanOutGrace` is now the watcher's 90 minutes, so "stopped counting as in flight" and "nothing is watching" are one moment instead of two.
- 2026-09-23T19:45 — the threshold is pinned by `watcher_budget_parity_test.dart`, which **reads `watch_parser_batch_task.py` and computes `MAX_POLL_ATTEMPTS × POLL_INTERVAL_SECONDS`** rather than restating the numbers, so a server change fails the client test instead of drifting silently the way the two `processed_items` definitions did. Verified RED: setting the client to 80 minutes fails it with both durations named. A second test fails loudly if either constant is renamed, so the parity test cannot pass vacuously.
- 2026-09-23T19:50 — phase 5: flutter test 1704 passed, flutter analyze 0 errors, all nine tools/*.sh guards pass.
