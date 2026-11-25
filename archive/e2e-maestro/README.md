# Archived — gen-1 Maestro E2E harness

Reference only. Nothing here runs, and nothing in the live tree points at
it. The live E2E suite is `services/e2e/` (flutter drive + integration
tests, one-command via `npx nx run e2e:test`).

| Path | What it was |
|------|-------------|
| `flows/` | Gen-1 Maestro YAML flows, moved verbatim. Superseded by `app/integration_test/0*_test.dart`. Never repaired — archived as-is. |
| `config.yaml` | Gen-1 Maestro config, moved verbatim. |
| `NEXT_STEPS.md` | Gen-2 status doc from before the lifecycle wrapper existed. Its manual stack-up → test → down recipe double-runs the lifecycle now that `e2e:test` owns it end to end; the still-true parts (flake note, chromedriver prereq, run recipes) were folded into `services/e2e/README.md`. Kept for the bug-history and file-inventory tables. |
