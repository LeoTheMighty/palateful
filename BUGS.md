> **⚠️ Imported into devx 2026-07-27.** Live items now tracked in
> `DEBUG.md` (rbv101 card sizing, btri01 legacy triage, plus lgort1 /
> cldb01 / imptb1 / rcres1 filed during that triage) and `INTERVIEW.md`
> (RDS Performance Insights decision). New bug reports go to `DEBUG.md`
> via `/devx`; this file is a historical inbox. See
> `_devx/import-2026-07-27.md`.
>
> **btri01 triage complete (2026-07-27).** All five reports in the second
> section below now carry a dated verdict inline. Nothing in that section
> is double-tracked: where a report is still alive it points at its
> `DEBUG.md` spec rather than restating the bug.

Bugs/Improvements:

* Everything in the recipe book view should be the same size, meals and recipes.

===================

* Creating a Meal breaks
    * **btri01 2026-07-27 — CLOSED, fixed by `6d888c6`; one residual dead-end
      fixed here.** Primary cause: `MealService.create_with_components` bulk-added
      the `MealRecipe` join rows through the ORM. Every row in the batch shares
      one `meal_id`, which collides SQLAlchemy 2.0's `insertmanyvalues` sentinel
      matcher — so *every* `POST /v1/recipe-books/{id}/meals` raised "Can't match
      sentinel values in result set to parameter sets" and 500'd. Not
      conditional, not data-dependent: meal creation was 100% broken from mcv-2
      (`c41620f`, 2026-04-18) until `6d888c6` (2026-04-21 21:59) swapped the join
      inserts to Core executemany. This report came off the same dogfood list
      that seeded `epic-bugs-auth-and-shopping` (drafted 2026-04-21 15:16), i.e.
      hours *before* the fix landed — which is also why the bas epic picked up
      the other four items and left this one alone. The Core-executemany shape is
      pinned by `test_meal_service.py::TestCreateWithComponents` and survived the
      aam-10 async rewrite.
    * **Residual, fixed here:** creating a Meal that includes a recipe the user
      can no longer read still dead-ended. mcv-5 built a per-row "Unavailable" +
      Remove affordance on `CreateMealSheet` for exactly this case, but it was
      unreachable end-to-end: (a) the client mapped only `422` +
      `MEAL_COMPONENT_UNAVAILABLE` (306) — a code **nothing on the server has
      ever raised** — while `CreateMeal`/`AddRecipeToMeal` emit `404` +
      `MEAL_COMPONENT_UNREADABLE` (302); and (b) `Endpoint.run` /
      `AsyncEndpoint.run` hard-coded `failure(data={})`, so the `recipe_ids` the
      sheet reads could never leave the server even with the codes aligned. Net
      effect: a generic "Could not create meal. Please try again." on a payload
      that can never succeed, with no way to tell which recipe to drop. Fixed by
      giving `APIException` an optional `data` dict (threaded through both
      `run()` paths; unset still serialises as `{}`), having both meal handlers
      ship `{"recipe_ids": [...]}`, and teaching `MealService._rethrowTyped` the
      404/302 shape. Pinned by `test_meal_router.py`,
      `test_meal_components.py`, and 3 new cases in `meal_service_test.dart`
      (all verified failing against the unfixed code).
    * Test-gap note: this survived because both sides were tested against the
      *assumed* contract and never against each other — `create_meal_sheet_test`
      throws `MealComponentUnavailableException` from a fake service, and
      `meal_service_test` fed itself a 422/306 body no endpoint produces.
