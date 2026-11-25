#!/usr/bin/env python3
"""Find catch blocks that neither surface nor report their exception.

Used by `tools/no-silent-catch-check.sh`. Prints one `path:lineno` per
offending catch block (path relative to the repo root), sorted, to stdout.

Why a scanner instead of the shell guard's `sed`-window: the window takes
the 40 lines after a catch header and accepts any safe token in them, so a
catch that swallows silently passes whenever the *next* function happens to
report (measured: `app/lib/features/shopping_cart/services/shopping_cart_service.dart`
passes on an `ErrorReporter.report(` 30 lines below, in a different method).
This walks the catch body's own braces instead, so a token only counts when
it is inside the block that caught.

Brace-matching is done on a version of the line with comments, string
literals and character escapes blanked out, because a `{` inside a string or
a `//` comment is not a block. Dart string interpolation (`${...}`) is
tracked so its braces are ignored too.

A safe token inside a NESTED catch does not rescue the catch that encloses
it: `try { … } catch (e) { debugPrint(e); try { … } catch (e2) {
ErrorReporter.report(e2); } }` swallows `e` however loudly it reports `e2`.
Nested catch bodies are therefore excised before the enclosing block is
searched. This shape is not hypothetical — `api_client.dart`'s 401
interceptor and `AuthService.logout()` are both built this way.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

# The union of acceptable recovery paths. Kept byte-identical in meaning to
# SAFE_TOKENS in tools/no-silent-catch-check.sh — change both together.
SAFE_TOKEN = re.compile(
    r"(rethrow|[^A-Za-z_]throw\s|showMutationFailureSnackbar\(|emitMutation\(|"
    r"ErrorReporter\.(report|reportPreAuth)\()"
)

# A catch clause in any layout `dart format` may or may not have
# imposed: `} catch (e) {`, `} on Foo catch (e) {`, a prefixed or generic
# type (`} on p.Foo<Bar> catch …`), `catch (e) {` alone on its own line,
# and the inline `try { … } catch (e) { … }`. Matching only the formatted
# norm left the last two as evasion paths, and CI has no
# `dart format --set-exit-if-changed` step to force the norm.
# `} on Foo {` with no `catch` binding counts too — it handles the
# exception without naming it, which is a swallow with fewer characters.
# (perf_flags_service.dart:92 is a live instance.)
CATCH_HEADER = re.compile(
    r"(^|\})\s*("
    r"on\s+[A-Za-z_][\w.]*(<[^<>]*>)?\s*(catch\s*\(|\{)"  # on Foo [catch (e)] {
    r"|catch\s*\("                                            # catch (e)
    r")"
)


def strip_noncode(line: str, state: dict) -> str:
    """Blank out comments and string bodies so only real code braces remain.

    `state` carries across lines: whether we are inside a block comment, and
    the interpolation/quote stack for multi-line strings.
    """
    out = []
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        nxt = line[i + 1] if i + 1 < n else ""

        if state["block_comment"]:
            if ch == "*" and nxt == "/":
                state["block_comment"] = False
                out.append("  ")
                i += 2
                continue
            out.append(" ")
            i += 1
            continue

        quote = state["quote"]
        if quote:
            # Inside a string literal. Escapes hide the next char; `${`
            # opens an interpolation where code (and braces) resume.
            # In a raw string (`r'…'`) a backslash is an ordinary character
            # — treating it as an escape consumed the closing quote and
            # blanked the rest of the line, real braces included
            # (`debugPrint(r'weird C:\')` is valid Dart).
            if ch == "\\" and not state["raw"]:
                out.append("  ")
                i += 2
                continue
            if ch == "$" and nxt == "{":
                # Remember the quote so the matching `}` can resume the
                # string. Without this the rest of the literal was scanned
                # as code, so a `}` in the text after an interpolation —
                # `'oops ${e.runtimeType} } trailing'` — closed the catch
                # body early and the report below it was never seen.
                state["interp"].append((quote, state["depth"]))
                state["quote"] = None
                out.append(" {")
                state["depth"] += 1
                i += 2
                continue
            if line.startswith(quote, i):
                out.append(" " * len(quote))
                i += len(quote)
                state["quote"] = None
                state["raw"] = False
                continue
            out.append(" ")
            i += 1
            continue

        if ch == "/" and nxt == "/":
            out.append(" " * (n - i))
            break
        if ch == "/" and nxt == "*":
            state["block_comment"] = True
            out.append("  ")
            i += 2
            continue
        if ch == "}" and state["interp"] and \
                state["depth"] - 1 == state["interp"][-1][1]:
            # Closing brace of a `${...}` — code ends, the string resumes.
            quote_resumed, _ = state["interp"].pop()
            state["depth"] -= 1
            state["quote"] = quote_resumed
            out.append("}")
            i += 1
            continue
        if ch == "{":
            state["depth"] += 1
            out.append(ch)
            i += 1
            continue
        if ch == "}":
            state["depth"] -= 1
            out.append(ch)
            i += 1
            continue
        if ch in "'\"" or (
            ch in "rR"
            and nxt in "'\""
            and (i == 0 or not (line[i - 1].isalnum() or line[i - 1] == "_"))
        ):
            raw = ch in "rR"
            if raw:
                out.append(" ")
                i += 1
                ch = line[i]
            triple = line[i : i + 3]
            if triple in ("'''", '"""'):
                state["quote"] = triple
                state["raw"] = raw
                out.append("   ")
                i += 3
                continue
            state["quote"] = ch
            state["raw"] = raw
            out.append(" ")
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def scan_file(path: str) -> list[int]:
    """Return the 1-based line numbers of unguarded catch blocks in `path`."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()

    state = {
        "block_comment": False,
        "quote": None,
        # Brace nesting depth, tracked only so a `${...}` interpolation
        # knows which `}` closes it.
        "depth": 0,
        "interp": [],
        "raw": False,
    }
    code = []
    for line in lines:
        code.append(strip_noncode(line, state))
        # A single-quoted (non-triple) string never spans lines in Dart.
        if state["quote"] in ("'", '"'):
            state["quote"] = None
            state["raw"] = False

    offenders = []
    for idx in range(len(lines)):
        # Header matched on the STRIPPED line. Matching raw source reported
        # a commented-out or quoted `} catch (e) {` as a real offender, so
        # commenting out a block of core code broke the baseline.
        if not CATCH_HEADER.search(code[idx]):
            continue
        body = _catch_body(code, idx)
        if body is None:
            # Unbalanced braces to EOF — report it rather than pass silently.
            offenders.append(idx + 1)
            continue
        start, end = body
        # `code`, not `lines`: matching the raw source means a catch is
        # rescued by the word "rethrow" in a comment, or by
        # `ErrorReporter.report(` inside a string — a new silent catch
        # ships by writing a comment about one.
        text = _body_without_nested_catches(code, code, start, end)
        if not SAFE_TOKEN.search(text):
            offenders.append(idx + 1)
    return offenders


def _body_without_nested_catches(
    text_lines: list[str], code: list[str], start: int, end: int
) -> str:
    """The catch body's own text, with any nested catch bodies removed.

    A report inside a nested catch handles the nested exception, not the one
    this block caught, so it must not count as this block's recovery.
    """
    excluded: set[int] = set()
    for i in range(start + 1, end + 1):
        if not CATCH_HEADER.search(code[i]):
            continue
        if i in excluded:
            continue
        nested = _catch_body(code, i)
        if nested is None:
            continue
        n_start, n_end = nested
        # Keep the nested header line itself: `} catch (e2) {` carries no
        # recovery, and dropping whole lines keeps this cheap.
        excluded.update(range(n_start + 1, min(n_end, end) + 1))
    return "".join(
        line for i, line in enumerate(text_lines[start : end + 1], start=start)
        if i not in excluded
    )


def _catch_body(code: list[str], header_idx: int) -> tuple[int, int] | None:
    """Locate the catch body's `{` … matching `}` in the comment-stripped code.

    Returns (start_line_idx, end_line_idx), both 0-based and inclusive, or
    None when the braces never balance.
    """
    depth = 0
    started = False
    for i in range(header_idx, len(code)):
        line = code[i]
        # Skip the `}` that closes the *try* block on the header line — it
        # precedes the `catch`, so start counting at the first `{` at or
        # after the catch keyword.
        scan_from = 0
        if i == header_idx:
            m = CATCH_HEADER.search(line)
            # Start just past the clause keyword, so neither the `}` closing
            # the try block nor a brace earlier on an inline
            # `try { … } catch` line is counted. For `on Foo {` the match
            # ends at that `{`, which is the body brace we want.
            scan_from = m.end() - 1 if m else 0
        for ch in line[scan_from:]:
            if ch == "{":
                depth += 1
                started = True
            elif ch == "}":
                depth -= 1
                if started and depth == 0:
                    return (header_idx, i)
        if started and depth < 0:
            return None
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True, help="repo root")
    ap.add_argument(
        "--dir",
        action="append",
        default=[],
        dest="dirs",
        help="directory to scan, relative to --root (repeatable)",
    )
    ap.add_argument(
        "--file",
        action="append",
        default=[],
        dest="files",
        help="an individual .dart file to scan, relative to --root "
        "(repeatable) — for entrypoints like app/lib/main.dart that sit in "
        "no scanned directory",
    )
    ap.add_argument(
        "--path-contains",
        default=None,
        help="only scan files whose path contains this fragment",
    )
    ap.add_argument(
        "--min-files",
        type=int,
        default=0,
        help="fail (exit 2) if fewer than this many .dart files were "
        "scanned — a guard that matches almost nothing passes exactly as "
        "loudly as one that matches everything",
    )
    ap.add_argument(
        "--count-by-file",
        action="store_true",
        help="print `path:count` per file with >0 offenders instead of "
        "`path:lineno` per offender",
    )
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    if not args.dirs and not args.files:
        ap.error("at least one --dir or --file is required")
    results: list[tuple[str, list[int]]] = []
    scanned = 0
    for rel_file in args.files:
        full = os.path.join(root, rel_file)
        if not os.path.isfile(full):
            print(
                f"silent_catch_scan: --file {rel_file} does not exist",
                file=sys.stderr,
            )
            return 2
        scanned += 1
        offenders = scan_file(full)
        if offenders:
            results.append((os.path.relpath(full, root), offenders))

    for rel_dir in args.dirs:
        base = os.path.join(root, rel_dir)
        for dirpath, _dirnames, filenames in os.walk(base):
            for name in sorted(filenames):
                if not name.endswith(".dart"):
                    continue
                full = os.path.join(dirpath, name)
                if args.path_contains and args.path_contains not in full:
                    continue
                scanned += 1
                offenders = scan_file(full)
                if offenders:
                    results.append((os.path.relpath(full, root), offenders))

    if scanned < args.min_files:
        print(
            f"silent_catch_scan: scanned only {scanned} file(s), expected at "
            f"least {args.min_files} — the scan is not seeing the tree it "
            f"thinks it is (wrong --root/--dir, or a moved directory)",
            file=sys.stderr,
        )
        return 2

    for rel, offenders in sorted(results):
        if args.count_by_file:
            print(f"{rel}:{len(offenders)}")
        else:
            for lineno in offenders:
                print(f"{rel}:{lineno}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
