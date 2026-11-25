#!/usr/bin/env bash
#
# Self-test for deploy-freshness.yml's image-existence step (imgexist1).
#
# WHY THIS EXISTS
# ---------------
# ECR's lifecycle policy deleted the images prod was running, and the api and
# worker were down for 21 and 27 days (2026-10-29 .. 2026-11-25) because no
# replacement task could pull. A probe for that failure has exactly one job
# before any other: to be able to SEE it. One that is green today proves
# nothing — a probe that never looks is green today too. So this drives the
# shipped bash into every answer on purpose:
#
#   - the incident, replayed: worker's tag AND pinned digest gone     -> RED
#   - a re-pushed tag over a pinned digest that is gone               -> RED
#     (the tag-only check this could have been is green here)
#   - everything present                                              -> GREEN
#   - every way of not being able to look                             -> NO VERDICT
#     (AWS error, non-ECR image, a CLI that cannot return service
#     revisions, a missing service, empty lists) — never GREEN
#
# and then runs the two notify steps' bodies, because a red verdict that never
# reaches SNS is the same as no check (deploy-freshness once failed 52 runs in
# a row, visible only in a UI nobody opens).
#
# HOW
# ---
# Step bodies are EXTRACTED FROM THE WORKFLOW YAML at run time (shared
# extractor, tools/deploy-freshness-extract.py), never copied. Only `aws` is
# faked, from fixture files. tools/image-exists-live-check.sh runs the same
# body against real prod, and checks the fake's one load-bearing assumption —
# the error text of a real ImageNotFoundException — against real ECR.
#
# Usage: bash tools/image-exists-self-test.sh   (no AWS, no node_modules)
# Exit:  0 all cases pass, 1 any case fails or extraction fails.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOW="$REPO_ROOT/.github/workflows/deploy-freshness.yml"
STEP_NAME="Check prod's referenced images still exist in ECR"
NOTIFY_NAME="Notify on a red verdict"
NOVERDICT_NAME="Notify when the check itself failed to reach a verdict"

SANDBOX="$(mktemp -d)"
trap 'rm -rf "$SANDBOX"' EXIT

EXTRACT="$REPO_ROOT/tools/deploy-freshness-extract.py"
python3 "$EXTRACT" "$WORKFLOW" "$STEP_NAME" "$SANDBOX/images.sh"
python3 "$EXTRACT" "$WORKFLOW" "$NOTIFY_NAME" "$SANDBOX/notify.sh"
python3 "$EXTRACT" "$WORKFLOW" "$NOVERDICT_NAME" "$SANDBOX/noverdict.sh"

# The real lists, from the workflow env, so a case cannot pass against a
# service set the workflow no longer probes.
wf_env() { sed -n "s/^  $1: *//p" "$WORKFLOW" | head -1; }
CLUSTER="$(wf_env CLUSTER)"
WF_SERVICES="$(wf_env IMAGE_SERVICES)"
WF_JOBDEFS="$(wf_env IMAGE_JOB_DEFINITIONS)"
[ -n "$CLUSTER" ] && [ -n "$WF_SERVICES" ] && [ -n "$WF_JOBDEFS" ] \
  || { echo "FAIL: could not read CLUSTER / IMAGE_SERVICES / IMAGE_JOB_DEFINITIONS from workflow env"; exit 1; }
echo "workflow env: CLUSTER=$CLUSTER IMAGE_SERVICES='$WF_SERVICES' IMAGE_JOB_DEFINITIONS='$WF_JOBDEFS'"

# ── Fake `aws` ───────────────────────────────────────────────────────────
# Fixtures live in $MOCK_DIR:
#   td.<svc>          running task-definition ARN    (absent: service not found)
#   revs.<svc>        current service-revision ARNs  (absent: CLI returns None)
#   tdimg.<td-arn>    container images, tab-separated
#   rev.<rev-id>      "image<TAB>digest" lines
#   jd.<name>         "revision<TAB>image"
#   ecr.tsv           "repo<TAB>digest<TAB>tag[,tag]<TAB>pushedAt" — what EXISTS
#   repos             repositories that exist, one per line
#   ecr_error         if present, every ecr call fails with this exception
# ARNs contain '/' and ':'; fixture names use only the part after the last '/'.
mkdir -p "$SANDBOX/bin"
cat > "$SANDBOX/bin/aws" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "$MOCK_CALL_LOG"
svc1="$1"; op="$2"; shift 2
q="" services="" td="" revarn="" jd="" repo="" ids="" subject=""
while [ $# -gt 0 ]; do
  case "$1" in
    --query) q="$2"; shift ;;
    --services) services="$2"; shift ;;
    --task-definition) td="$2"; shift ;;
    --service-revision-arns) revarn="$2"; shift ;;
    --job-definition-name) jd="$2"; shift ;;
    --repository-name) repo="$2"; shift ;;
    --image-ids) ids="$2"; shift ;;
    --subject) subject="$2"; shift ;;
  esac
  shift
