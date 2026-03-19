# Story 7.2: Invitation System

Status: review

## Story

As a user,
I want to invite others to my shared recipe books via direct invitation or a shareable link,
So that my household members can join my recipe books without needing to know each other's user IDs.

## Acceptance Criteria

1. **Given** I own a shared recipe book **When** I open the members screen **Then** I see an "Invite" button that lets me send a direct invitation by user ID, username, or email.
2. **Given** I send a direct invitation **When** the recipient opens the app **Then** they see a pending invitation in their Invitations inbox with the sender's name, resource name, and role offered; they can accept or decline.
3. **Given** I own a shared recipe book **When** I open the members screen **Then** I can generate a shareable invite link and copy it to the clipboard or share it via the system share sheet.
4. **Given** someone taps a `palateful://invite/{token}` deep link **When** they are authenticated **Then** they are taken to an invite preview screen showing the book name, inviter name, and role offered; they can accept to join immediately.
5. **Given** someone taps a `palateful://invite/{token}` deep link **When** they are not yet authenticated **Then** after sign-up/sign-in the app calls POST /invitations/claim to auto-accept email-matched pending invitations and then navigates to the preview screen.
6. **Given** I own a shared recipe book **When** I view my sent invitations **Then** I can see all pending invitations I have sent and revoke any of them.
7. **Given** I have pending invitations **When** I open my profile or a notification badge **Then** I can navigate to the invitations inbox.

## Implementation Notes

### Backend — Already Implemented (DO NOT RE-IMPLEMENT)

All backend endpoints, routers, models, and backend tests for invitations and invite links already exist:

**Invitation endpoints** (`services/api/src/api/v1/invitations/`):
- `SendInvitation` — POST /v1/invitations — accepts `{resource_type, resource_id, role_offered, to_user_id?, to_username?, to_email?, message?}`; rate-limited to 30/day; sends push notification
- `AcceptInvitation` — POST /v1/invitations/{id}/accept
- `DeclineInvitation` — POST /v1/invitations/{id}/decline
- `RevokeInvitation` — DELETE /v1/invitations/{id}
- `ListReceivedInvitations` — GET /v1/invitations — returns pending non-expired invitations with full `from_user` info and `resource_name`
- `ListSentInvitations` — GET /v1/invitations/sent
- `ClaimInvitations` — POST /v1/invitations/claim — matches pending email invitations to the current user; call after sign-up

**Invite link endpoints** (`services/api/src/api/v1/invite_links/`):
- `CreateInviteLink` — POST /v1/invite-links — accepts `{resource_type, resource_id, role_offered, max_uses?, expires_in_days?}`; returns `deep_link: "palateful://invite/{token}"`
- `PreviewInviteLink` — GET /v1/invite-links/{token} — returns `state: active|expired|full|inactive|already_member` plus resource/inviter info
- `JoinViaLink` — POST /v1/invite-links/{token}/join
- `DeactivateInviteLink` — DELETE /v1/invite-links/{id}

**Routers**: `services/api/src/routers/v1/invitations_router.py`, `services/api/src/routers/v1/invite_links_router.py`

**Backend tests**: `services/api/tests/test_invitations.py`, `services/api/tests/test_invite_links.py`

> NOTE: The existing backend tests are mostly smoke tests (missing fields → 422, not-found → 404/500). The dev agent should add meaningful tests per the Tasks below.

### Deep Link Scheme

- Deep link: `palateful://invite/{token}`
- GoRouter path: `/invite/:token`
- When app is cold-started via deep link: GoRouter's redirect logic will handle auth gating; after auth redirect returns to `/invite/:token`

### Flutter Features to Build

1. **ApiClient methods** for all invitation and invite-link endpoints
2. **InvitationsScreen** — inbox of received invitations + tab or toggle for sent invitations
3. **InviteLinkPreviewScreen** — shown when opening `palateful://invite/{token}`
4. **Invite UI in RecipeBookMembersScreen** — "Invite" button opens a bottom sheet with two tabs: "By username/email" (direct invite) and "Invite Link" (create/copy/share link)
5. **Claim-on-signup** — in `AuthService` or onboarding completion, call POST /v1/invitations/claim after first sign-up
6. **Route registration** — add `/invitations` and `/invite/:token` routes
7. **Profile screen badge/link** — link to InvitationsScreen from profile (notification count optional)

