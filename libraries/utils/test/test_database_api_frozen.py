"""Frozen sync Database public API (aam-2).

During the async migration the sync `Database` surface MUST NOT change:
services/worker + services/parser + ops scripts + manage.py all import
from it, and every one of them is a blocking consumer. This test locks
the class's public signature against unintentional drift.

If this test fails, either:
1. You meant to change the sync API — update the golden snapshot below
   AND re-run worker + parser test suites AND make sure the scripts in
   services/api/scripts/ still run (bin/prod-script <script>.py).
2. You didn't mean to — revert the change, add the behavior to
   AsyncDatabase instead, or follow up with the post-cutover cleanup
   epic.
"""

import inspect

from utils.services.database import Database


# Golden snapshot of the sync Database public surface at aam-2 landing
# (2026-04-23). Methods listed here are the stable contract.
_EXPECTED_PUBLIC_METHODS = {
    "find_by": "(self, model_class, desc: str | list | None = None, asc: str | list | None = None, include_archived: bool | None = False, **kwargs)",
    "find_or_create_by": "(self, model_class, defaults: dict | None = None, desc: str | list | None = None, asc: str | list | None = None, include_archived: bool | None = False, **kwargs)",
    "where": "(self, model, desc: str | list | None = None, asc: str | list | None = None, include_archived: bool | None = False, **kwargs)",
    "create": "(self, model)",
    "create_all": "(self, models)",
    "update": "(self, model, **kwargs)",
    "update_all": "(self, models, **kwargs)",
    "bulk_update": "(self, query, **kwargs)",
    "find_and_bulk_update": "(self, model_class, updates: dict, include_archived: bool | None = False, **filters)",
    "save": "(self, model)",
    "save_all": "(self, models)",
    "delete": "(self, model)",
    "lock": "(self, key)",
    "close": "(self)",
}


def _method_signature(cls, name: str) -> str:
    method = getattr(cls, name)
    return str(inspect.signature(method))


def test_sync_database_public_methods_present():
    """Every frozen method must still exist on Database."""
    actual = {
        name
        for name, _ in inspect.getmembers(Database, predicate=inspect.isfunction)
        if not name.startswith("_")
    }
    missing = set(_EXPECTED_PUBLIC_METHODS) - actual
    extra = actual - set(_EXPECTED_PUBLIC_METHODS) - {"__init__"}
    # Missing is a hard failure — worker/scripts call these.
    assert not missing, (
        f"Sync Database public API drifted — missing methods: {sorted(missing)}. "
        "Worker/parser/scripts rely on these signatures."
    )
    # Extra public methods are allowed but flag them in the test output so
    # the reviewer decides whether to add to the frozen list.
    if extra:
        print(f"note: new public methods on Database: {sorted(extra)}")


def test_sync_database_signatures_match_frozen():
    """Each frozen method's signature must match the golden snapshot."""
    drift = []
    for name, expected in _EXPECTED_PUBLIC_METHODS.items():
        actual = _method_signature(Database, name)
        if actual != expected:
            drift.append(f"  {name}: expected {expected}, got {actual}")
    assert not drift, (
        "Sync Database signature drift detected:\n"
        + "\n".join(drift)
        + "\n\nIf the drift is intentional, update _EXPECTED_PUBLIC_METHODS in "
        "this test AND confirm worker/parser test suites still pass."
    )
