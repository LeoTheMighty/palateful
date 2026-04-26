# QA walkthrough — Story pos-6b (FreeForeverChip on limit-shaped surfaces)

**What shipped:** the canonical `FreeForeverChip` widget mounted in
two places — the AddRecipeSheet footer and the recipe-book invite
bottom sheet. Future epics that touch a "this would be a paywall in
another app" surface mount this widget; do not invent feature-
specific copy.

## Setup

Recent local debug build (`flutter run` from `/app`) on iOS or Android.

## AddRecipeSheet (import flow)

- [ ] Open the app. From any recipe-list screen (Home, a recipe-book
  detail, etc.), tap the FAB / "+" to open the **AddRecipeSheet**
  bottom sheet.
- [ ] Scroll to the bottom of the sheet (past all the import options:
  URL, photo, share-sheet, voice memo, spreadsheet, video, manual).
- [ ] Below the option rows there is a chip:
  - Icon: `Icons.all_inclusive` in primary brand color.
  - Headline: `Unlimited — free forever` (bold, primary text color).
  - Subtitle: `No 5/week cap. No premium tier.` (smaller, muted).
- [ ] The chip aligns left, has a tinted-primary background, rounded
  corners. No overflow on a 360-px-wide device.

## Recipe-book invite sheet (household flow)

- [ ] Open a recipe book that has the "Members" affordance. Tap
  Members → the icon button opens the invite bottom sheet.
- [ ] The sheet has two tabs: "By username/email" and "Invite link."
- [ ] Below the TabBarView (regardless of which tab is active) a
  **FreeForeverChip.household** is rendered:
  - Headline: `Unlimited — free forever`.
  - Subtitle: `No seat limits. Invite anyone.`
- [ ] Both tabs continue to function as before — sending an invitation
  by email / username works, generating an invite link works.
- [ ] On a 360-px-wide device, the chip wraps cleanly — subtitle on a
  second line if needed.

## Accessibility

- [ ] VoiceOver / TalkBack on the chip reads a single Semantics label
  combining headline + subtitle (e.g. `Unlimited — free forever. No
  5/week cap. No premium tier.`). Because of the wrapping
  `Semantics(container: true, label: …)`, the screen reader does not
  read the icon and three Texts as four separate items.

## Cross-epic contract

- [ ] Open `app/lib/shared/widgets/free_forever_chip.dart` and read
  the class doc comment. It names the contract: any future epic that
  introduces a limit-shaped surface (where a competitor would
  paywall) mounts this widget, not feature-specific copy.
- [ ] Variants are `const` constructors with hardcoded subtitles.
  Adding a fourth requires touching this file. Confirm by inspection.

## Grep-guard sanity (pos-6a interaction)

- [ ] Run from repo root:
  ```bash
  bash tools/copy-grep-guard.sh
  ```
- [ ] Output: `copy-grep-guard: OK (scanned N file(s))`. The chip
  widget's `premium`-bearing lines are pre-allowlisted in
  `tools/copy-grep-allowlist.txt` (4 entries under the
  pos-6b heading).

## Out of scope

- Mounting on calendar share sheet, future social-video import
  landing, or any other limit-shaped surface — those land in their
  own epic's stories. The widget exists; later epics import it.
- Animation / dismissibility — the chip is a passive affordance, not
  a tutorial card.