done
f() { printf '%s/%s' "$MOCK_DIR" "$1"; }
case "$svc1 $op" in
  "ecs describe-services")
    case "$q" in
      *currentServiceRevisions*) [ -f "$(f "revs.$services")" ] && cat "$(f "revs.$services")" || echo None ;;
      *taskDefinition*)          [ -f "$(f "td.$services")" ] && cat "$(f "td.$services")" || echo None ;;
      *) echo "MOCK: unexpected describe-services query: $q" >&2; exit 253 ;;
    esac ;;
  "ecs describe-task-definition")
    [ -f "$(f "tdimg.${td##*/}")" ] || { echo "MOCK: no task definition $td" >&2; exit 254; }
    cat "$(f "tdimg.${td##*/}")" ;;
  "ecs describe-service-revisions")
    [ -f "$(f "rev.${revarn##*/}")" ] || { echo "MOCK: no service revision $revarn" >&2; exit 254; }
    cat "$(f "rev.${revarn##*/}")" ;;
  "batch describe-job-definitions")
    [ -f "$(f "jd.$jd")" ] && cat "$(f "jd.$jd")" || echo None ;;
  "ecr describe-images")
    if [ -f "$(f ecr_error)" ]; then
      echo "An error occurred ($(cat "$(f ecr_error)")) when calling the DescribeImages operation: mocked" >&2; exit 254
    fi
    if ! grep -qxF "$repo" "$(f repos)"; then
      echo "An error occurred (RepositoryNotFoundException) when calling the DescribeImages operation: The repository with name '$repo' does not exist in the registry with id '592349850338'" >&2; exit 254
    fi
    kind="${ids%%=*}"; val="${ids#*=}"
    line=$(awk -F'\t' -v r="$repo" -v k="$kind" -v v="$val" '
      $1 != r { next }
      k == "imageDigest" && $2 == v { print; exit }
      k == "imageTag" { n = split($3, t, ","); for (i = 1; i <= n; i++) if (t[i] == v) { print; exit } }
    ' "$(f ecr.tsv)")
    if [ -z "$line" ]; then
      # Wording copied from real ECR; tools/image-exists-live-check.sh
      # --verify-mock-assumptions re-checks the exception name against it.
      echo "An error occurred (ImageNotFoundException) when calling the DescribeImages operation: The image with imageId {$ids} does not exist within the repository with name '$repo' in the registry with id '592349850338'" >&2; exit 254
    fi
    printf '%s\t%s\n' "$(printf '%s' "$line" | cut -f2)" "$(printf '%s' "$line" | cut -f4)" ;;
  "sns list-topics")
    [ -f "$(f no_topic)" ] && echo None || echo "arn:aws:sns:us-east-1:592349850338:palateful-prod-alerts" ;;
  "sns publish")
    printf '%s\n' "$subject" >> "$(f published_subjects)"
    echo '{"MessageId":"mock"}' ;;
  *) echo "MOCK: unexpected aws call: $svc1 $op $*" >&2; exit 253 ;;
esac
MOCK
chmod +x "$SANDBOX/bin/aws"

# ── Fixture builders ─────────────────────────────────────────────────────
REG=592349850338.dkr.ecr.us-east-1.amazonaws.com
TDARN=arn:aws:ecs:us-east-1:592349850338:task-definition
REVARN=arn:aws:ecs:us-east-1:592349850338:service-revision/palateful-prod
SHA_OLD=cd6a3c3efdcd8b6a0b0e8f594a766dc2b5a84896
SHA_NEW=f23b9e7c20f9bd16170cc72e6134da834b27ea93
dig() { printf 'sha256:%064d' "$1"; }   # deterministic fake digests

new_fixture() {
  MOCK_DIR="$SANDBOX/mock"
  rm -rf "$MOCK_DIR"; mkdir -p "$MOCK_DIR"
  export MOCK_DIR
  printf 'palateful/api\npalateful/worker\npalateful-parser\n' > "$MOCK_DIR/repos"
  : > "$MOCK_DIR/ecr.tsv"
}
ecr_has() {  # repo digest tags
  printf '%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "2026-11-25T08:39:58+00:00" >> "$MOCK_DIR/ecr.tsv"
}
# svc_runs <svc> <family:rev> <repo> <tag> <pinned digest> [<rev-id>]
svc_runs() {
  local svc="$1" td="$2" repo="$3" tag="$4" d="$5" rid="${6:-1000}"
  printf '%s/%s\n' "$TDARN" "$td" > "$MOCK_DIR/td.$svc"
  printf '%s/%s:%s\n' "$REG" "$repo" "$tag" > "$MOCK_DIR/tdimg.$td"
  printf '%s/%s/%s\n' "$REVARN" "$svc" "$rid" > "$MOCK_DIR/revs.$svc"
  printf '%s/%s:%s\t%s\n' "$REG" "$repo" "$tag" "$d" > "$MOCK_DIR/rev.$rid"
}
# The healthy state of real prod on 2026-11-25 after #43's deploy, by shape.
healthy() {
  new_fixture
  svc_runs palateful-api-prod    palateful-api-prod:76    palateful/api    "$SHA_NEW" "$(dig 1)" 1001
  svc_runs palateful-worker-prod palateful-worker-prod:66 palateful/worker "$SHA_NEW" "$(dig 2)" 1002
  ecr_has palateful/api    "$(dig 1)" "$SHA_NEW"
  ecr_has palateful/worker "$(dig 2)" "$SHA_NEW"
  printf '41\t%s/palateful-parser:%s\n' "$REG" "$SHA_NEW" > "$MOCK_DIR/jd.palateful-parser-job-prod"
  ecr_has palateful-parser "$(dig 3)" "$SHA_NEW"
}

# ── Runner ───────────────────────────────────────────────────────────────
PASS=0; FAIL=0; MARK=0
OUT="$SANDBOX/out.txt"; GH_OUT="$SANDBOX/gh_out.txt"
run_body() {  # $1 = script, $2 = expected exit, rest = extra env assignments
  local script="$1" want="$2" got=0; shift 2
  MARK="$FAIL"
  export MOCK_CALL_LOG="$SANDBOX/calls.log"
  : > "$MOCK_CALL_LOG"; : > "$GH_OUT"
  set +e
  env PATH="$SANDBOX/bin:$PATH" CLUSTER="$CLUSTER" \
      IMAGE_SERVICES="$WF_SERVICES" IMAGE_JOB_DEFINITIONS="$WF_JOBDEFS" \
      TOPIC_NAME=palateful-prod-alerts GITHUB_OUTPUT="$GH_OUT" \
      GITHUB_SERVER_URL=https://github.com GITHUB_REPOSITORY=o/r GITHUB_RUN_ID=1 \
      "$@" bash "$script" > "$OUT" 2>&1
  got=$?
  set -e
  if [ "$got" -ne "$want" ]; then
    echo "FAIL [$CASE]: exit $got, want $want"; sed 's/^/    | /' "$OUT"
    FAIL=$((FAIL + 1)); return 1
  fi
}
fail() { echo "FAIL [$CASE]: $1"; sed 's/^/    | /' "$OUT"; FAIL=$((FAIL + 1)); }
expect_out() { grep -qF -- "$1" "$OUT" || fail "output missing: $1"; }
refute_out() { ! grep -qF -- "$1" "$OUT" || fail "output contains forbidden: $1"; }
verdict() { local v; v="$(sed -n 's/^verdict=//p' "$GH_OUT" | tail -1)"; echo "${v:-none}"; }
expect_verdict() { [ "$(verdict)" = "$1" ] || fail "verdict '$(verdict)', want '$1'"; }
# The multi-line detail, from GitHub's delimiter form.
detail() { awk '/^detail<<__IMGEXIST_DETAIL__$/{on=1;next} /^__IMGEXIST_DETAIL__$/{on=0} on' "$GH_OUT"; }
expect_detail() { detail | grep -qF -- "$1" || { fail "detail missing: $1"; detail | sed 's/^/    D /'; }; }
refute_detail() { ! detail | grep -qF -- "$1" || fail "detail contains forbidden: $1"; }
end_case() {
  [ -z "${SELFTEST_VERBOSE:-}" ] || sed 's/^/    | /' "$OUT"
  if [ "$FAIL" -eq "$MARK" ]; then echo "pass [$CASE]"; PASS=$((PASS + 1)); fi
}

# ── GREEN: everything present ────────────────────────────────────────────
healthy
CASE='healthy prod: every tag and pinned digest present -> GREEN'
if run_body "$SANDBOX/images.sh" 0; then
  expect_verdict present
  grep -qx 'images_checked=5' "$GH_OUT" || fail "images_checked is not 5 (api tag+digest, worker tag+digest, parser tag)"
  expect_out "Every image prod references exists in ECR."
  # Proves it LOOKED, per reference, rather than reaching green by skipping.
  for want in "imageTag=$SHA_NEW" "imageDigest=$(dig 1)" "imageDigest=$(dig 2)"; do
    grep -qF -- "--image-ids $want" "$SANDBOX/calls.log" || fail "never probed ECR for $want"
  done
  # The family-shortcut trap: the revision ARN in service, never the family.
  grep -qE 'describe-task-definition --task-definition palateful-api-prod( |$)' "$SANDBOX/calls.log" \
    && fail "resolved the task definition by family name"
fi
end_case

# ── RED: the incident, replayed ──────────────────────────────────────────
# Prod's revision still names cd6a3c3e and ECS pinned its digest, but rule 3
# expired the image: neither the tag nor the digest is in ECR any more.
# (api is healthy here so the case also proves a red is attributed to the
# right service, not smeared across all of them.)
healthy
svc_runs palateful-worker-prod palateful-worker-prod:64 palateful/worker "$SHA_OLD" "$(dig 9)" 1009
CASE='incident replay: worker tag AND pinned digest expired -> RED'
if run_body "$SANDBOX/images.sh" 1; then
  expect_verdict missing
  expect_detail "palateful-worker-prod: task definition palateful-worker-prod:64 tag $REG/palateful/worker:$SHA_OLD — ECR: ImageNotFoundException"
  expect_detail "palateful-worker-prod: revision 1009 pinned digest of $REG/palateful/worker:$SHA_OLD@$(dig 9) — ECR: ImageNotFoundException"
  expect_detail "Force Deploy"
  refute_detail "palateful-api-prod"
  refute_out "Every image prod references exists"
fi
end_case

# ── RED: tag re-pushed, pinned digest gone ───────────────────────────────
# Tags are MUTABLE. Re-pushing a SHA's tag moves it to a new digest; the one
# ECS pinned goes untagged and rule 1 expires it a day later. A check that
# only resolves the tag is GREEN here, and ECS cannot replace the task.
healthy
: > "$MOCK_DIR/ecr.tsv"
ecr_has palateful/api    "$(dig 1)" "$SHA_NEW"
ecr_has palateful/worker "$(dig 7)" "$SHA_NEW"     # the re-push; dig 2 is gone
ecr_has palateful-parser "$(dig 3)" "$SHA_NEW"
CASE='tag re-pushed over a pinned digest that expired -> RED on the digest only'
if run_body "$SANDBOX/images.sh" 1; then
  expect_verdict missing
  expect_detail "palateful-worker-prod: revision 1002 pinned digest of $REG/palateful/worker:$SHA_NEW@$(dig 2) — ECR: ImageNotFoundException"
  refute_detail "palateful-worker-prod: task definition"
  expect_out "present  palateful-worker-prod: task definition palateful-worker-prod:66 tag"
fi
end_case

# ── RED: the tag removed, digest still there (untagged — rule 1's fuse) ──
healthy
: > "$MOCK_DIR/ecr.tsv"
ecr_has palateful/api    "$(dig 1)" ""
ecr_has palateful/worker "$(dig 2)" "$SHA_NEW"
ecr_has palateful-parser "$(dig 3)" "$SHA_NEW"
CASE='task-definition tag gone while the digest survives untagged -> RED on the tag'
if run_body "$SANDBOX/images.sh" 1; then
  expect_verdict missing
  expect_detail "palateful-api-prod: task definition palateful-api-prod:76 tag"
  refute_detail "pinned digest"
fi
end_case

# ── RED: mid-deploy, the OLD revision's digest is the missing one ────────
# Two current revisions; ECS may still need to re-place tasks of either.
healthy
printf '%s/palateful-api-prod/1001\t%s/palateful-api-prod/1011\n' "$REVARN" "$REVARN" > "$MOCK_DIR/revs.palateful-api-prod"
printf '%s/palateful/api:%s\t%s\n' "$REG" "$SHA_OLD" "$(dig 8)" > "$MOCK_DIR/rev.1011"
CASE='two current revisions, the older one pinned to a deleted digest -> RED naming it'
if run_body "$SANDBOX/images.sh" 1; then
  expect_verdict missing
  expect_detail "palateful-api-prod: revision 1011 pinned digest of $REG/palateful/api:$SHA_OLD@$(dig 8)"
  refute_detail "revision 1001"
fi
end_case

# ── RED: repository gone ─────────────────────────────────────────────────
healthy
grep -vx 'palateful/worker' "$MOCK_DIR/repos" > "$MOCK_DIR/repos.new"; mv "$MOCK_DIR/repos.new" "$MOCK_DIR/repos"
CASE='repository deleted -> RED (RepositoryNotFoundException is a measurement too)'
if run_body "$SANDBOX/images.sh" 1; then
  expect_verdict missing
  expect_detail "ECR: RepositoryNotFoundException"
fi
end_case

# ── RED: the parser's Batch job definition ───────────────────────────────
healthy
printf '42\t%s/palateful-parser:%s\n' "$REG" "$SHA_OLD" > "$MOCK_DIR/jd.palateful-parser-job-prod"
CASE='parser job definition tag expired -> RED'
if run_body "$SANDBOX/images.sh" 1; then
  expect_verdict missing
  expect_detail "palateful-parser-job-prod: job definition revision 42 tag $REG/palateful-parser:$SHA_OLD — ECR: ImageNotFoundException"
fi
end_case

# ── RED survives a later probe that is green ─────────────────────────────
# Order-independence: the missing image is the FIRST service; the rest are
# fine. A findings accumulator that resets per service would go green here.
healthy
: > "$MOCK_DIR/ecr.tsv"
ecr_has palateful/worker "$(dig 2)" "$SHA_NEW"
ecr_has palateful-parser "$(dig 3)" "$SHA_NEW"
CASE='first service missing, later ones present -> still RED'
if run_body "$SANDBOX/images.sh" 1; then
  expect_verdict missing
  expect_detail "palateful-api-prod: task definition"
  expect_detail "palateful-api-prod: revision 1001 pinned digest"
fi
end_case

# ── NO VERDICT: every way of not being able to look ──────────────────────
nv_case() {  # $1 = name, $2 = substring the output must carry ('' = none); extra env in "$@"
  CASE="$1"; local must="$2"; shift 2
  if run_body "$SANDBOX/images.sh" 1 "$@"; then
    expect_verdict none
    refute_out "Every image prod references exists"
    [ -z "$must" ] || expect_out "$must"
  fi
  end_case
}

healthy; echo AccessDeniedException > "$MOCK_DIR/ecr_error"
nv_case 'ECR AccessDenied -> no verdict, never green' 'ECR could not answer'

healthy; echo ThrottlingException > "$MOCK_DIR/ecr_error"
nv_case 'ECR throttling -> no verdict, never green' 'ThrottlingException'

healthy; printf 'docker.io/library/nginx:1.27\n' > "$MOCK_DIR/tdimg.palateful-api-prod:76"
nv_case 'non-ECR image in the task definition -> no verdict (cannot see it)' 'is not an ECR image reference'

healthy; rm "$MOCK_DIR/revs.palateful-worker-prod"
nv_case 'currentServiceRevisions absent (CLI too old to know it) -> no verdict' 'no currentServiceRevisions'

healthy; printf '%s/palateful/worker:%s\tNone\n' "$REG" "$SHA_NEW" > "$MOCK_DIR/rev.1002"
nv_case 'service revision with no pinned digest -> no verdict' 'pinned no digest'

healthy; rm "$MOCK_DIR/td.palateful-api-prod"
nv_case 'service not found -> no verdict' 'not found in'

healthy; rm "$MOCK_DIR/jd.palateful-parser-job-prod"
nv_case 'job definition with no ACTIVE revision -> no verdict' 'has no ACTIVE revision'

healthy
nv_case 'IMAGE_SERVICES empty -> no verdict (checked nothing != nothing missing)' 'must both be set' IMAGE_SERVICES=
healthy
nv_case 'IMAGE_JOB_DEFINITIONS empty -> no verdict' 'must both be set' IMAGE_JOB_DEFINITIONS=

# ── The notify step: a red verdict has to reach SNS ──────────────────────
healthy
CASE='notify: images missing alone -> exactly one publish, ASCII subject'
if run_body "$SANDBOX/notify.sh" 0 VERDICT=fresh DETAIL= IMAGES_VERDICT=missing IMAGES_DETAIL="worker gone"; then
  subj="$(cat "$MOCK_DIR/published_subjects" 2>/dev/null || true)"
  [ "$(printf '%s\n' "$subj" | grep -c .)" -eq 1 ] || fail "want 1 publish, got: $subj"
  case "$subj" in *"IMAGE MISSING"*) ;; *) fail "subject does not say IMAGE MISSING: $subj" ;; esac
  # SNS rejects a non-ASCII Subject with InvalidParameter — the alert would
  # die at the last step, after the check had done everything right.
  if printf '%s' "$subj" | LC_ALL=C grep -q '[^ -~]'; then fail "non-ASCII SNS subject: $subj"; fi
  [ "${#subj}" -lt 100 ] || fail "SNS subject is ${#subj} chars; SNS limit is <100"
