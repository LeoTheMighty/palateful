# Investigation 09: iOS Native Features Integration

## Executive Summary

Palateful currently has a solid foundation of iOS integration -- push notifications via Firebase, local timer notifications, share sheet receipt via `receive_sharing_intent`, camera/photo library access, speech recognition, and wakelock for cook mode. However, the app uses **none** of the modern iOS platform features that make native apps feel deeply integrated with the operating system: no home screen widgets, no lock screen widgets, no Live Activities, no Siri Shortcuts, no notification actions, no Control Center controls, and no Apple Watch companion.

This investigation catalogs every iOS-native capability relevant to a kitchen management app, evaluates each for user value and implementation complexity within a Flutter codebase, and recommends a phased rollout order. The highest-impact opportunities are:

1. **Cooking timer Live Activities** (Dynamic Island + Lock Screen) -- the single highest-impact feature
2. **Notification actions on timer notifications** ("Add 2 min" / "Reset" on long-press)
3. **Home screen widgets** (next meal, shopping list, quick-start cooking)
4. **Lock screen widgets** (next meal glanceable)
5. **Siri Shortcuts** ("Start cooking [recipe]", "What's for dinner?")

These five alone would transform Palateful from "just another app" into an app that feels like part of the OS.

---

## Current State Analysis

### What iOS Integration Exists Today

| Feature | Status | Implementation |
|---------|--------|----------------|
| Push notifications (FCM) | Implemented | `firebase_messaging` + backend token registration |
| Local timer notifications | Implemented | `flutter_local_notifications` with `zonedSchedule` |
| Notification tap deep-linking | Implemented | Routes to cook mode, cart, calendar, recipe books, etc. |
| Notification preferences | Implemented | Push toggle, quiet hours, partner activity toggle |
| Share sheet receipt | Implemented | `receive_sharing_intent` -- URLs shared into app trigger recipe import |
| Camera / photo library | Implemented | `image_picker` for recipe photos and OCR import |
| Speech recognition | Implemented | `speech_to_text` for voice input in cook mode chat |
| Wakelock in cook mode | Implemented | `wakelock_plus` keeps screen on while cooking |
| Auth0 URL scheme | Implemented | `com.palateful.app` callback scheme |

### What Does NOT Exist

| Feature | Status |
|---------|--------|
| Home screen widgets (WidgetKit) | Not implemented |
| Lock screen widgets | Not implemented |
| StandBy mode widgets | Not implemented |
| Live Activities / Dynamic Island | Not implemented |
| Interactive widgets (buttons/toggles) | Not implemented |
| Notification actions (long-press) | Not implemented |
| Rich notifications (images) | Not implemented |
| Notification categories/grouping | Not implemented |
| Siri Shortcuts / App Intents | Not implemented |
| Spotlight search indexing | Not implemented |
| Share Extension (native iOS) | Not implemented (uses `receive_sharing_intent` plugin instead) |
| App Clips | Not implemented |
| Focus Filters | Not implemented |
| Apple Watch companion | Not implemented |
| CarPlay integration | Not implemented |
| Control Center controls | Not implemented |
| Handoff | Not implemented |
| Platform channels | Not implemented (no custom MethodChannel usage) |
| App Group data sharing | Not implemented |
| Entitlements file | Does not exist |

### Key Technical Observations

- **AppDelegate.swift** is stock Flutter boilerplate -- no custom iOS code at all
- **Info.plist** has permissions for camera, photo library, microphone, speech recognition, and the Auth0 URL scheme -- no background modes, no App Groups
- **No entitlements file** exists -- would need to be created for App Groups, push notifications entitlement, etc.
- **No widget extensions** in the Xcode project
- **No platform channels** -- all iOS interaction goes through Flutter plugins
- **Podfile** targets iOS 14.0 minimum -- would need to raise to 16.1+ for Live Activities, 17.0+ for interactive widgets and StandBy mode
- **No SwiftUI code** -- all UI is pure Flutter/Dart
- The existing timer notification uses `flutter_local_notifications` but does not register any notification categories or actions

---

## iOS Feature Catalog

### 1. Home Screen Widgets (WidgetKit)

#### What It Is
WidgetKit allows apps to display glanceable, read-only (or interactive on iOS 17+) content on the home screen. Widgets come in four sizes:
- **Small** (2x2 icon grid) -- single piece of info
- **Medium** (4x2) -- list or summary
- **Large** (4x4) -- detailed view
- **Extra Large** (iPad only, 8x4)

#### Palateful Use Cases

**A. "Next Meal" Widget (Small)**
- Shows the next scheduled meal from the calendar
- Displays: meal type icon (breakfast/lunch/dinner), recipe name, scheduled time
- Tapping opens the recipe detail or cook mode
- Updates via timeline provider checking meal events

**B. "Today's Meals" Widget (Medium)**
- Shows all meals planned for today (breakfast, lunch, dinner)
- Each row: meal type, recipe name, time, recipe thumbnail
- Tapping a meal opens its recipe
- Empty state: "No meals planned -- tap to plan"

