"""Discrimination suite for tools/stale-pointer-check.py (stptr1).

Proof artifact, not a CI gate. Copies the repo's own tracked Markdown and
`_devx/workstreams/` tree into a scratch git repo, plants one mutation per
case, and checks the guard's exit code.

Usage: python3 tools/stale-pointer-check.suite.py
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUARD = ROOT / "tools/stale-pointer-check.py"
WS = "_devx/workstreams/rotation-self-heal"

FLAT = "_devx/workstreams/rotation-self-heal/plan.md"
MIGRATED = "_devx/workstreams/rotation-self-heal/plan/agent.md"


def build(tmp):
    """A scratch git repo holding the repo's md files + workstream tree."""
    files = subprocess.run(["git", "ls-files", "*.md"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    for rel in files:
        dst = tmp / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dst)
    for d in (ROOT / "_devx/workstreams").iterdir():
        if d.is_dir():
            shutil.copytree(d, tmp / "_devx/workstreams" / d.name, dirs_exist_ok=True)
    (tmp / "tools").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "tools/stale-pointer-allowlist.txt", tmp / "tools/stale-pointer-allowlist.txt")
    subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp, check=True)


def allow(tmp, entry):
    p = tmp / "tools/stale-pointer-allowlist.txt"
    with p.open("a") as fh:
        fh.write(entry + "\n")


def newspec(body):
    def f(tmp):
        (tmp / "dev").mkdir(exist_ok=True)
        (tmp / "dev/dev-newspec-2026-09-22T18:00-written-after-the-rename.md").write_text(body)
        subprocess.run(["git", "add", "-A"], cwd=tmp, check=True)
    return f


CASES = [
    ("0  repo as-is", None, 0),
    ("1  0a's real case: NEW spec, flat path in Technical notes",
     newspec(f"---\nhash: newspec\n---\n\n## Technical notes\n\nFull context: plan `{FLAT}` §Phase 2.\n"), 1),
    ("2  bare form, no _devx/ prefix",
     newspec("---\nhash: newspec\n---\n\n## Technical notes\n\nSee `rotation-self-heal/plan.md` §Phase 2.\n"), 1),
    ("3  EXEMPT: same stale path inside a Status log",
     newspec(f"---\nhash: newspec\n---\n\n## Status log\n\n- 2026-07-27 — stage PLAN. Artifacts: `{FLAT}`.\n"), 0),
    ("4  EXEMPT: evals record the drill has yet to produce",
     newspec("---\nhash: newspec\n---\n\n## Technical notes\n\nRecord: `_devx/workstreams/rotation-self-heal/evals/E-drill-rotation.md`.\n"), 0),
    ("5  EXEMPT: allowlisted line",
     lambda tmp: (newspec(f"---\nhash: newspec\n---\n\n## Technical notes\n\nFull context: `{FLAT}`.\n")(tmp),
                  allow(tmp, "dev/dev-newspec-2026-09-22T18:00-written-after-the-rename.md:7:deliberate, quoting the old layout")), 0),
    ("6  not-yet-migrated artifact (flat file still exists)",
     lambda tmp: ((tmp / WS / "expectations.md").exists() and
                  newspec("---\nhash: newspec\n---\n\n## Technical notes\n\nSee `_devx/workstreams/rotation-self-heal/expectations.md`.\n")(tmp)), 0),
    ("7  unknown slug is not our business",
     newspec("---\nhash: newspec\n---\n\n## Technical notes\n\nSee `some-other-thing/plan.md`.\n"), 0),
    ("8  pointer to the migrated path itself",
     newspec(f"---\nhash: newspec\n---\n\n## Technical notes\n\nFull context: `{MIGRATED}` §Phase 2.\n"), 0),
    ("9  COVERAGE: workstream tree emptied -> exit 2, not a silent pass",
     lambda tmp: shutil.rmtree(tmp / "_devx/workstreams/rotation-self-heal") or
                 shutil.rmtree(tmp / "_devx/workstreams/browser-qa-agent"), 2),
    ("10 COVERAGE: references renamed away -> exit 2",
     lambda tmp: [p.write_text(p.read_text().replace("rotation-self-heal", "x-ws").replace("browser-qa-agent", "y-ws"))
                  for p in tmp.rglob("*.md")] and None, 2),
]

ok = True
for label, mut, want in CASES:
    tmp = Path(tempfile.mkdtemp())
    try:
        build(tmp)
        if mut:
            mut(tmp)
        r = subprocess.run([sys.executable, str(GUARD)], cwd=tmp, capture_output=True, text=True)
        good = r.returncode == want
        ok &= good
        summary = next((l for l in r.stdout.splitlines() if l.startswith("stale-pointer-check:")), "")
        print(f"{'PASS' if good else '*** WRONG ***':13s} exit={r.returncode} want={want}  {label}")
        print(f"                 {summary}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
print(f"\n{'ALL AS EXPECTED' if ok else 'SUITE FAILED'} ({len(CASES)} cases)")
sys.exit(0 if ok else 1)
