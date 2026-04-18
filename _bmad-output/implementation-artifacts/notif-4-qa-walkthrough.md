# notif-4 QA walkthrough

## Automated (green)
- [x] `flutter test test/onboarding_screen_test.dart` — 15/15 pass (9 existing + 6 new)
- [x] `dart analyze lib/features/onboarding/ lib/core/router/app_router.dart` — no issues
- [x] `poetry run pytest tests/test_user.py::TestCompleteOnboarding` — 10/10 pass (6 existing + 4 new)
- [x] `npx nx run utils:test` + `utils:lint` — green
- [x] `npx nx run api:lint` + `migrator:lint` — green

## On-device (TestFlight)
- [ ] Fresh install, sign in → notification step appears before start-method screen
- [ ] "Not now" → no OS prompt → proceeds to "How would you like to start?"; backend shows `notification_permission_status="declined"`
- [ ] "Turn on notifications" → OS prompt → **Allow** → start screen next; backend shows `"granted"`
- [ ] Fresh reinstall → "Turn on" → OS prompt → **Don't Allow** → backend shows `"declined"`
- [ ] Fresh reinstall → "Turn on" → swipe OS prompt away without choosing → backend shows `"declined"` (notDetermined bucket)
- [ ] After onboarding, the app never re-prompts (no auto-prompt banners)

## Backend persistence
- [ ] `SELECT notification_permission_status FROM users WHERE id = <your_user_id>;` matches onboarding choice
- [ ] Older clients that don't send the field → column stays NULL, onboarding still succeeds
- [ ] Client sending invalid value (e.g. `"unknown"`) → 422 validation error

## Migration
- [ ] `npx nx run migrator:check-models` passes on CI (against a fresh test DB with only committed migrations)
- [ ] Local: once cal-found-1 lands, their migration rebases `down_revision` to `n1o2t3i4f5p6` — no long-standing branch
