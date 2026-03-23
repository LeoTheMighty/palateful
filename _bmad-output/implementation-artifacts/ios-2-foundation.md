# Story iOS.2: iOS Foundation — App Group, Widget Extension, Entitlements

Status: done

## Story

As a developer,
I want the Xcode project set up with App Groups, entitlements, and a Widget Extension target,
so that all subsequent iOS-native features (widgets, Live Activities, Siri) have the foundation they need.

## Acceptance Criteria

1. App Group `group.com.palateful.app` is configured in Xcode for both the Runner target and a new Widget Extension target
2. Entitlements file exists with App Group and Push Notification capabilities
3. Widget Extension target exists in the Xcode project with SwiftUI boilerplate
4. `home_widget` Flutter package is integrated and can write data to shared UserDefaults
5. `live_activities` Flutter package is integrated and initialized
6. `Info.plist` includes `NSSupportsLiveActivities = YES`
7. A test widget (static "Palateful" placeholder) renders on the home screen to verify the full pipeline
8. Data bridge verified: Flutter writes to UserDefaults → Widget Extension reads it → widget displays it
9. App builds, signs, and runs correctly with the new extension

## Tasks / Subtasks

- [x] Task 1: Xcode project setup (AC: #1, #2)
  - [x] Create `Runner.entitlements` file
  - [x] Add App Group capability to Runner target: `group.com.palateful.app`
  - [x] Add Push Notifications capability
  - [x] Update provisioning profiles to include App Group

- [x] Task 2: Create Widget Extension target (AC: #3, #7)
  - [x] In Xcode: File → New → Target → Widget Extension
  - [x] Name: `PalatefulWidgets`
  - [x] Add same App Group: `group.com.palateful.app`
  - [x] Create entitlements for widget extension with App Group
  - [x] Add placeholder SwiftUI widget: static text "Palateful" in a small widget
  - [x] Verify widget appears in widget gallery and renders on home screen

- [x] Task 3: Integrate home_widget package (AC: #4, #8)
  - [x] Add `home_widget` to `app/pubspec.yaml`
  - [x] Configure with App Group identifier: `group.com.palateful.app`
  - [x] Write test data from Flutter: `HomeWidget.saveWidgetData('test_key', 'test_value')`
  - [x] Read in widget extension: `UserDefaults(suiteName: "group.com.palateful.app")?.string(forKey: "test_key")`
  - [x] Verify round-trip: Flutter writes → widget displays

- [x] Task 4: Integrate live_activities package (AC: #5, #6)
  - [x] Add `live_activities` to `app/pubspec.yaml`
  - [x] Add `NSSupportsLiveActivities = YES` to `Info.plist`
  - [x] Initialize `LiveActivitiesPlugin` in app startup
  - [x] No Live Activity UI yet — just the foundation (Story 4 adds the UI)

- [x] Task 5: Build verification (AC: #9)
  - [x] Verify `npx nx run app:build-ios` (or equivalent) succeeds
  - [x] Verify app runs on simulator with widget extension
  - [x] Verify signing for both Runner and Widget Extension targets
  - [x] Update Podfile if needed to include widget extension target

## Dev Notes

- This is pure infrastructure — no user-facing features beyond a test widget
- The App Group is the critical piece: it creates a shared container that both the Flutter app and native extensions can read/write
- `home_widget` package docs: https://pub.dev/packages/home_widget
- `live_activities` package docs: https://pub.dev/packages/live_activities
- Widget Extension must have its own provisioning profile and App ID
- The test widget proves the full pipeline works before we invest in real widget UIs
- Keep iOS minimum deployment target at 14.0 — use `@available` checks in Swift for newer features

### References

- [Investigation: 09-ios-native-features.md — Flutter Implementation Considerations section]
- [Epic: epic-ios-native.md]
