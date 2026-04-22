# QA Walkthrough — partner-1

Foundation-only story; no user-visible behavior to exercise directly.
Verified indirectly by partner-2 / partner-3 / partner-4 callsite
walkthroughs, which consume the copy functions and enum values added
here.

## Automated checklist

- [x] `npx nx run utils:lint` passes.
- [x] `poetry run pytest libraries/utils/test/` — 428 passed.
- [x] Module-import exhaustiveness assert in `push_notification.py`
      still holds after adding five new `NotificationType` values.
- [x] Each new copy function has a test asserting the title / body
      matches the epic templates.
- [x] Actor-name resolver test covers the full fallback chain.
- [x] Note-snippet truncation test confirms 200-char note → 120-char
      body with ellipsis.
- [x] All five new types respect `categories.partner_activity=false`.

## No manual smoke required

Callsites are not yet wired; nothing to trigger. See
`partner-2-qa-walkthrough.md` onward for end-to-end pushes.