**C. "Shopping List" Widget (Medium or Large)**
- Shows unchecked items from the active shopping list
- Displays item count badge: "5 items remaining"
- On iOS 17+: interactive checkboxes to mark items off right from the widget
- Groups by urgency (overdue items highlighted)

**D. "Quick Cook" Widget (Small)**
- Shows a random favorite recipe or recently cooked recipe
- One-tap to launch cook mode for that recipe
- Rotates daily or on each widget refresh

**E. "Cooking Stats" Widget (Small)**
- Shows cooking streak, recipes cooked this week, total cook time
- Motivational at-a-glance info

#### User Value: **HIGH**
Widgets are the #1 most visible iOS integration. They make the app feel "alive" even when not open.

#### Implementation Complexity: **Medium-High**
- Requires native Swift/SwiftUI code for widget UI (cannot use Flutter for widget rendering)
- Requires App Groups for data sharing between Flutter app and widget extension
- Uses `home_widget` Flutter package for data bridge
- Each widget size needs its own SwiftUI layout
- Timeline providers need to be configured for refresh intervals
- Interactive widgets (iOS 17+) require App Intents integration

---

### 2. Lock Screen Widgets (iOS 16+)

#### What It Is
Small, inline widgets displayed on the lock screen. Three placements:
- **Inline** (above the time) -- text only
- **Circular** (below the time) -- icon + small text
- **Rectangular** (below the time) -- icon + 2 lines of text

#### Palateful Use Cases

**A. "Next Meal" Circular Widget**
- Shows meal type icon + time (e.g., dinner icon + "6:30 PM")
- Tapping opens the app to that meal's recipe

**B. "Shopping Count" Circular Widget**
- Shows shopping cart icon + unchecked item count (e.g., "7")
- Tapping opens shopping list

**C. "Next Meal" Rectangular Widget**
- Shows: "Dinner at 6:30 PM" + recipe name
- Two lines of glanceable info

**D. "Timer Active" Circular Widget**
- When a cooking timer is running, shows remaining time
- Updates every minute via timeline

#### User Value: **HIGH**
Lock screen is the most frequently seen screen on any iPhone. Showing "Dinner: Pad Thai at 6:30" without unlocking is extremely valuable for meal planning.

#### Implementation Complexity: **Medium**
- Same WidgetKit extension as home screen widgets -- lock screen widgets are just different "families"
- Simpler UI (less SwiftUI needed)
- Shares data infrastructure with home screen widgets

---

### 3. StandBy Mode Widgets (iOS 17+)

#### What It Is
When iPhone is placed on a MagSafe charger in landscape orientation, StandBy mode shows enlarged widgets. Your existing widgets automatically work in StandBy mode with no extra code.

#### Palateful Use Cases
- **Kitchen countertop scenario**: Phone on MagSafe stand while cooking
- The "Next Meal" or "Shopping List" widget becomes a large, easy-to-read display
- Timer countdown visible across the kitchen

#### User Value: **HIGH** (for the cooking use case specifically)
This is the perfect kitchen scenario -- phone charging on the counter, showing what you are cooking next or your active timer.

#### Implementation Complexity: **Low** (free if home screen widgets are built)
- StandBy mode automatically uses existing WidgetKit widgets
- No additional code required beyond building home screen widgets

---

### 4. Interactive Widgets (iOS 17+)

#### What It Is
Widgets can contain buttons and toggles that execute actions without opening the app. Uses App Intents framework.

#### Palateful Use Cases

**A. Shopping List Checkboxes**
- Each item in the shopping list widget has a checkbox toggle
- Tapping marks the item as checked/unchecked and syncs to backend
- No need to open the app just to check off "milk"

**B. "Start Cooking" Button**
- Button on the "Next Meal" widget that launches directly into cook mode

**C. Timer Quick-Start**
- Pre-configured timer buttons (5 min, 10 min, 15 min) on a cooking widget

#### User Value: **HIGH**
Shopping list checkboxes alone make this extremely valuable -- checking items at the grocery store without opening the app.

#### Implementation Complexity: **High**
- Requires App Intents framework (native Swift)
- Each interactive element needs a corresponding AppIntent
- Data sync between widget action and Flutter app state
- Needs careful error handling for offline scenarios

---

### 5. Live Activities & Dynamic Island

#### What It Is
Live Activities display real-time, updating content on the lock screen and in the Dynamic Island (iPhone 14 Pro+). They are designed for time-bound events that the user wants to track.

#### Palateful Use Cases

**A. Active Cooking Timer (PRIMARY USE CASE)**
- When a cooking timer is started in cook mode, a Live Activity appears
- **Lock Screen**: Shows timer label ("Step 3: Simmer"), countdown, progress bar, recipe name
- **Dynamic Island (compact)**: Shows timer icon + countdown "04:32"
- **Dynamic Island (expanded)**: Shows timer label, countdown, "Add 2 min" button, "Cancel" button
- **Dynamic Island (minimal)**: Small countdown number when another app is in foreground
- Timer continues updating even when the app is backgrounded or screen is locked
- When timer completes: Live Activity shows "Done!" with haptic alert

**B. Active Cook Session**
- When user enters cook mode, a Live Activity shows
- Displays: recipe name, current step "Step 3 of 8", elapsed time
- Persists on lock screen so user can quickly return to cook mode
- Dynamic Island shows recipe name + step number

