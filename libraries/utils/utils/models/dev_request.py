"""DevRequest — an admin's request for a change to Palateful.

Workstream admin-request-intake (plan 1e84ad), PRD FR-1 / FR-2 / FR-12.

A row is created by exactly one HTTP route (``POST /v1/admin/dev-requests``,
always as ``submitted`` for the calling admin) and moved after that only by
the operator's write script over ``bin/prod-script``. No HTTP route sets a
status the bridge owns (PRD FR-12).

The status CHECK lists all 13 statuses and the source columns exist from the
first migration, so neither the widening nor slice 2 needs a second
migration (design, Trade-offs). Every length limit is a CHECK as well as API
validation, and the API checks it on the *normalized* value, so the CHECK
never fires on a well-formed request.

``normalize_request_text`` and ``content_sha256`` are the reference for what
the server stores. The operator scripts deliberately carry their own copy of
the hash (they may import only the standard library, SQLAlchemy and
``utils.constants``); the E-1 eval holds the two to the same answer.
"""

import hashlib
import json
import unicodedata
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    UUID,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.user import User


# PRD FR-12 — every status, in pipeline order.
DEV_REQUEST_STATUSES = (
    "submitted",
    "received",
    "accepted",
    "declined",
    "withdrawn",
    "scoping",
    "designing",
    "planning",
    "building",
    "waiting_on_leo",
    "shipped",
    "stopped",
    "reverted",
)
# Left out of `poll`; a terminal row has no open work. `shipped` may still
# move to `reverted` (FR-12), but it is not "open" for fault de-duplication.
TERMINAL_STATUSES = ("declined", "withdrawn", "shipped", "stopped", "reverted")

DEV_REQUEST_SOURCES = ("admin", "fault")
DEV_REQUEST_PRIORITIES = ("low", "normal", "high")
DEV_REQUEST_TARGET = "palateful"

TITLE_MAX_LENGTH = 120
BODY_MAX_LENGTH = 4000
DONE_WHEN_MAX_LENGTH = 1000

# Characters FR-2 keeps although their category is Cc.
_KEPT_CONTROL_CHARS = frozenset("\n\t")
_DROPPED_CATEGORIES = frozenset(("Cc", "Cf"))


def _sql_in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def normalize_request_text(value: str) -> str:
    """PRD FR-2: NFKC, then drop every Cc/Cf character except ``\\n`` and
    ``\\t``, then strip leading and trailing whitespace.

    The order matters: NFKC can *produce* a format character, and stripping
    before dropping would leave whitespace that sat behind a zero-width
    character. The caller rejects an empty result.
    """
    value = unicodedata.normalize("NFKC", value)
    value = "".join(
        ch
        for ch in value
        if ch in _KEPT_CONTROL_CHARS
        or unicodedata.category(ch) not in _DROPPED_CATEGORIES
    )
    return value.strip()


def content_sha256(title: str, body: str, done_when: str | None) -> str:
    """PRD FR-2: lowercase hex SHA-256 of the canonical JSON of the three
    normalized submitter-written fields (``done_when`` is JSON null when
    absent). Whoever reads the text later can recompute this and know it is
    the text the admin submitted."""
    payload = json.dumps(
        {"title": title, "body": body, "done_when": done_when},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def id8(request_id: uuid.UUID | str) -> str:
    """The first 8 hex characters of a request id — its short handle."""
    return str(request_id).replace("-", "")[:8]


class DevRequest(Base):
    """One request for a change, from an admin (or, in slice 2, a fault)."""

    __tablename__ = "dev_requests"

    # Identity. ON DELETE SET NULL: for an admin row, a null submitter reads
    # as revoked, and the write script refuses to adopt it.
    submitter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Source.
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, default="admin", server_default="admin"
    )
    fault_signature: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Submitter-written, immutable once stored.
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    done_when: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Integrity.
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    # Labels.
    target: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=DEV_REQUEST_TARGET,
        server_default=DEV_REQUEST_TARGET,
    )
    priority: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # Pipeline — written only by the operator's scripts after creation.
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="submitted", server_default="submitted"
    )
    status_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    workstream: Mapped[str | None] = mapped_column(String(128), nullable=True)
    spec_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pr_urls: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )

    # Timestamps beyond Base's created_at / updated_at.
    adopted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    submitter: Mapped["User | None"] = relationship(foreign_keys=[submitter_id])

    __table_args__ = (
        CheckConstraint(
            f"length(title) BETWEEN 1 AND {TITLE_MAX_LENGTH}",
            name="ck_dev_requests_title_length",
        ),
        CheckConstraint(
            f"length(body) BETWEEN 1 AND {BODY_MAX_LENGTH}",
            name="ck_dev_requests_body_length",
        ),
        CheckConstraint(
            f"done_when IS NULL OR length(done_when) BETWEEN 1 AND {DONE_WHEN_MAX_LENGTH}",
            name="ck_dev_requests_done_when_length",
        ),
        CheckConstraint(
            "content_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_dev_requests_content_sha256",
        ),
        CheckConstraint(
            f"status IN ({_sql_in(DEV_REQUEST_STATUSES)})",
            name="ck_dev_requests_status",
        ),
        CheckConstraint(
            f"target = '{DEV_REQUEST_TARGET}'",
            name="ck_dev_requests_target",
        ),
        CheckConstraint(
            f"priority IS NULL OR priority IN ({_sql_in(DEV_REQUEST_PRIORITIES)})",
            name="ck_dev_requests_priority",
        ),
        CheckConstraint(
            f"source IN ({_sql_in(DEV_REQUEST_SOURCES)})",
            name="ck_dev_requests_source",
        ),
        CheckConstraint(
            "(source = 'fault') = (fault_signature IS NOT NULL)",
            name="ck_dev_requests_fault_signature",
        ),
        # `poll`: non-terminal rows, oldest first.
        Index("ix_dev_requests_status_created", "status", "created_at"),
        Index("ix_dev_requests_submitter", "submitter_id"),
        # FR-20: at most one open row per fault signature. An index, not a
        # read-then-insert check, so two racing `open-fault` calls cannot
        # both insert.
        Index(
            "ux_dev_requests_open_fault_signature",
            "fault_signature",
            unique=True,
            postgresql_where=text(
                f"fault_signature IS NOT NULL AND status NOT IN ({_sql_in(TERMINAL_STATUSES)})"
            ),
        ),
    )

    def __repr__(self) -> str:
        return self.get_repr(["id", "submitter_id", "status", "source"])
