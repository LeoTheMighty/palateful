---
hash: sru4
type: dev
created: 2026-07-27T17:10:00-06:00
title: Presigned upload path for PDF / audio / video in the receiving screen
from: _bmad-output/planning-artifacts/epic-share-receiving-ux.md
status: in-progress
owner: /devx-loop-2026-07-27T21-15-34-312-36147
branch: feat/dev-sru4
---

## Goal
Wire the pure-upload branches (PDF, audio, video) of the universal receiving screen to the presigned-upload contract: request `upload-url`, PUT the file to S3, then POST `/import` with `{s3_key, etag, source_type, book_id}`, navigating to the Activity Hub on success. Byte-level progress renders on the receiving card throughout, and a dispose-time `HttpClient.abort()` prevents half-uploaded S3 objects when the user closes mid-upload. This is the last remaining story in the epic — sru-1/2/3/5 landed on main in commit 95b8cab.

## Acceptance criteria
- [ ] Sequence: request `upload-url` → PUT file to S3 (capture `ETag` header) → POST `/import` with `{s3_key, etag, source_type, book_id}`. On `201` navigate to Activity Hub; on `409 object_not_ready` retry `/import` up to 3× with 500 ms backoff before surfacing error.
- [ ] Byte-level progress rendered on the receiving screen during PUT. Progress card covers the full "copy-to-sandbox → uploading → sending" sequence — never black-screen.
- [ ] Screen holds an `HttpClient` that `abort()`s when the screen disposes (user tapped Close or Android back); this prevents half-uploaded S3 objects (lifecycle rule in Epic 1 sweeps them at 24 h as a backstop).
- [ ] Integration test mocks upload-url, S3 PUT, `/import` and asserts the `{s3_key, etag}` body shape + 409-retry path.

## Technical notes
- Upload contract is a locked cross-epic decision (epic file § "Locked cross-epic decisions" item 1) owned by Epic 1 (`epic-share-backend-foundations`): `upload-url` → PUT → `/import {s3_key, etag}` with 3× 500 ms backoff on 409 `object_not_ready`.
- Flows C/D/E in the epic's "End-user flow" section specify the per-type copy and `source_type` values (`pdf`, `audio`, `video_file`); routing logic lives in the epic's "New screen: /recipes/add/receive" section.
- Dedup key `sha256(path+mtime+size)` is used as the s3_key suffix so a double-fire second PUT to the same key is a no-op (epic § "Added by this workshop").
- Progress staging ("Receiving…" → "Uploading… N%" → "Sending to Palateful…" → check flash) and >5 s large-file behavior per epic § "Progress and confirmation UI"; error states (network, 401, 413, 409, generic) keyed on machine-readable `error_code` per epic § "Error states".
- Implementation surface: `app/lib/features/recipes/add_recipe/receive_import_screen.dart`, `state/receive_import_notifier.dart`, `widgets/receive_progress_card.dart` (all landed by sru-1/2); `VideoFileImportScreen` (sru-5) submits through this same upload sequence.
- Risks already mitigated in ACs: 201-before-S3-flush race (HeadObject in Epic 1 + 409 retry handshake here), close-mid-upload leaks (abort on dispose + 24 h lifecycle backstop). See epic § "Risks surfaced in party-mode".
- Original BMAD story key: sru-4-presigned-upload-for-pdf-audio-video-in-receive-screen.

## Status log
- 2026-07-27T17:10 — imported from BMAD (epic file + sprint-status.yaml) during BMAD→devx migration
- 2026-07-27T18:10:00-06:00 — claimed by /devx in session /devx-loop-2026-07-27T21-15-34-312-36147
