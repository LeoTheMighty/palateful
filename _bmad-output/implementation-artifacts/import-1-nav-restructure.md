# Story Import.1: Nav Restructure — Books to Home, Activity Tab Shell

Status: done

## Story

As a user,
I want the bottom navigation to prioritize my daily actions (home, cart, activity, calendar, profile),
so that recipe book management doesn't take up permanent nav space and I have quick access to my activity feed.

## Acceptance Criteria

1. Bottom nav tabs are: Home | Cart | Activity | Calendar | Profile (in this order)
2. Books tab is completely removed from bottom navigation
3. Activity tab shows a placeholder screen with "Activity" title and empty state
4. Activity tab icon shows a bell with a badge count placeholder (hardcoded 0 for now)
5. All existing Books-tab routes still work via direct navigation (push, not tab)
6. Home screen FAB still opens Add Recipe sheet
7. Cart screen FAB still creates new shopping list
8. Calendar screen FAB opens Plan Meal sheet (from calendar epic)
9. No FAB on Activity or Profile tabs

## Tasks / Subtasks

- [x] Task 1: Restructure bottom navigation shell (AC: #1, #2)
  - [x] Modify the app shell / scaffold that defines bottom nav tabs
  - [x] Remove Books tab, add Activity tab in position 3 (middle)
  - [x] Activity icon: `Icons.notifications_outlined` (active: `Icons.notifications`)
  - [x] Preserve existing tab indices for Home (0), Cart (1), Calendar (3), Profile (4)

- [x] Task 2: Create Activity shell screen (AC: #3, #4)
  - [x] Create `app/lib/features/activity/activity_screen.dart`
  - [x] AppBar title: "Activity"
  - [x] Body: empty state widget ("No activity yet" with appropriate icon)
  - [x] Badge count on nav icon (hardcoded 0, wired up in Story 3)

- [x] Task 3: Ensure Books routes still work (AC: #5)
  - [x] Recipe book list screen and detail screen remain accessible via `context.push()`
  - [x] Verify all deep links and navigation to books still function
  - [x] The "See All" link from Home (Story 2) will navigate to the books list screen

- [x] Task 4: Contextual FABs (AC: #6, #7, #8, #9)
  - [x] Verify Home FAB → Add Recipe sheet (existing)
  - [x] Verify Cart FAB → New shopping list (existing)
  - [x] Verify Calendar FAB → Plan Meal sheet (from calendar defaults epic)
  - [x] No FAB on Activity or Profile

## Dev Notes

- The app shell is likely in `app/lib/core/router/app_router.dart` or a shell scaffold widget
- Look for `BottomNavigationBar` or `NavigationBar` widget with the 5 current tabs
- Books screen files stay untouched — we're just removing the tab, not the screens
- The Activity screen is a shell for now — Story 3 fills it with content

### References

- [Epic: epic-import-activity-nav.md]
