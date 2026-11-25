#!/usr/bin/env bash
# run_flutter_eval.sh — shared runner for shake-to-report's Flutter-backed
# P0 evals (plan f89791). Each evals/E-*.sh wrapper pins this file's sha256
# and its own test file's; this file pins the harness's. So Gate 4's lock
# on a wrapper covers everything the wrapper runs.
#
# Usage: run_flutter_eval.sh <E-id> <test path, relative to evals/> <test sha256> <min tests>
#
# Exit codes — what Gate 4 and a human must read:
#   0  GREEN  — every test passed, and at least <min tests> ran.
#   1  RED    — every failing test failed an ASSERTION whose message carries
#               a `SHAKE-RED[...]` marker naming the missing behavior, and
#               every `control:` test passed.
#   3  EVAL-TAMPERED / EVAL-BLIND / EVAL-WRONG-REASON — the eval is broken,
#               edited, or cannot see: a pinned file changed; a `control:`
#               test failed (the harness cannot boot the app, deliver motion,
#               find a prompt or find the sheet); a compile or load error; an
#               exception rather than an assertion; an unmarked failure; a
#               skip; fewer tests than declared.
#
# Why the marker rule: on unbuilt code a test can fail for a reason that has
# nothing to do with the feature (a harness bug, a renamed widget). Counting
# that as RED would make the gate watch the wrong failure. Only a failure the
# eval author named in advance counts.
#
# The test files live outside the app/ package on purpose: CI's `flutter
# test` collects app/test/ only, so RED files here never redden the shared
# gate. The phase that turns an eval green adds it to CI's Flutter job.
set -uo pipefail

EID="${1:?E-id}"; TEST_REL="${2:?test path}"; TEST_SHA="${3:?test sha256}"; MIN_TESTS="${4:?min tests}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EVALS="$(cd "$HERE/.." && pwd)"
REPO="$(cd "$HERE/../../../../.." && pwd)"
HARNESS_REL="flutter/shake_harness.dart"
HARNESS_SHA="452beace78586bac7fe5aba1519deee24817dab0309e003df327976ff60b9244"

