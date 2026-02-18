# Invitation System Design Doc

## Overview

Palateful supports sharing four resource types—**Recipe Books**, **Pantries**, **Shopping Lists**, and **Meal Events**—with other users. The invitation system provides two mechanisms:

1. **Direct Invitations** — invite a specific user (by user ID, username, or email)
2. **Invite Links** — shareable tokens anyone with the link can use to join

## Architecture

### Resource Types & Roles

| Resource Type | Valid Roles | Permission Source |
|---|---|---|
| `recipe_book` | `owner`, `editor`, `viewer` | Join table (`recipe_book_users`) |
| `pantry` | `owner`, `editor`, `viewer` | Join table (`pantry_users`) |
| `shopping_list` | `owner`, `editor`, `viewer` | `owner_id` on resource + join table (`shopping_list_users`) |
| `meal_event` | `host`, `cohost`, `guest` | `owner_id` on resource + join table (`meal_event_participants`) |

### Models

- **`Invitation`** — tracks a direct invitation from one user to another (or to an email)
- **`InviteLink`** — tracks a shareable link token with optional max uses and expiration
- **`Activity`** — audit trail entries for `invited`, `joined`, `left` actions

---

## Flow 1: Direct Invitation

```
Inviter → POST /invitations → Invitation(status=pending)
                                  ↓
                          Push notification to recipient
                                  ↓
Recipient → POST /invitations/{id}/accept → Create membership → Activity log
         → POST /invitations/{id}/decline → Silent decline
```

### Resolving the Target

The `POST /invitations` endpoint accepts one of:
- `to_user_id` — direct user ID
- `to_username` — find user by @username
- `to_email` — create a pending email invitation (no notification sent, no email sent)

### Email Invitations (No Account)

When `to_email` is provided and no user exists with that email:
1. `Invitation` is created with `to_user_id = NULL` and `to_email` set
2. No notification is sent (the invite link is shared out-of-band)
3. When the invited person signs up, the client calls `POST /invitations/claim` to match their email against pending invitations
4. Claimed invitations are NOT auto-accepted — the user sees them as pending and can accept/decline

### Duplicate Prevention

Before creating an invitation, check for existing pending invitations to the same user for the same resource. If found, return error `INVITATION_ALREADY_SENT (242)`.

### Rate Limiting

Maximum 30 invitations per user per 24-hour window.

---

## Flow 2: Invite Links

```
Creator → POST /invite-links → InviteLink(token=..., is_active=true)
                                    ↓
                          Share deep link out-of-band
                                    ↓
Joiner → GET /invite-links/{token} → Preview (metadata, state)
       → POST /invite-links/{token}/join → Create membership → Activity log
```

### Deep Linking Schema

Invite links use deep links (no web landing page):

```
palateful://invite/{token}
```

With deferred deep linking for users without the app installed:
1. User clicks link → App Store / Play Store
2. Token stored client-side (clipboard / deferred deep link SDK)
3. After install + signup → client calls `GET /invite-links/{token}` then `POST /invite-links/{token}/join`

### Link States

`GET /invite-links/{token}` returns a `state` field:

| State | Condition |
|---|---|
| `active` | Link is valid and joinable |
| `expired` | `expires_at` has passed |
| `full` | `use_count >= max_uses` |
| `inactive` | `is_active = false` (deactivated by creator) |
| `already_member` | Current user is already a member of the resource |

---

## Flow 3: Claim on Signup

When a new user signs up, the client calls:

```
POST /invitations/claim
```

This matches the user's email (case-insensitive) against pending invitations where `to_user_id IS NULL`. Matched invitations get `to_user_id` set to the new user. They are NOT auto-accepted — the user sees them as pending invitations in their inbox.

---

## API Endpoints

### Invitations

| Method | Route | Description |
|---|---|---|
| `POST` | `/v1/invitations` | Send an invitation |
| `GET` | `/v1/invitations` | List received pending invitations |
| `GET` | `/v1/invitations/sent` | List sent invitations |
| `POST` | `/v1/invitations/{id}/accept` | Accept an invitation |
| `POST` | `/v1/invitations/{id}/decline` | Decline an invitation |
| `DELETE` | `/v1/invitations/{id}` | Revoke a sent invitation |
| `POST` | `/v1/invitations/claim` | Claim email invitations after signup |

### Invite Links

| Method | Route | Description |
|---|---|---|
| `POST` | `/v1/invite-links` | Create an invite link |
| `GET` | `/v1/invite-links/{token}` | Preview invite link metadata |
| `POST` | `/v1/invite-links/{token}/join` | Join a resource via invite link |
| `DELETE` | `/v1/invite-links/{id}` | Deactivate an invite link |

---

## Error Codes

### Invitation Errors (240-249)

| Code | Name | HTTP Status |
|---|---|---|
| 240 | `INVITATION_NOT_FOUND` | 404 |
| 241 | `INVITATION_ACCESS_DENIED` | 403 |
| 242 | `INVITATION_ALREADY_SENT` | 409 |
| 243 | `INVITATION_EXPIRED` | 410 |
| 244 | `INVITATION_NOT_PENDING` | 400 |
| 245 | `INVITATION_INVALID_RESOURCE_TYPE` | 400 |
| 246 | `INVITATION_INVALID_ROLE` | 400 |
| 247 | `INVITATION_SELF_INVITE` | 400 |
| 248 | `INVITATION_ALREADY_MEMBER` | 409 |

### Invite Link Errors (250-259)

| Code | Name | HTTP Status |
|---|---|---|
| 250 | `INVITE_LINK_NOT_FOUND` | 404 |
| 251 | `INVITE_LINK_INACTIVE` | 410 |
| 252 | `INVITE_LINK_EXPIRED` | 410 |
| 253 | `INVITE_LINK_MAX_USES_REACHED` | 410 |
| 254 | `INVITE_LINK_ACCESS_DENIED` | 403 |

---

## Notification Types

| Type | Trigger | Sent To |
|---|---|---|
| `INVITATION_RECEIVED` | Invitation created (user target only) | Recipient |
| `INVITATION_ACCEPTED` | Invitation accepted | Inviter |

---

## Membership Creation Details

When an invitation is accepted or a user joins via link, a membership row is created in the appropriate join table:

| Resource | Join Table | Special Behavior |
|---|---|---|
| `recipe_book` | `recipe_book_users` | Role from invitation |
| `pantry` | `pantry_users` | Role from invitation |
| `shopping_list` | `shopping_list_users` | Also sets `is_shared = true` on the shopping list |
| `meal_event` | `meal_event_participants` | Sets `status = "accepted"` on participant |

### Archived Membership Reactivation

If a user was previously a member (has an archived membership row), the existing row is un-archived and role is updated rather than creating a duplicate.

### Idempotency

If the user is already an active member, the accept/join operation succeeds silently without creating a duplicate.