fi
end_case

healthy
CASE='notify: stale AND images missing -> two publishes, one per verdict'
if run_body "$SANDBOX/notify.sh" 0 VERDICT=stale DETAIL="overdue" IMAGES_VERDICT=missing IMAGES_DETAIL="worker gone"; then
  n="$(grep -c . "$MOCK_DIR/published_subjects" 2>/dev/null || true)"
  [ "$n" = 2 ] || fail "want 2 publishes, got $n"
  if LC_ALL=C grep -q '[^ -~]' "$MOCK_DIR/published_subjects"; then fail "non-ASCII SNS subject"; fi
fi
end_case

healthy
CASE='notify: stale alone -> one publish, not the image subject'
if run_body "$SANDBOX/notify.sh" 0 VERDICT=stale DETAIL="overdue" IMAGES_VERDICT=present IMAGES_DETAIL=; then
  grep -q 'IMAGE MISSING' "$MOCK_DIR/published_subjects" && fail "published an image alert for a present verdict"
  [ "$(grep -c . "$MOCK_DIR/published_subjects")" = 1 ] || fail "want 1 publish"
fi
end_case

healthy; touch "$MOCK_DIR/no_topic"
CASE='notify: topic missing -> fails loudly and prints the image detail'
if run_body "$SANDBOX/notify.sh" 1 VERDICT=fresh DETAIL= IMAGES_VERDICT=missing IMAGES_DETAIL="worker gone"; then
  expect_out "not found"
  expect_out "worker gone"
