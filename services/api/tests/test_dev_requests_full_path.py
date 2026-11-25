# ruff: noqa: F811 — pytest fixtures (eval_db, shim_dir) are imported from devreq_harness by design
"""E-1 — a request travels the whole path (admin-request-intake, 1e84ad).

RED artifact: registered in tools/red-artifacts.txt until Phase 2 lands.
Pinned by sha256 in _devx/workstreams/admin-request-intake/evals/E-1_full_path.sh.

An admin creates a request through the API; then a reference bridge that
follows PRD FR-13 drives the real `bin/prod-script` (through the `aws` shim)
through poll → transition received → adopt → transition accepted, against a
real Postgres. Every channel run is judged by the FR-6 consumer.
"""

import json
import textwrap

from devreq_harness import (  # noqa: F401  (eval_db and shim_dir are fixtures)
    READ_SCRIPT,
    READ_SCRIPT_REL,
    WRITE_SCRIPT,
    WRITE_SCRIPT_REL,
    api_client,
    audit_rows,
    channel,
    count_rows,
    create_request,
    disallowed_imports,
    eval_db,
    fingerprint,
    make_user,
    ref_hash,
    request_row,
    require_create_route,
    require_script,
    require_table,
    reset,
    shim_dir,
)

_ARGV_PROBE = textwrap.dedent(
    """\
    import json
    import sys

    def _emit(record):
        line = "DEVREQ1 " + json.dumps(record, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        sys.stdout.write(line + "\\n")
        sys.stdout.flush()

    _emit({"kind": "argv", "v": 1, "argv": sys.argv[1:]})
    _emit({"kind": "end", "v": 1, "ok": True, "count": 1, "error": None})
    """
)

# Spaces, a glob, shell metacharacters, quotes and non-ASCII: none of them may
# be split, expanded or re-quoted on the way into the task (PRD FR-5).
_PROBE_ARGS = [
    "poll",
    "two words",
    "--flag=x",
    "$HOME",
    "*",
    "'single'",
    '"double"',
    "é ✓",
    "a;b|c",
]


def test_prod_script_forwards_arguments_and_stays_compatible(eval_db, shim_dir, tmp_path):
    probe = tmp_path / "argv_probe.py"
    probe.write_text(_ARGV_PROBE)

    bare = channel(eval_db, shim_dir, probe)
    assert bare.ok, f"a no-argument bin/prod-script call no longer runs: {bare.describe()}"
    assert bare.of_kind("argv") == [{"kind": "argv", "v": 1, "argv": []}], bare.describe()

    run = channel(eval_db, shim_dir, probe, *_PROBE_ARGS)
    assert run.ok, run.describe()
    got = run.of_kind("argv")[0]["argv"]
    assert got == _PROBE_ARGS, (
        f"RED: bin/prod-script did not forward its arguments intact (PRD FR-5, Phase 2): "
        f"sent {json.dumps(_PROBE_ARGS, ensure_ascii=False)}, the script saw "
        f"{json.dumps(got, ensure_ascii=False)}"
    )


def test_scripts_import_only_the_allowlist():
    for path, phase in ((READ_SCRIPT, "Phase 2"), (WRITE_SCRIPT, "Phase 2")):
        require_script(path, phase, "PRD FR-7/FR-11")
        bad = disallowed_imports(path)
        assert not bad, (
            f"{path.name} imports outside stdlib + sqlalchemy + utils.constants "
            f"(PRD FR-7: the origin/main script runs against an older image): {bad}"
        )


def test_request_travels_the_whole_path(eval_db, shim_dir):
    require_table(eval_db)
    reset(eval_db)
    admin = make_user(eval_db, is_admin=True)

    # 1. An admin files a request.
    with api_client(eval_db, admin) as client:
        resp = create_request(
            client,
            {
                "title": "Dark mode toggle",
                "body": "Add a dark-mode toggle.",
                "done_when": "It persists.",
            },
        )
    require_create_route(resp)
    assert resp.status_code == 201, resp.text
    created = resp.json()
    created = created.get("data", created)
    request_id, sha = created["id"], created["content_sha256"]
    assert created["status"] == "submitted"
    assert count_rows(eval_db, "dev_requests") == 1

    require_script(READ_SCRIPT, "Phase 2", "PRD FR-7")
    require_script(WRITE_SCRIPT, "Phase 2", "PRD FR-11")

    # 2. The bridge polls: ids and hashes, no text, and nothing written.
    before = fingerprint(eval_db)
    poll = channel(eval_db, shim_dir, READ_SCRIPT_REL, "poll")
    assert poll.ok, f"poll run failed (is bin/prod-script forwarding arguments?): {poll.describe()}"
    assert fingerprint(eval_db) == before, "poll wrote to the database"
    [rec] = [r for r in poll.of_kind("request") if r["id"] == request_id]
    assert rec["status"] == "submitted" and rec["content_sha256"] == sha, rec
    assert not {"title", "body", "done_when"} & rec.keys(), (
        f"poll record carries text fields: {rec}"
    )

    # 3. The bridge acknowledges it.
    ack = channel(
        eval_db, shim_dir, WRITE_SCRIPT_REL, "transition", request_id, "submitted", "received"
    )
    assert ack.ok, ack.describe()
    assert ack.of_kind("transition")[0]["changed"] is True, ack.describe()
    poll2 = channel(eval_db, shim_dir, READ_SCRIPT_REL, "poll")
    assert poll2.ok, poll2.describe()
    assert [r["status"] for r in poll2.of_kind("request") if r["id"] == request_id] == ["received"]

    # 4. Leo adopts: the text crosses once, and its hash is the one taken at submission.
    before = fingerprint(eval_db)
    adopt = channel(eval_db, shim_dir, READ_SCRIPT_REL, "adopt", request_id, sha)
    assert adopt.ok, adopt.describe()
    assert fingerprint(eval_db) == before, "adopt (a read) wrote to the database"
    [doc] = adopt.of_kind("adopt")
    assert ref_hash(doc["title"], doc["body"], doc["done_when"]) == sha == doc["content_sha256"], (
        doc
    )
    assert (doc["title"], doc["body"], doc["done_when"]) == (
        "Dark mode toggle",
        "Add a dark-mode toggle.",
        "It persists.",
    )

    # 5. The bridge marks it accepted.
    acc = channel(
        eval_db,
        shim_dir,
        WRITE_SCRIPT_REL,
        "transition",
        request_id,
        "received",
        "accepted",
        "--sha",
        sha,
    )
    assert acc.ok, acc.describe()
    assert acc.of_kind("transition")[0]["changed"] is True

    row = request_row(eval_db, request_id)
    assert row["status"] == "accepted"
    assert row["adopted_at"] is not None and row["synced_at"] is not None
    assert audit_rows(eval_db, request_id) == 2, "expected one audit row per applied transition"
    assert count_rows(eval_db, "dev_requests") == 1
