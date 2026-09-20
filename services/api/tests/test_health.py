"""Tests for health check endpoints.

The credential-aware probe's own specification — E-2 (503 on a real auth
failure), E-3 (fail open on everything else) and E-4 (at most one fresh
connection per TTL) — lives in `test_health_credential_probe.py`, which
was this file's RED artifact for rsh102 and is now an ordinary test
module.

`test_health_check` and `test_readiness_check` moved there with it, so
the happy-path body assertion sits next to the failure cases that define
it. What used to live here and does **not** survive is
`test_health_check_db_failure`: it asserted that a bare `RuntimeError`
produced `503 {"detail": "db unavailable"}`. Under FR-2's fail-open rule
an unclassified exception returns **200** — a deliberate contract change,
not a regression. Its replacement is
`test_non_auth_failure_returns_200[unclassified-exception]`.

This module is kept as the pointer so the next person looking for
"the health tests" by filename lands somewhere that tells them where to
go, rather than on a file that quietly no longer exists.
"""