fi
end_case

healthy
CASE='no-verdict notifier: image probe blind, overdue green -> names the image check'
if run_body "$SANDBOX/noverdict.sh" 0 MEASURE_VERDICT=fresh IMAGES_VERDICT=; then
  [ "$(grep -c . "$MOCK_DIR/published_subjects")" = 1 ] || fail "want 1 publish"
  grep -qF 'still exist in ECR' "$SANDBOX/calls.log" || fail "message does not say the image check is blind"
  grep -qF 'overdue a deploy;' "$SANDBOX/calls.log" && fail "message claims the overdue check is blind too"
fi
end_case

# ── Wiring: the YAML around the bodies ───────────────────────────────────
# The cases above run the bodies directly, so they are blind to everything
# that must hold for the bodies to ever run in Actions or reach a human.
python3 - "$WORKFLOW" "$STEP_NAME" "$NOTIFY_NAME" "$NOVERDICT_NAME" > "$SANDBOX/wiring.txt" <<'PY'
import re, sys
wf, step, notify, noverdict = sys.argv[1:5]
lines = open(wf).read().splitlines()
out = []
ok = lambda n: out.append("OK " + n)
bad = lambda n, why: out.append("FAIL " + n + ": " + why)
ind = lambda l: len(l) - len(l.lstrip())