## Tasks / Subtasks

- [x] Task 1: Backend tests — improve test coverage (AC: all)
  - [x] In `services/api/tests/test_invitations.py`, add meaningful test cases:
    - `TestSendInvitation.test_send_invitation_to_username_success`: mock owner membership, mock target user lookup by username, assert 201 and `status == "pending"`
    - `TestSendInvitation.test_send_invitation_no_permission_returns_403`: mock no membership for sender, assert 403
    - `TestSendInvitation.test_send_invitation_self_invite_returns_400`: mock target_user same as sender (same ID), assert 400
    - `TestAcceptInvitation.test_accept_invitation_success`: create mock invitation with `status="pending"`, `to_user_id=mock_user.id`; mock membership helpers; assert 200 and `status == "accepted"`
    - `TestRevokeInvitation.test_revoke_success`: mock invitation with `from_user_id=mock_user.id`, assert 200
    - `TestListReceivedInvitations.test_list_returns_invitation_items`: mock a real invitation query result with `from_user` data, assert items list has one item with expected fields
  - [x] In `services/api/tests/test_invite_links.py`, add:
    - `TestCreateInviteLink.test_create_returns_deep_link`: assert `deep_link` starts with `"palateful://invite/"`
    - `TestPreviewInviteLink.test_preview_returns_state_active`: assert `state == "active"` in response (already has mock setup)
    - `TestJoinViaLink` class (new): `test_join_via_link_not_found` asserting 404/500; `test_join_via_link_success` with mock active link and membership creation
  - [x] Run `npx nx run api:test` — all tests pass

- [x] Task 2: Flutter — ApiClient additions (AC: all)
  - [x] In `app/lib/core/services/api_client.dart`, add the following methods:

  **Invitations:**
  ```dart
  Future<Response> listReceivedInvitations() =>
      _dio.get('/v1/invitations');

  Future<Response> listSentInvitations() =>
      _dio.get('/v1/invitations/sent');

  Future<Response> sendInvitation(Map<String, dynamic> data) =>
      _dio.post('/v1/invitations', data: data);

  Future<Response> acceptInvitation(String invitationId) =>
      _dio.post('/v1/invitations/$invitationId/accept');

  Future<Response> declineInvitation(String invitationId) =>
      _dio.post('/v1/invitations/$invitationId/decline');

  Future<Response> revokeInvitation(String invitationId) =>
      _dio.delete('/v1/invitations/$invitationId');

  Future<Response> claimInvitations() =>
      _dio.post('/v1/invitations/claim');
  ```

  **Invite Links:**
  ```dart
  Future<Response> createInviteLink(Map<String, dynamic> data) =>
      _dio.post('/v1/invite-links', data: data);

  Future<Response> previewInviteLink(String token) =>
      _dio.get('/v1/invite-links/$token');

  Future<Response> joinViaLink(String token) =>
      _dio.post('/v1/invite-links/$token/join');

  Future<Response> deactivateInviteLink(String inviteLinkId) =>
      _dio.delete('/v1/invite-links/$inviteLinkId');
  ```

