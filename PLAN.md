# PLAN — Planning work in flight

Backlog of plan-spec files for `/devx-plan` to draw from. Each entry points at a `plan/plan-<hash>-<ts>-<slug>.md` file. All entries below were imported from the BMAD backlog on 2026-07-27 (`_devx/import-2026-07-27.md`); the first four are already story-split in `_bmad-output/implementation-artifacts/sprint-status.yaml`, so `/devx-plan` should emit dev specs from the pre-split stories rather than re-chunking.

Conventions: `[ ]` ready · `[/]` in-progress · `[-]` blocked · `[x]` done · `~~strikethrough~~` deleted. Status field on each entry is the source of truth; checkbox is the glanceable mirror.

---

## Feature epics (BMAD pre-split)

- [ ] `plan/plan-svi000-2026-07-27T17:20-social-video-import.md` — Social-media video import — TikTok / Instagram / YouTube via Whisper + AI extractor. Status: ready. Blocked-by: —. Ship before nutrition-auto-calc; optional INSTAGRAM_API_TOKEN / YOUTUBE_API_KEY env vars (MANUAL if adopted).
- [ ] `plan/plan-pcw000-2026-07-27T17:21-pantry-cook-with-what-you-have.md` — Pantry — cook with what you have (decrement hooks, cookable ranking, use-it-up nudge). Status: ready. Blocked-by: —. Reuses unit normalization from epic-extractor-richer-ingredients; perf budgets in scope.
- [ ] `plan/plan-rmi000-2026-07-27T17:22-recime-mass-import.md` — Recime mass-import — Chrome extension MVP with kill-switch, magic link, and contract canary. Status: ready. Blocked-by: —. Lawyer review (recime-imp-5) runs parallel but gates the public Chrome Web Store launch — human step, see spec.
- [ ] `plan/plan-nac000-2026-07-27T17:23-nutrition-auto-calc.md` — Nutrition auto-calculation — USDA-sourced macros on every recipe, free for everyone. Status: ready. Blocked-by: — (soft: after svi000). nutri-0 operator S3-snapshot decision blocks nutri-1a/1b.

## Ops / cleanup epics (placeholders — /devx-plan drafts the story split)

- [ ] `plan/plan-aoc000-2026-07-27T17:25-activity-orphan-cleanup.md` — Activity orphan cleanup — hard DELETE of soft-archived import_* user_activity rows. Status: ready. Blocked-by: — (scheduling gate passed: activity-full-history shipped). Soak-period verification is a pre-flight AC before the irreversible DELETE.
- [ ] `plan/plan-rib000-2026-07-27T17:24-recipe-images-bucket-migration.md` — Recipe images bucket migration — dedicated palateful-recipe-photos bucket. Status: ready. Blocked-by: —. Placeholder scope; flesh out when parser-inputs storage entanglement becomes a real pain.
