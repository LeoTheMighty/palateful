# Expectations — Rotation Self Heal

<!-- Gate 1 input. Minimum 3 E-blocks (config: engine.expectations_min).
     Every business goal (G-) must be covered by at least one expectation;
     every Covers: ID must resolve in prd.md. EARS regex enforced by
     `devx gate prd`: "When .+, the system SHALL .+". A P0 with a vague
     Verified-by target fails the gate. -->

## E-1: Deploy path on main completes

- **Priority:** P0
- **Covers:** `G-1, CAP-1, FR-1, UC-1`
- **Trigger:** A push to `main` runs `.github/workflows/ci.yml`.
- **Expectation (EARS):** When a commit lands on `main`, the system SHALL
  complete every job the deploy jobs depend on without failure, so
  `deploy-services` executes rather than being skipped.
- **Threshold:** `flutter-test` reports 0 failures (currently 3 of 1524);
  `deploy-services` reaches conclusion `success`.
- **Verified by:** `app/test/features/activity/imports_tab_test.dart`

## E-2: Stale credentials fail the health check

- **Priority:** P0
- **Covers:** `G-2, CAP-2, CAP-3, FR-2, UC-3`
- **Trigger:** A fresh database connection is refused with PostgreSQL
  SQLSTATE `28P01` or `28000` (password authentication failed).
- **Expectation (EARS):** When a new database connection fails
  authentication, the system SHALL return HTTP 503 from `GET /v1/health`
  so ECS replaces the task.
- **Threshold:** 503 returned on both `28P01` and `28000`; response body
  identifies the failure as credential-related.
- **Verified by:** `services/api/tests/test_health.py`

## E-3: Transient database failures do not fail the health check

- **Priority:** P0
- **Covers:** `G-2, CAP-2, FR-2, UC-4`
- **Trigger:** A fresh database connection fails for a non-authentication
  reason — timeout, connection refused, DNS failure.
- **Expectation (EARS):** When a new database connection fails for a
  non-authentication reason, the system SHALL return HTTP 200 from
  `GET /v1/health`, because replacing the task cannot fix connectivity and
  mass replacement escalates a transient blip into a full outage.
- **Threshold:** 200 returned for timeout, `OperationalError` without an
  auth SQLSTATE, and DNS resolution failure.
- **Verified by:** `services/api/tests/test_health.py`

## E-4: Fresh-connection probe is rate-limited

- **Priority:** P1
- **Covers:** `FR-2`
- **Trigger:** Health checks arrive every 30s (container) and 60s (ALB).
- **Expectation (EARS):** When health checks arrive more frequently than
  the configured probe interval, the system SHALL open at most one new
  database connection per interval and serve cached verdicts in between.
- **Threshold:** At most 1 fresh connection per 60s window regardless of
  probe rate.
- **Verified by:** `services/api/tests/test_health.py`

## E-5: Rotation event redeploys both services

- **Priority:** P0
- **Covers:** `G-3, CAP-4, FR-4, UC-2`
- **Trigger:** Secrets Manager emits `Secret Label Updated` with
  `labelUpdated: AWSCURRENT` for the RDS-managed secret.
- **Expectation (EARS):** When the `AWSCURRENT` label moves on the
  database secret, the system SHALL force a new deployment of both the
  api and worker ECS services.
- **Threshold:** `update_service` called exactly 1 time per service (2
  calls total) with `forceNewDeployment=True`; a non-matching secret
  produces 0 calls; a partial failure yields a non-0 handler result.
- **Verified by:** `libraries/utils/test/test_rotation_redeploy_handler.py`

## E-6: Password rotation needs no restart

- **Priority:** P0
- **Covers:** `G-2, G-3, CAP-5, CAP-6, FR-5`
- **Trigger:** The database password changes while a process is running,
  with `DB_PASSWORD_SECRET_ARN` configured.
- **Expectation (EARS):** When a connection attempt fails authentication
  and a secret ARN is configured, the system SHALL invalidate its cached
  credential, re-resolve from Secrets Manager, and retry exactly once
  before surfacing the error.
- **Threshold:** Exactly 1 re-resolution and 1 retry per auth failure;
  the retried connection succeeds; with `DB_PASSWORD_SECRET_ARN` unset,
  0 Secrets Manager calls occur and engine construction is unchanged.
- **Verified by:** `libraries/utils/test/test_db_credential_provider.py`

## E-7: Deploy freeze becomes visible

- **Priority:** P2
- **Covers:** `G-4, FR-6, UC-5`
- **Trigger:** The image deployed to prod falls more than 7 days behind
  `main`.
- **Expectation (EARS):** When the deployed prod image is more than 7
  days behind `main`, the system SHALL surface that gap to the operator
  rather than leaving it silent.
- **Threshold:** Gap reported within 24h of crossing 7 days.
- **Verified by:** `evals/E-7_deploy-freeze-visibility.md`

## E-8: Worker liveness is observable

- **Priority:** P1
- **Covers:** `FR-3, CAP-3`
- **Trigger:** The worker task is running.
- **Expectation (EARS):** When the worker task is running, the system
  SHALL report a health status other than `UNKNOWN`, so ECS can detect
  and replace a broken worker.
- **Threshold:** 0 worker tasks report `healthStatus: UNKNOWN`; the
  worker reports `HEALTHY` within 120s of task start.
- **Verified by:** `evals/E-8_worker-healthcheck.md`
