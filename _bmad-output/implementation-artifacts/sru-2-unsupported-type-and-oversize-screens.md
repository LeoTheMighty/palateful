# Story sru-2: Unsupported type + oversize screens

**Status:** done
**Epic:** epic-share-receiving-ux

## Goal

Finish the two "terminal" states of the receiving flow: the
"we can't read this" card (shipped as part of sae-3 placeholder, now
preserved under the sru-1 screen rewrite) and a new oversize card
for files ≥ 100 MB. Ensure the oversize branch never issues an
`/imports/upload-url` request.

## Acceptance criteria

1. `?unsupported=true&filename=<name>` renders the "We can't read
   this yet" card with a Paste Text Instead + Close action pair.
2. Before any `upload-url` call, the receiving screen reads file
   size via `File(path).stat()` (async). If size ≥ 100 MB or stat
   fails, the oversize card renders with the actual size formatted
   via `formatBytes` (e.g. "118 MB"). **No upload-url request is
   made** — the gating is in `_dispatch` before any network call.
3. Both terminal states have a Close button that returns home.
4. Widget tests cover: unsupported render, Paste Text Instead nav,
   Close-to-home.

## Implementation

Both cards live inside `receive_import_screen.dart` as private
`_UnsupportedCard` and `_OversizeCard` widgets, driven by a
`_terminal` flag set in `initState` (for `unsupported=true`) or
after the size check in `_dispatch`. `formatBytes` is re-exported
from `widgets/receive_progress_card.dart` so the byte counter on the
progress card and the oversize-state copy share the same logic.

The screen writes the `_oversizeBytes` value into local state when it
trips the 100 MB gate; the card then renders a hyphen-lead
parenthetical with the size. If `File.stat` throws (e.g. permission-
denied sandbox path), the screen falls through to the unsupported
card instead — same copy, same actions — because we can't show the
size without the stat.

### File List

Modified:
- `app/lib/features/recipes/add_recipe/receive_import_screen.dart` —
  adds the `_OversizeCard` widget + the size gate in `_dispatch`.
- `app/lib/features/recipes/add_recipe/widgets/receive_progress_card.dart`
  — exports `formatBytes`.

Widget tests live in
`app/test/features/recipes/add_recipe/receive_import_screen_test.dart`
(shared file with sru-1).

## Carry-overs

- Screenshot tests (golden renders) for the two states are nice-to-
  have but not blocking; the text assertions cover the substantive
  failures.
- The oversize integration test would need a real 100 MB file on
  disk; `flutter_tester`'s fake-async zone stalls `File.stat` anyway.
  Manual QA per the walkthrough.

## QA walkthrough

See `sru-2-qa-walkthrough.md`.
