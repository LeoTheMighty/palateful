"""Route path redaction + validation helpers.

Client-emitted telemetry (`POST /v1/client-latencies`, cla-1b) sends a
`route` string per event. To keep the column's cardinality bounded
(it's the grouping key for the dashboard) and to avoid leaking raw
identifiers into an append-only table, routes MUST be redacted *before*
ingest.

The client redacts proactively (`app/lib/core/router/route_redaction.dart`,
cla-4). This module is the server-side backstop: any event whose route
still contains a raw UUID or long numeric id is rejected with 422.
Defense in depth — the client can't regress redaction without the
server shouting.

Design:
- `is_route_redacted(route)` — True if every path segment is either a
  literal word, a short numeric, a `:name` / `{name}` template
  placeholder, or empty. Returns False on any UUID-shaped segment or
  numeric segment of length ≥ 4 (the smallest realistic raw-id length
  in this codebase).
- `redact_route(route)` — conservative inverse: replace any UUID or
  long-numeric segment with `:id`. Not used on the hot path (the
  client redacts) but handy in tests and for future ops tooling.

A route missing entirely (`None` or empty string) is treated as
"redacted" — some event types (cold-start, MetricKit payloads) have no
route at all, and we don't want to reject them here.

Lives under `api/v1/client_latency/` rather than a top-level `utils/`
helper on purpose: the service already uses the `utils` namespace for
the `libraries/utils` package, and a `src/utils/` folder would shadow
that package under the test harness's sys.path.
"""

from __future__ import annotations

import re

# Full-shape UUID: 8-4-4-4-12 hex groups. Case-insensitive.
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

# Four or more digits — anything shorter is assumed to be a real path
# token (versioning, pagination, legit small number). Catches DB
# integer PKs which start at 1 and grow monotonically.
_NUMERIC_ID_RE = re.compile(r"^\d{4,}$")


def is_route_redacted(route: str | None) -> bool:
    """Return True if `route` has no raw UUID or long-numeric segments.

    A None or empty value is considered redacted — callers that forbid
    empty routes must enforce that elsewhere (the client-latency ingest
    allows a null route for app_start / MetricKit events).
    """
    if not route:
        return True

    # Strip query string and anchor — we only inspect the path.
    path = route.split("?", 1)[0].split("#", 1)[0]

    for segment in path.split("/"):
        if not segment:
            continue
        if segment[0] in (":", "{"):
            # Template placeholder (`:id` or `{id}`) — already redacted.
            continue
        if _UUID_RE.match(segment):
            return False
        if _NUMERIC_ID_RE.match(segment):
            return False
    return True


def redact_route(route: str | None) -> str | None:
    """Replace UUID / long-numeric segments with `:id`.

    Pass-through on None / empty. Query and fragment are stripped.
    Used by tests and ops scripts; the hot path relies on
    `is_route_redacted` + client-side redaction.
    """
    if not route:
        return route

    path = route.split("?", 1)[0].split("#", 1)[0]
    redacted_segments: list[str] = []
    for segment in path.split("/"):
        if not segment:
            redacted_segments.append(segment)
            continue
        if segment[0] in (":", "{"):
            redacted_segments.append(segment)
            continue
        if _UUID_RE.match(segment) or _NUMERIC_ID_RE.match(segment):
            redacted_segments.append(":id")
            continue
        redacted_segments.append(segment)
    return "/".join(redacted_segments)
