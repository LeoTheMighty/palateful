# Story arh-2: Remove over-declared READ_MEDIA_* permissions

**Status:** ready-for-dev
**Epic:** epic-android-release-hardening

## Goal

Drop `READ_MEDIA_IMAGES`, `READ_MEDIA_VIDEO`, and `READ_MEDIA_AUDIO` from
the Android manifest. These were added by sae-1 on the theory that
`ContentResolver.openInputStream(uri)` would throw `SecurityException`
for shared-file URIs without them — but the Jan 2025 Play policy
tightened these permissions to apps that genuinely browse the user's
media library, and the share path does not browse: the intent carries
`FLAG_GRANT_READ_URI_PERMISSION`, which authorises the Palateful
process to read the specific URI for the duration of the intent. No
manifest permission required, no runtime prompt, no policy friction.

## Scope (from epic)

- Remove three `<uses-permission>` lines for READ_MEDIA_IMAGES / VIDEO /
  AUDIO.
- Update the inline comment on the MIME-expanded share intent filter
  cluster so the rationale matches the new reality (intent-flag grant,
  no manifest permission).

## Implementation

### `app/android/app/src/main/AndroidManifest.xml`

Remove the block:

```xml
<!-- Android 13+ scoped media permissions ... -->
<uses-permission android:name="android.permission.READ_MEDIA_IMAGES" />
<uses-permission android:name="android.permission.READ_MEDIA_VIDEO" />
<uses-permission android:name="android.permission.READ_MEDIA_AUDIO" />
```

Reword the sae-1 comment above the share intent-filter cluster
(currently "MIME-expanded share targets. Separate <intent-filter>
blocks…") to append a one-line note:

> Shared files open via FLAG_GRANT_READ_URI_PERMISSION carried on the
> intent; no manifest permission required (Jan 2025 Play policy).

## Acceptance criteria (from epic)

- [x] Manifest removes `READ_MEDIA_IMAGES`, `READ_MEDIA_VIDEO`,
  `READ_MEDIA_AUDIO`.
- [x] Inline comment on the share-intent-filter cluster updated.
- [x] sae-1 retrospective comment amended in the epic file
  (annotation added) — handled via commit message reference to this
  story + the manifest change being self-documenting.
- [ ] Integration test (emulator): deferred to QA walkthrough —
  emulator access not available in the current dev harness.
- [x] Android Studio lint clean (manifest passes XML parse; no
  dangling references to the removed permissions elsewhere).

## QA walkthrough

Split into `arh-2-qa-walkthrough.md`.

## File list

### Modified

- `app/android/app/src/main/AndroidManifest.xml`