**C. Recipe Import Progress**
- When a batch import is running, show progress
- "Importing 5 recipes... 3/5 complete"
- Less critical but nice for long-running background imports

#### User Value: **VERY HIGH**
This is the single most impactful feature for Palateful. The cooking timer in the Dynamic Island is the exact use case Apple designed Live Activities for. Users can:
- See their timer countdown without unlocking the phone
- See it in the Dynamic Island while browsing other apps
- Interact with it (add time, cancel) from the Dynamic Island
- Get alerted when the timer completes with a prominent notification

#### Implementation Complexity: **High**
- Requires iOS 16.1+ (would need to raise minimum deployment target)
- Uses ActivityKit framework (native Swift)
- Live Activity UI must be built in SwiftUI
- Flutter communicates via `live_activities` package or custom platform channels
- Needs App Groups for shared data
- Push-to-update support for server-driven updates
- Testing requires real device (Dynamic Island is hardware-specific, though simulators support it on iOS 18+)

---

### 6. Notification Actions (Long-Press Actions)

#### What It Is
iOS notifications can have custom action buttons that appear when the user long-presses (or swipes and taps "View") on a notification. These are defined via `UNNotificationCategory` and `UNNotificationAction`.

#### Palateful Use Cases

**A. Cooking Timer Notification Actions**
When a timer notification fires ("Timer done: Step 3 - Simmer sauce"):
- **"Add 2 Minutes"** -- restarts the timer with 2 extra minutes
- **"Add 5 Minutes"** -- restarts with 5 extra minutes
- **"Reset Timer"** -- restarts the original duration
- **"Open Cook Mode"** -- opens the app to the cooking screen (already implemented as default tap)

**B. Meal Reminder Notification Actions**
When a meal reminder fires ("Dinner in 30 minutes: Pad Thai"):
- **"Start Cooking"** -- opens cook mode for the recipe
- **"View Recipe"** -- opens recipe detail
- **"Snooze 15 min"** -- reschedules the reminder

**C. Shopping List Notification Actions**
When a shopping deadline reminder fires ("Shopping list items due today"):
- **"View List"** -- opens shopping list
- **"Mark All Done"** -- checks off all due items

**D. Import Complete Notification Actions**
When a recipe import finishes:
- **"Review Now"** -- opens the review queue
- **"Dismiss"** -- clears the notification

#### User Value: **VERY HIGH**
The timer actions ("Add 2 min", "Reset") are the exact feature the user requested. This is high-value, low-friction interaction. Users do not need to open the app just to add time to a timer -- they long-press the notification and tap a button.

#### Implementation Complexity: **Medium**
- `flutter_local_notifications` supports iOS notification categories and actions via `DarwinNotificationCategory` and `DarwinNotificationAction`
- Requires registering categories during initialization
- Action handlers need to be implemented (background Dart isolate or native code)
- The "Add 2 min" action needs to schedule a new notification and potentially communicate with the Flutter app if it is in the foreground
- Some actions (like "Add 2 min") may need a Notification Service Extension for processing without launching the app

---

### 7. Rich Notifications

#### What It Is
iOS notifications can include images, GIFs, video thumbnails, and custom UI via Notification Content Extensions.

#### Palateful Use Cases

**A. Recipe Import Complete**
- Show the recipe photo as the notification image
- "Your recipe 'Grandma's Apple Pie' has been imported" with the recipe photo

**B. Meal Reminder**
- Show the recipe photo in the meal reminder notification
- Visual recognition of what you are cooking tonight

**C. Partner Activity**
- "Sarah added 'Banana Bread' to Family Recipes" with the recipe thumbnail

#### User Value: **Medium**
Nice polish but not transformative. Users appreciate visual notifications but they are not a core workflow improvement.

#### Implementation Complexity: **Medium**
- Requires a Notification Service Extension to download and attach images
- `firebase_messaging` can pass image URLs; the extension downloads them
- Need to handle image caching and download failures gracefully

---

### 8. Notification Summary & Grouping

#### What It Is
iOS 15+ allows apps to declare notification categories for the notification summary (scheduled digest). iOS groups notifications by thread identifier.

#### Palateful Use Cases

- Group shopping list notifications together
- Group partner activity notifications together
- Allow non-urgent notifications (partner activity, import complete) to appear in scheduled summary
- Keep time-sensitive notifications (timer alerts, meal reminders) as immediate

#### User Value: **Low-Medium**
Reduces notification fatigue for collaborative features.

#### Implementation Complexity: **Low**
- Thread identifiers can be set on existing notifications
- Relevance scores can be assigned to help iOS prioritize
- Minimal code changes to existing notification implementation

---

### 9. Siri Shortcuts & App Intents

#### What It Is
The App Intents framework (successor to SiriKit/Shortcuts) lets apps expose actions to Siri, the Shortcuts app, Spotlight, and Apple Intelligence. Actions can be triggered by voice, automation, or search.

#### Palateful Use Cases

