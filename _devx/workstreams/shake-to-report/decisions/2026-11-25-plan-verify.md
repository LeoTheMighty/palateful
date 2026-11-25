---
gate: PASS
status_reason: 'All 10 source IDs fully covered in plan mode.'
reviewer: 'devx gate coverage (plan mode)'
updated: 2026-11-25
waiver: { active: false, approver: null, reason: null }
---

# Verify — _devx/workstreams/shake-to-report — 2026-11-25

## Subject

`_devx/workstreams/shake-to-report/plan/agent.md` reviewed against `_devx/workstreams/shake-to-report/design/agent.md + _devx/workstreams/shake-to-report/expectations.md` (plan mode; workstream `f89791`).

## Coverage

| ID | Status | Where covered | Note |
|---|---|---|---|
| E-1 | ✅ | Phase 4 (T4.3, T4.5; success: E-1 wrapper exits 0, CI runs it) — artifact `_devx/workstreams/shake-to-report/evals/E-1_user_path.sh`, matches expectations.md E-1 | self-judged by the authoring session (no subagent tool). Needs Phase 2's trigger in the sheet and Phase 3's plugin; both are Phase 4 dependencies. |
| E-2 | ✅ | Phase 4 (T4.3, T4.5) — artifact `_devx/workstreams/shake-to-report/evals/E-2_everyday_motion.sh` | self-judged by the authoring session (no subagent tool). Recognizer lands in Phase 3 but only Phase 4 wires it to a prompt, which E-2's positive control needs. |
| E-3 | ✅ | Phase 4 (T4.2, T4.3, T4.5) — artifact `_devx/workstreams/shake-to-report/evals/E-3_no_interruption.sh` | self-judged by the authoring session (no subagent tool).  |
| E-4 | ✅ | Phase 6 (T6.1, T6.3) — artifact `_devx/workstreams/shake-to-report/evals/E-4_role_and_ring.sh`; external gate X-1 | self-judged by the authoring session (no subagent tool). Admin case green only once arq103's route is on main; the plan says Phase 6 merges only after X-1. |
| E-5 | ✅ | Phase 4 (T4.4) — artifact `app/test/core/shake/shake_eligibility_test.dart` | self-judged by the authoring session (no subagent tool). Motion-error half of the adapter lands in Phase 3; the eligibility test that observes it is Phase 4's. |
| E-6 | ✅ | Phase 1 (T1.3) — artifact `services/api/tests/test_shake_flags_and_trigger.py` | self-judged by the authoring session (no subagent tool).  |
| E-7 | ✅ | Phase 6 (T6.4) — artifact `_devx/workstreams/shake-to-report/evals/E-7_device_protocol.md`; external gate X-2 | self-judged by the authoring session (no subagent tool). Human, on release builds. |
| E-8 | ✅ | Phase 2 (T2.5) — artifact `app/test/features/profile/feedback_launcher_test.dart` | self-judged by the authoring session (no subagent tool).  |
| E-9 | ✅ | Phase 5 (T5.3) — artifact `app/test/features/profile/shake_settings_test.dart` | self-judged by the authoring session (no subagent tool).  |
| E-10 | ✅ | Phase 6 (T6.2) — artifact `app/test/features/profile/non_shake_paths_test.dart` | self-judged by the authoring session (no subagent tool). Dev-request half needs arq103's tile (X-1). |

## Extras requiring product approval

- none

## Execution graph

| Phase | Depends on | Parallel-safe | Changes |
|---|---|---|---|
| 1 | — | yes | services/api/src/config.py, services/api/src/api/v1/flags/get_perf_flags.py, services/api/src/api/v1/user/create_user_feedback.py, services/api/tests/test_shake_flags_and_trigger.py, terraform/modules/ecs/main.tf, terraform/environments/prod/main.tf, docs/PERFORMANCE_OPS.md |
| 2 | 1 | yes | app/lib/features/profile/services/feedback_launcher.dart, app/lib/features/profile/widgets/feedback_sheet.dart, app/lib/features/profile/profile_screen.dart, app/lib/main.dart, app/test/features/profile/feedback_launcher_test.dart |
| 3 | — | yes | app/pubspec.yaml, app/pubspec.lock, app/ios/Podfile.lock, app/ios/Runner/Info.plist, app/lib/core/shake/motion_source.dart, app/lib/core/shake/shake_recognizer.dart, app/test/core/shake/shake_recognizer_test.dart |
| 4 | 2, 3 | yes | app/lib/core/shake/shake_host.dart, app/lib/core/shake/modal_route_tracker.dart, app/lib/core/services/perf_flags_service.dart, app/lib/core/router/app_router.dart, app/lib/main.dart, app/test/core/shake/shake_eligibility_test.dart, .github/workflows/ci.yml |
| 5 | 4 | yes | app/lib/core/shake/shake_settings.dart, app/lib/core/shake/shake_host.dart, app/lib/features/profile/profile_screen.dart, app/test/features/profile/shake_settings_test.dart |
| 6 | 5 | yes | app/lib/core/shake/shake_host.dart, app/test/features/profile/non_shake_paths_test.dart, .github/workflows/ci.yml, _devx/workstreams/shake-to-report/evals/E-7_device_protocol.md |

## Verdict detail

PASS — every source ID is ✅ covered.
