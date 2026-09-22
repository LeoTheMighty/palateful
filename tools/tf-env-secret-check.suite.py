"""Discrimination suite for tools/tf-env-secret-check.py (tfval1), run against
the repo's own terraform/ tree. Proof artifact, not a CI gate: the coverage
expectation is pinned to the tree at the time of writing (58 entries, 7
secret-shaped), so update it when task-definition env changes.

Usage: python3 tools/tf-env-secret-check.suite.py [terraform-dir]

Asserts coverage first (the guard must SEE today's entries: a zero from a
parser that saw nothing is a vacuous pass), then plants one mutation per
case into a fresh copy of the tree and checks the CLI's exit code.
"""
import collections
import importlib.util
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location("g", HERE / "tf-env-secret-check.py")
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)
BASE = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else HERE.parent / "terraform")
ECS, BATCH, RDS = "modules/ecs/main.tf", "modules/batch/main.tf", "modules/rds/parameter_group.tf"

# ---- coverage on the real tree ------------------------------------------
per_file = collections.Counter()
shaped = []
for f in sorted(BASE.rglob("*.tf")):
    text = f.read_text()
    masked, _ = g.mask(text)
    for s, e in g.list_element_objects(masked):
        nm = g.NAME.search(text[s:e])
        if nm:
            per_file[str(f.relative_to(BASE))] += 1
            if g.SECRET_NAME.search(nm.group(1)):
                shaped.append((nm.group(1), "value" if g.PLAIN_VALUE.search(text[s:e]) else "valueFrom"))
total = sum(per_file.values())
print("COVERAGE (named list-element entries seen, by file):")
for k, v in sorted(per_file.items()):
    print(f"   {k:34s} {v}")
print(f"   total {total}; secret-shaped {len(shaped)}: {collections.Counter(shaped)}")
EXPECT_ENTRIES, EXPECT_SHAPED = 58, 7
cov_ok = total == EXPECT_ENTRIES and len(shaped) == EXPECT_SHAPED and all(v == "valueFrom" for _, v in shaped)
print(f"   coverage {'OK' if cov_ok else '*** WRONG ***'} (expected {EXPECT_ENTRIES} entries, {EXPECT_SHAPED} secret-shaped, all valueFrom)\n")


# ---- cases ---------------------------------------------------------------
def ins_after(rel, anchor, text):
    def f(root):
        p = root / rel
        t = p.read_text()
        i = t.index(anchor) + len(anchor)
        p.write_text(t[:i] + text + t[i:])
    return f


def add_file(rel, body):
    def f(root):
        (root / rel).write_text(body)
    return f


def ecs_env_via_local(root):
    p = root / ECS
    t = p.read_text()
    i = t.index("      environment = [\n")
    j = t.index("      ]\n", i) + len("      ]\n")
    p.write_text(t[:i] + "      environment = local.api_env\n" + t[j:])
    (root / "modules/ecs/zz_env.tf").write_text(
        'locals {\n  api_env = [\n    { name = "LEAKED_API_KEY", value = var.k },\n  ]\n}\n')