**A. Voice Commands**
- "Hey Siri, start cooking Pad Thai" -- opens cook mode for that recipe
- "Hey Siri, what's for dinner?" -- reads out the next dinner meal event
- "Hey Siri, add milk to my shopping list" -- adds item to active shopping list
- "Hey Siri, how many items are on my shopping list?" -- reads count
- "Hey Siri, start a 10 minute cooking timer" -- starts a timer

**B. Shortcuts App Actions**
- "Start Cooking [recipe]" -- parameterized with recipe picker
- "Add to Shopping List [item]" -- parameterized with text input
- "Plan Meal [recipe] for [date] [meal type]" -- full meal planning
- "Import Recipe from [URL]" -- trigger URL import
- "Random Recipe" -- opens a random recipe from the collection

**C. Spotlight Integration**
- Recipes indexed in Spotlight search
- User searches "banana bread" in Spotlight, Palateful recipe appears
- Tapping opens the recipe in the app

**D. Apple Intelligence Integration (iOS 18+)**
- App Intents are the gateway to Apple Intelligence
- Siri can chain multiple actions together
- "Plan dinner for tonight and add the ingredients to my shopping list"

**E. Shortcut Automations**
- "Every Sunday at 9 AM, show me my meal plan for the week"
- "When I arrive at the grocery store, show my shopping list"
- Location-based triggers for shopping list

#### User Value: **HIGH**
Voice commands while cooking (hands are messy) and Spotlight search for recipes are very high value. The app already has voice input in cook mode chat, but Siri integration works system-wide without opening the app first.

#### Implementation Complexity: **High**
- Requires native Swift App Intents implementation
- Flutter packages (`flutter_app_intents`, `intelligence`) provide some bridge, but custom intents still need native code
- Each intent needs parameter types, result types, and localization
- Spotlight indexing requires `CSSearchableItem` donations
- Testing Siri interactions requires device testing

---

### 10. Share Extension (Native iOS)

#### What It Is
A proper iOS Share Extension appears as a target in the system share sheet from any app. It runs as a separate process and can process shared content even without launching the main app.

#### Current State
Palateful already receives shared URLs via the `receive_sharing_intent` plugin. However, this is not a native Share Extension -- it relies on URL schemes and the main app being launched.

#### Upgrade Opportunity
A native Share Extension would:
- Appear with the Palateful icon in the share sheet
- Show a mini UI for import confirmation without fully launching the app
- Support sharing from Safari, Chrome, Instagram, TikTok, etc.
- Handle images (recipe photos) and text (recipe text) in addition to URLs
- Work even if the app is not running

#### User Value: **Medium** (incremental over existing implementation)
The existing `receive_sharing_intent` covers the primary use case. A native extension adds polish but the core workflow already works.

#### Implementation Complexity: **Medium-High**
- Requires creating a Share Extension target in Xcode
- Extension UI in SwiftUI or UIKit
- App Groups for data sharing with main app
- Needs to handle the same URL parsing/import logic natively

---

### 11. App Clips

#### What It Is
Lightweight versions of your app (under 15 MB) that users can access without installing the full app. Triggered by NFC tags, QR codes, Safari App Clip banners, or iMessage links.

#### Palateful Use Cases

**A. Recipe Sharing via App Clip**
- When someone shares a public recipe link, non-Palateful users see an App Clip
- Shows the recipe in a lightweight viewer
- "Get the full app" CTA to install Palateful
- QR code on a physical recipe card triggers the App Clip

**B. Meal Event RSVP**
- Shared meal event link opens an App Clip for RSVP
- Guest can see what is being cooked without installing the app

#### User Value: **Medium**
Good for user acquisition and sharing, but not a daily-use feature for existing users.

#### Implementation Complexity: **High**
- Flutter has documentation for App Clips but they are limited in size (15 MB)
- Would need a stripped-down Flutter app or native Swift UI
- Separate target, provisioning, and App Store review

---

### 12. Focus Filters

#### What It Is
Apps can customize their behavior based on the active Focus mode (e.g., "Cooking", "Do Not Disturb"). Uses the App Intents framework.

#### Palateful Use Cases

**A. "Cooking" Focus Mode**
- When "Cooking" Focus is active, Palateful only shows cook mode-related notifications
- Suppresses shopping list and partner activity notifications during cooking
- Could auto-enter a simplified UI

**B. "Shopping" Focus Mode**
- Only shows shopping list notifications
- Could auto-open the shopping list when Focus activates

#### User Value: **Low**
Very niche. Most users do not set up custom Focus modes, and the notification preferences system already handles quiet hours.

#### Implementation Complexity: **Medium**
- Requires App Intents framework for Focus Filter definitions
- Native Swift implementation
- Limited Flutter integration support

---

### 13. Handoff

#### What It Is
Handoff allows users to start an activity on one Apple device and continue it on another (iPhone to iPad, iPhone to Mac).

#### Palateful Use Cases

**A. Recipe Browsing Continuity**
- Start browsing a recipe on iPhone, continue on iPad
- Uses `NSUserActivity` to advertise the current activity

**B. Cook Mode Handoff**
- Start cooking on iPhone, hand off to iPad (bigger screen on the counter)

#### User Value: **Low-Medium**
Only useful for multi-device Apple users. The app does not currently have an iPad or Mac version.

