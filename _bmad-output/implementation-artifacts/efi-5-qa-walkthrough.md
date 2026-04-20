# efi-5 — QA walkthrough

Flutter primitives story. No screen wiring yet — just the widget, the
constant, the decoder, and the API-client method.

## Local checks

```bash
cd app
flutter test test/core/constants/inferable_fields_test.dart \
             test/features/recipes/widgets/inferred_field_badge_test.dart
dart analyze lib/core/constants/inferable_fields.dart \
             lib/core/services/api_client.dart \
             lib/features/recipes/add_recipe/widgets/inferred_field_badge.dart
```

Expected: 13 tests green (8 constant + decoder, 5 widget), `dart analyze`
clean on all three files.

## Visual smoke (optional)

In a `dev` device, drop the badge into any debug screen to eyeball the
sparkle color + tap-to-explainer flow:

```dart
// Somewhere in a debug widget:
Row(
  children: [
    const Text('Cook time'),
    const InferredFieldBadge(),
  ],
);
```

Verify:
* The sparkle uses the ColorScheme tertiary tone (purple-ish in the default
  theme, correctly flips on dark mode).
* Tap opens "AI guess" bottom sheet with the explainer copy. Dismiss by
  tapping outside or swiping down.

## Contract drift guardrail

If the backend `INFERABLE_FIELDS` tuple gains / loses entries, the
contract test in `inferable_fields_test.dart` fails immediately. The
expected failure message points straight at the need to hand-sync the
Dart set — matches the existing riip-1 / irrd-3 precedent for
client-server allow-list sync.
