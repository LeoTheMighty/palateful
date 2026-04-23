# cla-13 — QA Walkthrough

## What shipped

Privacy / Data Safety disclosures now match the telemetry that
`epic-perf-client-analytics` ships. Three touch-points:

1. **`app/web/privacy.html`** — a new "Diagnostic and performance data"
   section describes what the custom `client_latencies` pipeline,
   iOS MetricKit, Android JankStats, and Firebase Performance each
   sample. The existing Firebase subprocessor entry is extended to
   include "performance monitoring" alongside Crashlytics + FCM.
   Retention (30 days, automatic) is called out explicitly.

2. **`ANDROID.md` Section 15 — Data Safety form** gains a new
   **Block 7 — Diagnostic performance data** with paste-ready
   declaration text for the Play Console Data Safety form. The
   existing Play Billing block is renumbered from Block 7 → Block 8.
   The section header also now notes that Block 7 must be pasted
   alongside existing blocks — copy-pastes from pre-cla-epic revisions
   would otherwise miss it.

3. **iOS App Store Connect** (via cross-ref at `ANDROID.md:35`): the
   same declaration content should be pasted under App Privacy →
   Diagnostics → Performance data. No separate file update needed;
   Apple's App Privacy form reads from the web, not from a repo file.

## Acceptance criteria mapping

| AC                                                      | How cla-13 satisfies it |
|---------------------------------------------------------|--------------------------|
| (1) `app/web/privacy.html` "Diagnostic data" section    | Added after Notification section, before AI section |
| (2) App Store Data Safety form updated                  | Declaration text sits in ANDROID.md Block 7 — operator pastes into App Privacy form at rollout |
| (3) Play Console Data safety form updated               | Same — Block 7 is paste-ready |
| (4) cross-reference documented in ANDROID.md            | Block 7 added; Section 15 intro updated |
| (5) soft dependency on epic-android-play-console-launch | See "Rollout coordination" below |

## Rollout coordination (AC5)

`epic-android-play-console-launch` is `in-progress` as of this PR
(sprint-status.yaml). The Data Safety form is filled out during
`apl-3`, which consumes the ANDROID.md blocks. Block 7 is now in
place, so whenever apl-3 runs next it'll pick up the diagnostic-data
declaration automatically — **no coordination conflict**.

If the Play Console submission has already happened (apl-3 done)
before `epic-perf-client-analytics` ships to production, the
operator re-opens the Data Safety form in Play Console, adds the
Block 7 declaration, and re-submits. Play Console accepts incremental
Data Safety updates without a full app-content re-review.

## Manual QA steps

- [ ] `grep -F "Diagnostic and performance data" app/web/privacy.html`
      — 1 match expected.
- [ ] `grep -F "Block 7" ANDROID.md` — Block 7 header is "Diagnostic
      performance data"; Block 8 header is "Play Billing".
- [ ] Render `app/web/privacy.html` locally (`open app/web/privacy.html`
      or deploy preview) — visual-check that the new section renders
      between the Notification section and the AI chat section, with
      the same heading-scale and list style.
- [ ] `grep -F leonid@ac93.org app/web/privacy.html` — at least 4
      matches, consistent with the cross-check in ANDROID.md line 29.
- [ ] Before the next production rollout that includes the cla-epic
      changes: operator paste-check that Block 7 text landed in both
      Play Console Data Safety + App Store Connect App Privacy.
      Screenshot both forms into the operator's epic-finalization
      artefact folder.

## Regression surface

- No code changes. `app/web/privacy.html` is a static page served via
  Cloudflare Pages; its deploy pipeline (`deploy-web` workflow)
  re-deploys on main-branch push.
- No new tests — the privacy-policy page doesn't have a widget-test
  surface. Content accuracy is verified visually + via the grep
  checks above.
- `ANDROID.md` is docs — renumber from Block 7 → Block 8 doesn't
  affect any tooling; block numbers are an internal organizing
  convention.

## Known-safe choices (and why)

- **One Block, three telemetry sources.** The custom pipeline,
  MetricKit, JankStats, and Firebase Performance all fit in Play
  Console's "Diagnostics — Performance data" bucket. Splitting them
  into separate blocks would be over-detailed for Play review and
  the public privacy policy collapses them into one section for the
  same reason.
- **Retention stated as 30 days.** Matches the
  `prune_latencies.py` nightly job and Firebase Performance's own
  default retention. If one of the two changes, the number has to
  move in lockstep.
- **Firebase called out as "secondary cross-check"** in the privacy
  policy. Consistent with the internal runbook language in
  `docs/PERFORMANCE_OPS.md` — we don't want our legal disclosures to
  overstate how load-bearing Firebase is to app functionality.

## Backout

- Revert the commit. `app/web/privacy.html` loses the Diagnostic
  section; ANDROID.md loses Block 7 (Play Billing becomes Block 7
  again). No schema / build / runtime impact.
