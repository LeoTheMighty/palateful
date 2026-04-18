# QA walkthrough — sru-2 (unsupported + oversize terminal states)

## Happy paths

- Share a `.docx` from Files → "We can't read this yet" card with
  the filename. Tapping "Paste Text Instead" opens the text-paste
  screen; tapping Close returns home.
- Share a `.rtf`, `.zip`, `.doc` — same behavior. The handler in
  sae-2 tagged these as unsupported before the receive screen
  sees them; sru-1 also falls through to this card if the MIME +
  extension are both unknown.

## Oversize path

- Pick a file ≥ 100 MB (e.g. a long video). Receive screen reads
  the size and renders "That file is too large" with the actual
  size and a Close action. The 100 MB limit matches the backend's
  `MAX_UPLOAD_BYTES` in `/imports/upload-url` so we fail fast before
  burning a presigned URL.
- Verify via network inspector: **no request to
  `/imports/upload-url`** is made on this branch.

## Edge cases

- Permission-denied sandbox path: falls through to the unsupported
  card (not oversize), since we can't show a size without the stat.
- Empty file (0 bytes): size gate passes; flows through as normal.
  Backend will reject `size_bytes <= 0` if the user ever reaches an
  upload path.
- Share a perfectly 100 MB file: current code uses `>=` so 100.0 MB
  exactly is rejected. This mirrors the backend's `> MAX_UPLOAD_BYTES`
  check with the same value — close enough; the difference is a
  single byte and either answer ships a consistent error.

## Regression checklist

- [ ] After seeing the unsupported card, tapping Close then
      re-opening the home screen doesn't leave the receive screen
      behind in the nav stack (use the back button to verify).
- [ ] The `share_intent_unsupported` ErrorReporter event still
      fires on the unsupported card so the `*/*`-unlock metrics
      gate keeps ticking.
