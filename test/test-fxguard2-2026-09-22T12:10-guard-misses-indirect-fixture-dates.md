---
hash: fxguard2
type: test
created: 2026-09-22T12:10:00-06:00
title: The fixture-date guard only sees inline literals — a date bound to a variable or default parameter slips through
from: dev/dev-fxfuse-2026-09-20T10:35-drain-the-fixture-date-fuse-baseline.md
status: ready
owner: null
branch: null
---

## Goal

`app/test/fixture_date_guard_test.dart` matches `'created_at': '<year>-…'`
**on one line**. That shape is not the only way a frozen date reaches a
`DateTime.now()`-relative surface, and the alternatives are invisible to
the guard — so the fuse the guard exists to prevent can still be lit by a
PR that the guard passes.

Two concrete shapes, both found while draining the baseline in `fxfuse`:

1. **Bound to a variable / default parameter.**
   `app/test/features/home/home_bulk_actions_test.dart:173` —
   `String updatedAt = '2026-04-01T00:00:00Z'` as a default parameter,
   fed to `'updated_at'` and `'created_at'` at `:180-181`. The guard sees
   `'created_at': updatedAt` — no opening quote followed by a year, no
   match. (This particular instance is not a live fuse: those values only
   feed `home_screen.dart:126-127`'s descending string compare, which is
   ordering, not age.)
2. **A different key on the same fuse.** The guard scans `created_at`
   only. `updated_at`, `archived_at`, `dismissed_at`, `last_cooked`,
   `due_at`, `last_seen_at` and `username_changed_at` all reach
   now-relative code somewhere in `lib/`. `fxfuse` anchored the
   `updated_at` / `archived_at` / `dismissed_at` literals that shared a
   formatter with a `created_at` sibling, but nothing stops a *new* one
   landing alone.

The sharpest example of (2):
`app/test/features/profile/export_collection_test.dart:31` carries
`'username_changed_at': null`. That key is the input to the now-30d
cutoff at `profile_screen.dart:414-417`. `null` today, so no fuse — but
any future literal on that line is a live fuse the guard will not catch.

## Acceptance criteria

- [ ] The guard (or a sibling test) detects a hardcoded date bound
      through a local variable / default parameter and then used as a
      date-bearing fixture key, OR the guard's header documents this as a
      deliberate, named limitation rather than leaving readers to assume
      coverage it doesn't have.
- [ ] The set of scanned keys is decided deliberately and written down:
      either widen beyond `created_at` (with the same two escapes) or
      record why `created_at` alone is the right blast radius.
- [ ] Whatever the guard ends up covering, `app/tool/time_travel_check.sh`
      catches more of the rest: it shifts every ISO date AND every
      `DateTime(y, m, d)` constructor under `test/`, so it is key-agnostic
      and variable-agnostic — but **not form-agnostic**. Its header lists
      what it still cannot see (epoch millis, dates assembled from
      variables, dates arriving from outside `test/`); don't cite it as
      complete coverage. Consider wiring it into CI on a schedule (it is a
      full extra suite run, so probably not per-PR) — a nightly +400d run
      turns "the next fixture to age out" from a surprise into a ticket.
- [ ] No false positives on the drained tree: the guard must stay green
      on `main` after `fxfuse` lands.

## Technical notes

- Detecting shape (1) properly means parsing Dart, not grepping — likely
  `package:analyzer` on the test tree, which is a real step up in cost
  from a regex. Weigh that against the scheduled time-travel run, which
  gets most of the same protection for none of the parsing.
- `fxfuse` deleted `app/test/fixture_date_guard_baseline.txt`; the guard
  now treats an absent baseline as empty. Don't reintroduce the file to
  grandfather anything found here.

## Status log
- 2026-09-22 — filed from `/devx fxfuse` (Phase 8 gap-filing). Both shapes
  were found by evidence during the 29-file triage, not hypothesized.
