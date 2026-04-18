# notif-2 QA walkthrough

Most of notif-2 is covered by unit tests. This checklist is for the docs + env wiring.

## Backend (automated — already green)
- [x] `npx nx run utils:test` passes (122/122, includes 7 new push_notification tests)
- [x] `npx nx run utils:lint` passes
- [x] `send_to_user` with existing callsite signature still returns `success_count`/`failure_count`/`cleaned_tokens`

## Local dev smoke
Confirm log-only mode works when env is empty.
- [ ] `docker compose up` — no `FIREBASE_CREDENTIALS_JSON` or `FIREBASE_CREDENTIALS_PATH` set
- [ ] Look for INFO log `push_notifications: running in log-only mode (no FIREBASE_CREDENTIALS_JSON / FIREBASE_CREDENTIALS_PATH); no pushes will be delivered` on first boot
- [ ] Trigger any push callsite (e.g., accept a friend request in local app) — confirm `[log-only] would multicast type=... title=...` INFO log, no error, no Firebase SDK init

## Docs review
- [ ] `docs/PUSH_NOTIFICATIONS.md` exists and renders on GitHub
- [ ] "Last verified" header includes placeholder for APNs Key ID (fill in during notif-1 ops step)
- [ ] APNs .p8 upload procedure is clear (step-by-step, what to click where)
- [ ] APNs .p8 rotation procedure covers upload-new-then-delete-old ordering
- [ ] Troubleshooting checklist has at least 6 distinct failure modes

## Prod (not verified until notif-1 ops step + notif-3 ships)
- [ ] `FIREBASE_CREDENTIALS_JSON` Secret Manager ARN unchanged
- [ ] ECS task definition reads secret into env (no Terraform change this story)
