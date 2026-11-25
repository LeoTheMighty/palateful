---
hash: e2etok1
type: dev
created: 2026-09-23T02:10:00-06:00
title: The e2e bypass token is a security constant that exists twice
from: dev/dev-envspell1-2026-09-22T21:30-environment-spelling-divergence.md
status: ready
owner: null
branch: null
---

## Goal

`_E2E_TOKEN` is hard-coded in **two** places —
`services/api/src/dependencies.py` and `services/api/src/mcp_server/auth.py`
— and each copy guards an Auth0 bypass that returns a fully-onboarded
`e2e@palateful.test` user without verifying a token.

**The duplication is the finding, not the comparison.** envspell1's spec
named *one* bypass call site. There are three, and the other two were found
by a grep guard rather than by reading. A security constant that exists
twice is how a security boundary stays invisible: anyone auditing "where can
auth be bypassed?" greps the constant, finds their copy, and stops.

Secondary: both copies compare with `==` rather than
`hmac.compare_digest`. On its own that is a weak finding — the token is a
fixed known string, not a secret being guessed — but it is free to fix while
the constant is being moved.

## Acceptance criteria

- [ ] One definition of the token and one bypass predicate, imported by all
      three call sites. No second copy anywhere.
- [ ] Comparison via `hmac.compare_digest`.
- [ ] A test that fails if a second definition appears — the grep-guard
      shape (`tools/environment-gate-check.sh` is the model), because the
      property to protect is "there is exactly one", which no unit test of
      the constant itself can express.
- [ ] The bypass's three conditions stay independent and unchanged:
      `E2E_TEST_MODE`, `is_local_bypass_allowed(environment)`, token match.
      This story moves code; it must not relax a gate.
- [ ] `services/e2e/README.md` points at the single definition.

## Technical notes

- Blocked by nothing, but land **after** envspell1 (#66), which is already
  editing all three call sites.
- Measured 2026-09-22: the bypass is not armed in prod by two independent
  conditions — `ENVIRONMENT=prod`, and no `E2E_TEST_MODE` in the task
  definition at all (`e2e_test_mode` defaults to `False`). This is a
  latent-exposure cleanup, not an incident.
- Do not "simplify" the three conditions into fewer while consolidating.
  Each one independently keeps the bypass shut in prod.

## Status log
- 2026-09-23T02:10 — filed from envspell1's adversarial review. Raised as
  "pre-existing, adjacent" by the reviewer; 41 ruled it should be filed as
  the duplication rather than as the comparison, since the duplication is
  what hid two of the three bypass sites from envspell1's own spec.
