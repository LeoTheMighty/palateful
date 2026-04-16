---
name: 'dev'
description: 'Autonomous development loop: create stories, implement, review, fix, CI, commit — then push at the end. Use when the user says "dev this epic" or "start the dev loop"'
---

# /dev — Autonomous BMAD Development Loop

You are an autonomous development agent executing the full BMAD lifecycle for an epic. You create stories, implement them, review them, fix issues, get CI passing, commit — then push everything at the end.

## Arguments

The user may provide arguments after `/dev`. Parse these from the user's message:

- **epic**: Which epic to work on (e.g., `epic-mcp-server`, or a path to the epic file). If not specified, ask.
- **stop_after**: When to stop (e.g., `story 3`, `all`, a specific story key). Default: `all` (complete every story).
- **instructions**: Any extra instructions or constraints (e.g., "skip tests for now", "focus on backend only", "use FastMCP not raw SDK").

## Core Principles

1. **Never duplicate business logic** — wrap existing endpoints and tools
2. **One commit per story** — atomic, reviewable units
3. **Fix forward** — if review finds issues, fix them in the same story, don't skip
4. **Local CI must pass** before moving to the next story — lint, tests, AND `check-models` (Alembic drift)
5. **Push only at the very end** — all commits stay local until the full run is done
6. **pubspec.yaml changes** (if any Flutter/app changes exist) go in a **separate final commit** before the push
7. **Remote CI must also pass** — after the push, wait for GitHub Actions and fix any failures before declaring the epic done

## Execution Loop

For each story in the epic (respecting `stop_after`):

### Phase 1: Create Story Context

1. Read the epic file to extract the current story's requirements, ACs, and technical approach
2. Read the sprint-status.yaml to find the story's current status
3. If story status is `backlog`:
   - Invoke the create-story workflow: Load `{project-root}/_bmad/core/tasks/workflow.xml`, execute with config `{project-root}/_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml`
   - This creates a comprehensive story file in `_bmad-output/implementation-artifacts/`
   - Use YOLO mode (minimal prompts) — do not pause for user confirmation
4. If story status is `ready-for-dev` or `in-progress`, the story file already exists — read it and continue

### Phase 2: Implement Story

1. Invoke the dev-story workflow: Load `{project-root}/_bmad/core/tasks/workflow.xml`, execute with config `{project-root}/_bmad/bmm/workflows/4-implementation/dev-story/workflow.yaml`
2. Pass the story file path as the story_file parameter
3. Execute ALL tasks and subtasks. Do NOT stop at milestones or session boundaries.
4. Follow red-green-refactor: write failing tests → implement → refactor
5. Update the story file's File List with every file created/modified/deleted
6. Mark story status as `review` when all ACs are satisfied

### Phase 3: Code Review

1. Invoke the code-review workflow: Load `{project-root}/_bmad/core/tasks/workflow.xml`, execute with config `{project-root}/_bmad/bmm/workflows/4-implementation/code-review/workflow.yaml`
2. Review is **adversarial** — find 3-10 specific issues minimum
3. For ALL findings (HIGH, MEDIUM, LOW): **fix them automatically** — do NOT ask the user or create action items
4. After fixing, re-run the review to verify fixes are clean
5. Update story status to `done` when review passes

### Phase 4: Local CI Validation

Run **every** relevant check for the story's surface area. Don't say "CI is
working" until all of these pass:

1. **Lint** every project the story touched:
   - `npx nx run api:lint` (if you changed `services/api/src/`)
   - `npx nx run utils:lint` (if you changed `libraries/utils/utils/`)
   - `npx nx run migrator:lint` (if you added/edited migration files)
   - `dart analyze lib/features/<feature>/` (if you touched Flutter)
2. **Tests** for every touched project:
   - `npx nx run api:test` (FastAPI suite)
   - `poetry run pytest libraries/utils/` (utils suite)
   - `flutter test test/features/<feature>/` (Flutter tests for the feature)
3. **Alembic model drift** — if the story added migrations OR changed any
   SQLAlchemy model in `libraries/utils/utils/models/`:
   - `npx nx run migrator:check-models`
   - This runs `alembic check` against a freshly-migrated test DB and
     fails if any model has changes without a migration. CI runs this on
     every PR, so catch drift locally.
