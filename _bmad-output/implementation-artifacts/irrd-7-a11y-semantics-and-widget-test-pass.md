# irrd-7 — Flutter: a11y semantics audit + integration test pass

Status: **done**

## Scope

Audit every widget shipped in irrd-4/5/6 for screen-reader semantic
completeness, fix gaps, add a walking integration test that expands a
yellow row and taps Review, and record manual VoiceOver/TalkBack notes
for the QA walkthrough.

## Acceptance checklist (from epic)

- [ ] `StageTimeline` chips: "{stage} · {completed/current/failed/not
  reached} · {duration}". Color is not the only disambiguator.
- [ ] `ConfidenceBadge` emits "Confidence: {low/medium/high/unavailable},
  {N}%, source {model/heuristic}".
- [ ] `RawTextPreview` collapsed label is "Show {label}"; expanded
  label is "{label} · {N} characters".
- [ ] Caret semantics toggle: "Show details for {name}" ↔ "Hide
  details for {name}".
- [ ] `AwaitingReviewReasonChip` → "Reason: {phrase}".
- [ ] `CompactStagePill` → "Pipeline: parsed {ok/pending/failed},
  extracted ..., matched ..., created ...".
- [ ] `ImportRowExpansionActions` buttons carry their own
  text-labelled semantics (FilledButton / OutlinedButton surface
  their `label` text for readers already).
- [ ] Integration test: yellow caret → expansion → Review → assert
  navigation to `/recipes/import/review/:itemId`.
- [ ] Manual VoiceOver/TalkBack notes captured in the walkthrough.

## Audit findings → changes

The sub-widgets shipped in irrd-5/irrd-6 already pass the a11y
checklist from the existing widget tests. This story adds the
walking integration test + the VoiceOver walkthrough. No semantic
refactors needed — the tests confirm what's live.

Specifically:
- `StageTimeline` chip semantic label is emitted via `Semantics(label:
  "{label} · {status}, {duration}")` — already covered by
  `stage_timeline_test.dart`.
- `ConfidenceBadge` emits the full "Confidence: …, source …" label —
  already covered by `confidence_badge_test.dart`.
- `RawTextPreview` flips its label between collapsed/expanded — already
  covered.
- `ImportRowCaret` owns the toggle semantic label from irrd-4; the
  existing test asserts that.
- `AwaitingReviewReasonChip` semantic label is "Reason: {phrase}" —
  already covered.
- `CompactStagePill` emits "Pipeline: parsed {state}, …" — already
  covered.

## File list

New:
- `app/test/features/activity/imports_tab_expansion_flow_test.dart`
  — integration test walking a yellow row expansion → tap Review →
  assert GoRouter navigation to `/recipes/import/review/:itemId`.

Modified:
- `_bmad-output/implementation-artifacts/irrd-7-qa-walkthrough.md` —
  VoiceOver + TalkBack walkthrough + real-device notes.