#### Implementation Complexity: **Medium**
- Requires `NSUserActivity` integration
- Need to handle activity continuation in AppDelegate
- Flutter does not have built-in Handoff support; requires platform channels

---

### 14. Apple Watch Companion App

#### What It Is
A watchOS app that runs on Apple Watch, communicating with the iPhone app via WatchConnectivity.

#### Palateful Use Cases

**A. Cooking Timer on Wrist**
- See active timer countdown on the watch
- Haptic tap when timer completes
- "Add 2 min" and "Reset" complications/buttons
- No need to look at the phone while cooking

**B. Shopping List on Wrist**
- View shopping list items on the watch
- Check off items with a tap at the grocery store
- Hands-free grocery shopping

**C. Next Meal Complication**
- Watch face complication showing next scheduled meal
- Quick glance: "Dinner: Pad Thai at 6:30"

**D. Quick Timer Start**
- Start common timers (5 min, 10 min, 15 min) from the watch
- Useful when phone is across the kitchen

#### User Value: **HIGH** (for Apple Watch owners)
Cooking timers and shopping lists are perfect watch use cases. Checking off grocery items from your wrist while pushing a cart is a delightful experience.

#### Implementation Complexity: **Very High**
- Requires a separate watchOS app target written in SwiftUI
- WatchConnectivity for data sync with iPhone
- Flutter cannot run on watchOS -- entire watch app is native Swift
- Need to duplicate some business logic or use a shared data layer
- Separate App Store review process
- Ongoing maintenance of two separate UI codebases

---

### 15. CarPlay Integration

#### What It Is
CarPlay allows apps to display content on the car's built-in screen. iOS 18+ supports widgets and Live Activities on CarPlay.

#### Palateful Use Cases

**A. Shopping List on CarPlay**
- View shopping list on the car screen while driving to the grocery store
- Read items aloud via Siri
- Not interactive (for safety), but viewable

**B. Meal Plan Glance**
- See tonight's dinner on the drive home
- "What's for dinner?" via Siri through CarPlay

#### User Value: **Low-Medium**
Niche use case. Most users will just use their phone or watch at the store.

#### Implementation Complexity: **Very High**
- CarPlay requires specific entitlements from Apple (apply via developer portal)
- Apple is selective about which app categories can use CarPlay
- A "kitchen management" app may not qualify
- Native Swift implementation required

---

### 16. Control Center Controls (iOS 18+)

#### What It Is
Third-party apps can add toggles and buttons to the redesigned Control Center. Uses WidgetKit + App Intents.

#### Palateful Use Cases

**A. Quick Timer Control**
- "Start 5 min timer" button in Control Center
- One-tap timer start without opening the app

**B. Shopping List Count**
- Shows unchecked item count as a read-only control
- Tapping opens the shopping list

**C. "Start Cooking" Control**
- Opens cook mode for the next scheduled meal

#### User Value: **Medium**
Convenient for quick actions, but most users would prefer widgets or Siri.

#### Implementation Complexity: **Medium**
- Built on WidgetKit + App Intents (same infrastructure as widgets)
- If widgets and App Intents are already implemented, Control Center controls are incremental
- Native Swift implementation

---

### 17. iCloud Sync

#### What It Is
Sync app data across devices via iCloud (CloudKit or iCloud Key-Value Store).

#### Palateful Use Cases
- The app already has a server-side backend with user accounts
- iCloud sync would be redundant with the existing API-based sync
- Could be used for offline-first data if the backend were removed

#### User Value: **None** (already handled by backend API)
Not applicable -- Palateful has a proper backend.

#### Implementation Complexity: N/A

---

## Widget Opportunities -- Detailed Design

### Widget Family Matrix

| Widget | Small | Medium | Large | Lock Screen Circular | Lock Screen Rectangular | Lock Screen Inline |
|--------|-------|--------|-------|---------------------|------------------------|-------------------|
| Next Meal | Recipe name + time | All today's meals | Week view | Meal icon + time | Meal name + time | "Dinner at 6:30" |
| Shopping List | Item count | Top 5 items + count | Full list with checkboxes | Item count | "5 items left" + top item | "5 items to buy" |
| Quick Cook | Random favorite | 3 suggested recipes | N/A | Cook icon | "Cook: [recipe]" | N/A |
| Active Timer | Countdown | Countdown + label + progress | N/A | Countdown | Label + countdown | "Timer: 04:32" |
| Cooking Stats | Streak count | Streak + recipes this week | N/A | Streak | Streak + count | "5 recipes this week" |

### Data Sharing Architecture

```
Flutter App (main process)
    |
    |-- home_widget package ---> UserDefaults (App Group)
    |                                    |
    |                                    v
    |                           Widget Extension (separate process)
    |                           reads UserDefaults, renders SwiftUI
    |
    |-- Updates widget data on:
    |   - Recipe load/change
    |   - Meal event create/update/delete
    |   - Shopping item check/uncheck
    |   - Timer start/stop/complete
    |   - App enters background
```

