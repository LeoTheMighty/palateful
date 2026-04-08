# Investigation: Sharing UX Overhaul

**Date:** 2026-03-22
**Status:** Investigation Complete
**Pain point:** "Sharing should be a lot fewer clicks and be able to pull up iOS native sharing options."

---

## Executive Summary

Palateful currently has three distinct sharing mechanisms across different content types, each with its own UX flow and varying levels of friction. Recipe sharing requires 3-5 taps to reach the iOS share sheet (if the user even discovers the option buried in a popup menu). Shopping list sharing uses a manual 6-character code system with no native share sheet integration at all. Recipe book sharing via invite links requires navigating to a separate Members screen, opening a bottom sheet, switching to the "Invite link" tab, generating a link, and then sharing it -- a 5-6 tap minimum.

The core problems are: (1) sharing actions are buried in overflow menus rather than being primary affordances, (2) the iOS share sheet (`UIActivityViewController`) is underutilized -- only recipe text sharing and recipe book invite links use it, (3) deep links use a custom `palateful://` scheme that does not work as universal HTTP links, making them useless outside the app, and (4) each content type has a completely different sharing paradigm rather than a unified pattern.

The recommended approach is to: promote share to a first-class action across all content types, standardize on the iOS share sheet via `share_plus`, migrate deep links to HTTPS universal links, and reduce every sharing flow to 1-2 taps.

---

## Current State Analysis

### Sharing Mechanisms by Content Type

#### 1. Recipe Sharing (Two Separate Flows)

**Flow A: "Share Link" (Public token-based link)**

- **Entry point:** Recipe detail screen > PopupMenuButton (overflow "..." menu) > "Share Link" item
- **Tap count to share:** 4-5 taps (open recipe > tap overflow > tap "Share Link" > wait for API > copy link from bottom sheet)
- **What happens:**
  1. Tapping "Share Link" calls `POST /v1/recipes/{id}/share` which generates a `share_token` and returns `palateful://recipe-public/{token}`
  2. A `_ShareLinkSheet` bottom sheet appears showing the deep link text, a "Copy Link" button, and a "Revoke" button
  3. The user must manually copy the link and then switch apps to paste it
- **No iOS share sheet used.** The bottom sheet only offers Copy to clipboard and Revoke.
- **Code:** `app/lib/features/recipes/recipe_detail_screen.dart` lines 423-468, 1134-1192
- **API:** `services/api/src/api/v1/recipe/share_recipe.py`

**Flow B: "Share" (Native text export)**

- **Entry point:** Recipe detail screen > PopupMenuButton > "Share" item
- **Tap count:** 3 taps (open recipe > tap overflow > tap "Share")
- **What happens:** Assembles a plain-text version of the recipe (name, description, ingredients, steps, "Shared via Palateful") and calls `Share.share()` which invokes the iOS share sheet
- **Limitation:** Shares plain text only -- no link back to the app, no image, no rich preview. The recipient gets a wall of text with no way to import the recipe into Palateful.
- **Code:** `app/lib/features/recipes/recipe_detail_screen.dart` lines 470-523

**Both options are hidden behind a PopupMenuButton** that also contains Add to Cart, Plan, Move, Copy, Fork, and Archive. The share actions are items 5 and 6 out of ~8 menu items.

#### 2. Shopping List Sharing

- **Entry point:** Shopping list screen > share icon in AppBar
- **Tap count:** 3-4 taps (open list > tap share icon > wait for API > view code dialog > copy code)
- **What happens:**
  1. Tapping the share icon calls `POST /v1/shopping-lists/{id}/share` which generates or retrieves a 6-character alphanumeric code
  2. An AlertDialog appears showing the code in large text with "Copy" and "Done" buttons
  3. The recipient must manually type the code into a "Join a Shopping List" dialog accessible from the cart screen
- **No iOS share sheet used.** No link generated. No deep link support.
- **Code:** `app/lib/features/shopping_cart/screens/shopping_list_screen.dart` lines 190-240
- **Join flow:** `app/lib/features/cart/cart_screen.dart` lines 111-159 -- requires manually typing a 6-char code
- **API:** `services/api/src/api/v1/shopping_list/share_shopping_list.py`

