# Research — Shake To Report

<!-- Blind answers to research-questions.md, one section per question; each
     claim cites `path:line`. "Not found" is an answer — say where you looked.
     Re-entry refreshes: re-verify cited lines, answer new questions. -->

<!-- NOT BLIND. This session has no subagent tool, so the authoring session
     answered these itself, having already read the PRD. Every answer cites
     a line read in this session (worktree base origin/main 8434722f, plus
     feat/dev-arq103 b9bf7104 where marked) or a fetched page. -->

## Q1 — Which widget sits above every route?

`PalatefulApp` (`app/lib/main.dart:407`), whose state is already a
`WidgetsBindingObserver` (`app/lib/main.dart:415`, lifecycle handler
`:439`). It builds `MaterialApp.router` with a `builder` that wraps every
route in `PerfOverlay` (`app/lib/main.dart:553`, `:562`). The root
navigator key is exported (`app/lib/core/router/app_router.dart:76`), and
the app already shows root-level snackbars through it
(`app/lib/main.dart:519-522`). `MaterialApp.router` accepts a
`scaffoldMessengerKey` (Flutter `material/app.dart:274`); the app sets none
today.

## Q2 — How does the client know the user is an admin?

`AuthService.isAdmin` (`app/lib/core/services/auth_service.dart:180`), a
private bool that starts `false` (`:23`), is set only by
`updateAdminState` (`:187`), and is reset by session clear (`:479`). It is
set from `/v1/users/me` at boot: E2E (`app/lib/main.dart:167`), normal
(`:219`), and the retry after a token refresh (`:241`). Nothing persists it
and nothing refreshes it mid-session (grep of `app/lib` for
`updateAdminState`). The router's admin redirect reads the same value
(`app/lib/core/router/app_router.dart:225`, `:257`); Profile shows the
admin tiles from it (`app/lib/features/profile/profile_screen.dart:817`).

## Q3 — How is the feedback sheet opened, and when does the queue flush?

Only from Profile: `_openFeedbackSheet`
(`app/lib/features/profile/profile_screen.dart:156`) shows
`FeedbackSheet` in a modal bottom sheet with `currentRoute: '/profile'`
hard-coded (`:173`) and a platform from `dart:io` (`:91-103`). The sheet
sends `app_version`, `platform` and `route` when given
(`app/lib/features/profile/widgets/feedback_sheet.dart:87-92`); on any
error it queues (`:126-136`). The queue is in SharedPreferences
(`app/lib/features/profile/services/feedback_cache_service.dart:8`, `:27`)
and is flushed by `_flushFeedbackQueue` at Profile's `initState` (`:65`)
and on resume while Profile is mounted (`:77`). Profile is a lazily built
tab branch (`app/lib/core/router/app_router.dart:839-845`), so a session
that never opens Profile never flushes. The client posts to
`/v1/users/me/feedback` (`app/lib/core/services/api_client.dart:871-877`).

## Q4 — What does the server accept in a feedback's context?

`FeedbackContext` (`services/api/src/api/v1/user/create_user_feedback.py:69`)
is `extra="forbid"` (`:77`) with `app_version`, `platform`, `route` (512
max) and `recipe_id` (`:79-82`). An unknown key is a 422. The route is
`POST /me/feedback` on the user router
(`services/api/src/routers/v1/user_router.py:214`).

## Q5 — Is there a server-to-client flag mechanism?

Yes. `GET /v1/flags/perf` (`services/api/src/routers/v1/flags_router.py:18`,
handler `services/api/src/api/v1/flags/get_perf_flags.py:28`), public and
unauthenticated, returns settings `client_latency_ingest_enabled` and
`client_latency_sampling_rate` (`services/api/src/config.py:66-67`). The
client's `PerfFlagsService` fetches it at boot and every 5 minutes with a
500 ms timeout, failing open
(`app/lib/core/services/perf_flags_service.dart:62-66`, `:74-102`); boot
calls `initialize()` from `main()` (`app/lib/main.dart:97`). The runbook
flips the value with a console task-definition revision
(`docs/PERFORMANCE_OPS.md:307-313`). Terraform owns the API task
definition's `environment` list (`terraform/modules/ecs/main.tf:277-301`)
and CI deploys through terraform-prod (`.github/workflows/ci.yml:1042-1046`),
so a console-added variable does not survive the next terraform-managed
revision.

## Q6 — Which navigators exist, and can an observer see each one?

The root navigator (`app/lib/core/router/app_router.dart:73`, observers at
`:248`) and one navigator per `StatefulShellRoute.indexedStack` branch
(`:723`), each already given its own observer list (`:731`, `:765`,
`:783`, `:820`, `:842`). The app has 82 `showModalBottomSheet`/`showDialog`
call sites and none passes `useRootNavigator` (grep of `app/lib`), so
sheets land on whichever navigator is nearest. `PopupRoute` is the base of
dialog and sheet routes (Flutter `widgets/routes.dart:2383`).