### App Group Configuration
- App Group identifier: `group.com.palateful.app`
- Shared UserDefaults keys:
  - `next_meal_json` -- next meal event data
  - `today_meals_json` -- today's meals array
  - `shopping_list_json` -- active shopping list with items
  - `active_timers_json` -- running timer data
  - `cooking_stats_json` -- streak and weekly stats
  - `favorites_json` -- favorite recipes for Quick Cook widget

---

## Notification Opportunities -- Detailed Design

### Notification Categories and Actions

#### Category: `cooking_timer`
| Action ID | Title | Options | Behavior |
|-----------|-------|---------|----------|
| `TIMER_ADD_2_MIN` | Add 2 Minutes | `.foreground` | Schedules new notification 2 min from now |
| `TIMER_ADD_5_MIN` | Add 5 Minutes | `.foreground` | Schedules new notification 5 min from now |
| `TIMER_RESET` | Reset Timer | `.foreground` | Restarts original timer duration |
| `TIMER_DISMISS` | Dismiss | `.destructive` | Clears the notification |

#### Category: `meal_reminder`
| Action ID | Title | Options | Behavior |
|-----------|-------|---------|----------|
| `MEAL_START_COOKING` | Start Cooking | `.foreground` | Opens cook mode |
| `MEAL_SNOOZE_15` | Snooze 15 min | (none) | Reschedules reminder |
| `MEAL_VIEW_RECIPE` | View Recipe | `.foreground` | Opens recipe detail |

#### Category: `shopping_reminder`
| Action ID | Title | Options | Behavior |
|-----------|-------|---------|----------|
| `SHOPPING_VIEW_LIST` | View List | `.foreground` | Opens shopping list |
| `SHOPPING_SNOOZE` | Remind Later | (none) | Reschedules reminder |

#### Category: `import_complete`
| Action ID | Title | Options | Behavior |
|-----------|-------|---------|----------|
| `IMPORT_REVIEW` | Review Now | `.foreground` | Opens import review queue |

### Implementation with `flutter_local_notifications`

The existing `CookTimerNotificationService` would be extended to register categories:

```dart
// During initialization:
final categories = [
  DarwinNotificationCategory(
    'cooking_timer',
    actions: [
      DarwinNotificationAction.plain('TIMER_ADD_2_MIN', 'Add 2 Minutes'),
      DarwinNotificationAction.plain('TIMER_ADD_5_MIN', 'Add 5 Minutes'),
      DarwinNotificationAction.plain('TIMER_RESET', 'Reset Timer'),
      DarwinNotificationAction.destructive('TIMER_DISMISS', 'Dismiss'),
    ],
  ),
  // ... other categories
];

const iosInit = DarwinInitializationSettings(
  requestAlertPermission: true,
  requestBadgePermission: true,
  requestSoundPermission: true,
  notificationCategories: categories,
);
```

Each notification would then specify its category:

```dart
const iosDetails = DarwinNotificationDetails(
  categoryIdentifier: 'cooking_timer',
  interruptionLevel: InterruptionLevel.timeSensitive,
  // ...
);
```

---

## Siri & Shortcuts Opportunities -- Detailed Design

### Proposed App Intents

| Intent | Parameters | Response | Trigger |
|--------|-----------|----------|---------|
| StartCookingIntent | recipe: RecipeEntity | Opens cook mode | "Start cooking [recipe]" |
| WhatsForDinnerIntent | (none) | Speaks next dinner meal | "What's for dinner?" |
| AddToShoppingListIntent | item: String, quantity?: Int, unit?: String | Confirms addition | "Add milk to my shopping list" |
| ShoppingListCountIntent | (none) | Speaks item count | "How many items on my shopping list?" |
| StartTimerIntent | minutes: Int, label?: String | Starts timer + Live Activity | "Start a 10 minute timer" |
| RandomRecipeIntent | (none) | Opens random recipe | "Show me a random recipe" |
| PlanMealIntent | recipe: RecipeEntity, date: Date, mealType: MealType | Confirms planning | "Plan [recipe] for dinner tomorrow" |
| ImportRecipeIntent | url: URL | Starts import | "Import recipe from [URL]" |

### Spotlight Indexing

Recipes would be indexed as `CSSearchableItem` with:
- Title: recipe name
- Description: recipe description or ingredient summary
- Thumbnail: recipe image
- Keywords: recipe tags, ingredient names, cuisine type
- Deep link: `palateful://recipes/{id}`

This would allow users to find their recipes from the iOS Spotlight search without opening the app.

---

## Other iOS Features Assessment

| Feature | Relevance to Palateful | User Value | Complexity | Recommendation |
|---------|----------------------|------------|------------|----------------|
| App Clips | Recipe sharing to non-users | Medium | High | Phase 4 -- nice for growth, not core |
| Focus Filters | Suppress non-cooking notifications | Low | Medium | Skip -- notification preferences already cover this |
| Handoff | Continue recipe browsing on iPad/Mac | Low | Medium | Skip -- no iPad/Mac app exists |
| Apple Watch | Timers + shopping list on wrist | High | Very High | Phase 3 -- high value but massive effort |
| CarPlay | Shopping list in car | Low | Very High | Skip -- unlikely to get Apple approval |
| Control Center | Quick timer, shopping count | Medium | Medium | Phase 2 -- easy if widgets + intents already done |
| iCloud Sync | Device sync | None | N/A | Skip -- backend API handles this |
| Rich Notifications | Recipe photos in notifications | Medium | Medium | Phase 2 -- nice polish |
| Notification Grouping | Group by type | Low-Medium | Low | Phase 1 -- minimal effort |

