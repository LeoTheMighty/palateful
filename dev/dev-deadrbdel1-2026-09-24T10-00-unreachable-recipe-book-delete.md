---
hash: deadrbdel1
type: dev
created: 2026-09-24T10:00:00-06:00
title: A live, cascading delete endpoint with no UI — one line from reachable
from: dev/dev-envspell1-2026-09-22T21:30-environment-spelling-divergence.md
status: ready
owner: null
branch: null
---

## Goal

`DELETE /v1/recipe-books/{id}` **permanently deletes a recipe book and every
recipe in it**, is routed and live in prod, has a fully wired client path —
and is **reachable from no UI surface at all**.

Dead destructive code does not stay dead. It gets wired up later by someone
who reasonably assumes that a service method, an API client method, a
`MutationType` and a failure-copy string mean the path was designed and
reviewed. Here the only thing standing between a user and permanent,
cascading deletion is that nobody has added the button yet.

## Measured 2026-09-24

**Server — live, routed, cascading:**
- `services/api/src/api/v1/recipe_book/delete_recipe_book.py` — docstring:
  *"Delete a recipe book and all its recipes."* Body:
  `await self.database.delete(recipe_book)` with the comment
  *"cascades to recipes and memberships"*.
- Routed at `services/api/src/routers/v1/recipe_book_router.py:117`.
- Guards that **do** exist: owner-only (403 otherwise), refuses
  `is_system` books (400), and restores `previous_recipe_book_id` when the
  deleted book was the user's default.
- Guard that does **not** exist: any confirmation of scale. A book with 200
  recipes deletes 200 recipes on one call, with no count returned and no
  undo.

**Client — fully wired, never called:**
- `app/lib/core/services/api_client.dart:311` — `deleteRecipeBook`.
- `app/lib/features/recipe_books/services/recipe_book_service.dart:93` —
  `deleteRecipeBook`, calls the above.
- `app/lib/core/state/mutation_failure_copy.dart:51,177` — a
  `MutationType.deleteRecipeBook` **and** user-facing failure copy.
- `app/test/features/recipe_books/recipe_book_service_reactivity_test.dart`
  — a test exercising it.
- **Zero call sites in any screen or widget.** The UI offers only `Archive`
  (`recipe_book_service.dart:72`), with an `Archived Books` screen.

So the feature is complete in every layer except the one that would make it
visible, and it looks reviewed because it *was* — just never connected.

## The decision this needs

Not "add a delete button". Someone has to decide which of these is true:

1. **Delete is intended**, and the missing piece is a UI with a confirmation
   proportional to a cascading permanent delete (recipe count shown, typed
   confirmation, or archive-first-then-delete from `Archived Books`).
2. **Archive is the product answer**, and the delete path should be removed
   from the client — service method, API client method, `MutationType`,
   failure copy, test — leaving the endpoint server-side only, or removed
   there too.

Either is defensible. Leaving it as-is is the one option that is not,
because it is the state where the next person to touch this area can make
it reachable in one line without anyone reviewing the consequence.

## Acceptance criteria

- [ ] A decision recorded between (1) and (2) above, with the reason.
- [ ] If (1): the confirmation states **what will be deleted, counted** —
      "Delete <name> and its 37 recipes?" — not a generic "Are you sure?".
      A cascading delete whose blast radius is invisible at the moment of
      confirmation is the same failure as a dry-run that prints a summary.
- [ ] If (2): the client path is removed in one commit — service, API
      client, `MutationType`, failure copy, test — so a future reader does
      not find half a feature and finish it.
- [ ] Either way, a test pinning the chosen state: either the button exists
      and confirms with a count, or **no call site exists** (a grep guard in
      the shape of `tools/environment-gate-check.sh`).
- [ ] Note for whoever implements: the endpoint's existing `is_system` and
      owner-only guards stay regardless; they are not the gap.

## Technical notes

- Relevant to the QA identity: this endpoint can permanently remove QA books
  **via the API** even though the UI cannot. Anyone scripting QA cleanup
  should know it exists — and `deluser1` should not be surprised by it.
- Found while tracing whether "delete a book" was a main flow for a browser
  QA plan. It isn't: `Archive` is. That is itself the answer to the
  product question, which is why (2) is the likelier decision.

## Status log
- 2026-09-24T10:00 — filed at 41's direction after the trace came back
  "wired everywhere, called nowhere". Raised originally as a footnote in
  the books/membership QA plan; promoted because dead destructive code is
  exactly the thing that stops being dead without review.