def step_at(name):
    return next((i for i, l in enumerate(lines) if l.strip() == "- name: " + name), -1)

def keys(i):
    """The step's own scalar keys (id, if, ...), stopping at the next step."""
    d = {}
    for l in lines[i + 1:]:
        if l.strip() and ind(l) <= ind(lines[i]):
            break
        m = re.match(r"^\s+([a-z-]+):\s*(.*)$", l)
        if m and ind(l) == ind(lines[i]) + 2:
            d[m.group(1)] = m.group(2)
    return d

def env_of(i):
    e, on = {}, False
    for l in lines[i + 1:]:
        if l.strip() and ind(l) <= ind(lines[i]):
            break
        if l.strip() == "env:":
            on = True; continue
        if on:
            if ind(l) <= ind(lines[i]) + 2 and l.strip():
                break
            if ":" in l:
                k, v = l.strip().split(":", 1); e[k] = v.strip()
    return e

s, n, nv = step_at(step), step_at(notify), step_at(noverdict)
creds = next((i for i, l in enumerate(lines) if "aws-actions/configure-aws-credentials" in l), -1)
meas = step_at("Measure how long prod has been overdue a deploy")
if min(s, n, nv, creds, meas) < 0:
    bad("steps present", "missing (images=%d notify=%d noverdict=%d creds=%d measure=%d)" % (s, n, nv, creds, meas))
    print("\n".join(out)); sys.exit()

