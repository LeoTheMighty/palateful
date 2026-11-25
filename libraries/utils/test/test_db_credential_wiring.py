"""E-6 (P0) — RED artifact, the call-site half (T6.3b), owned by rsh106.

Split verbatim out of `test_db_credential_provider.py` by rsh105. That
file's provider / retry / inert-path tests went GREEN with rsh105, which
by design wires **zero** call sites; the two tests below assert the call
sites rsh106 adds, so they stay RED until rsh106 lands and are
registered in `tools/red-artifacts.txt` under rsh106. The assertions are
unchanged — only their file moved, so the registry (which is
file-granular) can keep them out of default collection without also
hiding the tests that now pass.

The runtime half of T6.3b —
`test_real_engine_modules_are_inert_when_arn_unset` — stays in
`test_db_credential_provider.py`: it is already GREEN and is only
meaningful alongside these.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

AGENT_ENGINE_SITES = (
    Path(__file__).resolve().parents[2] / "agent" / "agent" / "runner.py",
    Path(__file__).resolve().parents[2] / "agent" / "agent" / "tasks.py",
)


def test_database_module_registers_all_three_of_its_engine_sites():
    """The other half of "inert": wired, but off.

    A module that never calls `register_rotating_credentials` also
    reports 0 listeners — so the zero-listener assertion above is only
    meaningful alongside proof the call sites exist. Source-level, because
    with the ARN unset there is by construction nothing at runtime to
    observe.
    """
    source = (
        Path(__file__).resolve().parents[1]
        / "utils"
        / "services"
        / "database.py"
    ).read_text()
    count = source.count("register_rotating_credentials")
    assert count >= 3, (
        f"expected all three long-lived engine sites in database.py "
        f"(db_engine, async engine, error_log_engine) to register; found "
        f"{count} reference(s)"
    )


@pytest.mark.parametrize("site", AGENT_ENGINE_SITES, ids=lambda p: p.name)
def test_agent_engine_sites_register_too(site):
    """`libraries/agent` is the easy miss (plan.md:681-687).

    `runner.py` and `tasks.py` each build their own engine, lazily,
    inside `_get_session_factory()` — so there is no import-time engine to
    inspect, and the package is not installed in the `libraries/utils`
    venv. Asserted at the source level here; Phase 6's T6.3 enumeration
    guard is what makes it run under the `agent` project's own test
    target.
    """
    assert site.exists(), f"{site} not found"
    tree = ast.parse(site.read_text(), filename=str(site))
    names = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    } | {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    assert "register_rotating_credentials" in names, (
        f"{site.name} builds a long-lived engine but never registers rotating "
        f"credentials — after a rotation this engine keeps failing while the "
        f"rest of the fleet self-heals"
    )
