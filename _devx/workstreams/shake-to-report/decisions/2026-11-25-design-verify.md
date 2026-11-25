---
gate: CONCERNS
status_reason: 'G-2 is ⚠️ partial (self-judged by the authoring session (no subagent tool). Mechanism and its physics are specified, but whether 2 g / 4 reversals hits 9 of 10 real shakes with 0 kitchen prompts is unproven until E-7 runs on hardware. The design says so.) G-4 is ⚠️ partial (self-judged by the authoring session (no subagent tool). Depends on arq103''s route reaching main (external). Until then admins get feedback by the route-exists check.)'
reviewer: 'devx gate coverage (design mode)'
updated: 2026-11-25
waiver: { active: false, approver: null, reason: null }
---

# Verify — _devx/workstreams/shake-to-report — 2026-11-25

## Subject

`_devx/workstreams/shake-to-report/design/agent.md` reviewed against `_devx/workstreams/shake-to-report/prd/agent.md` (design mode; workstream `f89791`).

## Coverage

| ID | Status | Where covered | Note |
|---|---|---|---|
| G-1 | ✅ | Design § Feedback launcher (trigger tag); § Rollout ring and switch; Migration plan step 7 | self-judged by the authoring session (no subagent tool). Design supplies the tag G-1 counts and the rollout that reaches non-admins; the count itself is an outcome, scored by E-1's Measure. |
| G-2 | ⚠️ | Design § Recognizer; Unresolved design questions 2; Assumptions 2 | self-judged by the authoring session (no subagent tool). Mechanism and its physics are specified, but whether 2 g / 4 reversals hits 9 of 10 real shakes with 0 kitchen prompts is unproven until E-7 runs on hardware. The design says so. |
| G-3 | ✅ | Design § Rollout ring and switch; Constraints (terraform owns env); Trade-offs (terraform over console) | self-judged by the authoring session (no subagent tool). Client refresh is 5 min (RQ5), inside the 10-minute budget; durability across deploys via terraform. |
| G-4 | ⚠️ | Design § Host (routing on tap); Migration plan step 6; Assumptions 1 | self-judged by the authoring session (no subagent tool). Depends on arq103's route reaching main (external). Until then admins get feedback by the route-exists check. |
| UC-1 | ✅ | Design § Recognizer, § Host, § Feedback launcher | self-judged by the authoring session (no subagent tool).  |
| UC-2 | ✅ | Design § Recognizer (reversal shape), § Host (4 s prompt, mute) | self-judged by the authoring session (no subagent tool).  |
| UC-3 | ✅ | Design § Host (routing on tap: push, pop returns) | self-judged by the authoring session (no subagent tool). Return-to-screen relies on arq103's pop-to-pusher (RQ12). |
| UC-4 | ✅ | Design § Host (suppression), § Modal-route tracking | self-judged by the authoring session (no subagent tool).  |
| UC-5 | ✅ | Design § Feedback launcher (Profile keeps its tile); Wrap (arq103 tile) | self-judged by the authoring session (no subagent tool). Dev-request tap path is arq103's dashboard tile. |
| UC-6 | ✅ | Design § Rollout ring and switch (device switch) | self-judged by the authoring session (no subagent tool).  |
| UC-7 | ✅ | Design § Rollout ring and switch (server, terraform) | self-judged by the authoring session (no subagent tool).  |
| UC-8 | ✅ | Design § Feedback launcher (flush at startup and resume) | self-judged by the authoring session (no subagent tool).  |
| CAP-1 | ✅ | Design § Recognizer (MotionSource), § Host (eligibility, lifecycle) | self-judged by the authoring session (no subagent tool).  |
| CAP-2 | ✅ | Design § Recognizer | self-judged by the authoring session (no subagent tool).  |
| CAP-3 | ✅ | Design § Host (the prompt) | self-judged by the authoring session (no subagent tool).  |
| CAP-4 | ✅ | Design § Host (suppression), § Modal-route tracking | self-judged by the authoring session (no subagent tool).  |
| CAP-5 | ✅ | Design § Host (routing on tap) | self-judged by the authoring session (no subagent tool).  |
| CAP-6 | ✅ | Design § Feedback launcher | self-judged by the authoring session (no subagent tool).  |
| CAP-7 | ✅ | Design § Rollout ring and switch | self-judged by the authoring session (no subagent tool).  |
| CAP-8 | ✅ | Design § Rollout ring and switch (hint) | self-judged by the authoring session (no subagent tool).  |
| FR-1 | ✅ | Design § Host (eligibility: platform, kE2EMode); § Recognizer failure handling | self-judged by the authoring session (no subagent tool). Web never subscribes; missing sensor → breadcrumb, no UI. |
| FR-2 | ✅ | Design § Recognizer (MotionSource, 20 ms); Constraints 1-2 | self-judged by the authoring session (no subagent tool).  |
| FR-3 | ✅ | Design § Recognizer (algorithm steps 1-5, ShakeTuning) | self-judged by the authoring session (no subagent tool).  |
| FR-4 | ✅ | Design § Recognizer step 5 (cooldown); § Host (two ignored → session mute) | self-judged by the authoring session (no subagent tool).  |
| FR-5 | ✅ | Design § Host (the prompt: floating SnackBar, 4 s, copy, closed reasons) | self-judged by the authoring session (no subagent tool). Screen-reader persistence is Flutter's own behavior (RQ10). |
| FR-6 | ✅ | Design § Host (suppression list); § Modal-route tracking | self-judged by the authoring session (no subagent tool). Text focus via EditableTextState ancestor (RQ7). |
| FR-7 | ✅ | Design § Host (routing on tap: isAdmin twice, route-exists check, push) | self-judged by the authoring session (no subagent tool).  |
| FR-8 | ✅ | Design § Host (eligibility inputs) | self-judged by the authoring session (no subagent tool).  |
| FR-9 | ✅ | Design § Feedback launcher | self-judged by the authoring session (no subagent tool).  |
| FR-10 | ✅ | Design § Rollout ring and switch (server, client, last value, admins default) | self-judged by the authoring session (no subagent tool).  |
| FR-11 | ✅ | Design § Rollout ring and switch (device switch) | self-judged by the authoring session (no subagent tool).  |
| FR-12 | ✅ | Design § Rollout ring and switch (hint) | self-judged by the authoring session (no subagent tool).  |
| FR-13 | ✅ | Design § Interfaces row 2; Migration plan step 1 | self-judged by the authoring session (no subagent tool). Server-first ordering is the migration plan's step 1. |
| FR-14 | ✅ | Design § Feedback launcher (Profile tile stays); Wrap (arq103 tile) | self-judged by the authoring session (no subagent tool).  |

## Extras requiring product approval

- Web feedback gains platform `web` (today none is sent on web) — Design § Feedback launcher
- Route-exists check before pushing the admin route — Design § Host (routing on tap)

## Hygiene (advisory)

- none

## Verdict detail

- G-2 is ⚠️ partial (self-judged by the authoring session (no subagent tool). Mechanism and its physics are specified, but whether 2 g / 4 reversals hits 9 of 10 real shakes with 0 kitchen prompts is unproven until E-7 runs on hardware. The design says so.)
- G-4 is ⚠️ partial (self-judged by the authoring session (no subagent tool). Depends on arq103's route reaching main (external). Until then admins get feedback by the route-exists check.)
