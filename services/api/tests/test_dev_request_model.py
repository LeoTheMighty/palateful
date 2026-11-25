"""In-process tests for the DevRequest model, its helpers and the create
endpoint (admin-request-intake, plan 1e84ad, phase 1 / arq101).

No database: the endpoint runs against the suite's mock session, so these
hold `src/` at 100% branch coverage whether or not a Postgres is reachable.
The live-database contract checks are the E-3 / E-5 evals
(`test_dev_requests_operator_only.py`, `test_dev_requests_normalization.py`)
and E-6 (`test_dev_requests_rate_limit.py`).

Also here: a model ↔ migration drift guard. Alembic's autogenerate (what
CI's `check-models` runs) does not compare CHECK constraints or partial
index predicates, so a CHECK present on the model and missing from the
migration would pass every eval — the evals build their database from the
model — and ship without its constraint. This file compares the two
directly.
"""

import importlib.util
import json
import logging
import re
import uuid
from pathlib import Path

import pytest
from devreq_harness import STATUSES, TERMINAL, ref_hash, ref_normalize
from sqlalchemy import CheckConstraint, Column, Index
from utils.models.dev_request import (
    DEV_REQUEST_STATUSES,
    TERMINAL_STATUSES,
    DevRequest,
    content_sha256,
    id8,
    normalize_request_text,
)

CREATE_PATH = "/v1/admin/dev-requests"
REPO = Path(__file__).resolve().parents[3]
MIGRATION = (
    REPO
    / "services/migrator/migrations/versions/20261124010000_add_dev_requests.py"
)


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    from api.v1.admin.create_dev_request import _reset_rate_limit_for_test

    _reset_rate_limit_for_test()
    yield
    _reset_rate_limit_for_test()


@pytest.fixture
def admin(mock_user):
    mock_user.is_admin = True
    return mock_user


def _added(mock_async_db) -> list[DevRequest]:
    return [
        c.args[0]
        for c in mock_async_db.db.add.call_args_list
        if isinstance(c.args[0], DevRequest)
    ]


# ---------------------------------------------------------------------------
# Constants and helpers
# ---------------------------------------------------------------------------


class TestConstants:
    def test_statuses_and_terminal_set_match_the_prd(self):
        assert DEV_REQUEST_STATUSES == STATUSES
        assert TERMINAL_STATUSES == TERMINAL
        assert set(TERMINAL_STATUSES) <= set(DEV_REQUEST_STATUSES)


class TestNormalize:
    @pytest.mark.parametrize(
        "raw",
        [
            "Add​ dark mode",
            "‮evil‬ text",
            "ﬁle ＡＢＣ",
            "  padded \n",
            "line\x00one\x07two",
            "a\n\tb",
            "Ti﻿tle",
            "  done‍ when⁦ ",
            "​​ ‮",
            "",
        ],
    )
    def test_agrees_with_the_contract_reference(self, raw):
        assert normalize_request_text(raw) == ref_normalize(raw)

    def test_keeps_newline_and_tab_inside_but_strips_them_at_the_ends(self):
        assert normalize_request_text("\n\ta\n\tb\t\n") == "a\n\tb"

    def test_drops_format_characters_before_stripping(self):
        # Whitespace hidden behind a zero-width character is still trimmed.
        assert normalize_request_text("​  title  ​") == "title"


class TestContentSha256:
    def test_pinned_vector(self):
        # Pinned literally so a change to the canonical form in both the
        # helper and the harness at once still fails here.
        assert (
            content_sha256("Add dark mode", "Please.", None)
            == "98191c4b822f17bacd71b1921625d23c1c29a50c498f7bbaca98d048fb449b67"
        )

    @pytest.mark.parametrize(
        "fields",
        [
            ("t", "b", None),
            ("t", "b", "d"),
            ("ünïcödé — 日本", "line\n\tline", "done"),
        ],
    )
    def test_agrees_with_the_contract_reference(self, fields):
        assert content_sha256(*fields) == ref_hash(*fields)

    def test_absent_done_when_differs_from_empty_string(self):
        assert content_sha256("t", "b", None) != content_sha256("t", "b", "")