#### 3. Recipe Book Sharing (Invitation System)

- **Entry point:** Recipe book detail > Members icon (only visible to owners of shared books) > Members screen > "Invite" button in AppBar > Bottom sheet with two tabs
- **Tap count:** 5-6 taps minimum (open book > tap members icon > tap Invite > switch to "Invite link" tab > tap "Generate Link" > tap "Share")
- **Two sub-flows in the bottom sheet:**
  - **Tab 1 "By username/email":** Direct invitation via `POST /v1/invitations` -- requires knowing the target user's username or email
  - **Tab 2 "Invite link":** Generates an invite link via `POST /v1/invite-links`, then shows the link with Copy and Share buttons. **This is the only recipe book sharing flow that uses `Share.share()`.**
- **Code:** `app/lib/features/recipe_books/recipe_book_members_screen.dart` lines 196-402
- **API:** `services/api/src/api/v1/invite_links/create_invite_link.py`, `services/api/src/api/v1/invitations/send_invitation.py`

#### 4. Incoming Share Handler (receive_sharing_intent)

- The app listens for incoming shared URLs from other apps via `receive_sharing_intent` package
- When a URL is shared to Palateful, it navigates to `/recipes/add/share?url=...` which triggers a recipe import flow
- **Code:** `app/lib/main.dart` lines 142-186
- This is the reverse direction (sharing INTO Palateful) and works well

### Deep Link Architecture

- All deep links use the custom `palateful://` scheme
- Recipe public links: `palateful://recipe-public/{token}`
- Invite links: `palateful://invite/{token}`
- **Critical problem:** Custom URL schemes only work when the app is installed. They cannot be:
  - Opened in a browser
  - Previewed with Open Graph metadata
  - Used as universal links on iOS
  - Shared meaningfully to non-Palateful users
- The API constructs these links server-side (`share_recipe.py` line 47, `create_invite_link.py` line 55)

### Package Inventory

- `share_plus: ^10.1.4` -- installed but underutilized (only used in 3 places: recipe text share, recipe book invite link share, profile data export)
- `receive_sharing_intent: ^1.8.0` -- for handling incoming shares from other apps

---

## Research Findings

### iOS Share Sheet Best Practices (share_plus)

1. **`Share.share()` for text/URLs** -- triggers `UIActivityViewController` immediately. Supports a `subject` parameter for email subjects and a `sharePositionOrigin` for iPad popover positioning (required for iPad -- crashes without it).

2. **`Share.shareXFiles()` for rich content** -- can share images alongside text/URLs, enabling rich previews in Messages, WhatsApp, etc. Recipe sharing should include the recipe image when available.

3. **`ShareResult` return value** -- `Share.share()` returns a `ShareResult` that indicates whether the user completed the share, dismissed it, or which app they chose. This can be used for analytics.

4. **Positioning on iPad** -- The share sheet must be anchored to a `Rect` on iPad via `sharePositionOrigin`. Without this, the app crashes on iPad. Current code in `recipe_detail_screen.dart` does not pass this parameter.

### Recipe/Food App Sharing Patterns

1. **Primary share button placement:** Top-tier recipe apps (Paprika, Mela, Crouton) place a share icon directly in the AppBar or as a floating action, not buried in overflow menus. Share is typically 1 tap away.

2. **What gets shared:** A URL (universal link) that opens a rich web preview or the app. The link includes Open Graph metadata so iMessage/WhatsApp/Facebook show a card with the recipe image, title, and description.

3. **Share sheet content:** Best practice is to share a URL + brief text. Example: "Check out this recipe: Chicken Tikka Masala https://app.example.com/r/abc123". This gives the recipient a clickable link with a rich preview.

4. **"Save to my recipes" for recipients:** When a Palateful user receives a shared recipe link and opens it, they should be able to fork/save it to their own recipe book with one tap -- not just view it read-only.

