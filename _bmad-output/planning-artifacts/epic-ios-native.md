# Epic: iOS Native Features — Widgets, Live Activities, Notifications & Siri

## Overview

Transform Palateful from "an app on the phone" to "part of the phone." This epic adds iOS-native features that make the app feel deeply integrated with the OS: notification actions on cooking timers, home screen and lock screen widgets, Live Activities in the Dynamic Island, interactive shopping list widgets, Siri Shortcuts, and Spotlight search indexing.

## Design Principles (from Party Mode discussion)

1. **Users choose** — build multiple widget types, let users pick which to display on their home screen
2. **Foundation first** — App Group + Widget Extension target unlocks everything; do it once, do it right
3. **Each phase delivers a "wow moment"** — no half-finished infrastructure releases
4. **Graceful degradation** — core app works on iOS 14+; native features available on iOS 16.1+ / 17+
5. **Flutter-native bridge** — data flows via UserDefaults (App Group), UI is SwiftUI, communication via `home_widget` and `live_activities` packages

## Story Map

| Story | Title | Est. Effort | Dependencies |
|-------|-------|-------------|--------------|
| 1 | Notification Actions — Timer + Meal Reminders | 3–5 days | None |
| 2 | iOS Foundation — App Group, Widget Extension, Entitlements | 2–3 days | None |
| 3 | Home Screen & Lock Screen Widgets — Next Meal + Shopping List | 8–12 days | Story 2 |
| 4 | Live Activities — Cooking Timer in Dynamic Island | 8–10 days | Story 2 |
| 5 | Interactive Shopping List Widget (iOS 17+) | 4–6 days | Story 3 |
| 6 | Siri Shortcuts + Spotlight Search | 6–8 days | Story 2 |
| 7 | Control Center + Rich Notifications | 3–5 days | Stories 5, 6 |

**Total estimated effort: 5–7 weeks**

**Phase 1 (1-2 weeks):** Story 1 (notification actions — independent, quick win)
**Phase 2 (3-5 weeks):** Stories 2 → 3 + 4 (parallel) → 5
**Phase 3 (2-3 weeks):** Stories 6 → 7

**Future (separate project):** Apple Watch companion app
