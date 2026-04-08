# Epic: Recipe Vibes (V1 — Vibes Lite)

## Overview

Add a feeling-based categorization system to Palateful recipes. Every recipe gets 1-2 "vibes" — Light & Fresh, Hearty, Comfort, Energizing, Carb-Load, Indulgent, Warming — assigned automatically by AI during the existing extraction/creation flow at zero additional cost. Users can browse by vibe, override assignments, and see colored vibe pills on every recipe card.

## Design Principles (from Party Mode discussion)

1. **No hierarchy** — "Indulgent" is not worse than "Light & Fresh." A well-lived week has variety
2. **No scores, no grades, no numbers** — vibes are qualitative, not quantitative
3. **Zero additional AI cost** — vibe assignment is embedded in existing extraction prompts
4. **Opt-in engagement** — vibes appear automatically but users never have to interact with them
5. **Food-focused, not person-focused** — "This recipe is Comfort" not "You ate too much Comfort"
6. **Colored dot + label** — simple pill design, no custom icon assets for V1

## Vibe Categories

| Vibe | Color | Hex |
|------|-------|-----|
| Light & Fresh | Soft green | #A8D8A8 |
| Hearty & Filling | Warm amber | #D4A853 |
| Comfort | Soft terracotta | #CB8B73 |
| Energizing | Bright sage | #8FA882 |
| Carb-Load | Golden wheat | #C8A96E |
| Indulgent | Deep plum | #8B6B8B |
| Warming | Deep cinnamon | #A0522D |

## Story Map

| Story | Title | Est. Effort | Dependencies |
|-------|-------|-------------|--------------|
| 1 | Backend — Vibe Columns, Embedded AI Assignment, Backfill | 2–3 days | None |
| 2 | API — Vibe Fields, Vibe Filter, Import Pipeline Integration | 1–2 days | Story 1 |
| 3 | Flutter — VibeChip Widget, Recipe Card + Detail Integration | 1–2 days | Story 2 |
| 4 | Flutter — Vibe Filter Bar + User Override | 1–2 days | Story 3 |

**Total estimated effort: 5–9 days**
**All stories are sequential: 1 → 2 → 3 → 4**

## Future (V2)

- Weekly vibe strip on calendar
- Weekly summary card ("Your week was mostly cozy with a fresh start")
- Vibe-aware AI chat suggestions
- "Plan by vibe" in meal planning
- Per-user vibe overrides in shared recipe books