---

## Flutter Implementation Considerations

### The Flutter-Native Boundary

Flutter cannot render iOS widgets, Live Activities, or watch apps. Every WidgetKit feature requires:
1. **SwiftUI code** for the visual layout
2. **App Groups** for shared data storage
3. **A Flutter plugin or platform channel** for data communication

The recommended approach is:

```
Flutter App
    |
    +--> home_widget package --> UserDefaults (App Group) --> WidgetKit Extension (SwiftUI)
    |
    +--> live_activities package --> ActivityKit --> Live Activity Extension (SwiftUI)
    |
    +--> flutter_local_notifications --> UNNotification categories/actions
    |
    +--> Platform Channel --> Native AppIntent definitions --> Siri/Shortcuts
    |
    +--> Platform Channel --> CSSearchableItem --> Spotlight
```

### Key Flutter Packages

| Package | Purpose | Maturity |
|---------|---------|----------|
| `home_widget` | Bridge data to WidgetKit extensions | Stable, well-maintained |
| `live_activities` | Bridge data to ActivityKit Live Activities | Stable, actively developed |
| `flutter_local_notifications` | Local notifications with categories/actions | Stable, mature |
| `flutter_app_intents` | Bridge to App Intents framework | Newer, basic support |
| `intelligence` | Apple Intelligence / App Intents integration | Newer |

### Minimum iOS Version Implications

| Feature | Minimum iOS | Current Minimum | Impact |
|---------|-------------|-----------------|--------|
| WidgetKit (basic) | 14.0 | 14.0 | No change needed |
| Lock screen widgets | 16.0 | 14.0 | Would need availability checks |
| Live Activities | 16.1 | 14.0 | Would need availability checks |
| Interactive widgets | 17.0 | 14.0 | Would need availability checks |
| StandBy mode | 17.0 | 14.0 | Automatic if widgets exist |
| Control Center controls | 18.0 | 14.0 | Would need availability checks |

**Recommendation**: Keep the minimum deployment target at 14.0 but use `@available` checks in Swift and conditional feature activation in Dart. This avoids dropping support for older devices while enabling modern features on newer ones.

### Xcode Project Changes Required

1. **Add App Group capability** to Runner target
2. **Add entitlements file** (`Runner.entitlements`) with App Group and Push Notification entitlements
3. **Add Widget Extension target** (SwiftUI)
4. **Add Live Activity extension** (can share the widget extension target)
5. **Update Podfile** to include widget extension target
6. **Update `Info.plist`** with `NSSupportsLiveActivities = YES`
7. **Update provisioning profiles** to include App Group and new extension identifiers

---

## Priority Matrix

### Value vs. Complexity Chart

```
HIGH VALUE
    |
    |  [Notification Actions]     [Live Activities]
    |       (Medium)                   (High)
    |
    |  [Lock Screen Widgets]      [Home Screen Widgets]
    |       (Medium)                  (Medium-High)
    |
    |                             [Siri Shortcuts]
    |                                  (High)
    |
    |                             [Apple Watch]
    |                              (Very High)
    |
    |  [StandBy Mode]
    |     (Free)
    |
MED |  [Control Center]           [Interactive Widgets]
    |     (Medium)                     (High)
    |
    |  [Rich Notifications]       [Share Extension]
    |     (Medium)                   (Medium-High)
    |
    |  [Notification Grouping]    [Spotlight Search]
    |      (Low)                      (Medium)
    |
    |                             [App Clips]
    |                                (High)
    |
LOW |  [Focus Filters]            [CarPlay]
    |     (Medium)                (Very High)
    |
    +------------------------------------------------------
        LOW                  MEDIUM               HIGH
                        COMPLEXITY
```

---

## Recommended Rollout Order

### Phase 1: Notification Enhancement (1-2 weeks)
**Goal: Immediately improve the existing timer notification experience**

1. **Notification actions for cooking timers** -- "Add 2 Minutes", "Add 5 Minutes", "Reset Timer"
2. **Notification actions for meal reminders** -- "Start Cooking", "View Recipe", "Snooze"
3. **Notification grouping** -- thread identifiers for shopping, partner activity, imports
4. **Time-sensitive notification flag** -- already partially implemented, ensure consistent use

**Why first**: This builds on existing infrastructure (`flutter_local_notifications` already in use), requires no new Xcode targets, and directly addresses the user's #1 request (timer notification actions). Lowest cost, highest immediate impact.

### Phase 2: Widgets & Live Activities (3-5 weeks)
**Goal: Make Palateful visible on home screen and lock screen**

1. **App Group setup** -- foundation for all widget/Live Activity work
2. **Home screen widgets** -- "Next Meal" (small), "Today's Meals" (medium), "Shopping List" (medium)
3. **Lock screen widgets** -- "Next Meal" (circular + rectangular), "Shopping Count" (circular)
4. **StandBy mode** -- free with home screen widgets
5. **Live Activities for cooking timers** -- Dynamic Island + lock screen countdown
6. **Interactive shopping list widget** (iOS 17+) -- checkbox toggles

