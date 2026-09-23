---
hash: e2echat1
type: dev
created: 2026-09-23T00:10:00-06:00
title: E2E flag without an environment guard — the class envspell1's gate cannot see
from: dev/dev-envspell1-2026-09-22T21:30-environment-spelling-divergence.md
status: ready
owner: null
branch: null
---

## Goal

`services/api/src/api/v1/chat/agent_loop.py:58` branches on
`settings.e2e_test_mode` **alone**, with no environment condition. Found
while independently verifying envspell1 (#66) by sweeping for bypass sites
rather than reading the PR's list.

**This is not an auth bypass and it did not belong in #66.** It grants no
identity and reaches no permission — the caller is already authenticated. It
is filed separately for that reason.

## What it costs

If `E2E_TEST_MODE` were ever true in production, `/v1/chat` would silently
return a canned string to real users:

    "I'm the E2E test assistant. I can see your recipes and help you cook!"

and persist it as an assistant message in their thread. No error, no 5xx, no
log line — the request succeeds. A user would see the product answer their
cooking question with test scaffolding, and nothing in prod would report it.

## ⚠️ The new CI gate structurally cannot catch this

`tools/environment-gate-check.sh` (envspell1) greps for **comparisons against
`ENVIRONMENT` / `settings.environment`** outside `utils/environment.py`. This
site contains no such comparison — that is precisely what is wrong with it.
So the gate protecting the environment predicate is blind to every site that
*omits* the environment check rather than spelling it wrong.

That is worth stating loudly rather than as a footnote: **envspell1's gate
guards the spelling of a condition, not its presence.** A whole class of the
thing it exists to protect is invisible to it, and the class is the more
dangerous one — a misspelled check fails closed and gets caught; an absent
check just isn't there.

## Measured state (2026-09-22, branch `feat/dev-envspell1` @ `3fd547c0`)

Four reads of `settings.e2e_test_mode` exist in `services/api/src`:

| site | environment guard | grants identity |
|---|---|---|
| `dependencies.py:119` | yes — `is_local_bypass_allowed` | yes |
| `dependencies.py:339` | yes — `is_local_bypass_allowed` | yes |
| `mcp_server/auth.py:138` | yes — `is_local_bypass_allowed` | yes |
| **`api/v1/chat/agent_loop.py:58`** | **none** | no |

Latency, measured: `e2e_test_mode` defaults `False`
(`services/api/src/config.py:38`); `E2E_TEST_MODE` appears in **no** terraform,
no CI workflow, and is absent from `palateful-api-prod:68`'s `environment`
and `secrets`. The only place it is set true is `docker-compose.e2e.yml:13`,
the local e2e stack. **So this is latent, not live** — as is the whole class.

## Acceptance criteria

- [ ] `agent_loop.py:58` requires an environment condition alongside
      `e2e_test_mode`, so the flag alone cannot change behaviour.
- [ ] **Decide the general rule, and make the gate able to see it**: every
      read of `e2e_test_mode` must be accompanied by an environment check.
      The natural enforcement is to extend `environment-gate-check.sh` to
      flag any `e2e_test_mode` read whose surrounding condition contains no
      environment predicate — turning an invisible class into a visible one.
      Without that, this recurs the next time someone adds a test shortcut.
- [ ] A test that the chat endpoint does **not** return the canned reply when
      `e2e_test_mode` is true but the environment is not bypass-eligible.
- [ ] Whatever guard is added, **prove it fails**: plant a bare
      `e2e_test_mode` read and confirm CI rejects it. envspell1's gate was
      verified this way and it is the only reason it is trusted.

## Technical notes

- Consider whether the right primitive is a single `is_e2e_bypass_armed()`
  helper that ANDs the flag with the environment, so no call site can read
  the flag bare. That makes the correct thing the easy thing and gives the
  gate one symbol to police instead of a pattern to infer. It would also
  cover `agent_loop.py`, which needs no identity but does need the guard.
- Cheapest possible mitigation, independent of code: never set
  `E2E_TEST_MODE` in any prod-adjacent configuration. That is true today and
  is what makes this latent — but it is a convention, not a control, and it
  is one copied `.env` away from being false.

## Status log

- 2026-09-23T00:10 — filed from independent verification of #66, at the
  coordinator's request. The site was found by sweeping for `e2e_test_mode`
  rather than reading #66's list of three; the sweep is what showed there is
  a fourth. Not a security finding, and deliberately not folded into #66.