### Universal Links / HTTPS Deep Links

1. **Universal Links (iOS)** use HTTPS URLs (e.g., `https://app.palateful.com/r/{token}`) that open directly in the app when installed, or fall back to a web page when not installed.

2. **Requirements:**
   - An `apple-app-site-association` (AASA) file hosted at `https://app.palateful.com/.well-known/apple-app-site-association`
   - The app must declare Associated Domains entitlement with `applinks:app.palateful.com`
   - A web landing page as fallback (can be a simple page with app store link + recipe preview)

3. **Advantages over custom schemes:**
   - Links work in browsers, social media, email
   - Rich previews via Open Graph tags on the web landing page
   - Deferred deep linking (user installs app, then is taken to the content)
   - No "Open in App?" confirmation dialog

4. **Implementation path:**
   - API returns `https://app.palateful.com/r/{token}` instead of `palateful://recipe-public/{token}`
   - Minimal web landing page (could be a Lambda@Edge or CloudFront function)
   - AASA file on the domain
   - `uni_links` or `app_links` Flutter package for handling incoming universal links

---

## Gap Analysis

| Area | Current State | Ideal State | Gap Severity |
|---|---|---|---|
| **Recipe share discoverability** | Hidden in 8-item overflow menu | Dedicated share icon in AppBar | HIGH |
| **Recipe share link + native sheet** | Two separate flows (link-only vs text-only) | Single tap: generate link + open iOS share sheet with link + image | HIGH |
| **Shopping list sharing** | Manual 6-char code, no share sheet | Share link via iOS share sheet, join via deep link | HIGH |
| **Recipe book sharing** | 5-6 taps through Members screen | Share button on book detail, 1-2 taps | HIGH |
| **Deep link format** | Custom `palateful://` scheme | HTTPS universal links | HIGH |
| **Rich previews** | None (plain text or raw deep link) | Open Graph previews in iMessage/WhatsApp | MEDIUM |
| **iPad share sheet** | Missing `sharePositionOrigin` | Proper anchor rect | MEDIUM |
| **Share + image** | Text-only sharing | Include recipe image via `Share.shareXFiles()` | MEDIUM |
| **Recipient experience** | Read-only view, no save action | "Save to my recipes" one-tap fork | MEDIUM |
| **Sharing consistency** | 3 different paradigms | Unified share pattern across all content | MEDIUM |
| **Share analytics** | None | Track share events and `ShareResult` | LOW |

---

## Recommendations

### P0: Critical (Do First)

#### R1. Promote Share to Primary Action on Recipe Detail
**Estimated Complexity:** LOW

Move the share action from the overflow menu to a dedicated `IconButton` in the AppBar (using `Icons.ios_share` on iOS). This alone cuts recipe sharing from 3+ taps to 1 tap.

**Changes:**
- `app/lib/features/recipes/recipe_detail_screen.dart`: Add `IconButton(icon: Icon(Icons.ios_share), onPressed: _shareRecipe)` to the AppBar `actions` list, before the overflow menu
- Remove `share_link` and `share_native` from the `PopupMenuButton`

#### R2. Unified Share Flow: Generate Link + Open iOS Share Sheet
**Estimated Complexity:** MEDIUM

Merge the two recipe sharing flows into one. When the user taps Share:
1. Generate a share link (API call, with loading indicator)
2. Immediately open the iOS share sheet with the link URL + recipe title as subject
3. Include the recipe image if available (via `Share.shareXFiles()`)

This replaces both the current "Share Link" (copy-only bottom sheet) and "Share" (text dump) flows.

**Changes:**
- `app/lib/features/recipes/recipe_detail_screen.dart`: Replace `_shareRecipe()` and `_nativeShareRecipe()` with a single `_share()` method
- The `_ShareLinkSheet` widget can be removed or repurposed as a "Manage Link" option in the overflow menu (for revoking)

#### R3. Add Share Button to Recipe Book Detail Screen
**Estimated Complexity:** LOW

