# ruff: noqa: F811 — pytest fixtures (eval_db, shim_dir) are imported from devreq_harness by design
"""E-3 — only the operator can adopt (admin-request-intake, 1e84ad).

RED artifact: registered in tools/red-artifacts.txt until Phase 1 lands.
Pinned by sha256 in _devx/workstreams/admin-request-intake/evals/E-3_operator_only.sh.

No HTTP caller can create a request in any state but `submitted`, for anyone
but itself, and no route outside the PRD FR-3/FR-15 allowlist touches
`dev_requests`. The route scan first proves it can see a route that exists.
"""

import re

import pytest
from devreq_harness import (  # noqa: F401  (eval_db is a fixture)
    CREATE_PATH,
    api_client,
    count_rows,
    create_request,
    eval_db,
    make_user,
    request_row,
    require_create_route,
    require_table,
    reset,
)

_ALLOWED = {
    ("POST", "/v1/admin/dev-requests"),
    ("GET", "/v1/admin/dev-requests"),
    ("GET", "/v1/admin/dev-requests/{}"),
    ("POST", "/v1/admin/dev-requests/{}/cancel"),
}
_MENTIONS = re.compile(r"dev[-_]?requests?", re.IGNORECASE)
_PARAM = re.compile(r"\{[^}]*\}")

_VALID = {"title": "A title", "body": "A body"}


def _routes(fragment: re.Pattern) -> set[tuple[str, str]]:
    from main import app

    found = set()
    for route in app.routes:
        path = getattr(route, "path", "")
        if not fragment.search(path):
            continue
        for method in getattr(route, "methods", None) or {"*"}:
            if method in ("HEAD", "OPTIONS"):
                continue
            found.add((method, _PARAM.sub("{}", path)))
    return found


def test_route_scan_can_see_and_finds_the_create_route():
    # Control: the scan finds a route that exists today.
    assert ("GET", "/v1/admin/feedback") in _routes(re.compile("feedback")), (
        "the route scan is blind — it cannot find GET /v1/admin/feedback"
    )
    assert ("POST", CREATE_PATH) in _routes(_MENTIONS), (
        f"RED: POST {CREATE_PATH} is not routed — Phase 1 (PRD FR-3) is not built"
    )


def test_harness_reaches_a_real_admin_route_as_the_right_user(eval_db):
    """Control: the API harness binds the real app to the throwaway database and
    to a real user row, so an existing admin route answers 200 for an admin and
    403 for a non-admin. Without this, every RED below could be harness noise."""
    admin = make_user(eval_db, is_admin=True)
    user = make_user(eval_db, is_admin=False)
    with api_client(eval_db, admin) as client:
        ok = client.get("/v1/admin/feedback")
    with api_client(eval_db, user) as client:
        denied = client.get("/v1/admin/feedback")
    assert (ok.status_code, denied.status_code) == (200, 403), (ok.text[:300], denied.text[:300])


def test_no_route_outside_the_allowlist_touches_dev_requests():
    extra = _routes(_MENTIONS) - _ALLOWED
    assert not extra, f"routes touching dev_requests outside PRD FR-3/FR-15: {sorted(extra)}"


def test_admin_create_stores_submitted_for_the_caller(eval_db):
    require_table(eval_db)
    reset(eval_db)
    admin = make_user(eval_db, is_admin=True)
    with api_client(eval_db, admin) as client:
        resp = create_request(client, dict(_VALID))
    require_create_route(resp)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    data = data.get("data", data)
    assert data["status"] == "submitted"
    row = request_row(eval_db, data["id"])
    assert row is not None
    assert (row["status"], str(row["submitter_id"]), row["source"], row["target"]) == (
        "submitted",
        admin,
        "admin",
        "palateful",
    )


def test_non_admin_gets_403_and_no_row(eval_db):
    require_table(eval_db)
    reset(eval_db)
    user = make_user(eval_db, is_admin=False)
    with api_client(eval_db, user) as client:
        resp = create_request(client, dict(_VALID))
    require_create_route(resp)
    assert resp.status_code == 403, resp.text
    assert count_rows(eval_db, "dev_requests") == 0


@pytest.mark.parametrize(
    "smuggled",
    [
        {"status": "accepted"},
        {"submitter_id": "00000000-0000-4000-8000-000000000000"},
        {"workstream": "admin-req-deadbeef"},
    ],
    ids=["status", "submitter_id", "workstream"],
)
def test_smuggled_fields_are_rejected(eval_db, smuggled):
    require_table(eval_db)
    reset(eval_db)
    admin = make_user(eval_db, is_admin=True)
    with api_client(eval_db, admin) as client:
        resp = create_request(client, {**_VALID, **smuggled})
    require_create_route(resp)
    assert resp.status_code == 422, f"{smuggled} was accepted: {resp.status_code} {resp.text}"
    assert count_rows(eval_db, "dev_requests") == 0
