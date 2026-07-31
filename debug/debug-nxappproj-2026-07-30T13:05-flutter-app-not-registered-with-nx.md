---
hash: nxappproj
type: debug
created: 2026-07-30T13:05:00-06:00
title: Flutter app is not an nx project — `npx nx run app:test` does not exist
from: dev/dev-fltup1-2026-07-30T09:00-align-local-flutter-to-ci-pin.md
status: in-progress
owner: /devx-loop-2026-07-30T17-52-24-754-38586
---

## Goal

`npx nx run app:test` (and `app:analyze` / `app:build-web`) work, so the
Flutter app is reachable through the same interface as every other project
in the monorepo. Today `app` is invisible to nx.

CLAUDE.md opens with "**ALWAYS** use `npx nx` commands whenever possible" —
the Flutter app is the one surface where that is not possible, and specs
keep being written against nx commands for it that cannot run.

## Acceptance criteria

- [ ] Repro exists (below).
- [ ] Root cause documented: why `app` has no project config while the 11
      Python/infra projects do.
- [ ] `npx nx show projects` lists `app`.
- [ ] `npx nx run app:test` runs the Flutter suite and propagates its exit
      code (green today: 1564 passed).
- [ ] Targets match what `devx.config.yaml → projects[name=app]` already
      declares (`test: flutter test`, cwd `app`) so devx's gate runner and
      the nx target cannot drift apart.
- [ ] Decide and record whether `analyze` / `build-web` targets are added
      now or deliberately deferred.

## Repro

```bash
$ npx nx run app:test
 NX   Cannot find project 'app'

$ npx nx show projects        # 11 projects, no 'app'
ingredient-scraper test-helper migrator agent parser utils worker eval api e2e terraform

$ ls app/project.json
ls: app/project.json: No such file or directory
```

Fails identically from the repo root and from a worktree, so it is a
missing project config, not a resolution or `node_modules` issue.

## Evidence (fltup1, 2026-07-30)

`dev/dev-fltup1` AC #2 was written as "`npx nx run app:test` (`flutter
test`) passes locally on 3.41.7". The nx form exits 1 with `Cannot find
project 'app'` — no suite is run, so a careless reading of that exit code
would look like a failing test suite after a toolchain upgrade when nothing
of the sort happened. The gate was satisfied via `flutter test` in `app/`
(the AC's own parenthetical, and what `devx.config.yaml` declares).

Note `services/e2e/project.json` *does* define Flutter-invoking targets
(`test-single`, `test-headless` run `flutter drive` / `flutter test` with
`cwd: {workspaceRoot}/app`), so the app is driven through nx today only
indirectly, under the `e2e` project. That is probably why the gap went
unnoticed.

## Technical notes

- Smallest fix is an `app/project.json` with `projectType: application`
  and a `test` target running `flutter test` with `cwd: {workspaceRoot}/app`
  — mirroring the shape `services/e2e/project.json` already uses.
- Keep the target command identical to `devx.config.yaml → projects[app]`;
  two sources of truth for "how do I test the app" is how this drifts again.
- Worth checking whether CI (`ci.yml` flutter-test job) invokes `flutter
  test` directly; if so, consider routing it through nx in the same change
  so all three callers agree.

## Status log

- 2026-07-30T13:05 — filed from `dev/dev-fltup1` AC #2, which named an nx
  command that does not exist in this repo. Recorded rather than silently
  substituting the working command.
- 2026-07-30T12:16:23-06:00 — claimed by /devx in session /devx-loop-2026-07-30T17-52-24-754-38586
- 2026-07-30T18:25:17.265Z — loop iteration 1: Registered the Flutter app as an nx project with test/analyze/build-web targets matching devx.config.yaml and ci.yml, verified end-to-end including exit-code propagation.
  - Change: Added app/project.json (projectType: application, cwd {projectRoot}) with test, analyze, and build-web targets whose commands are byte-identical to devx.config.yaml projects[app] and the ci.yml flutter-test/deploy-web steps
  - Change: Documented the root cause and the nx target list in app/README.md, including why an `install` target was deliberately omitted (it would silently join `nx run-many -t install`)
  - Change: Recorded in ci.yml the decision to keep CI on bare flutter commands rather than routing through nx, with cross-references so the three callers can't drift
  - Learning: nx.json in this repo registers no `plugins` at all, so nx does zero project inference — every project is discovered solely by a hand-written project.json. Any new non-Python surface will be invisible to nx by default, same as app/ was.
  - Learning: The ci.yml flutter-test job installs only Flutter (no setup-node, no yarn install), so routing it through `npx nx` is not a free swap — it would add Node setup to every run for no dedup benefit.
  - Learning: The suite is at 1567 passing tests, not the 1564 the spec's repro block recorded.
  - Learning: tools/image-network-check.sh takes >2 min to run locally (timed out in a guard sweep); budget for it separately rather than batching it with the fast grep guards.
- 2026-07-31 — fix-forward during merge sweep. Registering `app` as an nx project made
  `nx affected -t test` select it in the **Python** `test` job, which has no Flutter
  toolchain (only `flutter-test` runs `subosito/flutter-action`). CI failed with
  `/bin/sh: 1: flutter: not found` — a real defect introduced by this story, not
  inherited red. Fixed by adding `app` to that job's `--exclude` list.
  - Verified: `nx show projects --affected -t test --exclude=e2e` lists `app`;
    `--exclude=e2e,app` lists nothing. The Dart suite still runs in `flutter-test`.
  - Rejected: routing `flutter-test` through `npx nx run app:test` so the registration
    is exercised in CI. That job does `actions/checkout` + `flutter-action` only — it
    never installs `node_modules`, so `npx` would fetch an unpinned nx from the registry
    without workspace plugins. The nx targets remain a local-developer affordance, which
    is what the spec asked for.
