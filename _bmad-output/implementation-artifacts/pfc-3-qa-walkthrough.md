# QA walkthrough — pfc-3 recipe detail keep-alive

Pre-dogfood sanity check that reopening a recipe within 5 minutes is
zero-network, and that every mutation path busts the cache.

## 1. Cache hit on reopen

- [ ] Open the app. DevTools → Network.
- [ ] Tap into Recipe A. `GET /v1/recipes/{A}` fires.
- [ ] Back out to home.
- [ ] Tap Recipe A again within ~5 minutes. Network log shows NO
      `GET /v1/recipes/{A}`. Detail renders instantly from cache.

## 2. Mutation busts cache

Exercise each mutation site. After each one, reopen the recipe and
verify the new data is visible (i.e. a fresh fetch happened).

- [ ] **Vibes (inside detail screen)** — open Recipe A, tap vibe
      pill, pick a new vibe, back out, reopen. New vibe renders.
- [ ] **Favorite toggle (inside detail screen)** — toggle heart, back
      out, reopen. Heart state matches.
- [ ] **Archive (inside detail screen)** — archive, it pops back to
      the caller. Navigate to Archived Recipes → Restore → open
      detail. Recipe is no longer archived.
- [ ] **Move (inside detail screen)** — move Recipe A to a different
      book, pops. From new book → open detail. Recipe shows the new
      book name.
- [ ] **Note add (inside detail screen)** — scroll to notes, submit a
      note, back out, reopen. Note is still visible.
- [ ] **Note delete (inside detail screen)** — delete a note, back
      out, reopen. Note is gone.
- [ ] **Edit screen** — open Recipe A → edit → change name → Save →
      back twice to the detail screen. New name visible.
- [ ] **Photo upload via edit** — open Recipe A → edit → pick photo →
      wait for upload → Save → back. New hero photo visible.
- [ ] **Version rollback** — open Recipe A → Versions → open a diff →
      Restore. Back to detail. Restored content visible.
- [ ] **Favorite from home** — home grid tile → tap heart. Open the
      same recipe in detail. Heart state matches home.
- [ ] **Bulk archive from home** — long-press a recipe in home grid →
      select → Archive. Then open Archived Recipes → tap the same
      recipe. Detail shows it (now from archived context). When you
      then Restore → open again → detail reflects non-archived state.
- [ ] **Bulk move from book detail** — open Recipe Book detail →
      long-press recipes → select → Move. Open one of the moved
      recipes in detail. New book shown.
- [ ] **Cook mode post-cook notes (online)** — cook a recipe → post-
      cook sheet → type notes → submit. Open the recipe detail.
      Notes list shows the fresh entry.
- [ ] **Cook mode pending-note flush** — go offline, cook + submit
      notes (queued). Go back online, stay in cook mode. Open the
      recipe detail. Notes list eventually shows the flushed note.

## 3. TTL expiry

- [ ] Open Recipe A. Back out.
- [ ] Wait 6 minutes (leave the app idle on another tab).
- [ ] Reopen Recipe A. Network log shows `GET /v1/recipes/{A}` —
      cache TTL expired.

## 4. No regression on detail-screen features

- [ ] Favorite toggle optimistic path still works (heart fills
      before the mutation returns).
- [ ] Vibes optimistic path still works.
- [ ] Servings scaler updates ingredient amounts inline without
      refetching.
- [ ] Recipe add-to-cart flow unchanged.
- [ ] Recipe share (link + native) unchanged.
- [ ] Meals-using-this-recipe section renders.
- [ ] Admin debug badge renders for admin users (was wired through
      `_authService.isAdmin` — now routed via the provider's inline
      admin check).
