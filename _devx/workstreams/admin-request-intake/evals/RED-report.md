---
gate: PASS
status_reason: 'Every runnable expectation observed RED for the right reason (5 run(s), 9 deferred).'
reviewer: 'devx gate evals'
updated: 2026-11-24
waiver: { active: false, approver: null, reason: null }
---

# RED report — _devx/workstreams/admin-request-intake — 2026-11-24

## Runs

### E-1: A request travels the whole path (P0)

- **Artifact**: _devx/workstreams/admin-request-intake/evals/E-1_full_path.sh
- **Command**: `bash run-eval.sh admin-request-intake/evals/E-1_full_path.sh`
- **Exit code**: 1
- **Failure quote**:
  ```
  [31m[1m_____________________ test_request_travels_the_whole_path ______________________[0m
  RED: no `dev_requests` table in the model metadata — Phase 1 (PRD FR-1) is not built
  - generated xml file: /var/folders/y_/sc23spkj46318zzjqj4fw0gc0000gn/T/devreq-eval-ntkIJU -
  [36m[1m=========================== short test summary info ============================[0m
  [31mFAILED[0m tests/test_dev_requests_full_path.py::[1mtest_prod_script_forwards_arguments_and_stays_compatible[0m - AssertionError: RED: bin/prod-script did not forward its arguments intact (...
  [31mFAILED[0m tests/test_dev_requests_full_path.py::[1mtest_scripts_import_only_the_allowlist[0m - Failed: RED: services/api/scripts/dev_requests_read.py does not exist — Pha...
  [31mFAILED[0m tests/test_dev_requests_full_path.py::[1mtest_request_travels_the_whole_path[0m - Failed: RED: no `dev_requests` table in the model metadata — Phase 1 (PRD F...
  [31m[31m[1m3 failed[0m[31m in 2.12s[0m[0m
  EVAL E-1: tests=3 passed=0 failed=3 errors=0 skipped=0 pytest_exit=1
  EVAL-RED E-1: 3 failing: ['test_prod_script_forwards_arguments_and_stays_compatible', 'test_scripts_import_only_the_allowlist', 'test_request_travels_the_whole_path']
  ```
- **RED verdict**: right-reason

### E-2: No submitter text before adoption (P0)

- **Artifact**: _devx/workstreams/admin-request-intake/evals/E-2_containment_canary.sh
- **Command**: `bash run-eval.sh admin-request-intake/evals/E-2_containment_canary.sh`
- **Exit code**: 1
- **Failure quote**:
  ```
  RED: no `dev_requests` table in the model metadata — Phase 1 (PRD FR-1) is not built
  [31m[1m____________________ test_adopt_returns_all_three_canaries _____________________[0m
  RED: no `dev_requests` table in the model metadata — Phase 1 (PRD FR-1) is not built
  - generated xml file: /var/folders/y_/sc23spkj46318zzjqj4fw0gc0000gn/T/devreq-eval-31vtbH -
  [36m[1m=========================== short test summary info ============================[0m
  [31mFAILED[0m tests/test_dev_requests_containment.py::[1mtest_pre_adoption_calls_carry_no_submitter_text[0m - Failed: RED: no `dev_requests` table in the model metadata — Phase 1 (PRD F...
  [31mFAILED[0m tests/test_dev_requests_containment.py::[1mtest_adopt_returns_all_three_canaries[0m - Failed: RED: no `dev_requests` table in the model metadata — Phase 1 (PRD F...
  [31m[31m[1m2 failed[0m, [32m1 passed[0m[31m in 0.55s[0m[0m
  EVAL E-2: tests=3 passed=1 failed=2 errors=0 skipped=0 pytest_exit=1
  EVAL-RED E-2: 2 failing: ['test_pre_adoption_calls_carry_no_submitter_text', 'test_adopt_returns_all_three_canaries']
  ```
- **RED verdict**: right-reason

### E-3: Only the operator can adopt (P0)