k = keys(s)
name = "image step has id: images (both notifiers read steps.images)"
ok(name) if k.get("id") == "images" else bad(name, "id is %r" % k.get("id"))

# A red overdue verdict exits 1; under the default success() the image probe
# would be SKIPPED exactly when prod is already in trouble.
name = "image step runs whatever the overdue verdict was (!cancelled())"
ok(name) if re.search(r"!cancelled\(\)|always\(\)", k.get("if", "")) else bad(name, "if is %r" % k.get("if", ""))

name = "image step runs after the AWS credentials and after the measure step"
ok(name) if creds < meas < s < n else bad(name, "order creds@%d measure@%d images@%d notify@%d" % (creds, meas, s, n))

nk, ne = keys(n), env_of(n)
name = "notify fires on images verdict 'missing' and is handed its detail"
probs = []
if "steps.images.outputs.verdict == 'missing'" not in nk.get("if", ""):
    probs.append("if: lacks steps.images.outputs.verdict == 'missing'")
if "steps.images.outputs.detail" not in ne.get("IMAGES_DETAIL", ""):
    probs.append("env IMAGES_DETAIL is not steps.images.outputs.detail")
if "steps.images.outputs.verdict" not in ne.get("IMAGES_VERDICT", ""):
    probs.append("env IMAGES_VERDICT is not steps.images.outputs.verdict")