- [x] Task 3: Flutter — InvitationsScreen (AC: #2, #6, #7)
  - [x] Create `app/lib/features/invitations/invitations_screen.dart`
    - `StatefulWidget InvitationsScreen`
    - State: `_receivedInvitations`, `_sentInvitations`, `_isLoading`, `_error`, `_selectedTab` (0=received, 1=sent)
    - `initState()`: call `_loadInvitations()`
    - `_loadInvitations()`: fetch both `listReceivedInvitations()` and `listSentInvitations()` in parallel; parse `List<dynamic>` from responses
    - Received tab: shows a `ListView` of invitation cards — each card shows `from_user.name` (or `@from_user.username`), `resource_name`, role chip, `Accept` / `Decline` buttons
    - `_accept(id)` → `acceptInvitation(id)` → reload; `_decline(id)` → `declineInvitation(id)` → reload
    - Sent tab: shows pending sent invitations — each card shows target (`to_user_id` or `to_email`), resource_name, role, `Revoke` button
    - `_revoke(id)` → `revokeInvitation(id)` → reload
    - Empty state: friendly message ("No pending invitations")
    - Error state: retry button

- [x] Task 4: Flutter — Invite UI in RecipeBookMembersScreen (AC: #1, #3)
  - [x] In `app/lib/features/recipe_books/recipe_book_members_screen.dart`:
    - Add `_showInviteBottomSheet()` method — opens a `showModalBottomSheet` with a `DefaultTabController` (2 tabs: "By username/email", "Invite link")
    - **Tab 1 — Direct invite:**
      - TextField for username or email input (label: "Username or email")
      - Dropdown or SegmentedButton for role (editor/viewer)
      - "Send Invite" button — calls `sendInvitation({resource_type: "recipe_book", resource_id: bookId, role_offered: role, to_username or to_email: ...})` depending on whether input looks like an email
      - Success: show snackbar "Invitation sent"; error: show error message in dialog
    - **Tab 2 — Invite link:**
      - "Generate Link" button — calls `createInviteLink({resource_type: "recipe_book", resource_id: bookId, role_offered: "viewer"})` — stores returned `deep_link` in state
      - Once generated: show the `deep_link` text in a row with a copy icon button and a share icon button
      - Copy: `Clipboard.setData(ClipboardData(text: deepLink))`; show snackbar "Link copied"
      - Share: use `Share.share(deepLink)` from `share_plus` package
    - Add "Invite" `IconButton` (or `TextButton`) in AppBar `actions` — only shown when `_userRole == 'owner'`

- [x] Task 5: Flutter — InviteLinkPreviewScreen (AC: #4, #5)
  - [x] Create `app/lib/features/invitations/invite_link_preview_screen.dart`
    - Constructor: `InviteLinkPreviewScreen({required String token})`
    - State: `_previewData`, `_isLoading`, `_error`, `_isJoining`
    - `initState()`: call `_loadPreview()` → `previewInviteLink(token)` → parse response
    - Show: inviter name, resource name, role offered, state label
    - `state == 'active'`: show "Join" button → calls `joinViaLink(token)` → on success navigate to the recipe book (`/recipe-books/{resource_id}`)
    - `state == 'already_member'`: show "Already a member — view book" button
    - `state == 'expired'|'full'|'inactive'`: show informational message, no action button
    - Loading and error states with retry

- [x] Task 6: Flutter — Deep link route registration (AC: #4, #5)
  - [x] In `app/lib/core/router/app_router.dart`:
    - Add import for `InvitationsScreen` and `InviteLinkPreviewScreen`
    - Add routes in the non-shell section (before `StatefulShellRoute`):
      ```dart
      GoRoute(
        path: '/invitations',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) => const InvitationsScreen(),
      ),
      GoRoute(
        path: '/invite/:token',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) {
          final token = state.pathParameters['token']!;
          return InviteLinkPreviewScreen(token: token);
        },
      ),
      ```
    - Add GoRouter `initialRoute` deep link support: ensure `initialLocation` can be overridden by incoming link — GoRouter handles this automatically with `GoRouter(initialLocation:...)` as long as routes are registered

- [x] Task 7: Flutter — Claim invitations on signup (AC: #5)
  - [x] In `app/lib/core/services/auth_service.dart`, find where `completeOnboarding` is called (the first successful sign-up completion):
    - After `completeOnboarding()` succeeds, call `_apiClient.claimInvitations()` — ignore errors silently (best-effort)
    - This ensures email-invited users get their pending invitations auto-accepted on first login

- [x] Task 8: Flutter — Profile screen link to invitations (AC: #7)
  - [x] In `app/lib/features/profile/profile_screen.dart`:
    - Add a `ListTile` row: "Invitations" with `Icons.mail_outline` icon
    - `onTap`: `context.push('/invitations')`

- [x] Task 9: Flutter widget tests (AC: all)
  - [x] Create `app/test/features/invitations/invitations_screen_test.dart`
    - Test: renders without error when invitations list is empty (mock ApiClient returns `[]`)
    - Test: shows invitation card with sender name and resource name when data is present
    - Test: tapping Accept calls `acceptInvitation` (mock ApiClient, verify call)
    - Test: tapping Decline calls `declineInvitation`
    - Test: Sent tab shows sent invitation with Revoke button
  - [x] Create `app/test/features/invitations/invite_link_preview_screen_test.dart`
    - Test: shows Join button when state is `active`
    - Test: shows "Already a member" message when state is `already_member`
    - Test: shows expired message when state is `expired`
  - [x] Run `flutter test` in `app/` — all tests pass

## File List

- `services/api/tests/test_invitations.py` — add meaningful test cases
- `services/api/tests/test_invite_links.py` — add join via link tests and deep_link assertion
- `app/lib/core/services/api_client.dart` — add invitation and invite-link methods
- `app/lib/features/invitations/invitations_screen.dart` — new file
- `app/lib/features/invitations/invite_link_preview_screen.dart` — new file
- `app/lib/features/recipe_books/recipe_book_members_screen.dart` — add invite bottom sheet and AppBar button
- `app/lib/core/router/app_router.dart` — add `/invitations` and `/invite/:token` routes
- `app/lib/core/services/auth_service.dart` — call claimInvitations on first signup completion
- `app/lib/features/profile/profile_screen.dart` — add Invitations list tile
- `app/test/features/invitations/invitations_screen_test.dart` — new file
- `app/test/features/invitations/invite_link_preview_screen_test.dart` — new file

## QA Walkthrough

**Happy paths:**
1. Open RecipeBookMembersScreen as owner → tap Invite → type a username → tap Send Invite → verify success snackbar appears
2. As the invited user: open Invitations screen → see pending invitation card with sender name, book name, role → tap Accept → verify card disappears
3. As owner: open Invite bottom sheet → tab "Invite link" → tap Generate Link → verify deep link appears → tap Copy → verify clipboard has `palateful://invite/...`
4. On a second device: navigate to `/invite/{token}` → verify preview screen shows book name and inviter → tap Join → verify navigated to the recipe book
5. Profile screen → tap Invitations → verify navigated to InvitationsScreen

**Edge cases:**
- Invite non-existent username → verify error message shown in dialog
- Invite yourself → verify "You cannot invite yourself" error
- Accept already-accepted invitation → verify graceful error message
- Open expired invite link → verify "This link has expired" message, no Join button

## Dev Agent Record

### Implementation Notes

- Added `share_plus: ^10.1.4` as a new dependency (required for share sheet in invite link tab)
- Backend was 100% complete before this story — no backend code was written; only backend tests were improved
- `test_invitations.py` improved from 7 smoke tests to 12 meaningful tests covering send, accept, revoke, and list with real mock data
- `test_invite_links.py` improved from 5 smoke tests to 10 tests including `TestJoinViaLink` class and deep_link assertion
- `InvitationsScreen` uses `SingleTickerProviderStateMixin` with `TabController` for received/sent tabs
- `RecipeBookMembersScreen` invite bottom sheet uses `DefaultTabController` (not stored as state) — tab 1 for direct invite by username/email, tab 2 for invite link generation/share
- Email detection in direct invite tab: input containing `@` and `.` treated as email, otherwise treated as username (leading `@` stripped)
- Route `/invite/:token` registered before `StatefulShellRoute` so deep links work without bottom nav
- `claimInvitations()` called after `completeOnboarding()` succeeds in `onboarding_start_screen.dart` — best-effort with silent error swallow

### Completion

- [x] All tasks implemented
- [x] `npx nx run api:test` passes — 252 tests
- [x] `flutter test` passes — 171 tests
- [x] Story file status updated to `review`
