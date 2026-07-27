---
gate: PASS
status_reason: 'Every runnable expectation observed RED for the right reason (6 run(s), 2 deferred).'
reviewer: 'devx gate evals'
updated: 2026-07-27
waiver: { active: false, approver: null, reason: null }
---

# RED report — _devx/workstreams/rotation-self-heal — 2026-07-27

## Runs

### E-1: Deploy path on main completes (P0)

- **Artifact**: app/test/features/activity/imports_tab_test.dart
- **Command**: `flutter test test/features/activity/imports_tab_test.dart`
- **Exit code**: 1
- **Failure quote**:
  ```
  This was caught by the test expectation on the following line:
    file:///Users/leonidbelyi/personal/palateful/app/test/features/activity/imports_tab_test.dart line 542
  The test description was:
    buckets by item.status — items still render when parent job.status differs
  ════════════════════════════════════════════════════════════════════════════════════════════════════
  00:02 +4 -3: buckets by item.status — items still render when parent job.status differs [E]                                                                                                            
    Test failed. See exception logs above.
    The test description was: buckets by item.status — items still render when parent job.status differs
  To run this test again: /Users/leonidbelyi/personal/flutter/bin/cache/dart-sdk/bin/dart test /Users/leonidbelyi/personal/palateful/app/test/features/activity/imports_tab_test.dart -p vm --plain-name 'buckets by item.status — items still render when parent job.status differs'
  00:02 +4 -3: yellow row taps navigate to review screen                                                                                                                                                 00:02 +5 -3: yellow row taps navigate to review screen                                                                                                                                                 00:02 +5 -3: (tearDownAll)                                                                                                                                                                             00:02 +5 -3: Some tests failed.                                                                                                                                                                        
  ```
- **RED verdict**: right-reason

### E-2: Stale credentials fail the health check (P0)

- **Artifact**: services/api/tests/test_health.py
- **Command**: `poetry run pytest tests/test_health.py`
- **Exit code**: 1
- **Failure quote**:
  ```
  ERROR tests/test_health.py::test_non_auth_failure_returns_200[unclassified-exception]
  ERROR tests/test_health.py::test_non_auth_200_body_does_not_claim_credentials_are_bad[timeout]
  ERROR tests/test_health.py::test_non_auth_200_body_does_not_claim_credentials_are_bad[operational-error-without-sqlstate]
  ERROR tests/test_health.py::test_non_auth_200_body_does_not_claim_credentials_are_bad[dns-resolution-failure]
  ERROR tests/test_health.py::test_non_auth_200_body_does_not_claim_credentials_are_bad[unclassified-exception]
  ERROR tests/test_health.py::test_burst_of_probes_opens_one_connection - Impor...
  ERROR tests/test_health.py::test_concurrent_misses_coalesce_onto_one_connection
  ERROR tests/test_health.py::test_interleaved_30s_and_60s_schedule_holds_the_budget
  ERROR tests/test_health.py::test_unset_database_url_is_ok_not_a_failure - Imp...
  ============= 1 failed, 1 passed, 13 warnings, 17 errors in 10.84s =============
  ```
- **RED verdict**: right-reason

### E-3: Transient database failures do not fail the health check (P0)

- **Artifact**: services/api/tests/test_health.py
- **Command**: `poetry run pytest tests/test_health.py`
- **Exit code**: 1
- **Failure quote**:
  ```
  ERROR tests/test_health.py::test_non_auth_failure_returns_200[unclassified-exception]
  ERROR tests/test_health.py::test_non_auth_200_body_does_not_claim_credentials_are_bad[timeout]
  ERROR tests/test_health.py::test_non_auth_200_body_does_not_claim_credentials_are_bad[operational-error-without-sqlstate]
  ERROR tests/test_health.py::test_non_auth_200_body_does_not_claim_credentials_are_bad[dns-resolution-failure]
  ERROR tests/test_health.py::test_non_auth_200_body_does_not_claim_credentials_are_bad[unclassified-exception]
  ERROR tests/test_health.py::test_burst_of_probes_opens_one_connection - Impor...
  ERROR tests/test_health.py::test_concurrent_misses_coalesce_onto_one_connection
  ERROR tests/test_health.py::test_interleaved_30s_and_60s_schedule_holds_the_budget
  ERROR tests/test_health.py::test_unset_database_url_is_ok_not_a_failure - Imp...
  ============= 1 failed, 1 passed, 13 warnings, 17 errors in 8.94s ==============
  ```