## Q7 — How does a widget tell that a text input has focus?

`FocusManager.instance.primaryFocus` is the focused node (Flutter
`widgets/focus_manager.dart:1845`, top-level `primaryFocus` `:2357`). A
text field's focus node belongs to an `EditableText`, so the node's
context has an `EditableTextState` ancestor. Not found: any existing
helper for this in `app/lib`.

## Q8 — What does the motion plugin need?

sensors_plus (pub.dev, fetched 2026-11-25): latest 7.1.1; Android, iOS
and web (web cannot set a sampling rate). 7.0.0 raised the Android floor
to AGP ≥ 8.12.1, Gradle ≥ 8.13, Kotlin 2.2.0; 5.0.0 set Java 17, compile
SDK 34, Flutter 3.19, iOS 12; 6.0.0 made `NSMotionUsageDescription`
required in `Info.plist` ("not doing so will crash your app when it
attempts to access motion data", tied to the barometer). Missing sensors:
the plugin does not crash and recommends `onError`. The `shake` package
(3.0.0) depends on sensors_plus `^6.1.1` and defaults to one 2.7 g spike
(`minimumShakeCount: 1`). The app: AGP 8.7.3 and Kotlin 2.1.0
(`app/android/settings.gradle.kts:22`, `:27`), Gradle 8.12
(`app/android/gradle/wrapper/gradle-wrapper.properties:5`), iOS 15.0
(`app/ios/Podfile:9`), Flutter 3.41.7 in CI (`.github/workflows/ci.yml:400`),
no `NSMotionUsageDescription` (grep of `app/ios/Runner/Info.plist`).
Web: `DeviceMotionEvent.requestPermission()` needs transient activation
(a tap) and a secure context (MDN, fetched 2026-11-25).

## Q9 — The plugin's channels and payloads

`dev.fluttercommunity.plus/sensors/user_accel` and
`…/accelerometer` are EventChannels; `…/method` is the MethodChannel;
`setUserAccelerometerSamplingPeriod` takes microseconds. Each event is a
list of doubles `[x, y, z, timestamp_us]` decoded into
`UserAccelerometerEvent(x, y, z, DateTime.fromMicrosecondsSinceEpoch(...))`
(plus_plugins `sensors_plus_platform_interface/lib/src/method_channel_sensors.dart`
on `main`, fetched 2026-11-25).

## Q10 — Snackbars under screen readers

"A SnackBar with an action will not time out when TalkBack or VoiceOver
are enabled", controlled by `accessibleNavigation` (Flutter
`material/snack_bar.dart:227-228`; `material/scaffold.dart:207`, `:446`).

## Q11 — Does iOS's Shake to Undo reach Flutter text fields?

Flutter's iOS engine bridges `NSUndoManager`: "only iOS has an
UndoManagerPlugin implemented on the engine side" (Flutter
`services/undo_manager.dart:30`; engine
`shell/platform/darwin/ios/framework/Source/FlutterUndoManagerPlugin.mm`).
Shake to Undo is driven by `NSUndoManager`, so it can reach a Flutter
field. Not verified on a device in this session.

## Q12 — Where is the dev-request form?

On `feat/dev-arq103` (`b9bf7104`, PR #132 into `feat/admin-request-slice`;
not on `main`): `AdminDevRequestNewScreen.routePath =
'/admin/dev-requests/new'`
(`app/lib/features/admin/admin_dev_request_new_screen.dart:49`), opened by
route alone (`:13-21`), registered in the router (`app_router.dart:681`
on that branch). Closing pops to the pusher with the id8, or `go('/admin')`
when nothing can pop (`:222-229`). Under `/admin`, so the router's admin
redirect applies (`app/lib/core/router/app_router.dart:225`).

## Q13 — Can the real app root be pumped in a widget test?

Yes, measured with a probe in this session (not committed). It needs:
`await GetIt.instance.reset()` before `setupDependencies()` (an un-awaited
reset wipes the new registrations a microtask later); a fake
`PushNotificationService`, whose real one reads `FirebaseMessaging.instance`
in a field initializer (`app/lib/core/services/push_notification_service.dart:74`);
the three provider overrides `main()` applies
(`app/lib/main.dart:300-308`); mock handlers for
`receive_sharing_intent/messages` and `…/events-media`; and an HTTP
adapter that leaves unknown requests pending, since answering every call
instantly made a retry loop spin forever inside the test clock. With
those, the app boots signed in at `/` and `/profile` with no exception,
from a test file outside the `app/` package. Subscribing to and cancelling
a faked EventChannel inside the same test that pumps the app hangs it, so
a channel control runs as its own test.