**Why second**: This is the highest-visibility set of features. Widgets and Live Activities are what make an app feel "native". The cooking timer Live Activity is the marquee feature. This phase requires the most Xcode/SwiftUI work but establishes the foundation for everything else.

### Phase 3: Siri, Shortcuts & Intelligence (2-3 weeks)
**Goal: Voice-driven and automated interactions**

1. **Core App Intents** -- "Start Cooking", "What's for dinner?", "Add to shopping list"
2. **Spotlight recipe indexing** -- recipes searchable from iOS search
3. **Control Center controls** -- quick timer, shopping list count (leverages Phase 2 App Intents infrastructure)
4. **Rich notifications** -- recipe images in import/meal notifications
5. **Shortcut automations support** -- allow Shortcuts app to chain Palateful actions

**Why third**: Builds on the App Intents infrastructure established in Phase 2 (interactive widgets). Voice commands and Spotlight search add significant convenience but are less visible than widgets.

### Phase 4: Advanced Native Features (4-8 weeks)
**Goal: Deep platform integration for power users**

1. **Apple Watch companion app** -- timer, shopping list, next meal complication
2. **Native Share Extension upgrade** -- replace `receive_sharing_intent` with proper extension
3. **App Clips** -- lightweight recipe viewer for sharing
4. **Advanced Siri intents** -- meal planning, recipe import, multi-step actions

**Why last**: These features require the most native development effort (especially Apple Watch), serve smaller user segments, and have diminishing returns compared to earlier phases.

---

## Estimated Complexity per Feature

| Feature | Dev Effort | Native Code Required | Flutter Plugin | New Xcode Targets |
|---------|-----------|---------------------|----------------|-------------------|
| **Notification actions (timer)** | 3-5 days | Minimal (category registration) | `flutter_local_notifications` | None |
| **Notification actions (meal/shopping)** | 2-3 days | Minimal | `flutter_local_notifications` | None |
| **Notification grouping** | 1 day | None | `flutter_local_notifications` | None |
| **App Group setup** | 1 day | Xcode config | N/A | None (config only) |
| **Home screen widgets (3 types)** | 8-12 days | SwiftUI layouts, timeline providers | `home_widget` | Widget Extension |
| **Lock screen widgets (3 types)** | 3-5 days | SwiftUI layouts (simpler) | `home_widget` | Shared with above |
| **Live Activities (cooking timer)** | 8-10 days | ActivityKit, SwiftUI layouts | `live_activities` | Shared widget extension or new |
| **Interactive widget (shopping)** | 4-6 days | App Intents, SwiftUI | `home_widget` | Shared |
| **StandBy mode** | 0 days | Automatic | N/A | N/A |
| **Control Center controls** | 3-4 days | App Intents, WidgetKit | Custom platform channel | Shared |
| **Siri Shortcuts (5 intents)** | 6-8 days | App Intents framework | `flutter_app_intents` / custom | None |
| **Spotlight indexing** | 3-4 days | CSSearchableItem | Custom platform channel | None |
| **Rich notifications** | 3-4 days | Notification Service Extension | `firebase_messaging` | Notification Service Extension |
| **Apple Watch app** | 20-30 days | Full watchOS app in SwiftUI | WatchConnectivity bridge | watchOS target |
| **Native Share Extension** | 5-7 days | Share Extension UI | App Groups | Share Extension |
| **App Clips** | 8-12 days | App Clip target | Limited Flutter or native | App Clip target |
| **Focus Filters** | 3-4 days | App Intents | Custom | None |

### Total Estimates by Phase

| Phase | Estimated Duration | Key Deliverables |
|-------|-------------------|------------------|
| Phase 1 | 1-2 weeks | Timer notification actions, meal reminder actions, notification grouping |
| Phase 2 | 3-5 weeks | 3 home screen widgets, 3 lock screen widgets, Live Activities, interactive shopping widget |
| Phase 3 | 2-3 weeks | 5 Siri intents, Spotlight indexing, Control Center controls, rich notifications |
| Phase 4 | 4-8 weeks | Apple Watch app, native Share Extension, App Clips |

---

## Key Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| SwiftUI learning curve | Slows widget development | Start with simple widgets; SwiftUI is declarative like Flutter |
| App Group data freshness | Widgets show stale data | Use `WidgetCenter.shared.reloadAllTimelines()` on data changes; push-to-update for server changes |
| Live Activity 8-hour limit | Timer Live Activities expire | Handle gracefully; restart if user re-opens app |
| Notification action in background | iOS may not launch Dart isolate | Use native notification handler for simple actions (reschedule); queue complex actions for app launch |
| Apple Watch data sync | Connectivity delays | Cache last-known data on watch; show "last updated" timestamp |
| iOS 14 users lose features | Feature gap between OS versions | Use `@available` checks; graceful degradation; core app works on all versions |
| App Store review for new extensions | Potential rejection | Follow Apple Human Interface Guidelines strictly; ensure each extension adds clear value |