- **RED verdict**: right-reason

### E-4: Fresh-connection probe is rate-limited (P1)

- **Artifact**: services/api/tests/test_health.py
- **Command**: `poetry run pytest tests/test_health.py`
- **Exit code**: 1
- **Failure quote**:
  ```
  ERROR tests/test_health.py::test_non_auth_failure_returns_200[unclassified-exception]
  ERROR tests/test_health.py::test_non_auth_200_body_does_not_claim_credentials_are_bad[timeout]
  ERROR tests/test_health.py::test_non_auth_200_body_does_not_claim_credentials_are_bad[operational-error-without-sqlstate]
  ERROR tests/test_health.py::test_non_auth_200_body_does_not_claim_credentials_are_bad[dns-resolution-failure]
  ERROR tests/test_health.py::test_non_auth_200_body_does_not_claim_credentials_are_bad[unclassified-exception]
  ERROR tests/test_health.py::test_burst_of_probes_opens_one_connection - Impor...
  ERROR tests/test_health.py::test_concurrent_misses_coalesce_onto_one_connection
  ERROR tests/test_health.py::test_interleaved_30s_and_60s_schedule_holds_the_budget
  ERROR tests/test_health.py::test_unset_database_url_is_ok_not_a_failure - Imp...
  ============= 1 failed, 1 passed, 13 warnings, 17 errors in 8.72s ==============
  ```
- **RED verdict**: right-reason

### E-5: Rotation event redeploys both services (P0)

- **Artifact**: libraries/utils/test/test_rotation_redeploy_handler.py
- **Command**: `poetry run pytest test/test_rotation_redeploy_handler.py`
- **Exit code**: 1
- **Failure quote**:
  ```
  ERROR test/test_rotation_redeploy_handler.py::test_matching_secret_forces_one_deployment_per_service[cloudtrail-rotation-succeeded]
  ERROR test/test_rotation_redeploy_handler.py::test_non_matching_secret_redeploys_nothing[secret-label-updated]
  ERROR test/test_rotation_redeploy_handler.py::test_non_matching_secret_redeploys_nothing[cloudtrail-rotation-succeeded]
  ERROR test/test_rotation_redeploy_handler.py::test_event_without_any_secret_identifier_redeploys_nothing
  ERROR test/test_rotation_redeploy_handler.py::test_partial_failure_names_the_failing_service_and_logs_it
  ERROR test/test_rotation_redeploy_handler.py::test_first_service_failure_does_not_skip_the_second
  ERROR test/test_rotation_redeploy_handler.py::test_missing_required_env_raises[ECS_CLUSTER]
  ERROR test/test_rotation_redeploy_handler.py::test_missing_required_env_raises[ECS_SERVICES]
  ERROR test/test_rotation_redeploy_handler.py::test_missing_required_env_raises[WATCHED_SECRET_ARN]
  ========================= 2 failed, 10 errors in 2.63s =========================
  ```
- **RED verdict**: right-reason

### E-6: Password rotation needs no restart (P0)

- **Artifact**: libraries/utils/test/test_db_credential_provider.py
- **Command**: `poetry run pytest test/test_db_credential_provider.py`
- **Exit code**: 1
- **Failure quote**:
  ```
  ERROR test/test_db_credential_provider.py::test_first_resolution_may_fall_back_to_db_password_env
  ERROR test/test_db_credential_provider.py::test_resolve_password_provider_returns_none_when_arn_unset
  ERROR test/test_db_credential_provider.py::test_register_is_a_total_noop_when_arn_unset
  ERROR test/test_db_credential_provider.py::test_register_attaches_exactly_one_listener_when_arn_set
  ERROR test/test_db_credential_provider.py::test_auth_failure_triggers_exactly_one_reresolution_and_one_retry
  ERROR test/test_db_credential_provider.py::test_second_consecutive_auth_failure_propagates
  ERROR test/test_db_credential_provider.py::test_non_auth_exception_propagates_with_zero_reresolutions
  ERROR test/test_db_credential_provider.py::test_secrets_manager_outage_on_retry_does_not_represent_stale_password
  ERROR test/test_db_credential_provider.py::test_real_engine_modules_are_inert_when_arn_unset
  ========================= 3 failed, 13 errors in 1.76s =========================
  ```
- **RED verdict**: right-reason

## Deferred stubs

- E-7: not-run (deferred: human) (P2)
- E-8: not-run (deferred: human) (P1)