- **Artifact**: _devx/workstreams/admin-request-intake/evals/E-3_operator_only.sh
- **Command**: `bash run-eval.sh admin-request-intake/evals/E-3_operator_only.sh`
- **Exit code**: 1
- **Failure quote**:
  ```
  [36m[1m=========================== short test summary info ============================[0m
  [31mFAILED[0m tests/test_dev_requests_operator_only.py::[1mtest_route_scan_can_see_and_finds_the_create_route[0m - AssertionError: RED: POST /v1/admin/dev-requests is not routed — Phase 1 (P...
  [31mFAILED[0m tests/test_dev_requests_operator_only.py::[1mtest_admin_create_stores_submitted_for_the_caller[0m - Failed: RED: no `dev_requests` table in the model metadata — Phase 1 (PRD F...
  [31mFAILED[0m tests/test_dev_requests_operator_only.py::[1mtest_non_admin_gets_403_and_no_row[0m - Failed: RED: no `dev_requests` table in the model metadata — Phase 1 (PRD F...
  [31mFAILED[0m tests/test_dev_requests_operator_only.py::[1mtest_smuggled_fields_are_rejected[status][0m - Failed: RED: no `dev_requests` table in the model metadata — Phase 1 (PRD F...
  [31mFAILED[0m tests/test_dev_requests_operator_only.py::[1mtest_smuggled_fields_are_rejected[submitter_id][0m - Failed: RED: no `dev_requests` table in the model metadata — Phase 1 (PRD F...
  [31mFAILED[0m tests/test_dev_requests_operator_only.py::[1mtest_smuggled_fields_are_rejected[workstream][0m - Failed: RED: no `dev_requests` table in the model metadata — Phase 1 (PRD F...
  [31m[31m[1m6 failed[0m, [32m2 passed[0m[31m in 5.42s[0m[0m
  EVAL E-3: tests=8 passed=2 failed=6 errors=0 skipped=0 pytest_exit=1
  EVAL-RED E-3: 6 failing: ['test_route_scan_can_see_and_finds_the_create_route', 'test_admin_create_stores_submitted_for_the_caller', 'test_non_admin_gets_403_and_no_row', 'test_smuggled_fields_are_rejected[status]', 'test_smuggled_fields_are_rejected[submitter_id]', 'test_smuggled_fields_are_rejected[workstream]']
  ```
- **RED verdict**: right-reason

### E-4: Transitions are validated, compare-and-set and audited (P0)

- **Artifact**: _devx/workstreams/admin-request-intake/evals/E-4_transitions.sh
- **Command**: `bash run-eval.sh admin-request-intake/evals/E-4_transitions.sh`
- **Exit code**: 1
- **Failure quote**:
  ```
  [31mFAILED[0m tests/test_dev_requests_transitions.py::[1mtest_bad_arguments_are_refused[bad-status][0m - Failed: RED: no `dev_requests` table in the model metadata — Phase 1 (PRD F...
  [31mFAILED[0m tests/test_dev_requests_transitions.py::[1mtest_bad_arguments_are_refused[free-text-reason][0m - Failed: RED: no `dev_requests` table in the model metadata — Phase 1 (PRD F...
  [31mFAILED[0m tests/test_dev_requests_transitions.py::[1mtest_bad_arguments_are_refused[bad-sha][0m - Failed: RED: no `dev_requests` table in the model metadata — Phase 1 (PRD F...
  [31mFAILED[0m tests/test_dev_requests_transitions.py::[1mtest_wrong_sha_is_refused[0m - Failed: RED: no `dev_requests` table in the model metadata — Phase 1 (PRD F...
  [31mFAILED[0m tests/test_dev_requests_transitions.py::[1mtest_adopting_for_a_revoked_submitter_is_refused[no-longer-admin][0m - Failed: RED: no `dev_requests` table in the model metadata — Phase 1 (PRD F...
  [31mFAILED[0m tests/test_dev_requests_transitions.py::[1mtest_adopting_for_a_revoked_submitter_is_refused[submitter-deleted][0m - Failed: RED: no `dev_requests` table in the model metadata — Phase 1 (PRD F...
  [31mFAILED[0m tests/test_dev_requests_transitions.py::[1mtest_unknown_id_is_not_found[0m - Failed: RED: no `dev_requests` table in the model metadata — Phase 1 (PRD F...
  [31m[31m[1m23 failed[0m[31m in 0.77s[0m[0m
  EVAL E-4: tests=23 passed=0 failed=23 errors=0 skipped=0 pytest_exit=1
  EVAL-RED E-4: 23 failing: ['test_slice_edges_apply_with_one_audit_row[submitted->received]', 'test_slice_edges_apply_with_one_audit_row[submitted->accepted]', 'test_slice_edges_apply_with_one_audit_row[received->accepted]', 'test_slice_edges_apply_with_one_audit_row[submitted->declined]', 'test_slice_edges_apply_with_one_audit_row[received->declined]', 'test_slice_edges_apply_with_one_audit_row[submitted->withdrawn]', 'test_slice_edges_apply_with_one_audit_row[received->withdrawn]', 'test_never_legal_edges_are_refused[received->submitted]', 'test_never_legal_edges_are_refused[accepted->received]', 'test_never_legal_edges_are_refused[declined->accepted]', 'test_never_legal_edges_are_refused[withdrawn->received]', 'test_never_legal_edges_are_refused[submitted->shipped]', 'test_never_legal_edges_are_refused[stopped->building]', 'test_stale_from_is_a_conflict', 'test_a_repeat_is_a_no_op', 'test_bad_arguments_are_refused[bad-id]', 'test_bad_arguments_are_refused[bad-status]', 'test_bad_arguments_are_refused[free-text-reason]', 'test_bad_arguments_are_refused[bad-sha]', 'test_wrong_sha_is_refused', 'test_adopting_for_a_revoked_submitter_is_refused[no-longer-admin]', 'test_adopting_for_a_revoked_submitter_is_refused[submitter-deleted]', 'test_unknown_id_is_not_found']
  ```
