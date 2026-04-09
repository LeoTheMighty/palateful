# Story 12.4: Admin Web Dashboard

## Status: Complete

## Summary
Implemented a web-only admin dashboard for the Palateful Flutter app with 5 screens: dashboard overview, logs viewer, errors list, error detail, and user management.

## Changes Made

### Auth & State
- **`auth_service.dart`**: Added `_isAdmin` field, `isAdmin` getter, `updateAdminState()` method; cleared on logout
- **`main.dart`**: Extract `is_admin` from `/me` response in both E2E and normal auth flows, pass to `authService.updateAdminState()`

### API Client
- **`api_client.dart`**: Added 6 admin endpoint methods: `getAdminLogs`, `getAdminErrors`, `getAdminErrorDetail`, `getAdminUsers`, `updateUserAdmin`, `getAdminStats`

### Admin Screens (new files)
- **`features/admin/admin_dashboard_screen.dart`**: Stats cards (users, recipes, books, errors, active users) + navigation tiles to logs/errors/users
- **`features/admin/admin_logs_screen.dart`**: Filterable log viewer with service/level dropdowns, search, time range chips, auto-refresh toggle (5s polling)
- **`features/admin/admin_errors_screen.dart`**: Paginated error list with pull-to-refresh and infinite scroll
- **`features/admin/admin_error_detail_screen.dart`**: Full error detail view with stack trace on dark background + copy button
- **`features/admin/admin_users_screen.dart`**: Paginated user list with admin badge, toggle switch with confirmation dialog

### Routing
- **`app_router.dart`**: Added 5 admin routes outside shell route with `parentNavigatorKey: _rootNavigatorKey`; added admin route guard in redirect function

### Profile Link
- **`profile_screen.dart`**: Added "Admin Dashboard" tile in Settings section, visible only when `kIsWeb && authService.isAdmin`

## Acceptance Criteria
- [x] Admin dashboard shows stats and navigation
- [x] Logs screen with filters, search, and auto-refresh
- [x] Errors list with pagination and navigation to detail
- [x] Error detail with stack trace and copy functionality
- [x] User management with admin toggle and confirmation
- [x] Routes protected by admin guard
- [x] Admin link only visible on web for admin users
