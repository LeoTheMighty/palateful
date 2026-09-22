#!/usr/bin/env python3
"""Fail if a secret could print in plaintext in a terraform plan.

`aws_ecs_task_definition.container_definitions` and Batch
`container_properties` are NOT sensitive in the AWS provider schema, so
every change prints the full container JSON in the plan, and plans land in
public Actions logs. A secret is only safe when it enters a container
through `secrets = [{ name, valueFrom = <ARN> }]`, so the plan shows an ARN.

Flags:
  1. a secret-shaped name carrying a plaintext `value`, in any list of
     {name, value} objects, which is the container `environment` shape
     (e.g. `{ name = "SOME_API_KEY", value = var.x }`). This includes lists
     built in `locals` and passed by reference, and raw-JSON heredocs;
  2. any `secrets` entry carrying `value` instead of `valueFrom`.

Scoped to list elements on purpose. RDS `parameter { name, value }` and
`aws_ssm_parameter` are HCL blocks, not list elements, so a real Postgres
setting like `password_encryption` is not a false positive.

A secret-shaped *config* name (e.g. TOKEN_TTL_SECONDS) is allowed with an
inline comment on the entry's first line:
  { name = "TOKEN_TTL_SECONDS", value = "3600" }  # tf-env-secret-check: allow <reason>

Brackets are matched on a *masked* copy of the source, in which string
contents (including `${...}` templates with nested quotes), comments and
heredoc bodies are blanked with offsets preserved. Heredoc bodies are then
scanned as documents of their own. Without the mask, an apostrophe in a
comment ("don't") or `"${x["api"]}"` desyncs the bracket stack and
silently hides every entry after it.

Exit: 0 clean, 1 violations, 2 usage/tooling error.
"""
import re
import sys
from pathlib import Path

SECRET_NAME = re.compile(r"(KEY|SECRET|TOKEN|PASSWORD|CREDENTIAL)", re.I)
SECRETS_ATTR = re.compile(r"\bsecrets\s*[=:]\s*", re.I)
NAME = re.compile(r"""["]?\bname["]?\s*[=:]\s*"([^"]+)\"""")
PLAIN_VALUE = re.compile(r"""["]?\bvalue["]?\s*[=:]""")  # word-bounded, so not valueFrom
HEREDOC = re.compile(r"<<-?\s*([A-Za-z_][A-Za-z0-9_]*)[^\n]*\n")
ALLOW = "tf-env-secret-check: allow"


def mask(text):
    """Return (masked_text, heredoc_bodies[(offset, body)])."""
    out = list(text)
    bodies = []
    stack = ["code"]  # code | str | tmpl
    depth = [0]       # brace depth per tmpl frame
    i, n = 0, len(text)

    def blank(a, b):
        for k in range(a, b):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        c, st = text[i], stack[-1]
        two = text[i:i + 2]
        if st in ("code", "tmpl"):
            if c == "#" or two == "//":
                j = text.find("\n", i)
                j = n if j < 0 else j
                blank(i, j)
                i = j
                continue
            if two == "/*":
                j = text.find("*/", i + 2)
                j = n if j < 0 else j + 2
                blank(i, j)
                i = j
                continue
            if st == "code":
                hd = HEREDOC.match(text, i)
                if hd:
                    ident = hd.group(1)
                    body_start = hd.end()
                    end = re.compile(rf"^[ \t]*{re.escape(ident)}[ \t]*$", re.M).search(text, body_start)
                    body_end = end.start() if end else n
                    bodies.append((body_start, text[body_start:body_end]))
                    blank(body_start, body_end)
                    i = end.end() if end else n
                    continue
            if c == '"':
                stack.append("str")
            elif st == "tmpl" and c == "{":
                depth[-1] += 1
            elif st == "tmpl" and c == "}":
                if depth[-1] == 0:
                    stack.pop()
                    depth.pop()
                else:
                    depth[-1] -= 1
            if st == "tmpl":
                out[i] = " "  # a template is inside a string: blank it all
            i += 1
            continue
        # st == "str"
        if c == "\\":
            blank(i, min(i + 2, n))
            i += 2
            continue
        if two in ("${", "%{"):
            blank(i, i + 2)
            stack.append("tmpl")
            depth.append(0)
            i += 2
            continue
        if c == '"':
            stack.pop()
            # keep a closing quote only if it closes a top-level string
            if stack[-1] != "code":
                out[i] = " "
            i += 1
            continue
        if c != "\n":
            out[i] = " "
        i += 1
    return "".join(out), bodies


