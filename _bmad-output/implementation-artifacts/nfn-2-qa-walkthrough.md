# nfn-2 — QA walkthrough

Run all of this on a fresh prod-like deploy with a real iOS device
registered via the admin test-push button.

## Smoke A: single-recipe URL import → push has the recipe name + image

1. From the app, import a single URL recipe (any obvious-name recipe with
   a hero photo, e.g. https://example.com/sweet-potato-quiche).
2. Wait for it to land in awaiting-review.
3. Push lands within 5–10s of the worker finishing.
4. Confirm:
   - Title contains the recipe name AND the 🍳 emoji.
   - Body is `"Tap to confirm the details we extracted."`.
   - Notification has the recipe cover image attached (visible on iOS lock screen and notification center).
5. Tap the push → opens the import review list.

## Smoke B: bulk URL list (5+ recipes) → bulk variant

1. From the app, kick off a bulk URL-list import with ≥2 URLs.
2. When the job finishes:
   - Title is `"Your bulk import is ready"`.
   - Body is `"{N} recipes need a quick review."` matching the count.
   - No image attached.

## Smoke C: import with no extracted name (corrupt source) → fallback copy

1. Import a URL where the extractor can't pull a recipe name (rare, but
   try a non-recipe page that gets routed to extraction).
2. Push body uses the generic `"Your recipe is ready to review"` —
   no awkward template artifacts.

## Logs verification

Watch `bin/prod-logs api` while running smoke A:
- Single line: `push_notifications: sent type=import_needs_review message_id=...`
- No exception traces from `import_notifications`.

## Regression

- Existing `epic-notifications-ios-proofoflife` test push still works
  (admin button → push lands → tap → app opens). Nothing about the
  copy refactor touched diagnostic paths.
- `categories.imports = false` (from nfn-1) still suppresses these
  pushes — copy refactor is callsite-only.
