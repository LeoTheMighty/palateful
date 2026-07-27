---
hash: rmi000
type: plan
created: 2026-07-27T17:22:00-06:00
title: Recime mass-import — Chrome extension MVP with kill-switch, magic link, and contract canary
from: _bmad-output/planning-artifacts/epic-recime-mass-import.md
status: ready
mode: YOLO
---

## Scope
One-click migration from Recime to Palateful via a Palateful-branded Chrome extension (Manifest V3), converting Recime's lock-in friction into an acquisition lever — no competitor has built this in 4 years. The user logs into recime.app in their own browser; the extension uses their own session cookie to paginate Recime's internal web API and POST each recipe to `POST /v1/recipes/import/recime`, where `recime_normalizer.py` maps the payload into Palateful's recipe model, runs the existing duplicate-detection path, and files results into `Trying Out`. The legal posture is user-side data portability (mirroring Recime's own GDPR promise) rather than server-side scraping, with lawyer review running parallel to dev and gating only the public Chrome Web Store listing. Party-mode hardened the design with explicit session lifecycle endpoints, a `payload_schema_version` contract with schema-drift audit rows, a server-side kill-switch endpoint, a magic-link mobile→desktop hand-off, extension telemetry, extension CI/CD to the unlisted CWS track, and a nightly contract-drift canary.

## Pre-split stories (BMAD)
- recime-imp-1a — Spike: capture recime.app XHR/fetch shapes in DevTools, document the list/detail JSON contract, commit recorded fixtures (hard prerequisite for 1b; split from recime-imp-1 per party-mode 2026-04-25)
- recime-imp-1b — Backend: `recime_normalizer.py` + `POST /v1/recipes/import/recime` built from the 1a fixtures; dedup integration; `Trying Out` routing
- recime-imp-2 — Backend: per-endpoint rate limit (200 req / 5 min), `RecimeImportSession` start/end audit rows, 2-sessions/24h cap with friendly 429, `recime_mass_import` job type
- recime-imp-3a — Chrome extension MVP: manifest + popup + content script + background paginated-fetch worker with progress UI (split from recime-imp-3 per party-mode 2026-04-25)
- recime-imp-3b — Chrome extension hardening: kill-switch status query, `payload_schema_version` stamping, telemetry reporting, magic-link consumption
- recime-imp-4 — Frontend: walkthrough screen (video/Lottie steps, install CTA, FAQ, idle/no-recipes/disabled states, "email me the desktop link"), Activity Hub `recime_mass_import` row + per-recipe verdict sheet, deep-link to `Trying Out`
- recime-imp-5 — Lawyer checklist (parallel, sign-off captured in story file under `## Lawyer Sign-off`) + Chrome Web Store listing prep + e2e against a Recime test account
- recime-imp-6 — CI/CD + kill-switch + magic-link: `.github/workflows/chrome-extension.yml` (lint→build→zip→unlisted upload), `/v1/extensions/recime/status` + `/magic-link` + `/telemetry` endpoints, developer-account docs, rollback runbook (added by party-mode)
- recime-imp-7 — Contract-drift canary (nightly diff of recime.app response shape) + QA fixture set for CI replay + documented QA account roster (added by party-mode)

## Dependencies / notes
- Depends on `epic-recipe-default-books` (`Trying Out` destination) and `epic-import-duplicate-detection` (dedup helper) — both already shipped/shipping per sprint-status.
- Human/legal steps: lawyer review of TOS framing, FAQ/walkthrough copy, extension privacy policy, and CWS listing — runs parallel to dev but gates public Chrome Web Store launch (recommended: unlisted v1 → public after 30-day dogfood + green-light). Google developer account ownership/MFA/recovery must be documented.
- Escalated open questions needing human decisions: lawyer mechanics and SLA, listing strategy, mid-import API-break behavior, QA Recime account policy, whether pure-mobile users (no desktop) are acceptable v1 gap.
- Biggest risk is Recime silently breaking their internal API — mitigated by schema-version rejection, nightly canary, and the server-side kill-switch (no CWS push needed to disable).
- Also feeds `epic-nutrition-auto-calc`'s bulk-import inline-nutrition path (87-recipe import must not fire 87 recalc tasks).
- When /devx-plan picks this up it should emit dev specs from the pre-split stories rather than re-chunking from scratch.

## Status log
- 2026-07-27T17:22 — imported from BMAD (epic file + sprint-status.yaml) during BMAD→devx migration; no implementation commits on main as of import
