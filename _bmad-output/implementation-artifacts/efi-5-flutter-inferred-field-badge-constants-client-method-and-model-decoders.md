# Story efi-5 — `InferredFieldBadge` widget + `kInferableFields` + client method + decoders

**Status:** done
**Epic:** epic-extractor-field-inference
**Depends on:** efi-4 (API surface: hoisted `inferred_fields` + `/corrections` endpoint).

## Scope

Client-side primitives the Review Import + Recipe Edit wiring (efi-6 / efi-7) will consume:

1. `kInferableFields` constant — Set<String>, hand-synced to backend.
2. `decodeInferredFields(raw)` — bulletproof decoder: null / non-list / non-string entries / non-allow-list names → empty set.
3. `InferredFieldBadge` widget — stateless, 14pt `Icons.auto_awesome` sparkle in `colorScheme.tertiary`, 40pt tap target, default tap opens explainer bottom sheet.
4. `ApiClient.submitImportCorrection` — thin dio wrapper on `POST /v1/import-items/{id}/corrections`, accepts dynamic `corrected`.

No Recipe / ImportItem Dart model classes exist; Flutter passes recipe data as `Map<String, dynamic>`, so the decoder is a standalone helper rather than a class member.

## Implementation notes

- The badge's visibility is **derived state** (design principle 4 from the epic). Parents own a `Set<String> _inferredFields`; the badge renders only when a field's name is in that set. Editing the field → parent removes the name → badge vanishes. No imperative show/hide.
- The explainer sheet lives alongside the widget so consumers don't have to import a separate dialog. Custom `onTap` overrides the default sheet (future uses may prefer an inline tooltip).
- `decodeInferredFields` is the single client-edge decoder so every screen (Review Import, Recipe Edit, future admin dashboard) shares one tolerance contract.
- `submitImportCorrection` returns the raw `Response` so callers can log-and-ignore without blocking save — per design principle 14 (debounced + best-effort).

## File list

- `app/lib/core/constants/inferable_fields.dart` [NEW] — `kInferableFields` + `decodeInferredFields`.
- `app/lib/features/recipes/add_recipe/widgets/inferred_field_badge.dart` [NEW] — stateless badge widget + explainer sheet.
- `app/lib/core/services/api_client.dart` [MODIFY] — `submitImportCorrection` method.
- `app/test/core/constants/inferable_fields_test.dart` [NEW] — 8 tests on the constant + decoder.
- `app/test/features/recipes/widgets/inferred_field_badge_test.dart` [NEW] — 5 widget tests (icon, a11y, default / custom onTap, tap-target size).

## Acceptance criteria — coverage

| AC | How |
|----|-----|
| 1 | `inferred_field_badge.dart` — stateless `StatelessWidget`, `Icons.auto_awesome` size 14 in `colorScheme.tertiary`, `InkWell` with 13pt padding = 40pt tap target, `Semantics(label: "AI-inferred value, tap for details", button: true)`. |
| 2 | `_showExplainer` — `showModalBottomSheet` with "AI guess" title + the body copy. Covered by `default onTap opens the explainer sheet`. |
| 3 | `inferable_fields.dart` — `kInferableFields` has exactly 9 entries; contract test pins length + content. |
| 4 | `api_client.dart` — `submitImportCorrection` wraps `_dio.post(.../corrections)` with `{field, corrected}`. |
| 5 / 6 | `decodeInferredFields` is the single decoder path. Covered by all 7 decoder tests. |
| 7 | Widget test covers icon glyph + color contract (non-null tertiary-scheme color) + accessibility label + both tap paths + tap-target size. |
| 8 | No review-import / recipe-edit wiring; efi-6 / efi-7 take it from here. |
