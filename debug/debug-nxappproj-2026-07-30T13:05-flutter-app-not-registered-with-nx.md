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