if not nk.get("if", "").startswith("always()"):
    probs.append("if: does not start with always() — a failed step would skip the alert")
bad(name, "; ".join(probs)) if probs else ok(name)

nvk, nve = keys(nv), env_of(nv)
name = "no-verdict notifier covers the image step"
probs = []
if "steps.images.outputs.verdict == ''" not in nvk.get("if", ""):
    probs.append("if: lacks steps.images.outputs.verdict == ''")
if "steps.images.outputs.verdict" not in nve.get("IMAGES_VERDICT", ""):
    probs.append("env IMAGES_VERDICT not wired")
bad(name, "; ".join(probs)) if probs else ok(name)

# Prod's own services must be in the probe list — the one the overdue check
# measures, and the worker, whose image went first in the incident.
env = {}
for l in lines:
    m = re.match(r"^  ([A-Z_]+):\s*(.*)$", l)
    if m: env[m.group(1)] = m.group(2)
svcs = env.get("IMAGE_SERVICES", "").split()
name = "IMAGE_SERVICES includes SERVICE and the worker"
need = [env.get("SERVICE", "?"), "palateful-worker-prod"]
missing = [x for x in need if x not in svcs]
bad(name, "missing %r from %r" % (missing, svcs)) if missing else ok(name)

name = "every SNS subject literal in the workflow is ASCII"
nonascii = [i + 1 for i, l in enumerate(lines)
            if ("--subject" in l or re.search(r'^\s*publish "', l)) and any(ord(c) > 126 for c in l)]
bad(name, "non-ASCII subject on line(s) %r" % nonascii) if nonascii else ok(name)

print("\n".join(out))
PY
while IFS= read -r w; do
  case "$w" in
    "OK "*)   echo "pass [wiring: ${w#OK }]"; PASS=$((PASS + 1)) ;;
    "FAIL "*) echo "FAIL [wiring: ${w#FAIL }]"; FAIL=$((FAIL + 1)) ;;
    *)        echo "FAIL [wiring]: unparseable: $w"; FAIL=$((FAIL + 1)) ;;
  esac
done < "$SANDBOX/wiring.txt"

echo
echo "image-exists self-test: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
