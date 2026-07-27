# Decision — Hybrid QA driver (revises framework QA.md 2026-04-23)

Date: 2026-07-27
Status: locked (user-selected via planning interview)
Scope: this workstream; propagates to devx repo `docs/QA.md` via FR-7

## Decision

QA driving is split by attendance, not by layer:

- **Attended, on-demand exploratory passes** (`/devx-test` under YOLO's
  `on-demand` cadence) use **Claude-in-Chrome** browser tooling inside the
  Claude Code session.
- **Scripted / mechanical verification** (RED-gate eval artifacts,
  regression flows) uses the existing **flutter-drive + ChromeDriver**
  harness via a `projects:` runner — no LLM in the loop.
- **Unattended / scheduled QA** remains governed by the original 2026-04-23
  decision (subprocess browser-use/Stagehand on a separate pay-as-you-go
  key) and is out of scope here.

## What this revises

`~/personal/devx/docs/QA.md` (§Layer 2) and `docs/OPEN_QUESTIONS.md:148-155`
(RESOLVED 2026-04-23) mark Claude Code browser-MCP ❌ "Don't use for
automated QA". Rationale then: usage-window cost coupling and
unattended-run reliability.

## Why the carve-out is sound now

1. The 2026-04-23 decision predates current Claude-in-Chrome tooling.
2. Palateful's mode-derived cadence is `on-demand` (YOLO) — passes are
   user-attended by definition, so the usage-window decoupling rationale
   doesn't bind.
3. The $1/day cost cap (docs/MODES.md §2.6) is kept as the guardrail (G-5).
4. Scripted verification stays deterministic and free of session coupling,
   so the RED gate never depends on an attended browser session.

## Losing artifact + propagation

- Loser: `~/personal/devx/docs/QA.md` blanket ❌. Fix: narrow the ❌ to
  unattended/scheduled QA; document the attended carve-out. Tracked as FR-7;
  O-4 status note updated when `/devx-test` ships.
- `devx.config.yaml` `qa:` block in palateful is corrected in FR-2 (config
  currently claims playwright, which contradicts both reality and this
  decision — spec ACs > config, config loses).