Add a share icon to `RecipeBookDetailScreen`'s AppBar that opens a bottom sheet with the invite link flow (generate link + iOS share sheet). Currently this requires navigating to the Members screen first.

**Changes:**
- `app/lib/features/recipe_books/recipe_book_detail_screen.dart`: Add share `IconButton` to AppBar actions (visible to owners/editors)
- Extract the invite link generation + share logic from `RecipeBookMembersScreen._showInviteBottomSheet()` into a reusable widget or function

#### R4. Modernize Shopping List Sharing
**Estimated Complexity:** MEDIUM

Replace the 6-character code system with a shareable link that opens the iOS share sheet. The flow should be:
1. Tap share icon on shopping list screen
2. API generates a deep link (not a code)
3. iOS share sheet opens with the link
4. Recipient taps link to join the list

**Changes:**
- `services/api/src/api/v1/shopping_list/share_shopping_list.py`: Return a deep link URL in addition to / instead of the share code
- `app/lib/features/shopping_cart/screens/shopping_list_screen.dart`: Replace `_shareList()` dialog with `Share.share(deepLink)`
- Add a route for handling shopping list deep links in the router
- Keep the code-based join as a fallback option

### P1: Important (Do Second)

#### R5. Migrate to HTTPS Universal Links
**Estimated Complexity:** HIGH

Replace `palateful://` custom scheme links with `https://app.palateful.com/...` universal links. This is the single highest-impact change for sharing outside the app ecosystem.

**URL scheme:**
- Recipes: `https://app.palateful.com/r/{token}`
- Invite links: `https://app.palateful.com/i/{token}`
- Shopping lists: `https://app.palateful.com/s/{token}`

**Changes:**
- **Infrastructure:** Add CloudFront distribution or API Gateway route for `app.palateful.com` with AASA file and minimal web landing pages
- **API:** Update link generation in `share_recipe.py`, `create_invite_link.py`, `share_shopping_list.py` to use HTTPS URLs. Could be driven by an environment variable `APP_LINK_BASE_URL`.
- **iOS:** Add Associated Domains entitlement (`applinks:app.palateful.com`) to the Xcode project
- **Flutter:** Add `app_links` package or use `go_router`'s built-in deep link handling
- **Web fallback:** Simple HTML pages with Open Graph meta tags that redirect to App Store or render a preview

#### R6. Rich Link Previews (Open Graph)
**Estimated Complexity:** MEDIUM

When sharing recipe links, the landing page should include Open Graph tags so iMessage, WhatsApp, Slack, etc. render a card preview with the recipe image, title, and description.

**Changes:**
- Web landing page for `https://app.palateful.com/r/{token}` should render:
  ```html
  <meta property="og:title" content="Chicken Tikka Masala" />
  <meta property="og:description" content="A flavorful Indian curry..." />
  <meta property="og:image" content="https://cdn.palateful.com/recipes/abc.jpg" />
  ```
- Could be a lightweight Lambda@Edge or CloudFront Function that fetches recipe metadata from the API

#### R7. Add "Save to My Recipes" on Public Recipe Screen
**Estimated Complexity:** LOW

When a Palateful user opens a shared recipe link, they currently see a read-only view. Add a "Save to My Recipes" button that forks the recipe into their default recipe book.

**Changes:**
- `app/lib/features/recipes/public_recipe_screen.dart`: Add a FAB or bottom bar with "Save to My Recipes"
- Calls existing fork/copy API endpoint
- Should detect if user is authenticated; if not, prompt login first

### P2: Nice to Have (Do Later)

#### R8. Fix iPad Share Sheet Crash
**Estimated Complexity:** LOW

All `Share.share()` calls need a `sharePositionOrigin` parameter for iPad. Without it, the share sheet has no anchor and crashes.

**Changes:**
- Pass `sharePositionOrigin: box.localToGlobal(Offset.zero) & box.size` where `box` is the `RenderBox` of the share button
- Affects all call sites: recipe detail, recipe book members, profile export

#### R9. Share with Image via shareXFiles
**Estimated Complexity:** LOW

