# ruff: noqa: F811 — pytest fixtures (eval_db, shim_dir) are imported from devreq_harness by design
"""E-2 — no submitter text before adoption (admin-request-intake, 1e84ad).

RED artifact: registered in tools/red-artifacts.txt until Phase 2 lands.
Pinned by sha256 in _devx/workstreams/admin-request-intake/evals/E-2_containment_canary.sh.

A guard's first job is to prove it can see. So every pre-adoption call must
be a well-formed run that actually saw the row (an absent canary in the
output of a call that crashed proves nothing), and the same detector must
find all three canaries in a successful adopt and in a record built with one.
"""

import json
import uuid

from devreq_harness import (  # noqa: F401  (eval_db and shim_dir are fixtures)
    READ_SCRIPT,
    READ_SCRIPT_REL,
    WRITE_SCRIPT,
    WRITE_SCRIPT_REL,
    api_client,
    channel,
    consume,
    contains_any,
    create_request,
    eval_db,
    make_user,
    require_create_route,
    require_script,
    require_table,
    reset,
    shim_dir,
)


def _canaries() -> dict[str, str]:
    tag = uuid.uuid4().hex[:10].upper()
    return {
        "title": f"CANARYTITLE{tag}",
        "body": f"CANARYBODY{tag}",
        "done_when": f"CANARYDONE{tag}",
    }


def _file_request(url: str, canaries: dict[str, str]) -> tuple[str, str]:
    admin = make_user(url, is_admin=True)
    with api_client(url, admin) as client:
        resp = create_request(
            client,
            {
                "title": f"Fix {canaries['title']} now",
                "body": f"Body text with {canaries['body']} inside it.",
                "done_when": f"Done when {canaries['done_when']} is gone.",
            },
        )
    require_create_route(resp)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    data = data.get("data", data)
    return data["id"], data["content_sha256"]


def test_detector_sees_a_canary_in_a_built_record():
    canary = "CANARYCONTROL" + uuid.uuid4().hex[:8].upper()
    record = "DEVREQ1 " + json.dumps(
        {"kind": "request", "v": 1, "title": canary},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    end = 'DEVREQ1 {"count":1,"error":null,"kind":"end","ok":true,"v":1}'
    # Same stream damage the shim applies: an escape inside the line, CRLF.
    raw = "\r\nbanner\r\n" + record[:12] + "\x1b[0C" + record[12:] + "\r\n" + end + "\r\n"
    run = consume(raw)
    assert run.ok, run.describe()
    assert contains_any(run.clean, [canary]) == [canary], "the detector is blind to a canary"


def test_pre_adoption_calls_carry_no_submitter_text(eval_db, shim_dir):
    require_table(eval_db)
    reset(eval_db)
    canaries = _canaries()
    request_id, sha = _file_request(eval_db, canaries)
    require_script(READ_SCRIPT, "Phase 2", "PRD FR-7")
    require_script(WRITE_SCRIPT, "Phase 2", "PRD FR-11")

    calls = {
        "poll": (READ_SCRIPT_REL, "poll"),
        "metrics": (READ_SCRIPT_REL, "metrics"),
        "transition received": (
            WRITE_SCRIPT_REL,
            "transition",
            request_id,
            "submitted",
            "received",
        ),
        "adopt, wrong hash": (READ_SCRIPT_REL, "adopt", request_id, "0" * 64),
        "adopt, unknown id": (READ_SCRIPT_REL, "adopt", str(uuid.uuid4()), sha),
        "transition, free-text reason": (
            WRITE_SCRIPT_REL,
            "transition",
            request_id,
            "received",
            "declined",
            "--reason",
            "because I said so",
        ),
    }
    expected_ok = {"poll": True, "metrics": True, "transition received": True}
    leaks: dict[str, list[str]] = {}
    for name, (script, *args) in calls.items():
        run = channel(eval_db, shim_dir, script, *args)
        # Prove the call ran: a crashed call would "pass" containment vacuously.
        assert run.wellformed, (
            f"{name}: not a well-formed run, so it proves nothing: {run.describe()}"
        )
        assert run.ok is expected_ok.get(name, False), f"{name}: unexpected outcome {run.end}"
        if name == "poll":
            assert [r for r in run.of_kind("request") if r["id"] == request_id], (
                f"poll did not return the row, so its silence proves nothing: {run.describe()}"
            )
        found = contains_any(run.clean, list(canaries.values()))
        if found:
            leaks[name] = found
    assert not leaks, f"submitter text reached the laptop before adoption: {leaks}"


def test_adopt_returns_all_three_canaries(eval_db, shim_dir):
    """Negative control through the real channel: the text is visible when it should be."""
    require_table(eval_db)
    reset(eval_db)
    canaries = _canaries()
    request_id, sha = _file_request(eval_db, canaries)
    require_script(READ_SCRIPT, "Phase 2", "PRD FR-8")
    run = channel(eval_db, shim_dir, READ_SCRIPT_REL, "adopt", request_id, sha)
    assert run.ok, run.describe()
    assert sorted(contains_any(run.clean, list(canaries.values()))) == sorted(canaries.values())