4. If any check fails:
   - Read the error output carefully
   - Fix the root cause (don't paper over it)
   - Re-run until green
5. Do NOT proceed to commit until lint + tests + check-models all pass.

### Phase 5: Commit (Local Only — Do NOT Push)

1. Stage only the files relevant to this story (use `git add <specific files>` — never `git add -A`)
2. Commit with message format:
   ```
   feat(mcp): Story X.Y — <story title>

   <1-2 sentence summary of what was built>

   Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
   ```
3. Do NOT push yet — continue to next story

### Phase 6: Next Story or Finish

- If more stories remain (and `stop_after` not reached): go back to Phase 1
- If all stories done or `stop_after` reached: proceed to Finalization

## Finalization (After All Stories)

### Step 1: pubspec.yaml Commit (if needed)

Check if any Flutter/app files were modified across all stories:
- If YES: Stage `app/pubspec.yaml` and `app/pubspec.lock` in a **separate commit**:
  ```
  chore(app): bump dependencies for MCP integration

  Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
  ```
- If NO: skip this step

### Step 2: Push Everything

1. Run `git log --oneline origin/main..HEAD` to show the user exactly what
   will be pushed.
2. Ask the user for confirmation before pushing (single prompt, not per
   commit).
3. Push to main: `git push origin main`.

### Step 3: Wait for GitHub Actions CI

Local checks catch most issues, but they do NOT catch:
- Docker builds
- Integration tests that only run in CI
- Cache/dependency skew between environments
- Platform-specific breakage (CI runs linux/arm64, dev runs darwin/arm64)

So after the push, you are NOT done — wait for remote CI before claiming
the epic is shipped.

1. Capture the latest run for the pushed commit:
   ```
   gh run list --branch main --limit 1 --json databaseId,status,conclusion,url,headSha
   ```
   Verify `headSha` matches the commit you just pushed (`git rev-parse HEAD`).
2. Poll until `status == "completed"`. Use the `ScheduleWakeup` tool with
   ~120s delays so you don't burn cache entries. Cheap command:
   ```
   gh run watch <run-id> --exit-status --interval 20
   ```
   (note: `watch` blocks, so prefer `run_in_background: true` or scheduled
   wakeups over a foreground poll).
3. If `conclusion == "success"`: done. Continue to Step 4.
4. If `conclusion != "success"`:
   - Fetch the failed job logs:
     ```
     gh run view <run-id> --log-failed
     ```
   - Identify the failing check (lint? test? check-models? docker build?)
   - Fix the root cause in a new commit on `main` (do NOT rewrite history).
   - Push the fix, go back to step 1.
   - Do NOT declare the epic done while CI is red.

### Step 4: Summary

Output a summary:
- Stories completed (with commit hashes)
- Files changed (total count)
- Local test pass counts (api / utils / flutter)
- Remote CI run URL + conclusion
- Any notes or follow-ups

## Key References

These documents provide critical context for implementation:

### BMAD Workflows
- **Create Story**: `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml`
- **Dev Story**: `_bmad/bmm/workflows/4-implementation/dev-story/workflow.yaml`
- **Code Review**: `_bmad/bmm/workflows/4-implementation/code-review/workflow.yaml`
- **Workflow Engine**: `_bmad/core/tasks/workflow.xml`

### Project Knowledge
- **Architecture**: `_bmad-output/planning-artifacts/architecture.md`
- **PRD**: `_bmad-output/planning-artifacts/prd.md`
- **Sprint Status**: `_bmad-output/implementation-artifacts/sprint-status.yaml`
- **Epic Files**: `_bmad-output/planning-artifacts/epic-*.md`
- **CLAUDE.md**: Project root — development commands, tech stack, env vars

### Codebase Patterns
- **Endpoint base class**: `libraries/utils/utils/api/endpoint.py` — `Endpoint.run()` returns `{success, data, status}`
- **Agent tool base**: `libraries/agent/agent/tools/base.py` — `BaseTool.execute(db, user_id, **kwargs)`
- **Auth dependency**: `services/api/src/dependencies.py` — JWT verification pattern
- **Router registration**: `services/api/src/routers/v1_router.py`
- **Main app**: `services/api/src/main.py` — middleware + router mounting

### Dev Workflow Preferences (from memory)
- After code review findings are addressed: commit and push to main
- Always fix review issues automatically — never ask or create action items
- Standard loop: read → implement → review → fix → commit → push → repeat
- QA walkthrough checklist output with each story completion
