---
hash: perfattr1
type: dev
created: 2026-09-28T02:30:00-06:00
title: Shell-branch route_paint data was attributed to one Navigator, not six
from: dev/dev-cla4-route-paint-observer.md
status: ready
owner: null
branch: null
---

## Goal

Decide what the `route_paint` telemetry collected between `cla-4` and the
fix in PR #122 is worth, and whether anything already concluded from it
needs revisiting. **This spec exists so the caveat is findable by someone
explaining an anomaly in that data months from now** — a note in the PR of
the fix would not be.

## What happened

[M] `app_router.dart` shared **one** `PerfNavigatorObserver` instance
across **six** Navigators: the root plus five
`StatefulShellRoute.indexedStack` branches. A Flutter `NavigatorObserver`
may attach to exactly one Navigator, and `HeroControllerScope` asserts
`observer.navigator == null` when installing it.

**In debug it threw** — 0e hit the red error screen entering a shell
branch. **In release the assertion is stripped**, so production never
threw: the `navigator` field was silently overwritten by the last attach
and events were attributed to whichever Navigator attached last.

So the defect's entire production lifetime was silent, and the data looks
complete.

## What is and isn't suspect

- **Root-route events** are probably fine — the root attaches first and
  the overwrite affects the observer's own `navigator` field, not the
  route path, which is resolved separately through
  `_routePathResolver()` → `_router?.state.fullPath`.
- **Shell-branch events** are the question. `route` came from the
  router's current full path, so the *label* may well be right even
  though the attachment was wrong.

**This spec deliberately does not claim the data is wrong.** [I] The
plausible outcome is that the labels are mostly correct and the defect
cost coverage rather than accuracy — pushes inside a branch may have gone
unobserved. Establishing which requires reading
`client_latency_ingest` rows by route and looking for branch routes that
are absent or thin relative to traffic, and that needs someone who knows
what the baseline should look like.

## Acceptance criteria

- [ ] A verdict on the pre-fix data: usable as-is, usable with a caveat,
      or discard before a stated date. **State which, with the query that
      supports it** — "probably fine" recorded without evidence is how a
      caveat becomes folklore.
- [ ] If any perf conclusion, budget or alarm threshold was derived from
      shell-branch `route_paint` data in that window, name it and say
      whether it survives.
- [ ] The verdict is recorded where the data is consumed (a note next to
      the dashboard/query, not only here), so the next reader of an
      anomaly finds it without knowing this spec exists.

## Technical notes

- The window opens at `cla-4`'s merge and closes at PR #122's deploy.
- Post-fix, each Navigator has its own observer and they all enqueue to
  the same `ClientLatencyIngest`, so comparisons across the boundary are
  between "one attach" and "six attaches" rather than between different
  emitters.
- `reportTabSwap` was never affected: it does not depend on Navigator
  attachment, and tab swaps always carried `duration_ms = 0`.

## Status log

- 2026-09-28T02:30 — filed by palateful-98 alongside PR #122 at 41's
  direction: a caveat about historical data that lives only in the fix's
  PR body will not be found by whoever later tries to explain an anomaly
  in it. Not assigned; the question of what a correct baseline looks like
  belongs with whoever owns perf.