sha256_of() { python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1"; }

for pair in "$TEST_REL=$TEST_SHA" "$HARNESS_REL=$HARNESS_SHA"; do
  rel="${pair%%=*}"; want="${pair#*=}"
  if [[ ! -f "$EVALS/$rel" ]]; then
    echo "EVAL-TAMPERED $EID: evals/$rel is missing"; exit 3
  fi
  got="$(sha256_of "$EVALS/$rel")"
  if [[ "$got" != "$want" ]]; then
    echo "EVAL-TAMPERED $EID: evals/$rel sha256 $got != pinned $want — fix the code, not the eval; a genuinely wrong eval is 'devx revise'"
    exit 3
  fi
done

if ! command -v flutter >/dev/null 2>&1; then
  echo "EVAL-WRONG-REASON $EID: flutter is not on PATH"; exit 3
fi
cd "$REPO/app" || { echo "EVAL-WRONG-REASON $EID: cannot cd to app/"; exit 3; }

EVENTS="$(mktemp "${TMPDIR:-/tmp}/shake-eval-XXXXXX")"
trap 'rm -f "$EVENTS"' EXIT
flutter test --reporter json "$EVALS/$TEST_REL" > "$EVENTS" 2>&1
FLUTTER_RC=$?

python3 - "$EID" "$EVENTS" "$FLUTTER_RC" "$MIN_TESTS" <<'PY'
import json, re, sys

eid, path, rc, min_tests = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
names, hidden, errors, results, prints = {}, set(), {}, {}, {}
saw_done = False
for line in open(path, encoding="utf-8", errors="replace"):
    line = line.strip()
    if not line.startswith("{"):
        continue
    try:
        ev = json.loads(line)
    except ValueError:
        continue
    t = ev.get("type")
    if t == "testStart":
        names[ev["test"]["id"]] = ev["test"]["name"]
    elif t == "error":
        errors.setdefault(ev["testID"], []).append((ev.get("isFailure", False), ev.get("error", "")))
    elif t == "print":
        prints.setdefault(ev["testID"], []).append(ev.get("message", ""))
    elif t == "testDone":
        if ev.get("hidden"):
            hidden.add(ev["testID"])
        results[ev["testID"]] = ("skipped" if ev.get("skipped") else ev.get("result"))
    elif t == "done":
        saw_done = True

def first_line(s):
    return (s.strip().splitlines() or [""])[0][:300]

# A hidden test is the loader. If it errored, the file never compiled or
# never loaded, so no assertion ran.
for tid in hidden:
    if results.get(tid) != "success":
        msg = " | ".join(first_line(e) for _, e in errors.get(tid, [])) or "no message"
        print(f"EVAL-WRONG-REASON {eid}: test file did not load (flutter exit {rc}): {msg}")
        sys.exit(3)
if not saw_done:
    print(f"EVAL-WRONG-REASON {eid}: flutter test did not finish (exit {rc}); no 'done' event")
    sys.exit(3)

visible = [tid for tid in results if tid not in hidden]
tests = len(visible)
blind, wrong, red, passed = [], [], [], 0
for tid in visible:
    name, res = names.get(tid, f"#{tid}"), results[tid]
    for p in prints.get(tid, []):
        if p.startswith("SHAKE-DIAG"):
            print(f"  {p}  [{name}]")
    if res == "success":
        passed += 1
        continue
    errs = errors.get(tid, [])
    if name.startswith("control:"):
        blind.append(f"{name}: {res}: " + " | ".join(first_line(e) for _, e in errs))
        continue
    if res == "skipped":
        wrong.append(f"{name}: skipped")
        continue
    # A failure is described either by an error event (plain `test`) or, in
    # `testWidgets`, by a framework dump printed as
    # "The following <Type> was thrown running a test:" followed by a
    # generic, non-failure "Test failed. See exception logs above." error.
    # Every description must be an assertion (TestFailure) whose message
    # carries a SHAKE-RED marker; anything else is the wrong reason.
    described = []
    for p in prints.get(tid, []):
        if "EXCEPTION CAUGHT BY FLUTTER TEST FRAMEWORK" in p:
            m = re.search(r"The following (\S+) was thrown", p)
            described.append((bool(m) and m.group(1) == "TestFailure",
                              m.group(1) if m else "unknown", p))
    for is_failure, e in errs:
        if not is_failure and described and e.startswith("Test failed. See exception logs above."):
            continue
        described.append((is_failure, "TestFailure" if is_failure else "error", e))
    markers = []
    for is_assertion, kind, text in described:
        if not is_assertion:
            wrong.append(f"{name}: {kind}, not an assertion: {first_line(text.split('thrown running a test:')[-1])}")
            break
        i = text.find("SHAKE-RED[")
        if i < 0:
            wrong.append(f"{name}: unmarked assertion: {first_line(text.split('thrown running a test:')[-1])}")
            break
        markers.append(text[i:text.find("]", i) + 1])
    else:
        if markers:
            red.append(f"{name} -> {', '.join(markers)}")
        else:
            wrong.append(f"{name}: {res} with no description of the failure")

print(f"EVAL {eid}: tests={tests} passed={passed} red={len(red)} blind={len(blind)} wrong={len(wrong)} flutter_exit={rc}")
if blind:
    for b in blind:
        print(f"EVAL-BLIND {eid}: {b}")
    sys.exit(3)
if wrong:
    for w in wrong:
        print(f"EVAL-WRONG-REASON {eid}: {w}")
    sys.exit(3)
if tests < min_tests:
    print(f"EVAL-WRONG-REASON {eid}: {tests} tests ran, the eval declares {min_tests}")
    sys.exit(3)
if red:
    for r in red:
        print(f"EVAL-RED {eid}: {r}")
    sys.exit(1)
print(f"EVAL-GREEN {eid}")
sys.exit(0)
PY
