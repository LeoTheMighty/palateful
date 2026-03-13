# QA Walkthrough: Story 1.1 — App Shell with Design System & Navigation

## Prerequisites

- [ ] Run `cd app && flutter pub get`
- [ ] Run `cd app && flutter test` — all 13 tests should pass
- [ ] Run `flutter analyze` — no errors (info/warnings are pre-existing)

## Light Mode

- [ ] Launch the app on a device/simulator with system set to **light mode**
- [ ] Verify background is warm cream (#FAF7F2), not pure white
- [ ] Verify headings use Playfair Display serif font (recipe titles, screen titles)
- [ ] Verify body text uses system sans-serif (not serif)
- [ ] Verify cards have cream background with beige borders
- [ ] Verify buttons use chocolate (#4A3728) primary color

## Dark Mode

- [ ] Switch device to **dark mode** (Settings → Display)
- [ ] Verify background changes to chocolate (#4A3728)
- [ ] Verify cards change to chocolateLight (#5D4A3A) with hazelnut borders
- [ ] Verify primary text is warmIvory (#F5ECD7) — readable, warm tone
- [ ] Verify accent color is terracotta (#BE8A60) — buttons, active nav items
- [ ] Verify bottom nav background is darker than the main scaffold
- [ ] Verify text contrast is comfortable to read (WCAG AA: ~8.5:1 warmIvory on chocolate)

## Bottom Navigation

- [ ] Verify bottom nav bar is visible with 5 tabs: Home, Books, Cart, Calendar, Profile
- [ ] Tap **Home** — shows recipe grid with search bar
- [ ] Tap **Books** — shows recipe books screen
- [ ] Tap **Cart** — shows "Shopping list coming soon" placeholder
- [ ] Tap **Calendar** — shows "Meal planning coming soon" placeholder
- [ ] Tap **Profile** — shows profile placeholder with Logout button
- [ ] Verify active tab icon is filled, inactive tabs use outlined icons
- [ ] Navigate to a sub-page within a tab, switch tabs, switch back — **tab state is preserved**

## Navigation Integrity

- [ ] From Home, tap a recipe card → recipe detail opens **without** bottom nav (full screen)
- [ ] From recipe detail, go back → returns to Home with bottom nav
- [ ] Long-press a recipe → cook mode opens **without** bottom nav (full screen)
- [ ] From Profile, tap Logout → redirected to login screen (no bottom nav)
- [ ] Login → should redirect to Home with bottom nav (if onboarded)
- [ ] The old recipe books button and logout button are **removed** from the Home search header

## Shimmer Loading

- [ ] In light mode: verify shimmer uses cream/beige tones (not grey)
- [ ] In dark mode: verify shimmer uses chocolate/hazelnut tones
- [ ] (Optional) Add a deliberate delay to recipe loading to see shimmer in action

## Reduce Motion

- [ ] Enable **Reduce Motion** in device settings (iOS: Settings → Accessibility → Motion → Reduce Motion)
- [ ] Navigate to recipe detail → transition should be **instant** (no fade animation)
- [ ] Go back → transition should be **instant**
- [ ] Disable Reduce Motion → navigate again → should see **fade transition**

## Riverpod Foundation

- [ ] App launches without errors (ProviderScope wrapping verified)
- [ ] Existing functionality still works: login, recipe browsing, cook mode, add recipe

---

**Story**: 1-1-app-shell-with-design-system-and-navigation
**Date**: 2026-03-13
**Implemented by**: Claude Opus 4.6
