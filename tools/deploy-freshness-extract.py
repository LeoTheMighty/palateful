#!/usr/bin/env python3
"""Extract a step's `run:` body out of .github/workflows/deploy-freshness.yml.

Shared by `deploy-freshness-self-test.sh` (runs it against mocked AWS) and
`deploy-freshness-live-check.sh` (runs it against real AWS). Both must run the
SHIPPED bash, never a copy: a copy drifts silently and both tools would go on
passing against code that is no longer deployed.

Deliberately dependency-free (no PyYAML) — the CI `lint` job that runs the
self-test has no guaranteed poetry env. Indentation-based and strict: a
structural change to the workflow breaks this loudly rather than yielding a
stale script.

Usage: deploy-freshness-extract.py <workflow.yml> <step name> <out path>
Exit:  0 written, non-zero with a message on any structural mismatch.
"""

import sys


def main() -> None:
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    path, step_name, out = sys.argv[1], sys.argv[2], sys.argv[3]
    with open(path) as fh:
        lines = fh.read().splitlines()

    # Find "- name: <step_name>", then the "run: |" that follows it, then take
    # the block of lines indented deeper than the "run:" key.
    try:
        i = next(
            n for n, line in enumerate(lines) if line.strip() == f"- name: {step_name}"
        )
    except StopIteration:
        sys.exit(f"EXTRACT FAIL: no step named {step_name!r} in {path}")

    try:
        j = next(
            n
            for n in range(i + 1, len(lines))
            if lines[n].strip() in ("run: |", "run: |-")
        )
    except StopIteration:
        sys.exit(f"EXTRACT FAIL: step {step_name!r} has no literal-block `run:`")

    run_indent = len(lines[j]) - len(lines[j].lstrip())
    body, body_indent = [], None
    for line in lines[j + 1 :]:
        if not line.strip():
            body.append("")
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= run_indent:
            break
        if body_indent is None:
            body_indent = indent
        body.append(line[body_indent:])

    if not [b for b in body if b.strip()]:
        sys.exit(f"EXTRACT FAIL: empty run block for {step_name!r}")

    with open(out, "w") as fh:
        fh.write("\n".join(body).rstrip() + "\n")
    print(f"extracted {len([b for b in body if b.strip()])} lines from {path}")


if __name__ == "__main__":
    main()
