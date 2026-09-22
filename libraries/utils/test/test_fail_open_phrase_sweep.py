"""Source sweep: no fail-open path may exist without the phrase `failing open`.

This is the enforcement half of dfrcp1's G11 CloudWatch metric filter
(`terraform/environments/prod/alarm_fail_open.tf`). The filter matches the
literal phrase in the API log group, which makes the phrase a contract: a
fail-open path that doesn't emit it is invisible to the only detector that
exists for it. `/v1/health` answers 200 while failing open, so nothing else
— not the container health check, not `curl -sf`, not an uptime monitor —
can tell the difference.

WHY THIS EXISTS ALONGSIDE selfheal1's TESTS. They fail on different mistakes:

  * `test_db_probe.py::test_every_fail_open_verdict_logs_failing_open` (and
    `test_probe_sync_survives_a_classifier_failure_on_an_absent_url`) DRIVE
    the paths they know about and assert the phrase comes out. They catch a
    reword of an existing branch.
  * This sweep ENUMERATES the source and asserts no fail-open site lacks the
    phrase. It catches the next branch — one added months from now whose
    author writes "continuing despite probe error". Every driving test stays
    green in that case, and the alarm silently under-covers.

That is not hypothetical: selfheal1 found `probe_sync`'s absent-URL path
returning a fail-open verdict while emitting no phrase at all, and the
existing suite was green, because it only drove the paths it knew about.

ANCHOR ON VERDICTS, NOT ON LOG CALLS. "Which paths are fail-open" is not
decidable from log statements — that's circular, since the missing log line
is what we're hunting. It IS decidable from the verdict: every
`ProbeVerdict` member except OK and AUTH_FAILED means "we could not tell,
so we're staying up". Reading the members from the enum (rather than listing
them here) means a new verdict is covered the day it's added, with no edit
to this file.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from utils.services.db_probe import ProbeVerdict

#: The phrase the CloudWatch metric filter matches. Changing it here without
#: changing `alarm_fail_open.tf` (and vice versa) silently deletes the alarm's
#: coverage, which is the failure this test exists to prevent.
PHRASE = "failing open"

#: Verdicts that mean "we could not confirm a problem, so we stay up".
#: Derived from the enum so a new member is covered automatically.
FAIL_OPEN_VERDICTS = frozenset(
    member.name for member in ProbeVerdict if member.name not in {"OK", "AUTH_FAILED"}
)

#: Every file that decides a fail-open verdict. A file listed here that does
#: not exist is an error, not a skip: a silent skip is how a sweep stops
#: sweeping without anyone noticing.
SOURCE_FILES = (
    "libraries/utils/utils/services/db_probe.py",
    "services/api/src/routers/v1/health_router.py",
)


def _repo_root() -> Path:
    """Walk up to the repository root (the directory holding `.git`)."""
    for candidate in Path(__file__).resolve().parents:
        if (candidate / ".git").exists():
            return candidate
    raise RuntimeError("repository root not found — cannot run the source sweep")


def _verdict_name(node: ast.AST) -> str | None:
    """Return `X` for an expression spelled `ProbeVerdict.X`, else None."""
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "ProbeVerdict"
    ):
        return node.attr
    return None


def _statement_settles_fail_open(stmt: ast.stmt) -> str | None:
    """Return the verdict name if this statement settles on a fail-open one.

    Two shapes count, because both decide the outcome:
      * `return ProbeVerdict.UNKNOWN`   (db_probe)
      * `verdict = ProbeVerdict.UNKNOWN` (health_router's except block)
    """
    value: ast.expr | None = None
    if isinstance(stmt, ast.Return | ast.Assign | ast.AnnAssign):
        value = stmt.value

    if value is None:
        return None
    name = _verdict_name(value)
    return name if name in FAIL_OPEN_VERDICTS else None


def _block_emits_phrase(body: list[ast.stmt], upto: int) -> bool:
    """True if any statement before `upto` in this block contains the phrase.

    Scope is the block, not the function: a fail-open branch logs its reason
    immediately before settling the verdict, and a phrase emitted in some
    *other* branch of the same function says nothing about this one.

    Only statements AT this block's level count. Descending into nested
    branches would accept a phrase logged in one arm of an earlier `if` as
    cover for a path that never logs at all — a false pass, which is the one
    outcome a guard must never produce.
    """
    for stmt in body[:upto]:
        if not isinstance(stmt, ast.Expr):
            continue
        for node in ast.walk(stmt):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and PHRASE in node.value
            ):
                return True
    return False


def _fail_open_sites_missing_phrase(tree: ast.AST) -> list[tuple[int, str]]:
    """Every fail-open site in `tree` whose own block never says the phrase."""
    offenders: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(node, field, None)
            if not isinstance(block, list):
                continue
            for index, stmt in enumerate(block):
                verdict = _statement_settles_fail_open(stmt)
                if verdict is None:
                    continue
                # `upto=index + 1` so a one-liner that both logs and returns
                # still counts, and so the log may sit on the same statement.
                if not _block_emits_phrase(block, index + 1):
                    offenders.append((stmt.lineno, verdict))

    return offenders


@pytest.mark.parametrize("relative_path", SOURCE_FILES)
def test_every_fail_open_site_emits_the_phrase(relative_path: str) -> None:
    """No fail-open verdict is settled without `failing open` in its block."""
    path = _repo_root() / relative_path
    assert path.exists(), (
        f"{relative_path} is listed in SOURCE_FILES but does not exist. "
        "If the file moved, update SOURCE_FILES — do not delete the entry, "
        "or the sweep stops covering that file silently."
    )

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders = _fail_open_sites_missing_phrase(tree)

    assert not offenders, (
        f"{relative_path} settles a fail-open verdict without logging "
        f"{PHRASE!r} in the same block: "
        + ", ".join(f"line {line} ({verdict})" for line, verdict in offenders)
        + ". The CloudWatch metric filter in "
        "terraform/environments/prod/alarm_fail_open.tf matches that phrase, "
        "and /v1/health returns 200 while failing open — a branch without the "
        "phrase is undetectable in production."
    )


def test_the_sweep_can_fail() -> None:
    """The sweep must reject a fail-open site whose block never says it.

    Without this, a bug that makes `_fail_open_sites_missing_phrase` return
    `[]` unconditionally would leave every assertion above passing, and the
    sweep would be decoration.
    """
    verdict = next(iter(sorted(FAIL_OPEN_VERDICTS)))
    source = f"""
def probe():
    try:
        connect()
    except Exception:
        logger.exception("db probe: continuing despite probe error")
        return ProbeVerdict.{verdict}
"""
    offenders = _fail_open_sites_missing_phrase(ast.parse(source))
    assert [v for _, v in offenders] == [verdict]


def test_the_sweep_accepts_a_phrased_site() -> None:
    """And it must accept the same site once the phrase is present."""
    verdict = next(iter(sorted(FAIL_OPEN_VERDICTS)))
    source = f"""
def probe():
    try:
        connect()
    except Exception:
        logger.exception("db probe: classifier raised — {PHRASE}")
        return ProbeVerdict.{verdict}
"""
    assert _fail_open_sites_missing_phrase(ast.parse(source)) == []


def test_fail_open_verdicts_are_derived_not_hardcoded() -> None:
    """Guard the guard: OK and AUTH_FAILED are the only non-fail-open ones.

    If someone adds a verdict that should NOT be treated as fail-open, this
    test is where that decision gets recorded — deliberately, rather than by
    the sweep quietly widening.
    """
    assert FAIL_OPEN_VERDICTS, "no fail-open verdicts found — enum changed shape?"
    assert "OK" not in FAIL_OPEN_VERDICTS
    assert "AUTH_FAILED" not in FAIL_OPEN_VERDICTS
    assert "UNKNOWN" in FAIL_OPEN_VERDICTS
    assert "UNREACHABLE" in FAIL_OPEN_VERDICTS
