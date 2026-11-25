# ruff: noqa: F811 — pytest fixtures (eval_db, shim_dir) are imported from devreq_harness by design
"""E-4 — transitions are validated, compare-and-set and audited (admin-request-intake, 1e84ad).

RED artifact: registered in tools/red-artifacts.txt until Phase 2 lands.
Pinned by sha256 in _devx/workstreams/admin-request-intake/evals/E-4_transitions.sh.

Runs `dev_requests_write.py transition` standalone against a real Postgres
with rows seeded under PRD FR-1's column names. The sampled illegal edges are
ones PRD FR-12 never gives the bridge in any phase, so no later phase can
make this eval wrong.
"""

import uuid

import pytest
from devreq_harness import (  # noqa: F401  (eval_db is a fixture)
    WRITE_SCRIPT,
    audit_rows,
    eval_db,
    fingerprint,
    insert_request,
    make_user,
    request_row,
    require_script,
    require_table,
    reset,
    run_direct,
    set_admin,
)

# (from, to, extra args) — every edge PRD FR-12 gives the bridge in slice 1.
_SLICE_EDGES = [
    ("submitted", "received", []),
    ("submitted", "accepted", ["--sha", "<sha>"]),
    ("received", "accepted", ["--sha", "<sha>"]),
    ("submitted", "declined", ["--reason", "duplicate"]),
    ("received", "declined", ["--reason", "unsafe"]),
    ("submitted", "withdrawn", ["--reason", "submitter_revoked"]),
    ("received", "withdrawn", ["--reason", "submitter_revoked"]),
]

_NEVER_LEGAL = [
    ("received", "submitted"),
    ("accepted", "received"),
    ("declined", "accepted"),
    ("withdrawn", "received"),
    ("submitted", "shipped"),
    ("stopped", "building"),
]


def _ready(url: str) -> None:
    require_table(url)
    require_script(WRITE_SCRIPT, "Phase 2", "PRD FR-11")
    reset(url)


def _transition(url, request_id, frm, to, *extra):
    return run_direct(url, WRITE_SCRIPT, "transition", request_id, frm, to, *extra)


@pytest.mark.parametrize(
    ("frm", "to", "extra"), _SLICE_EDGES, ids=[f"{f}->{t}" for f, t, _ in _SLICE_EDGES]
)
def test_slice_edges_apply_with_one_audit_row(eval_db, frm, to, extra):
    _ready(eval_db)
    admin = make_user(eval_db, is_admin=True)
    request_id, sha = insert_request(eval_db, status=frm, submitter_id=admin)
    args = [sha if a == "<sha>" else a for a in extra]
    run = _transition(eval_db, request_id, frm, to, *args)
    assert run.ok, run.describe()
    [rec] = run.of_kind("transition")
    assert (rec["id"], rec["from"], rec["to"], rec["changed"]) == (request_id, frm, to, True), rec
    row = request_row(eval_db, request_id)
    assert row["status"] == to
    assert row["synced_at"] is not None
    if to == "accepted":
        assert row["adopted_at"] is not None
    assert audit_rows(eval_db, request_id) == 1


@pytest.mark.parametrize(("frm", "to"), _NEVER_LEGAL, ids=[f"{f}->{t}" for f, t in _NEVER_LEGAL])
def test_never_legal_edges_are_refused(eval_db, frm, to):
    _ready(eval_db)
    admin = make_user(eval_db, is_admin=True)
    request_id, sha = insert_request(eval_db, status=frm, submitter_id=admin)
    before = fingerprint(eval_db)
    # Arguments are otherwise valid, so the only thing wrong is the edge:
    # `--sha` only where the target is `accepted` (PRD FR-11 requires it there).
    extra = ["--sha", sha] if to == "accepted" else []
    run = _transition(eval_db, request_id, frm, to, *extra)
    assert run.wellformed and run.error == "illegal_transition", run.describe()
    assert fingerprint(eval_db) == before
    assert request_row(eval_db, request_id)["status"] == frm


def test_stale_from_is_a_conflict(eval_db):
    _ready(eval_db)
    admin = make_user(eval_db, is_admin=True)
    request_id, sha = insert_request(eval_db, status="received", submitter_id=admin)
    before = fingerprint(eval_db)
    run = _transition(eval_db, request_id, "submitted", "accepted", "--sha", sha)
    assert run.wellformed and run.error == "conflict", run.describe()
    assert fingerprint(eval_db) == before


def test_a_repeat_is_a_no_op(eval_db):
    _ready(eval_db)
    admin = make_user(eval_db, is_admin=True)
    request_id, _ = insert_request(eval_db, status="submitted", submitter_id=admin)
    first = _transition(eval_db, request_id, "submitted", "received")
    assert first.ok, first.describe()
    before = fingerprint(eval_db)
    again = _transition(eval_db, request_id, "submitted", "received")
    assert again.ok, again.describe()
    assert again.of_kind("transition")[0]["changed"] is False
    assert fingerprint(eval_db) == before
    assert audit_rows(eval_db, request_id) == 1


@pytest.mark.parametrize(
    "args",
    [
        ["not-a-uuid", "submitted", "received"],
        ["<id>", "submitted", "bogus_status"],
        ["<id>", "submitted", "declined", "--reason", "because I said so"],
        ["<id>", "submitted", "accepted", "--sha", "xyz"],
    ],
    ids=["bad-id", "bad-status", "free-text-reason", "bad-sha"],
)
def test_bad_arguments_are_refused(eval_db, args):
    _ready(eval_db)
    admin = make_user(eval_db, is_admin=True)
    request_id, _ = insert_request(eval_db, status="submitted", submitter_id=admin)
    before = fingerprint(eval_db)
    run = run_direct(
        eval_db, WRITE_SCRIPT, "transition", *[request_id if a == "<id>" else a for a in args]
    )
    assert run.wellformed and run.error == "invalid_argument", run.describe()
    assert fingerprint(eval_db) == before


def test_wrong_sha_is_refused(eval_db):
    _ready(eval_db)
    admin = make_user(eval_db, is_admin=True)
    request_id, _ = insert_request(eval_db, status="received", submitter_id=admin)
    before = fingerprint(eval_db)
    run = _transition(eval_db, request_id, "received", "accepted", "--sha", "a" * 64)
    assert run.wellformed and run.error == "sha_mismatch", run.describe()
    assert fingerprint(eval_db) == before


@pytest.mark.parametrize("how", ["no-longer-admin", "submitter-deleted"])
def test_adopting_for_a_revoked_submitter_is_refused(eval_db, how):
    _ready(eval_db)
    admin = make_user(eval_db, is_admin=True)
    submitter = None if how == "submitter-deleted" else admin
    request_id, sha = insert_request(eval_db, status="received", submitter_id=submitter)
    if how == "no-longer-admin":
        set_admin(eval_db, admin, False)
    before = fingerprint(eval_db)
    run = _transition(eval_db, request_id, "received", "accepted", "--sha", sha)
    assert run.wellformed and run.error == "submitter_revoked", run.describe()
    assert fingerprint(eval_db) == before


def test_unknown_id_is_not_found(eval_db):
    _ready(eval_db)
    run = _transition(eval_db, str(uuid.uuid4()), "submitted", "received")
    assert run.wellformed and run.error == "not_found", run.describe()
