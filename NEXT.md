⏺ Epic + 7 stories done! Here's your dev agent snippet:

  Execute the iOS Native Features epic. Stories are at:
  _bmad-output/implementation-artifacts/ios-1-notification-actions.md
  _bmad-output/implementation-artifacts/ios-2-foundation.md
  _bmad-output/implementation-artifacts/ios-3-widgets.md
  _bmad-output/implementation-artifacts/ios-4-live-activities.md
  _bmad-output/implementation-artifacts/ios-5-interactive-widgets.md
  _bmad-output/implementation-artifacts/ios-6-siri-spotlight.md
  _bmad-output/implementation-artifacts/ios-7-control-center-rich-notifs.md

  For EACH story, follow this cycle:
  1. READ the story file fully
  2. IMPLEMENT all tasks/subtasks, checking them off as you go
  3. Set story status to "complete"
  4. SELF-REVIEW: Run /bmad-bmm-code-review on your own changes — fix all HIGH and MEDIUM issues automatically (do not ask, do not create action items — just fix them)
  5. COMMIT: Stage only story-related files, write a descriptive commit message summarizing what was implemented, push to main
  6. MOVE to the next story

  Dependency order:
  - iOS.1 is independent (quick win — do first)
  - iOS.2 is foundational (do second)
  - iOS.3 and iOS.4 depend on iOS.2 (can run in parallel)
  - iOS.5 depends on iOS.3
  - iOS.6 depends on iOS.2
  - iOS.7 depends on iOS.5 and iOS.6

  Suggested execution order: 1 → 2 → 3 → 4 → 5 → 6 → 7

  Reference the epic overview at _bmad-output/planning-artifacts/epic-ios-native.md for design principles.