def test_id8_is_the_first_eight_hex_characters():
    rid = uuid.UUID("0123abcd-4567-89ef-0123-456789abcdef")
    assert id8(rid) == "0123abcd"
    assert id8(str(rid)) == "0123abcd"


def test_repr_carries_no_text():
    row = DevRequest(title="secret title", body="secret body", status="submitted")
    assert "secret" not in repr(row)


# ---------------------------------------------------------------------------
# Model ↔ migration drift guard
# ---------------------------------------------------------------------------


class _RecordingOp:
    """Stands in for `alembic.op` while the migration's upgrade() runs."""

    def __init__(self):
        self.tables: dict[str, tuple] = {}
        self.indexes: dict[str, dict] = {}

    def create_table(self, name, *items, **_kw):
        self.tables[name] = items

    def create_index(self, name, table, columns, **kw):
        self.indexes[name] = {"table": table, "columns": columns, **kw}


def _squash(sql) -> str:
    return re.sub(r"\s+", " ", str(sql)).strip()


@pytest.fixture(scope="module")
def migration_ops():
    spec = importlib.util.spec_from_file_location("devrequests01_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    recorder = _RecordingOp()
    module.op = recorder
    module.upgrade()
    return module, recorder


class TestMigrationMatchesModel:
    def test_follows_the_head_it_was_written_against(self, migration_ops):
        module, _ = migration_ops
        assert (module.revision, module.down_revision) == ("devrequests01", "idupbookname1")

    def test_columns_match(self, migration_ops):
        _, ops = migration_ops
        columns = [c for c in ops.tables["dev_requests"] if isinstance(c, Column)]
        migrated = {c.name: (c.nullable, repr(c.type)) for c in columns}
        modelled = {c.name: (c.nullable, repr(c.type)) for c in DevRequest.__table__.columns}
        assert len(modelled) == 20
        assert migrated == modelled

    def test_foreign_keys_match(self, migration_ops):
        _, ops = migration_ops
        columns = [c for c in ops.tables["dev_requests"] if isinstance(c, Column)]
        migrated = {
            (c.name, fk.target_fullname, fk.ondelete) for c in columns for fk in c.foreign_keys
        }
        modelled = {
            (fk.parent.name, fk.target_fullname, fk.ondelete)
            for fk in DevRequest.__table__.foreign_keys
        }
        assert modelled == {("submitter_id", "users.id", "SET NULL")}
        assert migrated == modelled

    def test_check_constraints_match(self, migration_ops):
        _, ops = migration_ops
        migrated = {
            c.name: _squash(c.sqltext)
            for c in ops.tables["dev_requests"]
            if isinstance(c, CheckConstraint)
        }
        modelled = {
            c.name: _squash(c.sqltext)
            for c in DevRequest.__table__.constraints
            if isinstance(c, CheckConstraint)
        }
        assert len(modelled) == 9
        assert migrated == modelled

    def test_indexes_match(self, migration_ops):
        _, ops = migration_ops
        modelled: dict[str, dict] = {}
        for ix in DevRequest.__table__.indexes:
            assert isinstance(ix, Index)
            where = ix.dialect_options["postgresql"]["where"]
            modelled[ix.name] = {
                "columns": [c.name for c in ix.columns],
                "unique": bool(ix.unique),
                "where": None if where is None else _squash(where),
            }
        migrated = {
            name: {
                "columns": list(kw["columns"]),
                "unique": bool(kw.get("unique", False)),
                "where": (
                    None
                    if kw.get("postgresql_where") is None
                    else _squash(kw["postgresql_where"])
                ),
            }
            for name, kw in ops.indexes.items()
            if kw["table"] == "dev_requests"
        }
        assert migrated == modelled

    def test_status_check_lists_every_status(self, migration_ops):
        _, ops = migration_ops
        (status_check,) = [
            c
            for c in ops.tables["dev_requests"]
            if isinstance(c, CheckConstraint) and c.name == "ck_dev_requests_status"
        ]
        assert re.findall(r"'([a-z_]+)'", str(status_check.sqltext)) == list(STATUSES)

    def test_downgrade_drops_what_upgrade_made(self, migration_ops):
        module, _ = migration_ops
        dropped: list[str] = []

        class _DropOp:
            def drop_index(self, name, **_kw):
                dropped.append(name)

            def drop_table(self, name, **_kw):
                dropped.append(name)

        module.op = _DropOp()
        module.downgrade()
        _, ops = migration_ops
        assert set(dropped) == set(ops.indexes) | {"dev_requests"}
        assert dropped[-1] == "dev_requests"


# ---------------------------------------------------------------------------
# The endpoint, in process
# ---------------------------------------------------------------------------


class TestCreateHappyPath:
    def test_stores_a_submitted_row_for_the_caller(self, client, admin, mock_async_db):
        resp = client.post(
            CREATE_PATH,
            json={"title": " Add​ dark mode ", "body": "Please.", "priority": "high"},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()

        (row,) = _added(mock_async_db)
        assert (row.status, row.source, row.target, row.priority) == (
            "submitted",
            "admin",
            "palateful",
            "high",
        )
        assert str(row.submitter_id) == str(admin.id)
        assert (row.title, row.body, row.done_when) == ("Add dark mode", "Please.", None)
        assert row.pr_urls == []
        assert row.content_sha256 == content_sha256("Add dark mode", "Please.", None)
        mock_async_db.db.commit.assert_awaited_once()

        assert set(data) == {"id", "id8", "status", "content_sha256", "created_at"}
        assert data["id"] == str(row.id)
        assert data["id8"] == id8(row.id)
        assert data["status"] == "submitted"
        assert data["content_sha256"] == row.content_sha256

    def test_done_when_is_normalized_and_hashed(self, client, admin, mock_async_db):
        resp = client.post(
            CREATE_PATH, json={"title": "T", "body": "B", "done_when": "  done⁦ "}
        )
        assert resp.status_code == 201, resp.text
        (row,) = _added(mock_async_db)
        assert row.done_when == "done"
        assert resp.json()["content_sha256"] == content_sha256("T", "B", "done")

    def test_explicit_null_done_when_is_absent(self, client, admin, mock_async_db):
        resp = client.post(CREATE_PATH, json={"title": "T", "body": "B", "done_when": None})
        assert resp.status_code == 201, resp.text
        (row,) = _added(mock_async_db)
        assert row.done_when is None

    def test_limits_apply_to_the_normalized_value(self, client, admin, mock_async_db):
        # 120 visible characters plus invisible ones: the stored value fits.
        resp = client.post(CREATE_PATH, json={"title": "t" * 120 + "​" * 5, "body": "B"})
        assert resp.status_code == 201, resp.text
        (row,) = _added(mock_async_db)
        assert row.title == "t" * 120

    def test_logs_carry_no_request_text(self, client, admin, mock_async_db, caplog):
        """Every logger, at the level it is configured to run at (prod: INFO,
        terraform/modules/ecs/main.tf). `utils.api.endpoint` logs its kwargs
        at DEBUG — Params included — so this holds only while the API runs
        above DEBUG; that line is shared by every endpoint, not this one's."""
        caplog.set_level(logging.DEBUG)
        resp = client.post(
            CREATE_PATH,
            json={"title": "canary-title-x1", "body": "canary-body-x2", "done_when": "canary-dw-x3"},
        )
        assert resp.status_code == 201, resp.text
        logged = caplog.text  # every record, formatted, tracebacks included
        assert f"created {resp.json()['id8']}" in logged  # the check can see the log line
        assert "canary" not in logged


class TestCreateRefusals:
    def test_non_admin_is_refused(self, client, mock_user, mock_async_db):
        mock_user.is_admin = False
        resp = client.post(CREATE_PATH, json={"title": "T", "body": "B"})
        assert resp.status_code == 403
        assert _added(mock_async_db) == []

    @pytest.mark.parametrize(
        "payload",
        [
            {"title": "T", "body": "B", "status": "accepted"},
            {"title": "T", "body": "B", "submitter_id": str(uuid.uuid4())},
            {"title": "T", "body": "B", "source": "fault"},
            {"title": "T", "body": "B", "content_sha256": "0" * 64},
            {"title": "T", "body": "B", "pr_urls": []},
            {"title": "T", "body": "B", "priority": "urgent"},
            {"title": "T"},
            {"body": "B"},
            {"title": "t" * 121, "body": "B"},
            {"title": "T", "body": "b" * 4001},
            {"title": "T", "body": "B", "done_when": "d" * 1001},
            {"title": "​ ‮", "body": "B"},
            {"title": "T", "body": "\x00\x07"},
            {"title": "T", "body": "B", "done_when": "   "},
            {"title": 5, "body": "B"},
            {"title": "a\ud800b", "body": "B"},
            {"title": "T", "body": "x\udfffy"},
            {"title": "T", "body": "B", "done_when": "\ud83d"},
        ],
        ids=[
            "status",
            "submitter_id",
            "source",
            "content_sha256",
            "pr_urls",
            "bad-priority",
            "no-body",
            "no-title",
            "title-over-120",
            "body-over-4000",
            "done-when-over-1000",
            "blank-title",
            "blank-body",
            "blank-done-when",
            "non-string-title",
            "lone-surrogate-title",
            "lone-surrogate-body",
            "lone-surrogate-done-when",
        ],
    )
    def test_is_422_and_writes_nothing(self, client, admin, mock_async_db, payload):
        # Serialized by hand: a lone surrogate survives json.dumps' default
        # ASCII escaping ("\ud800"), which is exactly what a client can send.
        resp = client.post(
            CREATE_PATH,
            content=json.dumps(payload),
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 422, resp.text
        assert _added(mock_async_db) == []

    def test_unencodable_text_names_the_field_and_spends_no_allowance(
        self, client, admin, mock_async_db
    ):
        raw = json.dumps({"title": "T", "body": "x\udfffy"})
        for _ in range(6):
            resp = client.post(
                CREATE_PATH, content=raw, headers={"content-type": "application/json"}
            )
            assert resp.status_code == 422, resp.text
        (error,) = resp.json()["detail"]
        assert error["loc"] == ["body", "body"]
        assert "body is not valid Unicode text" in error["msg"]
        assert client.post(CREATE_PATH, json={"title": "T", "body": "B"}).status_code == 201

    @pytest.mark.parametrize(
        "payload",
        [
            {"title": "a\ud800" + "t" * 130, "body": "B"},
            {"title": "T", "body": "B", "status": "x\ud800"},
            {"title": "T", "body": "B", "priority": "\ud800"},
            {"title": "\ud800", "body": " "},
        ],
        ids=["surrogate-and-over-length", "surrogate-in-smuggled-key", "surrogate-priority", "two-bad-fields"],
    )
    def test_a_surrogate_beside_another_failure_is_still_a_422(self, client, admin, mock_async_db, payload):
        """FastAPI's 422 echoes every rejected input; with a lone surrogate in
        one, its UTF-8 body could not be rendered and the 422 became a 500."""
        resp = client.post(
            CREATE_PATH, content=json.dumps(payload), headers={"content-type": "application/json"}
        )
        assert resp.status_code == 422, resp.text
        resp.content.decode("ascii")  # the fallback escaped it
        assert resp.json()["detail"]
        assert _added(mock_async_db) == []

    def test_an_ordinary_422_is_unchanged_utf8(self, client, admin):
        resp = client.post(CREATE_PATH, json={"title": "é" * 121, "body": "B"})
        assert resp.status_code == 422, resp.text
        assert "é".encode("utf-8") in resp.content  # not escaped: the fallback did not run


class TestStoreFailure:
    """A failed insert must not carry the request text anywhere: SQLAlchemy's
    DBAPIError str() ends in `[parameters: (…)]`."""

    CANARIES = ("canary-title-s1", "canary-body-s2", "canary-dw-s3")

    def _db_error(self):
        from sqlalchemy.exc import OperationalError

        err = OperationalError(
            "INSERT INTO dev_requests (title, body, done_when) VALUES ($1, $2, $3)",
            self.CANARIES,
            Exception("connection reset"),
        )
        assert all(c in str(err) for c in self.CANARIES)  # control: the leak is real
        return err

    def _post(self, client):
        title, body, done_when = self.CANARIES
        return client.post(
            CREATE_PATH, json={"title": title, "body": body, "done_when": done_when}
        )

    @pytest.mark.parametrize("rollback_fails", [False, True], ids=["rollback-ok", "rollback-fails"])
    def test_carries_no_text_and_refunds_the_slot(
        self, client, admin, mock_async_db, caplog, monkeypatch, rollback_fails
    ):
        import traceback

        from api.v1.admin import create_dev_request as mod
        from utils.api.endpoint import Endpoint

        recorded: list[str] = []
        monkeypatch.setattr(
            Endpoint,
            "_log_error_to_db",
            lambda self, error: recorded.append(
                type(error).__name__ + " " + str(error) + "".join(traceback.format_exception(error))
            ),
        )
        mock_async_db.db.commit.side_effect = self._db_error()
        if rollback_fails:
            mock_async_db.db.rollback.side_effect = RuntimeError("rollback canary-title-s1")
        caplog.set_level(logging.DEBUG)

        resp = self._post(client)

        assert resp.status_code == 500
        assert resp.json()["error_message"] == "dev_request store failed: OperationalError"
        mock_async_db.db.rollback.assert_awaited_once()
        assert len(recorded) == 1 and recorded[0].startswith("DevRequestStoreFailed ")
        logged = caplog.text  # every record, formatted, tracebacks included
        assert "store failed" in logged  # the check can see the log lines
        for text in (resp.text, recorded[0], logged):
            assert not [c for c in self.CANARIES if c in text], text[-2000:]
        assert mod._rate_limit_events[str(admin.id)] == []  # the failed call was refunded

    def test_refund_without_a_window_is_a_no_op(self):
        from api.v1.admin import create_dev_request as mod

        mod._refund_rate_limit("never-seen")
        assert "never-seen" not in mod._rate_limit_events


class TestRateLimit:
    def test_sixth_create_in_an_hour_is_429_and_writes_nothing(
        self, client, admin, mock_async_db
    ):
        for _ in range(5):
            assert client.post(CREATE_PATH, json={"title": "T", "body": "B"}).status_code == 201
        resp = client.post(CREATE_PATH, json={"title": "T", "body": "B"})
        assert resp.status_code == 429, resp.text
        body = resp.json()
        assert body["data"]["error"] == "rate_limited"
        assert body["data"]["retry_after_s"] >= 1
        assert len(_added(mock_async_db)) == 5

    def test_window_rolls(self, monkeypatch):
        from api.v1.admin import create_dev_request as mod

        clock = [1000.0]
        monkeypatch.setattr(mod.time, "monotonic", lambda: clock[0])
        for _ in range(5):
            assert mod._check_rate_limit("u") == (True, 0)
        ok, retry_after = mod._check_rate_limit("u")
        assert (ok, retry_after) == (False, 3601)
        clock[0] += 1800
        assert mod._check_rate_limit("u") == (False, 1801)
        clock[0] += 1800.5  # the first five have aged out
        assert mod._check_rate_limit("u") == (True, 0)

    def test_limits_are_per_admin(self):
        from api.v1.admin import create_dev_request as mod

        for _ in range(5):
            mod._check_rate_limit("a")
        assert mod._check_rate_limit("a")[0] is False
        assert mod._check_rate_limit("b") == (True, 0)
