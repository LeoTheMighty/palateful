---
gate: PASS
status_reason: 'Scope widened by Leo (relayed by the orchestrator tab); PRD revised through devx revise and re-gated PASS.'
reviewer: '/devx revise'
updated: 2026-11-24
waiver: { active: false, approver: null, reason: null }
---

# Revision — admin-request-intake — 2026-11-24

## Subject

Leo's scope expansion, relayed mid-design by the orchestrator tab: a second
intake (faults from the running system), routing with four operations
(fit, create, split, combine), and removal of the `production` deploy
approval. Revised against the PRD as first gated.

## Decision

- **Slice 1 is unchanged**: the admin-request path only, because Leo's
  stated priority is "literally just want this working" and folding faults
  in would roughly double it.
- **Faults are slice 2.** Signals carry only server-chosen fields; `client`
  rows are excluded, because they arrive through a user endpoint
  (`services/api/src/api/v1/user/record_client_error.py:63`). The relay had
  framed fault text as non-adversarial; that was corrected and the relay
  agreed.
- **Routing ships with slice 2 as signals plus row bookkeeping.** The router
  is orchestrator work and split/combine are devx engine work (both
  external, O-5). Palateful supplies code locations, signatures and a
  compare-and-set `move`. A split that only prepares children and leaves the
  partition to a human still suffices.
- **The merge is the last human checkpoint.** 0 protection rules on
  `production`, checked with `gh api`.

## Corrections to relayed figures

- Relayed: "126 commits in 70 days, zero touching services/libraries/
  terraform". Measured: 23 of 127 touched them; the last is `cd6a3c3e`
  (2026-09-24); 0 of the 24 commits since. The relay confirmed the
  correction.

## Coverage

| ID | Status | Where covered | Note |
|---|---|---|---|
| G-6, G-7 | ✅ | prd/agent.md Goals | new |
| UC-9…UC-12, CAP-7, CAP-8 | ✅ | prd/agent.md | new |
| FR-18…FR-22 | ✅ | prd/agent.md | new |
| E-12…E-14 | ✅ | expectations.md | P1/P2, tests-after |

## Extras requiring product approval

- `source` and `fault_signature` columns in slice 1's migration, so slice 2
  needs no second migration — FR-1.
