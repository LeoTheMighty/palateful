# QA walkthrough — afh-6 regression

Mostly automated. Manual check:

- [ ] Before pushing: confirm `npx nx run api:test` is green locally — ensures the deploy-order guard is happy (any "import error" on `NOTIFICATION_TAB_TYPES` surfaces here).
- [ ] Confirm `flutter test test/features/activity/` is green — ensures the paginated-provider walk + archive-race tests pass.
- [ ] On a test user with ~30 notifications, scroll the Notifications See-all from top to bottom. Verify no row is skipped (each row has a unique identifier; visually confirm no blanks mid-list).
- [ ] Same on Imports See-all with ~30 archived items.
- [ ] Archive one notification, restore via Undo, archive again — bell count, See-all count, and list state all reconcile after 3s. No duplicate / missing rows.
- [ ] At dogfood-scale: use a power-user account with real history (>200 archived notifications if available). Scroll through several pages. No stalls.
