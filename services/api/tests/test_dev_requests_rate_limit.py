# ruff: noqa: F811 — the eval_db fixture is imported from devreq_harness by design
"""E-6 — submission is rate-limited (admin-request-intake, plan 1e84ad).

PRD FR-4: at most 5 creates per admin per rolling hour; the 6th call answers
429 with `retry_after_s` and creates no row. Run against a real Postgres
through the contract harness, so "no row" is a count of the table, not of a
mock's calls. The window's arithmetic (expiry, retry_after) is covered in
process by `test_dev_request_model.py::TestRateLimit`.

Tests-after (P1): not a Gate-4 locked eval, so not sha-pinned.
"""

import pytest
from devreq_harness import (  # noqa: F401  (eval_db is a fixture)
    api_client,
    count_rows,
    create_request,
    eval_db,
    make_user,
    require_create_route,
    reset,
)

_VALID = {"title": "A title", "body": "A body"}


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    from api.v1.admin.create_dev_request import _reset_rate_limit_for_test

    _reset_rate_limit_for_test()
    yield
    _reset_rate_limit_for_test()


def _rows_for(url: str, user_id: str) -> int:
    from devreq_harness import connect
    from sqlalchemy import text

    with connect(url) as conn:
        return int(
            conn.execute(
                text("SELECT count(*) FROM dev_requests WHERE submitter_id = :u"),
                {"u": user_id},
            ).scalar()
        )


def test_sixth_create_in_an_hour_is_429_and_creates_no_row(eval_db):
    reset(eval_db)
    admin = make_user(eval_db, is_admin=True)
    with api_client(eval_db, admin) as client:
        first_five = [create_request(client, dict(_VALID)) for _ in range(5)]
        require_create_route(first_five[0])
        sixth = create_request(client, dict(_VALID))

    assert [r.status_code for r in first_five] == [201] * 5, [r.text for r in first_five]
    assert sixth.status_code == 429, sixth.text
    data = sixth.json()["data"]
    assert data["error"] == "rate_limited"
    assert isinstance(data["retry_after_s"], int) and data["retry_after_s"] >= 1
    assert _rows_for(eval_db, admin) == 5
    assert count_rows(eval_db, "dev_requests") == 5


def test_a_second_admin_is_unaffected(eval_db):
    reset(eval_db)
    first = make_user(eval_db, is_admin=True)
    second = make_user(eval_db, is_admin=True)
    with api_client(eval_db, first) as client:
        for _ in range(6):
            create_request(client, dict(_VALID))
    with api_client(eval_db, second) as client:
        resp = create_request(client, dict(_VALID))

    assert resp.status_code == 201, resp.text
    assert _rows_for(eval_db, first) == 5
    assert _rows_for(eval_db, second) == 1


def test_a_refused_body_does_not_spend_the_allowance(eval_db):
    """A 422 never reaches the endpoint, so it is not counted: an admin who
    mistypes five times can still file."""
    reset(eval_db)
    admin = make_user(eval_db, is_admin=True)
    with api_client(eval_db, admin) as client:
        refused = [create_request(client, {"title": " ", "body": "B"}) for _ in range(5)]
        ok = create_request(client, dict(_VALID))

    assert [r.status_code for r in refused] == [422] * 5
    assert ok.status_code == 201, ok.text
    assert _rows_for(eval_db, admin) == 1
