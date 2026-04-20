# efi-6 — QA walkthrough

Flutter wiring story for Review Import. Badge renders on 4 inferable
fields (description, prep_time_minutes, cook_time_minutes, servings);
editing any of them clears the sparkle immediately and dispatches a
debounced correction to the audit endpoint.

## Local checks

```bash
cd app
dart analyze lib/features/recipes/add_recipe/import_item_review_screen.dart
flutter test test/features/recipes/add_recipe/import_review_list_nav_test.dart \
             test/core/constants/inferable_fields_test.dart \
             test/features/recipes/widgets/inferred_field_badge_test.dart
```

Expected: analyze shows only the 2 pre-existing warnings about
`error_banner` import + `_errorDetail` field (not introduced by this
story); all existing tests continue to pass.

## Manual device sanity

Requires a dev backend with `EXTRACTOR_INFER_MISSING_FIELDS=true`
(default) + a fresh import-item whose extraction flagged 1+ inferable
fields.

1. Launch the app → Activity → Imports → tap the awaiting-review item.
2. Verify: sparkle (✨) appears next to "Cook (min)" / "Prep (min)" /
   "Servings" / "Description" based on what the extractor flagged.
3. Tap the ✨ next to any field:
   * Expect a bottom sheet titled "AI guess" with the explainer copy.
   * Dismiss by swiping down.
4. Edit the field value (type a new digit / text):
   * Sparkle disappears immediately (no animation, just gone).
5. Click outside the field (focus-loss) or wait ~1.5s:
   * Network inspector should show `POST /v1/import-items/{id}/corrections`
     with `{"field": "<name>", "corrected": <value>}`.
6. Verify on the backend:
   ```sql
   SELECT error_message
     FROM error_logs
    WHERE service='audit'
      AND error_type='InferredFieldCorrected'
      AND import_item_id = '<item-id>'
    ORDER BY created_at DESC LIMIT 5;
   ```
   The metadata JSON should show the correct `field`, `original`,
   `corrected`, and `was_inferred: true`.
7. Revert the field to its original value:
   * Sparkle should NOT reappear (design principle 5: any-edit is
     dismissal).
   * A new dispatch fires on focus-loss with the original value — this
     is expected, the audit log just captures every edit cycle.
8. Tap Approve / Save:
   * Recipe creates normally; `recipes.inferred_fields` reflects the
     extractor's post-guardrail list MINUS whichever fields the user
     edited (handled server-side by `create_recipe_task`).

## Regression sanity

* Zero-inferred items (clean URL extraction): no sparkle anywhere. Review
  Import UX identical to pre-epi-6.
* Offline mode: correction dispatch silently fails, but badge still
  dismisses. No user-facing error.