API_ENV = '{ name = "ENVIRONMENT", value = var.environment },\n'
HEREDOC_TD = '''resource "aws_ecs_task_definition" "legacy" {
  family                = "legacy"
  container_definitions = <<EOF
[
  {
    "name": "legacy",
    "environment": [
      { "name": "REGION", "value": "us-east-1" },
      { "name": "MAILGUN_API_KEY", "value": "key-abc123" }
    ]
  }
]
EOF
}
'''
CASES = [
    ("0  today's tree, unmodified", None, 0),
    ("1  PLANTED SOME_API_KEY = var.x (coordinator's case)", ins_after(ECS, API_ENV, '        { name = "SOME_API_KEY", value = var.x },\n'), 1),
    ("2  PLANTED X_TOKEN = literal (0e's case)", ins_after(ECS, API_ENV, '        { name = "X_TOKEN", value = "tok_live_123" },\n'), 1),
    ("3  PLANTED interpolated value \"${var.k}\"", ins_after(ECS, API_ENV, '        { name = "STRIPE_SECRET", value = "${var.stripe}" },\n'), 1),
    ("4  PLANTED reversed key order", ins_after(ECS, API_ENV, '        { value = var.pw, name = "SMTP_PASSWORD" },\n'), 1),
    ("5  PLANTED lowercase name", ins_after(ECS, API_ENV, '        { name = "sendgrid_api_key", value = var.k },\n'), 1),
    ("6  PLANTED multi-line object, Batch env", ins_after(BATCH, "environment = [\n", '      {\n        name  = "HF_TOKEN"\n        value = var.hf\n      },\n'), 1),
    ("7  PLANTED `value` inside a secrets list", ins_after(ECS, '{ name = "OPENAI_API_KEY", valueFrom = var.openai_secret_arn },\n', '          { name = "REDIS_URL2", value = var.redis_url },\n'), 1),
    ("8  FP probe: plain config SENTRY_ENVIRONMENT", ins_after(ECS, API_ENV, '        { name = "SENTRY_ENVIRONMENT", value = "prod" },\n'), 0),
    ("9  FP probe: TOKEN_TTL_SECONDS, no allow", ins_after(ECS, API_ENV, '        { name = "TOKEN_TTL_SECONDS", value = "3600" },\n'), 1),
    ("10 FP probe: TOKEN_TTL_SECONDS + allow comment", ins_after(ECS, API_ENV, '        { name = "TOKEN_TTL_SECONDS", value = "3600" }, # tf-env-secret-check: allow TTL, not a secret\n'), 0),
    ("11 scope: RDS parameter password_encryption", ins_after(RDS, 'resource "aws_db_parameter_group" "perf" {\n', '  parameter {\n    name  = "password_encryption"\n    value = "scram-sha-256"\n  }\n'), 0),
    ("12 scope: real SSM param named .../api_key", add_file("modules/ecs/zz_ssm.tf", 'resource "aws_ssm_parameter" "k" {\n  name  = "/palateful/prod/api_key"\n  type  = "SecureString"\n  value = var.k\n}\n'), 0),
    ("13 PLANTED env list built in a local, by reference", ecs_env_via_local, 1),
    ("14 PLANTED raw-JSON heredoc task definition", add_file("modules/ecs/zz_legacy.tf", HEREDOC_TD), 1),
    ("15 REGRESSION: apostrophe comment before entry", ins_after(ECS, API_ENV, "        # don't leak this one\n        { name = \"POSTMARK_TOKEN\", value = var.pm },\n"), 1),
    ("16 REGRESSION: nested-quote interpolation before", ins_after(ECS, API_ENV, '        { name = "IMG", value = "${var.m["api"]}:x" },\n        { name = "ALGOLIA_API_KEY", value = var.a },\n'), 1),
]

ok = cov_ok
for label, mut, want in CASES:
    root = pathlib.Path(tempfile.mkdtemp()) / "terraform"
    shutil.copytree(BASE, root)
    if mut:
        mut(root)
    r = subprocess.run([sys.executable, str(HERE / "tf-env-secret-check.py"), str(root)], capture_output=True, text=True)
    flagged = [l.split(": ", 2)[1] for l in r.stderr.splitlines() if ": " in l]
    shutil.rmtree(root.parent, ignore_errors=True)
    good = r.returncode == want
    ok &= good
    print(f"{'PASS' if good else '*** WRONG ***':13s} exit={r.returncode} want={want}  {label}  {('flagged=' + str(flagged)) if flagged else ''}")
print(f"\n{'ALL AS EXPECTED' if ok else 'SUITE FAILED'} ({len(CASES)} cases + coverage)")
sys.exit(0 if ok else 1)
