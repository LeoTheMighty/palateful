---
gate: PASS
status_reason: 'Shake-to-report is its own workstream, depending on admin-request-intake only through one route path; combining it would reopen four passed gates for an audience that PRD names as its anti-persona.'
reviewer: '/devx-plan prd stage (authoring session)'
updated: 2026-11-25
waiver: { active: false, approver: null, reason: null }
---

# Decision — shake-to-report — 2026-11-25

## Subject

Whether shake-to-report belongs inside `admin-request-intake` (1e84ad,
four gates passed, `--verify` PASS) or stands alone. The orchestrator made
the call "separate" and asked for it to be checked, not inherited. Checked
against 1e84ad's PRD, plan and arq103's code on `feat/dev-arq103`
(`b9bf7104`).

## Coverage

| ID | Status | Where covered | Note |
|---|---|---|---|
| Audience | ✅ | 1e84ad PRD § Users | 1e84ad's anti-persona is "non-admin users"; shake's primary user is a non-admin |
| Surface | ✅ | 1e84ad PRD FR-14, arq103 | 1e84ad owns one admin screen; shake is app-wide, on every route |
| Dependency | ✅ | this PRD FR-2 | shake adds a native plugin, an `Info.plist` key and Android-toolchain constraints; 1e84ad adds none |
| Coupling | ✅ | this PRD FR-7 | the only contact is the path `/admin/dev-requests/new` (`AdminDevRequestNewScreen.routePath`), which arq103 made route-only on purpose |
| Backend | ✅ | this PRD FR-10, FR-13 | shake touches `/v1/flags/perf` and `user_feedbacks` context; 1e84ad touches neither and lists "reusing `user_feedbacks`" as a non-goal |

## Extras requiring product approval

- None. Nothing here edits a file 1e84ad's plan lists.

## Verdict detail

**Separate is right.** Folding it in would run `devx revise 1e84ad
--touched prd`, which resets all four gates and the RED lock of a
workstream with five green P0s, to add an audience that PRD excludes by
name. The two share one string: a route path. A shared string is a
contract, not a reason to share a plan.

**What would change this.** If the dev-request form had needed a non-route
entry (constructor arguments, a callback into the shake host), the two
would share code and the case for one workstream would be real. arq103
removed that by design. If they ever do converge, `devx workstream combine`
(D-18) absorbs this one later; nothing here is one-way.

**What the dependency costs.** The admin half of shake (plan phase for
FR-7's admin branch) cannot merge until arq103's route is on `main`, and
arq103 is held for 1e84ad's own external gate (its bridge). So the user
path ships first and does not wait on it.
