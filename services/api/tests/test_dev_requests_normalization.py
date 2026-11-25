# ruff: noqa: F811 — pytest fixtures (eval_db, shim_dir) are imported from devreq_harness by design
"""E-5 — what Leo reads is what an agent reads (admin-request-intake, 1e84ad).

RED artifact: registered in tools/red-artifacts.txt until Phase 1 lands.
Pinned by sha256 in _devx/workstreams/admin-request-intake/evals/E-5_normalization.sh.

Every case files through the API (a fresh admin each time, so the rate limit
never interferes) and reads the stored row back from the database. Stored
text must equal PRD FR-2's reference normalization, and the stored hash must
equal FR-2's reference hash over the stored text.
"""

import unicodedata

import pytest
from devreq_harness import (  # noqa: F401  (eval_db is a fixture)
    api_client,
    count_rows,
    create_request,
    eval_db,
    make_user,
    ref_hash,
    ref_normalize,
    request_row,
    require_create_route,
    require_table,
    reset,
)

_CASES = {
    "zero-width-space": {"title": "Add​ dark mode", "body": "Body"},
    "bidi-override": {"title": "Title", "body": "‮evil‬ text"},
    "nfkc-ligature-fullwidth": {"title": "ﬁle ＡＢＣ", "body": "Body"},
    "surrounding-whitespace": {"title": "  padded title \n", "body": "\t body \n"},
    "control-chars": {"title": "Title", "body": "line\x00one\x07two"},
    "keeps-newline-and-tab": {"title": "Title", "body": "a\n\tb"},
    "bom-mid-text": {"title": "Ti﻿tle", "body": "Body"},
    "done-when-normalized": {"title": "Title", "body": "Body", "done_when": "  done‍ when⁦ "},
}


def _create(url: str, payload: dict):
    admin = make_user(url, is_admin=True)
    with api_client(url, admin) as client:
        resp = create_request(client, payload)
    require_create_route(resp)
    return resp


def _bad_chars(value: str | None) -> list[str]:
    if value is None:
        return []
    return [
        f"U+{ord(ch):04X}"
        for ch in value
        if ch not in "\n\t" and unicodedata.category(ch) in ("Cc", "Cf")
    ]


@pytest.mark.parametrize("case", list(_CASES), ids=list(_CASES))
def test_stores_normalized_text_and_its_hash(eval_db, case):
    require_table(eval_db)
    reset(eval_db)
    payload = _CASES[case]
    resp = _create(eval_db, payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    data = data.get("data", data)
    row = request_row(eval_db, data["id"])

    expected = {
        "title": ref_normalize(payload["title"]),
        "body": ref_normalize(payload["body"]),
        "done_when": ref_normalize(payload["done_when"]) if "done_when" in payload else None,
    }
    stored = {k: row[k] for k in expected}
    assert stored == expected, f"stored {stored!r}, reference {expected!r}"
    for name, value in stored.items():
        assert not _bad_chars(value), f"{name} still holds {_bad_chars(value)}"
    want = ref_hash(expected["title"], expected["body"], expected["done_when"])
    assert row["content_sha256"] == want == data["content_sha256"]


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "t" * 121, "body": "Body"},
        {"title": "Title", "body": "b" * 4001},
        {"title": "Title", "body": "Body", "done_when": "d" * 1001},
        {"title": "​​ ‮", "body": "Body"},
    ],
    ids=["title-over-120", "body-over-4000", "done-when-over-1000", "blank-after-normalization"],
)
def test_rejects_over_limit_and_blank_fields(eval_db, payload):
    require_table(eval_db)
    reset(eval_db)
    resp = _create(eval_db, payload)
    assert resp.status_code == 422, f"accepted: {resp.status_code} {resp.text[:300]}"
    assert count_rows(eval_db, "dev_requests") == 0