When sharing a recipe that has an image, download the image to a temp file and share it alongside the URL using `Share.shareXFiles()`. This creates much richer previews in iMessage and other apps.

**Changes:**
- Download image from `_recipe['image_url']` to temp directory
- Use `Share.shareXFiles([XFile(tempPath)], text: shareUrl, subject: recipeName)`

#### R10. Unified Share Service
**Estimated Complexity:** MEDIUM

Create a `ShareService` class that encapsulates all sharing logic:
- `shareRecipe(recipeId)` -- generates link + opens share sheet
- `shareRecipeBook(recipeBookId)` -- generates invite link + opens share sheet
- `shareShoppingList(listId)` -- generates link + opens share sheet
- Handles iPad anchor, image downloading, analytics, error handling

This centralizes share logic currently spread across 3+ screens.

#### R11. Share Analytics
**Estimated Complexity:** LOW

Track when users share content and what app they share to (via `ShareResult`). This informs product decisions about which sharing channels to optimize for.

---

## Technical Considerations

### API Changes Required

1. **New environment variable:** `APP_LINK_BASE_URL` (e.g., `https://app.palateful.com`) to construct shareable HTTPS URLs. Fall back to `palateful://` for backward compatibility.

2. **Shopping list share endpoint update:** `POST /v1/shopping-lists/{id}/share` should return a `deep_link` field in addition to `share_code`.

3. **Recipe share endpoint update:** Return the HTTPS URL instead of/alongside the `palateful://` URL.

4. **New public endpoint (for universal links):** A web handler at `app.palateful.com` that serves:
   - AASA file at `/.well-known/apple-app-site-association`
   - Open Graph HTML pages for shared content URLs
   - Redirect to App Store for non-app users

### Flutter Package Changes

- `share_plus` is already installed (v10.1.4) -- no change needed
- May need `app_links` package for universal link handling (unless `go_router` handles it)
- `receive_sharing_intent` continues to handle the "share TO Palateful" direction

### Infrastructure Changes (for Universal Links)

- **Option A:** CloudFront distribution for `app.palateful.com` with Lambda@Edge for dynamic OG tags
- **Option B:** API Gateway route with a lightweight handler
- **Option C:** Static S3 site for AASA + simple redirect pages (no dynamic OG -- simplest)

### Backward Compatibility

- Existing `palateful://` deep links should continue working during migration
- The app should handle both URL formats during the transition period
- API should accept a `link_format` parameter or use a feature flag

### Testing Considerations

- `app/test/features/recipes/share_recipe_test.dart` exists and tests the current share link bottom sheet flow -- will need updating
- iPad-specific testing for share sheet positioning
- Universal link testing requires a real device (simulator does not support universal links)

---

## Open Questions

1. **Domain choice:** Should the universal link domain be `app.palateful.com`, `share.palateful.com`, or `palateful.com/app`? This depends on existing domain infrastructure and whether there is already a marketing site.

2. **Web preview page scope:** Should the web landing page be a full-featured recipe viewer (like the current `PublicRecipeScreen` but in HTML) or a minimal redirect page? A full viewer enables sharing with non-app users but is more work.

3. **Shopping list sharing model change:** Should shopping list sharing migrate from share codes to the invite link system (which already supports deep links)? This would unify the sharing model but requires API changes.

4. **Recipe book share without Members screen:** Should non-owner members (editors) be able to share a recipe book, or only owners? Currently the invite flow is owner-only.

5. **Meal event sharing:** The invitation system supports meal events, but there is no share UI for meal events in the app. Should this be included in the overhaul?

6. **Analytics tooling:** Is there an existing analytics service (Mixpanel, Amplitude, etc.) to send share events to, or does this need to be set up?

7. **Android parity:** This investigation focused on iOS, but Android share sheet (via `share_plus`) works similarly. Are there any Android-specific requirements?

8. **Rate limiting for share links:** Recipe share tokens currently persist indefinitely. Should they expire? The invite link system already supports expiration via `expires_in_days`.