- **RED verdict**: right-reason

### E-5: What Leo reads is what an agent reads (P0)

- **Artifact**: _devx/workstreams/admin-request-intake/evals/E-5_normalization.sh
- **Command**: `bash run-eval.sh admin-request-intake/evals/E-5_normalization.sh`
- **Exit code**: 1
- **Failure quote**:
  ```
  [31mFAILED[0m tests/test_dev_requests_normalization.py::[1mtest_stores_normalized_text_and_its_hash[keeps-newline-and-tab][0m - Failed: RED: no `dev_requests` table in the model metadata — Phase 1 (PRD F...
  [31mFAILED[0m tests/test_dev_requests_normalization.py::[1mtest_stores_normalized_text_and_its_hash[bom-mid-text][0m - Failed: RED: no `dev_requests` table in the model metadata — Phase 1 (PRD F...
  [31mFAILED[0m tests/test_dev_requests_normalization.py::[1mtest_stores_normalized_text_and_its_hash[done-when-normalized][0m - Failed: RED: no `dev_requests` table in the model metadata — Phase 1 (PRD F...
  [31mFAILED[0m tests/test_dev_requests_normalization.py::[1mtest_rejects_over_limit_and_blank_fields[title-over-120][0m - Failed: RED: no `dev_requests` table in the model metadata — Phase 1 (PRD F...
  [31mFAILED[0m tests/test_dev_requests_normalization.py::[1mtest_rejects_over_limit_and_blank_fields[body-over-4000][0m - Failed: RED: no `dev_requests` table in the model metadata — Phase 1 (PRD F...
  [31mFAILED[0m tests/test_dev_requests_normalization.py::[1mtest_rejects_over_limit_and_blank_fields[done-when-over-1000][0m - Failed: RED: no `dev_requests` table in the model metadata — Phase 1 (PRD F...
  [31mFAILED[0m tests/test_dev_requests_normalization.py::[1mtest_rejects_over_limit_and_blank_fields[blank-after-normalization][0m - Failed: RED: no `dev_requests` table in the model metadata — Phase 1 (PRD F...
  [31m[31m[1m12 failed[0m[31m in 0.90s[0m[0m
  EVAL E-5: tests=12 passed=0 failed=12 errors=0 skipped=0 pytest_exit=1
  EVAL-RED E-5: 12 failing: ['test_stores_normalized_text_and_its_hash[zero-width-space]', 'test_stores_normalized_text_and_its_hash[bidi-override]', 'test_stores_normalized_text_and_its_hash[nfkc-ligature-fullwidth]', 'test_stores_normalized_text_and_its_hash[surrounding-whitespace]', 'test_stores_normalized_text_and_its_hash[control-chars]', 'test_stores_normalized_text_and_its_hash[keeps-newline-and-tab]', 'test_stores_normalized_text_and_its_hash[bom-mid-text]', 'test_stores_normalized_text_and_its_hash[done-when-normalized]', 'test_rejects_over_limit_and_blank_fields[title-over-120]', 'test_rejects_over_limit_and_blank_fields[body-over-4000]', 'test_rejects_over_limit_and_blank_fields[done-when-over-1000]', 'test_rejects_over_limit_and_blank_fields[blank-after-normalization]']
  ```
- **RED verdict**: right-reason

## Deferred stubs

- E-6: not-run (deferred: tests-after) (P1)
- E-7: not-run (deferred: tests-after) (P1)
- E-8: not-run (deferred: human) (P1)
- E-9: not-run (deferred: tests-after) (P2)
- E-10: not-run (deferred: tests-after) (P2)
- E-11: not-run (deferred: tests-after) (P2)
- E-12: not-run (deferred: tests-after) (P1)
- E-13: not-run (deferred: tests-after) (P2)
- E-14: not-run (deferred: tests-after) (P2)
