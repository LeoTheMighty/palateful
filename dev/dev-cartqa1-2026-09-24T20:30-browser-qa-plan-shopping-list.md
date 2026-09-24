---
hash: cartqa1
type: dev
created: 2026-09-24T14:30:00-06:00
title: Browser QA plan — shopping list / cart (STAGED, awaiting the baton)
from: leonidbelyi-41, relaying Leo. One tab drives the browser at a time.
status: ready
owner: null
branch: null
---

## Status: PLAN ONLY. No browser tool has been called.

Browser tooling confirmed present via `ToolSearch` — `tabs_context_mcp`,
`navigate`, `computer`, `read_page`, `read_console_messages`,
`read_network_requests`. **None invoked.** Waiting for the baton.

## Why this flow, and what to actually watch

The cart was broken for months. It was verified fixed in prod **only by a
moved denominator** — 3 loads / 0 errors after, against 5 errors / 11 loads
before, with the client recorder shown alive in the same minutes. That
establishes *the crash stopped*. **Nobody has ever driven the cart through a
real user flow**, so nothing establishes that the feature works.

**The original defect is still reachable by shape.** Pydantic v2 serialises
`Decimal` as a JSON **string**; the client does
`(json['quantity'] as num?)?.toDouble()` at
`app/lib/features/shopping_cart/models/shopping_list_item.dart:56` — and
**that cast is still there today** (verified on `origin/main`). The fix was
upstream of it, not at this line. So **any path that returns a string
quantity throws `_TypeError` and the list fails to parse** — not one item,
the whole payload.

**Therefore quantity is the priority, not a nice-to-have.** Steps 5 and 9
are the ones most likely to find something, and a silent parse failure is a
likelier finding than a visibly broken button. A cart that renders empty
after an edit is the signature — **empty and broken look identical**.

Endpoint to watch throughout: **`/v1/shopping-lists`**.

## Before starting (on the baton)

1. `tabs_context_mcp` — confirm the tab group; create a fresh tab.
2. Confirm the **QA account** is the signed-in user. **If a password prompt
   appears, stop and report.** It must not appear in a message, file or
   commit.
3. **Split-screen the window first.** Flutter ignores synthetic clicks when
   macOS reports the window occluded (`visibilityState: hidden`).
4. `read_console_messages` and `read_network_requests` with `clear: true` —
   establish a clean baseline so later errors are attributable.

## Steps — one expected result each

| # | Step | Expected |
|---|---|---|
| 1 | Open the app, go to **Shopping List** | List screen renders; `GET /v1/shopping-lists` → 200; list state (empty or populated) is **legible**, not a spinner or blank |
| 2 | Open a recipe, tap **Add to shopping list** | Confirmation appears; ingredients appear on the list with names and quantities |
| 3 | Return to **Shopping List** | Every ingredient from step 2 is present; quantities **rendered**, not blank |
| 4 | Tap **Add Item**, add a manual item ("Test QA salt") | Item appears immediately; POST → 2xx |
| 5 | **Edit the quantity** of the manual item to `1.5` | **PRIORITY.** Value persists and re-renders as `1.5`. Watch for `_TypeError`, and for the **whole list** going empty rather than one row |
| 6 | Check an item off | Row shows checked; state survives leaving and re-entering the screen |
| 7 | Uncheck it | Returns to unchecked |
| 8 | Remove the manual item added in step 4 | Row disappears; DELETE → 2xx |
| 9 | **Add the same ingredient from a second, different recipe** | **The open question.** Record what happens — **merged** (one row, summed quantity) or **duplicated** (two rows). Either may be correct; **nobody knows which is intended.** Record, don't judge |
| 10 | **Reload the page** (`navigate` to the same URL) | List identical to pre-reload, including checked states |
| 11 | **Log out, log back in** | List identical again. **This is where a client-only cart would vanish** |
| 12 | **Clear All** | Only if the list contains solely items this run added. See scope rule below |

## Scope rule — create only

**Remove only what this run added.** Step 12 is conditional: if the list
holds anything pre-existing, **do not clear it** — remove this run's items
individually and record that step 12 was skipped and why. A skipped step
reported is worth more than a destroyed fixture.

## Recording

- After **each** step: `read_console_messages` with
  `pattern: "error|Error|TypeError|Exception|failed"`, and
  `read_network_requests` with `urlPattern: "/v1/"`.
- Record **every** non-2xx, and **every** console error, **even where the UI
  looked fine.** Given this feature's history, that is the likely finding.
- A step that *looks* right with an error underneath is a **failure**, and
  should be reported as one.

## What this plan cannot establish

- **It does not prove the Decimal bug is fixed** — only that it did not fire
  on these paths with these values. The vulnerable cast is still present.
- **Single-user only.** The cart is a *shared* list; nothing here exercises
  two members, and `member_presence.dart` suggests concurrent use is a real
  path. Out of scope, worth its own plan.
- **No quantity beyond `1.5`.** Fractions, zero, and very large values are
  the obvious next cases and are not covered.

## Status log

- 2026-09-24 — plan written and **held**. Browser tools confirmed loaded,
  none called. Awaiting the baton from leonidbelyi-41.
