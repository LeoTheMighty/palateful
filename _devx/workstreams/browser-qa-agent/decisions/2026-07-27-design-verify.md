---
gate: PASS
status_reason: 'All 25 source IDs fully covered in design mode.'
reviewer: 'devx gate coverage (design mode)'
updated: 2026-07-27
waiver: { active: false, approver: null, reason: null }
---

# Verify — _devx/workstreams/browser-qa-agent — 2026-07-27

## Subject

`design.md` reviewed against `prd.md` (design mode; workstream `41ee13`).

## Coverage

| ID | Status | Where covered | Note |
|---|---|---|---|
| G-1 | ✅ | Design > Architecture (surface 1: Config truth); Migration plan step 1; Constraints (RED-gate mechanics) | Concrete projects: table with four runner entries plus longest-prefix resolution semantics cited from gate-evals.ts; migration step 1 lands it immediately. |
| G-2 | ✅ | Design > Architecture (surface 2: Scripted layer); Risks (ChromeDriver flake); Assumptions (7-flow population); Interfaces | `npx nx run e2e:test` full lifecycle (up→wait→drive→teardown-trap→exit), targeted AppConnectionException retry, exit 0 iff all 7 flows pass, E-2 two-consecutive-runs bar. |
| G-3 | ✅ | Design > Architecture (surface 3: Story-derived QA); Wrap don't duplicate (Adds) | Single upstream template with machine/human item tags; /devx authors at Phase 5, executes every machine item inline with pasted evidence, commits with story in Phase 6. |
| G-4 | ✅ | Design > Architecture (Browser-flow eval convention); Risks (wrong-reason RED); Resolved design questions (right-reason mechanics) | Exit-code contract 0/1/2 with printed asserted behavior, one demonstration artifact (E-5) proving the shape; the subsequent-workstream usage is inherently future but the mechanism is fully specified. |
| G-5 | ✅ | Constraints (cost cap); Risks (attended-pass cost creep); Architecture (surface 4) | $1/day YOLO cap named as hard guardrail; skill enforces one-surface-per-invocation scope and reports spend against the cap; proven by E-4. |
| UC-1 | ✅ | Design > Architecture (surface 3); Interfaces (walkthrough files) | Emission wiring in /devx story flow: template-derived file, machine items executed with evidence, human items left unchecked with how-to-verify line, TEST.md entry appended. |
| UC-2 | ✅ | Design > Architecture (surface 4: Attended exploratory layer) | Full /devx-test protocol: precondition checks (Chrome connection, localhost:8888 E2E_MODE build), drive journeys, route friction→FOCUS.md / bugs→DEBUG.md / runner crashes→DEBUG.md-vs-devx. |
| UC-3 | ✅ | Design > Architecture (surface 1 + Browser-flow eval convention) | workstream-evals bash runner resolves eval scripts; scripts exit 1 (right-reason) while feature missing, exit 2 reserved for infra so wrong-reason REDs are distinguishable. |
| UC-4 | ✅ | Design > Interfaces; Architecture (surface 2) | `npx nx run e2e:test` is the one command; green/red via exit code; test-single/stack-up/stack-down retained for partial runs. |
| UC-5 | ✅ | Design > Architecture (Persona seeding paragraph); Migration plan step 4 | Seeding mechanism now concrete: persona goals/frustrations become journey priorities, vocabulary/tech-comfort sets interaction style, every finding annotated `persona: <name>` for greppable per-persona friction, unknown-name handling (list and stop) defined. |
| CAP-1 | ✅ | Design > Architecture (surface 1); Constraints (config shape, schema enum); Migration plan | projects: block specified entry-by-entry; qa: flip to claude-in-chrome/flutter-drive with the enum-extension ordering constraint handled explicitly. |
| CAP-2 | ✅ | Design > Architecture (surface 2); Wrap don't duplicate | Lifecycle wrapper over existing run_all.sh, flake pkill kept + one targeted retry, gen-1 moved to archive/e2e-maestro/, README rewritten. |
| CAP-3 | ✅ | Design > Architecture (surface 3); Constraints (skill/template ownership) | Template upstream in packaged templatesRoot modeled on ifh-1 skeleton; emission wiring in /devx skill; implements docs/QA.md:150-184 flow. |
| CAP-4 | ✅ | Design > Architecture (surface 4); Wrap don't duplicate (Adds) | .claude/commands/devx-test.md in the O-4 slot, mirrored to skills/ via sync:skills, routing mention at skills/devx.md:566 seam, devx next row in decide.ts with table test. |
| CAP-5 | ✅ | Design > Architecture (surface 4) | Explicit driver protocol (target resolution → precondition verify → drive → route findings per QA.md:129-133 → report spend) against local E2E_MODE build only. |
| CAP-6 | ✅ | Design > Architecture (Browser-flow eval convention); Trade-offs (.sh wrapper shape) | Documented .sh shape: self-locate repo root (cwd-independence per gate mechanics), precondition asserts, 0/1/2 exit contract, one demonstration artifact (E-5). |
| CAP-7 | ✅ | Design > Architecture (Decision propagation); Out of scope (unattended stays reserved) | Locked decisions/2026-07-27-hybrid-qa-driver.md propagates as devx-main commits to QA.md §Layer 2 (narrow carve-out wording given), OPEN_QUESTIONS addendum, O-4 update. |
| FR-1 | ✅ | Design > Architecture (surface 1 table); Constraints (config shape) | All four required entries present with concrete test commands; workstream-evals bash runner keeps eval scripts out of default suites; dry-run resolution stated. |
| FR-2 | ✅ | Design > Architecture (surface 1); Constraints (schema enum); Migration plan (ordering); Trade-offs (extend enum) | browser_harness: claude-in-chrome + scripted_test_runner: flutter-drive; the validator-rejection trap is caught and sequenced (enum lands upstream in step 2 before the step-3 flip). |
| FR-3 | ✅ | Design > Architecture (surface 2); Risks (bypass dormancy, DB mismatch); Data | Single nx target with teardown trap and nonzero exit; gen-1 flows/config archived to archive/e2e-maestro/; README rewritten to live path only; blocking env defects fixed in-scope. |
| FR-4 | ✅ | Design > Architecture (surface 3); Wrap don't duplicate (walkthrough format) | Template skeleton spelled out section-by-section from the ifh-1 exemplar with machine/human tags; note: design deliberately authors at Phase 5 (evidence freshest) and commits at Phase 6, a reasoned variation on the PRD's 'Phase 6 emits'. |
| FR-5 | ✅ | Design > Architecture (surface 4); Migration plan steps 2-3 | Skill body location, hybrid-driver protocol, TEST.md/walkthrough target reading, findings routing, cadence cap, routing row + devx next row; proved via first pass on recipe-import (step 3, E-4). |
| FR-6 | ✅ | Design > Architecture (Browser-flow eval convention); Interfaces (eval scripts) | Artifact shape documented (both .sh headless and test-single drive variants) with Gate 4 execution path and nonzero-while-missing contract; demonstration artifact in this workstream, real subsequent-workstream usage deferred to G-4's proof as the PRD itself specifies. |
| FR-7 | ✅ | Design > Architecture (Decision propagation); Out of scope | Narrow revision text specified (line 53 ❌ becomes split attended/unattended verdict), recorded in decisions/, propagated to QA.md + OPEN_QUESTIONS + O-4; unattended subprocess architecture explicitly preserved. |
| FR-8 | ✅ | Design > Architecture (Persona seeding paragraph); Migration plan step 4 | --persona <name> fully specified (persona-<name>.md resolution, derivation rules, annotation, error path) and the FR-5-first precondition is restated as a hard sequencing constraint, pinned by migration step 4 after step 3's end-to-end pass (E-6). |

## Extras requiring product approval

- E2E auth-bypass dormancy fix (ENVIRONMENT: development in docker-compose.e2e.yml api overlay)
- Migrator/API database mismatch fix (overlay DATABASE_URL override to the test database)
- Upstream config-schema.json browser_harness enum extension (claude-in-chrome)

## Verdict detail

PASS — every source ID is ✅ covered.
