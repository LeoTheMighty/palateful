---
hash: hmpseed
type: test
created: 2026-07-27T19:05:00-06:00
title: hmp-5 e2e flow self-skips — nothing seeds recipes into the e2e test DB
from: dev/dev-bqa102-2026-07-27T11:40-e2e-revival-one-command.md
status: ready
---

## Goal

`app/integration_test/08_meals_home_promotion_test.dart` actually exercises the
home long-press → Create Meal → meal-appears-in-grid flow when the suite runs,
instead of skipping itself.

## The gap

bqa102 renamed the hmp-5 flow into the `0*` glob, so it is now part of the
8-flow population. But the flow opens with:

```dart
if (find.byType(RecipeCard).evaluate().length < 2) {
  markTestSkipped('Fewer than 2 recipes on home — fixture backend must pre-seed.');
  return;
}
```

and the e2e stack has no seed step — `docker-compose.e2e.yml` points the API at
the freshly-migrated `test` database, and the auth bypass lazy-creates only the
`e2e@palateful.test` user (`find_or_create_by`, no recipes). So the home grid is
empty, the guard trips, and the flow reports as passed-by-skip.

This satisfies bqa102's AC as written (`git mv`, no content change) and keeps
the suite at 8/8, but the contract-drift protection the flow was written for —
`CreateMealSheet`'s submission payload, per
`_bmad-output/planning-artifacts/epic-meals-home-promotion.md` — is not
actually being exercised by the suite.

## Acceptance criteria

- [ ] The e2e stack seeds ≥2 recipes for the e2e user before flows run (a seed
      SQL applied by `migrator-test`, or an idempotent seed step in
      `services/e2e/scripts/e2e_lifecycle.sh` after the health gate).
- [ ] `08_meals_home_promotion_test.dart` reaches its assertions rather than
      `markTestSkipped` — verified by the flow failing when `CreateMealSheet`'s
      payload is deliberately broken.
- [ ] Seeding is idempotent across consecutive runs (the E-2 eval runs the
      suite twice back-to-back against the same volume).

## Technical notes

- Blocked in practice by `debug/debug-e2edwds-*` — no flow reaches its body
  until the dwds/Chrome attach failure is resolved.
- Prefer seeding through the API over raw SQL if it stays cheap: it keeps the
  fixture honest about the real create path. Raw SQL in `migrator-test` is the
  simpler option and matches how the `test` DB is already provisioned.
- Watch the interaction with the two-consecutive-runs bar: a seed that appends
  rather than upserts will drift the home grid between run 1 and run 2.
