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

## Answered by the history: deliberately unreachable, not unshipped

These imply opposite next actions, so it was worth checking rather than
assuming. `git log -S deleteRecipeBook -- app/lib` gives a clean answer:

**Story 2.8, "Archive & Restore Recipe Books — soft delete with archived
books screen" (`3a1f7e2f`), replaced the delete call site with archive:**

    - Future<void> _deleteRecipeBook() async {
    + Future<void> _archiveRecipeBook() async {
    -   await _apiClient.deleteRecipeBook(widget.recipeBookId);
    +   await _apiClient.archiveRecipeBook(widget.recipeBookId);
    -   _deleteRecipeBook();
    +   _archiveRecipeBook();

So a UI caller **did** exist, and a deliberate product decision removed it:
soft delete replaced hard delete, and the archived-books screen shipped in
the same commit. The client path was left wired behind it.

**This changes the risk and the recommendation.** It is not half-built work
waiting to be finished — it is a **shipped product decision with its
implementation still loaded**. Someone re-wiring `deleteRecipeBook` would be
**reversing Story 2.8 without knowing they were**, and the absence of a
caller would read to them as "never finished" rather than "deliberately
withdrawn". That is the precise misreading this spec exists to prevent, and
it makes option (2) the one the evidence supports.

**The live exposure is the server side.** `DELETE /v1/recipe-books/{id}` is
still routed and still cascades, so the API permits the hard delete the
product chose to stop offering. Any client — or any script — can still do
what the UI deliberately stopped doing.

## The decision this needs

The history points at (2). Someone still has to decide, because the server
side is a separate question from the client one:

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

- [ ] A decision recorded between (1) and (2) above, with the reason — and
      it must engage with Story 2.8 rather than re-deciding in ignorance of
      it. Choosing (1) means deliberately reversing a shipped decision, which
      is allowed but should be conscious.
- [ ] A separate decision on the **server** endpoint, which the client
      choice does not settle: it remains routed and cascading regardless, so
      "remove the client path" leaves the capability intact for anything
      holding a token.
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

## The same shape as `e2eprod1` — two instances, so a pattern

`e2eprod1` (filed in PR #103, not yet on `main` at time of writing):
`E2E_MODE=true` with no `API_BASE_URL` override builds a bundle that talks
to **production with the auth bypass armed**, because production is the
default in `environment.dart:9-12` and `kE2EMode` carries no environment
condition. Its only protection today is a single `--dart-define` inside
`run_all.sh`.

Put beside this story, the shared shape is sharper than "dead code":

> **The capability is fully present, and the only thing preventing its use
> is that the current call path happens not to exercise it. Adding a caller
> is sufficient to unlock it, and nothing in the system would object.**

- `e2eprod1`: the guard is that the one script everyone uses passes the
  right flag. Any path that skips the script is unsafe.
- This story: the guard is that no screen calls a method the client already
  exposes. Any screen that calls it is a permanent cascading delete.

Neither has a mechanism that would **refuse** the dangerous use — they have
a habit of not requesting it. That is the distinction worth carrying: a
guard refuses; an absence merely hasn't been asked yet. Two instances in
one day from unrelated areas suggests looking for a third rather than
treating either as a quirk.

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