def list_element_objects(masked):
    """Yield (start, end) of every innermost `{...}` that is a direct element
    of a list literal `[...]`, anywhere, including lists in `locals`."""
    stack = []  # [char, start, has_child_object]
    for i, c in enumerate(masked):
        if c in "[({":
            stack.append([c, i, False])
        elif c in "])}" and stack:
            ch, s, has_child = stack.pop()
            if ch == "{":
                if stack:
                    stack[-1][2] = True
                if not has_child and stack and stack[-1][0] == "[":
                    yield s, i + 1


def expression_end(masked, i):
    """End of the attribute expression at i: follows `concat(...)`, ternaries,
    literals; stops at a newline, `,` or unmatched closer at depth 0."""
    depth = 0
    for j in range(i, len(masked)):
        c = masked[j]
        if c in "[({":
            depth += 1
        elif c in "])}":
            if depth == 0:
                return j
            depth -= 1
        elif depth == 0 and c in "\n,":
            return j
    return len(masked)


def scan_text(text, base_line, label, out):
    masked, bodies = mask(text)
    lines = text.splitlines()

    def flag(off, name, why):
        ln = text.count("\n", 0, off)
        if ALLOW in (lines[ln] if ln < len(lines) else ""):
            return
        out.setdefault((label, base_line + ln, name), why)

    # Rule 1: secret-shaped name with a plaintext value, in any list element.
    for s, e in list_element_objects(masked):
        obj = text[s:e]
        nm = NAME.search(obj)
        if nm and PLAIN_VALUE.search(obj) and SECRET_NAME.search(nm.group(1)):
            flag(s, nm.group(1), "secret-shaped name with a plaintext `value` (container env shape)")

    # Rule 2: `value` (not valueFrom) inside a `secrets` list.
    for m in SECRETS_ATTR.finditer(masked):
        end = expression_end(masked, m.end())
        region = masked[m.end():end]
        for s, e in list_element_objects("[" + region + "]"):
            s, e = m.end() + s - 1, m.end() + e - 1
            obj = text[s:e]
            nm = NAME.search(obj)
            if nm and PLAIN_VALUE.search(obj):
                flag(s, nm.group(1), "secrets entry uses plaintext `value` instead of `valueFrom`")

    # Heredoc bodies (e.g. raw-JSON container definitions) are documents too.
    for off, body in bodies:
        scan_text(body, base_line + text.count("\n", 0, off), label, out)


def main(argv):
    root = Path(argv[1]) if len(argv) > 1 else Path("terraform")
    if not root.is_dir():
        print(f"tf-env-secret-check: {root} is not a directory", file=sys.stderr)
        return 2
    files = sorted(p for p in root.rglob("*.tf") if ".terraform" not in p.parts)
    out = {}
    for f in files:
        scan_text(f.read_text(), 1, str(f), out)
    for (path, line, name), why in sorted(out.items()):
        print(f"{path}:{line}: {name}: {why}. Move it to `secrets = [{{ name, valueFrom = <ARN> }}]`, "
              f"or if it is not a secret, add `# {ALLOW} <reason>`.", file=sys.stderr)
    print(f"tf-env-secret-check: scanned {len(files)} files, {len(out)} violation(s)")
    return 1 if out else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
