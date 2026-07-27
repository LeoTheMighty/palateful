# Expectations — Browser QA Agent

<!-- Gate 1 input. Minimum 3 E-blocks (config: engine.expectations_min).
     Every business goal (G-) must be covered by at least one expectation;
     every Covers: ID must resolve in prd.md. EARS regex enforced by
     `devx gate prd`: "When .+, the system SHALL .+". A P0 with a vague
     Verified-by target fails the gate. -->

## E-1: RED gate resolves runners in palateful

- **Priority:** P0
- **Covers:** G-1, FR-1, FR-2, CAP-1
- **Trigger:** `devx gate evals 41ee13 --dry-run` executed at repo root after
  the `projects:` block lands
- **Expectation (EARS):** When the RED-gate dry-run resolves this
  workstream's eval artifacts, the system SHALL match every artifact to a
  `projects:` runner with a test command, and the `qa:` config block SHALL
  name no tool that is not installed in the repo.
- **Threshold:** exactly 0 `not-run (no runner)` / "no `projects:` runner"
  lines in the dry-run output; `grep -c playwright devx.config.yaml` returns 0.
- **Verified by:** `_devx/workstreams/browser-qa-agent/evals/e1_runner_resolution.sh`

## E-2: One-command e2e suite green

- **Priority:** P0
- **Covers:** G-2, FR-3, CAP-2, UC-4
- **Trigger:** a single nx invocation (`npx nx run e2e:test`) on a clean
  checkout with Docker available
- **Expectation (EARS):** When the e2e target is invoked, the system SHALL
  bring up the e2e stack, run every `app/integration_test/*_test.dart` flow
  via `flutter drive` with the ChromeDriver flake mitigation applied, tear
  down, and exit 0 only if all flows pass.
- **Threshold:** ≥ 7 integration tests pass, exit code 0, on two consecutive
  runs back-to-back (flake bar).
- **Verified by:** `_devx/workstreams/browser-qa-agent/evals/e2_e2e_one_command.sh`

## E-3: Walkthrough template emission with executed checks

- **Priority:** P1
- **Covers:** G-3, FR-4, CAP-3, UC-1
- **Trigger:** a `/devx` story with a user-visible surface reaches Phase 6
- **Expectation (EARS):** When such a story completes, the system SHALL emit
  `test/test-<hash>-qa-walkthrough.md` from
  `_devx/templates/engine/qa-walkthrough.md` with every machine-checkable
  item executed and its evidence pasted, and human-only items left unchecked
  with a one-line verification hint.
- **Threshold:** template file exists; the first emitted walkthrough has
  100% of machine-checkable items checked with fenced evidence blocks and
  every human item carrying a "how to verify" line.
- **Verified by:** `_devx/workstreams/browser-qa-agent/evals/e3_walkthrough_emission.sh`

## E-4: Attended exploratory pass via /devx-test

- **Priority:** P1
- **Covers:** G-5, FR-5, FR-7, CAP-4, CAP-5, CAP-7, UC-2
- **Trigger:** Leo invokes `/devx-test <surface|story-hash>` in a session
  with Claude-in-Chrome connected and the local `E2E_MODE` web build running
- **Expectation (EARS):** When an attended exploratory pass runs, the system
  SHALL drive the named user journeys in the browser, route UX friction to
  `FOCUS.md` and reproducible bugs to `DEBUG.md`, and complete within the
  mode-derived cost cap.
- **Threshold:** ≥ 1 completed pass on the recipe-import journey; every
  finding lands in exactly one of FOCUS.md/DEBUG.md with a repro line;
  marginal spend ≤ $1; the framework QA.md carve-out (FR-7) is committed in
  the devx repo before the skill is installed here.
- **Verified by:** `_devx/workstreams/browser-qa-agent/evals/E-4_devx_test_pass.md`

## E-5: Interactive expectation goes RED for the right reason

- **Priority:** P1
- **Covers:** G-4, FR-6, CAP-6, UC-3
- **Trigger:** `devx gate evals` on a workstream whose expectation names a
  browser-flow eval artifact for a not-yet-built interactive feature
- **Expectation (EARS):** When the RED gate executes a browser-flow eval
  artifact for a missing feature, the system SHALL record a `right-reason`
  verdict (nonzero exit quoting the missing behavior), not
  `not-run (deferred: human)`.
- **Threshold:** 1 demonstration artifact in this workstream produces
  `right-reason` in `evals/RED-report.md`; the artifact shape is documented
  well enough that the next workstream reuses it without new wiring.
- **Verified by:** `_devx/workstreams/browser-qa-agent/evals/e5_red_browser_flow.sh`

## E-6: Persona-seeded pass (later phase)

- **Priority:** P2
- **Covers:** FR-8, UC-5
- **Trigger:** `/devx-test --persona <name>` with a persona file present in
  `focus-group/personas/`
- **Expectation (EARS):** When a persona-seeded pass is requested, the system
  SHALL seed the exploratory goals and tone from the named persona file and
  attribute findings to that persona.
- **Threshold:** ≥ 1 pass using a real persona file; findings annotated with
  the persona name.
- **Verified by:** `_devx/workstreams/browser-qa-agent/evals/E-6_persona_pass.md`
