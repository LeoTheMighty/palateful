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

**The queued-vs-parsing distinction survives the server's mapping.**
`aws.py:330-339` maps AWS Batch states onto ours: `SUBMITTED | PENDING |
RUNNABLE → submitted`, `STARTING | RUNNING → running`. So
`parser_job.status == 'submitted'` already means *accepted, no machine yet*
and `running` means *a GPU box has it*. That is exactly the distinction Leo
is missing, and it costs nothing to show.

Client-only. No new endpoint, no deploy — ships in the next build.

## Acceptance criteria

- [ ] A batch whose jobs are all `submitted` reads **"Waiting for a parser
      machine"** with the elapsed time since `batch.createdAt`
      (e.g. "queued 85 min"), not a bare spinner.
- [ ] A batch with any job `running` reads **"Parsing N of M photos"**,
      counted from `jobs[]`.
- [ ] **The stuck state.** Past the watcher's budget the batch is not
      "still queued" — nothing is watching it any more
      (`watch_parser_batch_task.py:38-39`: `POLL_INTERVAL_SECONDS = 30` ×
      `MAX_POLL_ATTEMPTS = 180` = 90 min). The row must say so — closer to
      *"This import seems stuck"* with a retry affordance than a minute
      counter that keeps climbing. Leo will hit this tonight.
- [ ] **The threshold is not a hardcoded 90 in the UI.** Either read the
      server constant, or declare in one named client constant that it
      duplicates `MAX_POLL_ATTEMPTS × POLL_INTERVAL_SECONDS`, with a test
      pinning the two together. A UI that says "stuck" at the wrong
      threshold is its own false verdict.
- [ ] **Tapping a batch row expands it in place** — listing each photo with
      its status and, where present, its `error_message`. Expansion, not
      navigation: there is no ImportJob behind a pre-fan-out batch, which
      is why these rows are currently inert (impvis1 made them
      non-openable after a synthetic id 500'd against a UUID route). Reuse
      `_ExpandableRow` / `ImportRowExpansion`, which already do this for
      item rows.
- [ ] **Where the app cannot know, it says so.** No invented numbers. This
      is the rule that produced "Importing 0 of N" — a label that was
      always wrong and looked authoritative — and it must not produce its
      successor. "Waiting for a parser machine" is true and useful;
      "Importing 0 of N" was worse than nothing.
- [ ] Tests cover: all-`submitted` copy, mixed `running` copy, the stuck
      threshold on both sides, expansion rendering per-photo rows, and a
      failed photo showing its error.

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
- Retry affordance: check whether an endpoint exists to resubmit a batch
  before promising one. If not, the stuck state says so without the button,
  and the button is its own item — better than a control that does nothing.

## Status log
- 2026-09-23T18:00 — filed from Leo's request, scoped against what the wire already carries; ranked with leonidbelyi-41, Leo chose all three stories. Blocked-by: —.
- 2026-09-23T18:35 — claimed for /devx. Client-only, so it ships in the next build independently of impstat2's deploy; base 9bbc3461. Retry-affordance copy is blocked on whether a resubmit path exists (asked palateful-4f); the other ACs proceed meanwhile.
