# notif-3 QA walkthrough

## Automated (green)
- [x] `poetry run pytest tests/test_admin_send_test_push.py` — 7/7 pass
- [x] Full `npx nx run api:test` — 1441 passed (87 failures pre-existing, all in cal-found / meal-event WIP files I did not touch)
- [x] `dart analyze lib/features/admin/admin_dashboard_screen.dart lib/core/services/api_client.dart` — no new issues from this story

## Dashboard UX (manual, on simulator/device)
- [ ] Admin dashboard renders a Notifications section under the existing Quick Actions
- [ ] "Send test push" button is visible with description text
- [ ] Tap while log-only mode (local dev) → result banner says "Sent in log-only mode — check the API logs." + link to docs
- [ ] Tap while no push tokens registered → result banner says "No push tokens registered…"
- [ ] Tap 11 times in quick succession → 11th shows "Rate-limited. Retry in Ns."
- [ ] Banner styling uses primaryContainer (success) vs errorContainer (failure) colors

## End-to-end (requires notif-1 ops step + FIREBASE_CREDENTIALS_JSON in prod)
- [ ] Deploy to prod
- [ ] Leo opens admin dashboard → Notifications → Send test push
- [ ] Dashboard shows "✓ Sent (msg-id: …). Check your phone."
- [ ] Within 5 seconds, phone displays push with title "Palateful test push"
- [ ] Tap push → app opens to home screen
- [ ] Query `error_logs` where service='audit' and error_type='AdminTestPushAudit' — one new row with the message_id from the response
- [ ] Confirm NO `service='push_notifications'` row with `error_type='PushSendFailure'` for the same send
