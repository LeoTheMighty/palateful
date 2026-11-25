---
hash: envspell1
type: dev
created: 2026-09-22T21:30:00-06:00
title: ENVIRONMENT has five spellings and the gates using it fail in opposite directions
from: dev/dev-selfheal1-2026-09-20T11:45-503-only-when-a-restart-can-fix-it.md
status: in-progress
owner: /devx-2026-09-22T1809-40329
branch: feat/dev-envspell1
---

## Goal

> **Opposite defaults are not enough, because normalisation is itself
> directional.** This is the finding. The first implementation gave the two
> predicates carefully opposite defaults and then a *shared* normaliser —
> which made all three auth-bypass gates looser than the byte-exact
> comparisons they replaced, while its comments claimed unchanged
> strictness. Decide the normalisation per predicate, by what the wrong
> answer costs: a stray newline tolerated is correct for a recorder and
> wrong for an authentication boundary.
>
> **Read this before reaching for a "canonicalise the spelling" helper.**
> Three of the gates keyed on `ENVIRONMENT` are **Auth0 bypasses** that
> return a fixed test user without verifying a token. Any normalisation that
> loosens matching moves an authentication bypass toward armed. That is a
> security consequence hiding inside what looks like a config tidy-up.

`ENVIRONMENT` is compared against string literals in gates that fail in
**opposite directions**, and the repo carries five spellings of it.

**Measured 2026-09-22, before changing anything:**

| Spelling | Where |
|---|---|
| `prod` | `terraform/environments/prod/main.tf` -> ECS. **What prod actually runs** (`palateful-api-prod:66` and `palateful-worker-prod:56` both measured). |
| `dev` | `terraform/environments/dev/main.tf` -> ECS. A **deployed** environment, not a local one — the trap in the name. |
| `development` | `docker-compose.e2e.yml` |
| `test` | `services/api/tests/conftest.py` |
| `production` | the **root** `SETUP.md`'s production `.env` template (`docs/SETUP.md` is a different file and never had the line) |

So the 4xx audit writer **is working in prod today** — the original filing
implied it had been silently quiet, which is false. The hazard is for
whoever deploys from the documented template.

**Two sources, which can disagree in one process.**
`utils.constants.ENVIRONMENT` reads `os.environ` directly.
`services/api/src/config.Settings.environment` is a pydantic field
defaulting to `"dev"`. With `ENVIRONMENT` unset, one is `None` and the other
is `"dev"`.

**Six consumers, two failure directions:**

- `utils/api/endpoint.py` — `!= "prod"` gates the 4xx audit writer. An
  unrecognised spelling **silently disables a recorder**. Fails quiet.
- `services/api/src/dependencies.py` (**two** call sites) and
  `services/api/src/mcp_server/auth.py` — `in ("development", "test")` gates
  an **Auth0 bypass**. An unrecognised spelling must **deny**. Fails closed,
  and must keep failing closed.
- `utils/services/db_probe.py` — `DEPLOYED_ENVIRONMENTS` allowlist
  (selfheal1). Unknown -> not deployed.
- `services/api/src/config.py` — interpolated into **AWS resource names**
  (`palateful-imports-{env}` and four more). Prod sets all five explicitly,
  so this is a fallback; a wrong spelling would only bite a deployment that
  omits them.
- `services/api/src/api/v1/admin/get_logs.py` — maps `dev` -> `prod` for a
  CloudWatch log group. Naming, not gating.
- `services/parser/project.json` — `${ENVIRONMENT:-dev}` in queue names.

## Why one canonical string is the wrong fix

A single helper has a single default, and these gates need opposite ones.
Make unknown mean "not production" and a typo silently stops recording;
make unknown mean "local" and a typo arms an auth bypass. The safe default
is a property of **what the wrong answer costs**, not of the variable.

So: two predicates, opposite defaults, in `utils/environment.py`.

    is_production(value)            unknown -> True   (recorders stay on)
    is_local_bypass_allowed(value)  unknown -> False  (the bypass stays shut)

They are deliberately **not inverses**. `staging` records like production
*and* refuses the bypass; `dev` does neither. Same rule the health probe
arrived at in selfheal1: the privileged or destructive decision needs
positive identification, never an inference from absence.

## Acceptance criteria

- [x] Two predicates with opposite defaults. **Normalisation is
      per-predicate, not shared**: `is_recording_environment` normalises
      case and whitespace (`"PROD"`, `" prod\n"` all read as `prod`);
      `is_local_bypass_allowed` compares **byte-exactly**, so it is no
      looser than the tuple tests it replaced.
- [x] Every gate routed through them. No bare `== "prod"` left outside the
      predicates' own module.
- [x] `BYPASS_ELIGIBLE` excludes `dev`, and says why in the code: the
      deployed dev environment is reachable from the internet.
- [x] The root `SETUP.md`'s template says `prod`, with a comment saying why
      the exact string matters.
- [x] `.env.example` documents the local default and its consequence
      (unset counts as production for recorders).