* PUSH NOTIFICATIONS
    * **btri01 2026-07-27 — plumbing CLOSED, delivery bug found and fixed
      here.** Everything the two notification epics built is present and
      correct on current main: `Runner.entitlements` carries
      `aps-environment=production`, `Info.plist` declares
      `UIBackgroundModes=remote-notification`, `AppDelegate.swift` forwards
      the APNs device token into `Messaging.messaging().apnsToken` with a
      10s watchdog reported over the `palateful/push` MethodChannel,
      `main.dart` calls `ensureRegistered` at boot **and** on every
      `AppLifecycleState.resumed`, `RegisterPushToken` persists to the
      `push_tokens` JSONB, terraform pipes `FIREBASE_CREDENTIALS_JSON` from
      Secrets Manager into both the api and worker task definitions, and
      every deep-link route `_routeForNotification` can emit exists in
      `app_router.dart`. So "do we even have firebase set up correctly?" —
      yes, since `epic-notifications-ios-proofoflife`.
    * **What was still broken: quiet hours were evaluated in the
      container's timezone, not the user's.** Every `users` row is created
      with `notification_preferences` defaulting (ORM default *and* the
      `20260117041822` migration's `server_default`) to
      `quiet_hours_start: "22:00"`, `quiet_hours_end: "08:00"`,
      `timezone: "America/Denver"`. But `PushNotificationService.
      _is_quiet_hours` called bare `datetime.now()` and never read the
      `timezone` key at all. ECS Fargate containers run UTC (nothing sets
      `TZ` in terraform or either Dockerfile), so the window was applied as
      22:00–08:00 **UTC** — i.e. **16:00–02:00 America/Denver**. Net effect:
      every non-forced push to a default-prefs user between 4pm and 2am
      local returned `suppressed_by_quiet_hours: True` and was never sent.
      That is the entire dogfooding window (evening meal planning, evening
      imports, evening shopping-list edits). Symmetrically, pushes leaked at
      07:00 local, which is inside the window the user actually asked for.
    * Why the proof-of-life epic looked green anyway: the admin test-push
      endpoint (`send_test_push.py`) defaults `force: bool = True`, and
      `force` is precisely the flag that bypasses the quiet-hours check. The
      one push path that was ever manually verified is the one path that
      skips the broken code. The unit tests missed it for the same reason —
      they only ever used windows like `00:00`–`23:59`, where the timezone
      offset cannot change the answer.
    * **Fixed here:** `_is_quiet_hours` now resolves the user's IANA tz via
      a new `_resolve_timezone` helper and evaluates `datetime.now(tz)`.
      Missing / malformed `timezone` falls back to `ZoneInfo("UTC")`,
      matching the existing `_owner_timezone` convention in
      `send_meal_reminders.py` and preserving the old behaviour for the
      (nonexistent) rows without the key. Pinned by 4 parametrised cases +
      an end-to-end `send_to_user` case + 5 bad-timezone fallback cases in
      `libraries/utils/test/test_push_notification.py`; the 3 that matter
      were verified failing against the pre-fix `datetime.now()`.
    * Follow-up worth watching, deliberately not changed:
      `users.notification_permission_status` is written in exactly one
      place — `complete_onboarding.py`. Nothing updates it when the user
      later grants or revokes permission in OS Settings, so the admin push
      health panel and `inspect_user_push.py` can both report a status
      that is months stale. Observability gap, not a delivery bug.
* Logging out shows a weird auth0 page
    * **btri01 2026-07-27 — STILL BROKEN, refiled.** bas-1 (`f839f67`) is not a
      fix: it hand-builds a `returnTo` with `Environment.auth0Scheme`
      (`com.palateful.app`) in the path segment that `auth0_flutter` fills with
      the bundle id / package name (`com.palateful.palateful`), and the SDK
      already defaults `returnTo` to the correct URL when the argument is
      omitted. Now tracked in
      `debug/debug-lgort1-2026-07-27T17:41-auth0-logout-returnto-malformed.md`
      (+ a MANUAL.md item to read back the tenant's Allowed Logout URLs).
* Change language to be "dismiss" in imports/notifs instead of archive (for successful ones it's weird language)
* Shopping cart still broken
    * Can't open at all because of "Import all from calendar" bug
        * **btri01 2026-07-27 — CLOSED, cause removed.** The bulk "import all
          from calendar" path was `POST /v1/shopping-lists/{id}/populate-from-
          calendar`; cpms-2 (`e94a48c`, 2026-04-18) deleted the endpoint, its
          `PopulateFromCalendar` class, router handler and tests outright and
          replaced it with the per-event `POST /v1/meal-events/{id}/add-to-
          shopping-list`. Nothing in `app/` references the old path any more
          (grep for `populate-from-calendar` / `populateFromCalendar` is clean
          outside two prose comments). The list-load path it used to poison is
          also hardened: bas-3 made `ShoppingListItem.fromJson` tolerate a
          null `name` and malformed dates, and bas-3's AC7 priority audit
          checks out — `shopping_list_items.priority` is `nullable=False,
          server_default="3"` (`20260130000001_add_shared_shopping_cart.py:110`),
          so `ItemResponse.priority: int` can't raise on a NULL row.
    * Also still seeing the Websocket errors in crashlytics
        * **btri01 2026-07-27 — WAS STILL BROKEN, fixed here.** bas-3's AC5
          added "refresh once on a 4xxx close code before reconnecting", but
          the hand-off never happened: `AuthService.refreshToken()` only
          rotates its own credentials, and the sole runtime writer of
          `ApiClient._authToken` is the Dio 401 interceptor (bas-4), which
          needs an HTTP 401 to fire. A WS-only rejection never produces one,
          so `_doConnect` re-read the same rejected token from
          `_apiClient.authToken`, the backend closed 4003 again, and the 5s
          reconnect + `ErrorReporter.report` pair repeated forever — exactly
          the Crashlytics noise reported here. `_refreshTokenThenReconnect`
          now installs the refreshed token via `_apiClient.setAuthToken`;
          pinned by `app/test/features/shopping_cart/ws_refresh_token_propagation_test.dart`
          (4 tests, verified failing before the fix).
        * Follow-up worth watching, deliberately not changed: the reconnect
          has no backoff and no give-up, so any permanently-failing socket
          still reports once every 5s. The bas epic locked the 5s timer, so
          re-tuning it is a separate item, not a btri01 fix. Same for the
          dangling `_errorDetail` field + unused `error_banner.dart` import on
          both `shopping_list_screen.dart` and `floating_cart_widget.dart` —
          bas-3 captures `ErrorReporter.detail(e)` but never renders it, so the
          user still gets a bare "Failed to load shopping list" + Retry. Cosmetic;
          the cart is not a dead end.
* When token needs a refresh sometimes get very strange errors in the app, should detect "need to refresh auth" errors everywhere
    * **btri01 2026-07-27 — CLOSED, fixed by bas-4 (`db1a8e4`).** The Dio
      interceptor now logs out (→ app-level redirect to `/login`) whenever the
      401 refresh path returns false or throws, instead of surfacing a raw
      `DioException` on whatever screen the user was on. bas-4 shipped without
      the unit tests its own ACs called for; btri01 added them in
      `app/test/core/services/api_client_401_refresh_test.dart` — 5 tests,
      passing, covering refresh-succeeds / returns-false / throws /
      retry-also-401 (loop guard) / no-auth-service.



=================== old =======

* Still experiencing bug on the current shopping cart after trying to import all ingredients from the calendar.
* **Calendar reminder — 2026-10-08 (day 170 of PI free tier)**: Performance Insights on `palateful-db-prod` switches off free tier around this date. Either keep it (~$2/mo, stays under NFR29's $50 cap) or toggle `performance_insights_enabled=false` in `terraform/modules/rds/main.tf`. Decide before the date so we don't get a surprise bill.
* 

======= OLD =========

* Latency data now lands at `/admin/metrics` (endpoint + task p50/p95/p99 + sparklines). Use this as the first stop before filing a "feels slow" bug.

========== OLD ==============

* Latency metrics on endpoints/tasks would be good. Still don't want to use datadog, wonder what a good way to handle this is
* Feedback from users will be crucial, I want that in the admin section, and also want notifications for it as an admin.
* Also let's make a prod script for fetching feedbacks

======= OLD ============

* Remove the "add image" icon from the top, not useful.
* Really need to get notifications going, I haven't seen a single one work yet. Do we even have firebase setup correctly?
    * **btri01 2026-07-27 — same report as "PUSH NOTIFICATIONS" above; see
      that entry for the verdict.** Short version: Firebase *was* set up
      correctly, but the UTC-vs-user-timezone quiet-hours bug suppressed
      every real push during evening hours. Fixed in this item.
* After you add a recipe, should go back to the current page (like from Photo) going back to the home page is little jarring, esp if we want to add another
* I wonder what would happen if we had two recipes in one image? Would we be smart enough to do it correctly? This feels like something HunyuanOCR could handle, we might be able to have it return separate recipes via a prompt.
* Review Import definitely need to see the unit and quantity and notes here. After extractor changes don't see it at all, probably should be in separate dropdown/unit fields.
* I wonder if the Import has an ability to store the images usually. Would be cool if we were able to grab a crop from the image for this, but I know that could be challenging. For web it might be easier to find and store the URL if that's accessible? But there are probably copyright issues there. Maybe we just have the end of a recipe having an easy to use "Snap Picture".
* We want to be able to change calendars and share calendars with others and have them able to have full edit/add permissions too.

========= OLD ================
* Tapping calendar meal should bring you to the Meal page
    * Maybe some combination of meal and mealplan where you can see the recipe, or reschedule, or unschedule it
    * Hmm honestly it should be a "Day View" when you tap on it, or a specific element based on where you tap. Different levels
    * You should always have a default shopping list, add it to the onboard flow or something
* Calendar needs recurrence, maybe not default but certainly easy to setup.
* When you plan a meal you absolutely need to have a autocomplete with your meals there, a meal should be attached to a meal plan for sure.
* I (leonid@ac93.org or @leo need to be an admin, gotta run a prod script to do that)
* Move the AI assistant out of the main view for now, I want to work on it later but not quite yet.
    * Additionally an MCP makes this virtually useless.
    * Maybe there's somewhere in the app to advertise this, but it's very tech heavy IDK.
* Since with the meal plan, the home screen could become bloated maybe it's best to use a Sort/Filter icon at the top row, move the "Sort" options into that and then get rid of the chat window.
* Maybe we should make our own error tracing in the database... As much as I like to use external resources, crashlytics won't be useful if you or I can't really read it.
    * Could build it out so that I as an admin can look at everyone's errors too... can't do that with crashlytics huh
    * Maybe I should use both ?
* Activity Hub
    * Needs a proper re-do and we need consolidate both the import activity in the "Add Recipe" page, I want that experience in the Activity hub/import hub
    * These notifications still aren't "readable" they don't go away and I can't get them to leave
    * Also there's literally information in the import activity that I can't see


======== OLD ===========


* Activity tab - Needs Review shows up but when I tap it nothing shows up, seems broken.
* Activity tab has "Photo OCR failed" but every time I go to it it's unread, can read in the moment, but going back always shows unread
* Activity tab always has a big number of unread. Is 'reading' working? 
* Import activity shows a (1) but then has "All Set", similar to needs review maybe?
* Calendar completely broken tried to add a meal but now it says failed to load calendar every time I go there
* Maybe recipe book icon to the left of the search bar?
* I like the in progress tab in the Add Recipe, but it should be how the Import Activity looks like. Currently the import history looks bad. "0 / 1 imported" confusing
