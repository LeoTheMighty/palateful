b# Story 1.2: Sign In with Google & Apple — QA Walkthrough

## Prerequisites

- [ ] Auth0 dashboard: Google social connection enabled and configured with OAuth client ID/secret
- [ ] Auth0 dashboard: Apple social connection enabled and configured with Service ID and key
- [ ] Auth0 dashboard: Callback URLs set for both iOS (`com.palateful.app`) and Android (`com.palateful.app`) schemes
- [ ] Run `cd app && flutter pub get`
- [ ] Run `cd app && flutter test` — all 25 tests should pass

## Sign In with Google (AC #1)

- [ ] Launch app on iOS or Android device/simulator
- [ ] On login screen, see "Sign in with Google" button (white background, Google icon)
- [ ] Tap button → redirected to Google OAuth consent screen (NOT Auth0 Universal Login)
- [ ] Complete Google sign-in → redirected back to app
- [ ] If new user → enters onboarding flow
- [ ] If returning user → lands on Home screen

## Sign In with Apple (AC #1)

- [ ] On iOS device/simulator, see "Sign in with Apple" button (black background, Apple icon)
- [ ] On Android, Apple button should NOT be visible
- [ ] Tap button → Apple authentication sheet appears
- [ ] Complete Apple sign-in → redirected back to app
- [ ] Same onboarding/home flow as Google

## Fallback Sign-In (AC #1)

- [ ] "Other sign-in options" text button exists below social buttons
- [ ] Tapping opens Auth0 Universal Login page with all available providers
- [ ] Can authenticate via any enabled connection

## JWT & API Calls (AC #2)

- [ ] After sign-in, navigate to Home → recipes load (API calls work)
- [ ] Check debug logs: `Authorization: Bearer <token>` header present on API requests

## Token Refresh (AC #3)

- [ ] Wait for token to approach expiry or force expiry
- [ ] App continues to work without re-login
- [ ] Debug logs show token refresh occurring (5-minute expiry buffer in `api_client.dart`)

## Security (AC #4, #5)

- [ ] All API calls use HTTPS (check network inspector)
- [ ] No plaintext tokens in app logs or storage
- [ ] Credentials stored via Auth0 `credentialsManager` (Keychain on iOS, Keystore on Android)

## Error Handling

- [ ] Dismiss Google/Apple auth mid-flow → error message displayed in themed error container, no crash
- [ ] Network offline during auth → appropriate error message
- [ ] Error message clears when retrying

## Platform Callbacks

- [ ] iOS: After Auth0 redirect, app correctly handles callback URL (Info.plist scheme: `com.palateful.app`)
- [ ] Android: After Auth0 redirect, app correctly handles callback intent (AndroidManifest intent-filter scheme: `com.palateful.app`)

## UI/UX Checks

- [ ] Login screen shows app icon, "Palateful" heading, "Your personal recipe book" subtitle
- [ ] Google button: white background, dark text, Google icon, rounded corners
- [ ] Apple button (iOS only): black background, white text, Apple icon, rounded corners
- [ ] Loading indicator appears during authentication
- [ ] "Use access token instead (for testing)" link still works for dev token input
- [ ] All colors are theme-aware (no hardcoded colors)

## Regression

- [ ] Existing Story 1.1 features still work (navigation, theme, shimmer loading, empty states)
- [ ] `cd app && flutter test` — all 25 tests pass (18 from Story 1.1 + 7 new)

## Files Changed

| File | Change |
|------|--------|
| `app/lib/core/services/auth_service.dart` | Added optional `connection` parameter to `login()` |
| `app/lib/core/services/auth_service_web.dart` | Added `connection` parameter to `loginWithRedirect()` |
| `app/lib/core/services/auth_service_stub.dart` | Updated stub signature to match |
| `app/lib/features/auth/login_screen.dart` | Redesigned with social buttons, `_SocialSignInButton` widget |
| `app/ios/Runner/Info.plist` | Fixed URL scheme: `com.palateful.palateful` → `com.palateful.app` |
| `app/android/app/src/main/AndroidManifest.xml` | Added Auth0 callback intent-filter |
| `app/test/login_screen_test.dart` | New file — 7 widget tests for login screen UI |
