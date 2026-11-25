#!/usr/bin/env python3
"""stptr1 — CI guard against stale pointers to migrated workstream artifacts.

A rename sweep can only rewrite files that exist when it runs. Two classes
escape it, and the second is why this guard exists:

  1. a file the sweep didn't cover;
  2. a file written AFTER the rename from an older template. Because the
     file is new, git has nothing to conflict against, so the stale pointer
     merges silently. (Found by palateful-0a: `rsh109b` in #46 carried a
     flat-era `plan.md` path after commit 64c8b7f5 moved those artifacts.)

Fails when a Markdown file points at `_devx/workstreams/<slug>/<artifact>.md`
while the migrated form `_devx/workstreams/<slug>/<artifact>/agent.md`
exists on disk. That is a pointer to a file that has moved.

EXEMPTIONS

  * `## Status log` sections. Those lines are append-only history recording
    where an artifact was at the time; rewriting them would make the log
    assert a layout that did not exist when it was written. Exempting by
    *section* rather than by an inline marker matters: an inline escape
    comment would force an edit to the very lines the convention protects.
  * any path under `evals/` — specs legitimately reference eval records a
    drill has yet to produce (e.g. `evals/E-drill-rotation.md`). Scoped to
    the directory, not to an `E-*` filename prefix: the directory is the
    convention, the prefix is a proxy for it, and a proxy would silently
    skip a stale pointer in any future `E-*.md` living elsewhere.
  * `tools/stale-pointer-allowlist.txt`, format `file:lineno:rationale`,
    for anything else deliberate. A file, not an inline comment, for the
    same reason.

COVERAGE

Prints what it scanned and fails with exit 2 on an implausible count. A
guard that silently matches nothing passes exactly as loudly as one that
matches everything — which is the failure mode this guard is guarding
against.

Exit: 0 clean, 1 stale pointers found, 2 tooling/coverage error.
"""
import re
import subprocess
import sys
from pathlib import Path

WS_ROOT = Path("_devx/workstreams")
ALLOWLIST = Path("tools/stale-pointer-allowlist.txt")
# `_devx/workstreams/<slug>/<artifact>.md`, or the bare `<slug>/<artifact>.md`
# form used in prose, which we only trust when <slug> is a real workstream.
REF = re.compile(r"(?:_devx/workstreams/)?([a-z0-9][a-z0-9-]*)/([A-Za-z0-9._-]+)\.md")
# The already-migrated form. Counted purely for coverage: it proves the
# scanner sees the healthy pointer population, not just stale-shaped hits.
# Without it a clean run could mean "nothing is stale" or "I matched almost
# nothing", and those must not look alike.
MIGRATED_REF = re.compile(r"(?:_devx/workstreams/)?([a-z0-9][a-z0-9-]*)/([A-Za-z0-9._-]+)/agent\.md")
MIN_FILES, MIN_REFS = 20, 15


def load_allowlist():
    allowed = set()
    if not ALLOWLIST.is_file():
        return allowed
    for raw in ALLOWLIST.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Two hazards in this repo, pulling in opposite directions:
        #   * paths contain colons — spec filenames carry timestamps
        #     (`…2026-09-22T18:00-…`) — so splitting on the FIRST colon lands
        #     inside the timestamp;
        #   * rationales cite line numbers (`see ci.yml:748: for …`), so
        #     anchoring on the LAST `:<digits>:` swallows the path into the
        #     rationale and silently allowlists a file that doesn't exist.
        # Lazy `.+?` stops at the first `:<digits>:`, which a timestamp cannot
        # produce (`T18:00-` has no colon after the digits). The `.md` check
        # then makes any remaining mis-split loud instead of silent: a
        # mis-parsed entry exempts nothing, and the symptom would otherwise be
        # "my allowlist entry is ignored" rather than "this line is malformed".
        m = re.match(r"^(?P<file>.+?):(?P<line>\d+):(?P<why>.*)$", line)
        if not m or not m.group("file").strip().endswith(".md"):
            print(f"stale-pointer-check: malformed allowlist line (expected "
                  f"`<path>.md:<lineno>:<rationale>`): {raw}", file=sys.stderr)
            sys.exit(2)
        allowed.add((m.group("file").strip(), int(m.group("line"))))
    return allowed


def main():
    if not WS_ROOT.is_dir():
        print(f"stale-pointer-check: {WS_ROOT} not found (run from the repo root)", file=sys.stderr)
        return 2
    slugs = {p.name for p in WS_ROOT.iterdir() if p.is_dir()}
    if not slugs:
        print(f"stale-pointer-check: no workstreams under {WS_ROOT}", file=sys.stderr)
        return 2
    allowed = load_allowlist()

    files = subprocess.run(["git", "ls-files", "*.md"], capture_output=True, text=True, check=True).stdout.split()
    scanned = refs = ok = skipped_log = skipped_evals = skipped_allow = 0
    bad = []

    for rel in files:
        p = Path(rel)
        try:
            lines = p.read_text().splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        scanned += 1
        section = ""
        for n, line in enumerate(lines, 1):
            if line.startswith("#"):
                section = line.lower()
            for m in MIGRATED_REF.finditer(line):
                if m.group(1) in slugs:
                    refs += 1
                    ok += 1
            for m in REF.finditer(line):
                slug, artifact = m.group(1), m.group(2)
                if slug not in slugs or artifact == "agent":
                    continue
                refs += 1
                flat = WS_ROOT / slug / f"{artifact}.md"
                migrated = WS_ROOT / slug / artifact / "agent.md"
                if "/evals/" in m.group(0):
                    skipped_evals += 1
                    continue
                if "status log" in section:
                    skipped_log += 1
                    continue
                if (rel, n) in allowed:
                    skipped_allow += 1
                    continue
                if flat.is_file():
                    ok += 1
                elif migrated.is_file():
                    bad.append((rel, n, m.group(0), str(migrated)))
                else:
                    ok += 1  # dangling for some other reason; not this guard's job

    for rel, n, ref, target in bad:
        print(f"{rel}:{n}: stale pointer `{ref}` — that artifact moved to `{target}`. "
              f"Update the path, or if the line is deliberate history, add `{rel}:{n}:<reason>` "
              f"to {ALLOWLIST}.", file=sys.stderr)

    print(f"stale-pointer-check: {scanned} markdown files, {refs} workstream references "
          f"({ok} resolve, {len(bad)} stale; skipped {skipped_log} status-log, "
          f"{skipped_evals} evals, {skipped_allow} allowlisted)")

    if scanned < MIN_FILES or refs < MIN_REFS:
        print(f"stale-pointer-check: implausible coverage (files={scanned} < {MIN_FILES} or "
              f"refs={refs} < {MIN_REFS}) — the guard is probably not matching anything. "
              f"Failing rather than passing silently.", file=sys.stderr)
        return 2
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