- [x] A CI grep guard blocking new bare comparisons, with an allowlist for
      naming-not-gating cases (`tools/environment-gate-check.sh`,
      `tools/environment-gate-allowlist.txt`), wired into `ci.yml`.
- [x] The guard is **mutation-verified** against ten planted shapes —
      `==`/`!=` in either operand order, `in` against tuple/list/set
      literals, `os.environ["ENVIRONMENT"]` and `os.environ.get(...)`, a
      gate with a trailing comment — plus a pure comment that must *not*
      trip it, plus a drifted allowlist fingerprint that must fail loudly.
      Shapes it still misses are named in the script header rather than
      implied absent.
- [x] Tests pin the asymmetry itself, not just the recognised spellings.
- [ ] ~~`db_probe.DEPLOYED_ENVIRONMENTS` drops the defensive `production`
      entry.~~ **Withdrawn.** Keeping it is the fail-safe direction, and a
      deployment that predates the SETUP.md correction must not silently
      lose `NOT_CONFIGURED`. It costs nothing to keep.

## What adversarial review changed

- **The first implementation made all three bypass gates looser** and its
  own comments claimed the opposite. Sharing one normaliser between the
  predicates meant `TEST`, `Test`, `" test "`, `"test\n"` and `"\xa0test"`
  denied the bypass before the change and armed it after. Normalisation is
  itself directional: tolerating a stray newline is right when a mismatch
  costs a silent recorder and wrong when it costs an authentication bypass.
  `is_local_bypass_allowed` is now byte-exact and pinned as a property.
- `is_production` was renamed `is_recording_environment`: a general-sounding
  name invites reuse in the permissive direction (`if is_production():
  use_real_payment_key()`), where unknown -> True is exactly backwards.
- The guard missed list/set-literal membership, reversed operands and direct
  `os.environ` reads — the last being the shape `utils/constants.py` itself
  uses, and so the likeliest re-introduction. Pattern widened; remaining
  blind spots documented in the script.
- Allowlist entries carry a **fingerprint** of the exempted line, not just a
  line number, so an exemption cannot drift onto code nobody reviewed.
- `"local"` was dropped from `NON_PRODUCTION`: it had no measured source,
  and that set is the fail-quiet one.
- `libraries/utils/test/conftest.py` now declares `ENVIRONMENT=test`, because
  unknown -> True otherwise starts exercising the 4xx audit writer in a
  suite that sets no database.

## Why the independent review's null result is worth something here

A clean second review is usually weak evidence — it rules out what the
reviewer thought to look for. It is stronger here for one structural reason:
**the code being replaced was byte-exact**, so "did this get stricter or
looser?" had a crisp, mechanically checkable answer. The reviewer could
enumerate inputs and diff old behaviour against new, rather than judge
whether a gate "looks right".

The next security-shaped change may not have that baseline — replacing a
fuzzy check with another fuzzy check, or adding a gate where none existed.
A clean review then proves considerably less, and the way to buy back the
evidence is to manufacture a baseline first: pin the current behaviour in a
test *before* changing it, so the diff is against something measured rather
than something remembered.

## Technical notes

- `db_probe._database_expected` shares the normaliser but **keeps its own
  default** (unknown -> False). `is_production`'s unknown -> True is right
  for recorders and wrong there: it would make every local run with no
  database assert `NOT_CONFIGURED`.
- Measured: the bypass is not armed in prod by two independent conditions —
  `ENVIRONMENT=prod`, and no `E2E_TEST_MODE` in the task definition at all
  (`e2e_test_mode` defaults to `False`).
- The third bypass copy (`mcp_server/auth.py`) and the second one in
  `dependencies.py` were **found by the guard**, not by reading — the
  original spec named one call site.

## Status log
- 2026-09-22T21:30 — filed from selfheal1's Phase 4 review (Blind Hunter F8).
  selfheal1 shipped the defensive `production` entry so its own verdict could
  not be silently lost; the underlying divergence is this spec.
- 2026-09-22T18:09:06-06:00 — claimed by /devx in session /devx-2026-09-22T1809-40329
- 2026-09-23T02:40 — **independently verified by palateful-0a** at 3fd547c0,
  at 41's direction, because the author had already armed this boundary once.
  It confirmed byte-exactness against the six shapes named here plus thirteen
  more nobody listed (including `te\u017ft`, the casefold widening); located
  the three bypass call sites itself rather than working from the author's
  list (they matched); confirmed each site keeps its three independent
  conditions; confirmed `is_recording_environment` cannot reach a permission;
  re-measured the prod posture itself rather than accepting the measurement
  here (`palateful-api-prod:68`, `ENVIRONMENT=prod`, `E2E_TEST_MODE` absent
  from both `environment` and `secrets`); and **proved the new CI gate can
  fail by planting a real violation**. It also found a fourth `e2e_test_mode`
  site (`agent_loop.py:58`) that gates on the flag alone and grants no
  identity — not an auth bypass, filed separately as #67.
