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
- If you decide to halt early (context budget, quality risk, blocker): emit the **Handoff Snippet** (below) and stop — do NOT push.

## Handoff Snippet (when stopping before the full run completes)

Emit this snippet whenever you stop short of finishing every story — `stop_after` reached, user asked to halt, or you decided to stop for context/quality reasons. The purpose is to let the user `/clear` and invoke `/dev` again in a fresh conversation **without that next agent having to rediscover anything**.

Rules:
- Only emit the snippet when stopping early. If the full run finished and pushed, skip it.
- Do NOT push. Unpushed commits are part of the handoff — the next agent will push them as part of its finalization after it finishes the remaining stories.
- Be concrete. Every fact a fresh agent would otherwise have to grep for belongs in the snippet.

Format the snippet exactly like this (inside a fenced ```` ```text ```` block so the user can copy-paste the whole thing as the next `/dev` input):

````text
/dev <epic-key>

RESUMING from prior session. Do not redo work below.

## Already done (do not rerun)
- <story-key>: <one-line summary> — commit <short-sha>
- <story-key>: <one-line summary> — commit <short-sha>
(Local commits unpushed; push in your finalization step.)

## Next up (in order)
- <next-story-key>: <one-line from epic file>
- <story-key>: ...
- <story-key>: ...

## State to trust
- `_bmad-output/planning-artifacts/<epic-file>.md` — current epic spec.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `<story-keys done>` marked `done`, rest `backlog`.
- `_bmad-output/implementation-artifacts/<done-story-key>.md` + `<done-story-key>-qa-walkthrough.md` — what shipped per story.
- Branch is ahead of origin by N commits; do `git log --oneline origin/main..HEAD` first to confirm.

## Gotchas from prior session (save time — don't rediscover)
- <concrete fact the next agent would otherwise waste context learning>
- <parallel-session / untracked-WIP collision note, if any>
- <framework/version quirk that bit us (e.g. "Riverpod 3.0-dev removed StateProvider — use NotifierProvider")>
- <any API/endpoint decision that deviated from the epic text and why>

## Do NOT
- Re-create story files that already exist under `_bmad-output/implementation-artifacts/`.
- Re-run migrations / re-stage commits that are already in `git log origin/main..HEAD`.
- Touch files outside this epic's File List unless a review finding requires it.

Continue from <next-story-key>. Full run expected to cover <remaining-story-keys>.
````

Fill every placeholder. The "Gotchas" list is the highest-value part — put anything concrete here that cost you more than a minute to figure out. Examples of good gotchas:

- "Router prefix is `/v1/activities`, not `/v1/user-activities` — epic text is wrong."
- "Untracked `services/migrator/migrations/versions/20260418030000_create_unit_aliases.py` is riip-1 WIP from a parallel agent; leave it alone, it'll chain off our migration once they rebase."
- "`migrator:check-models` fails locally due to the riip-1 untracked WIP (UnitAlias model without migration). CI on a clean checkout will pass."
- "Flutter tests that pump screens using Riverpod need `ProviderScope` — update legacy `MaterialApp(home: Screen())` test harnesses."

After emitting the snippet, say one sentence to the user summarizing why you stopped and then stop. Do not keep working.

## Finalization (After All Stories)

### Step 1: pubspec.yaml bump (if any app changes)

Inspect the changes on this branch:
```
git diff --name-only origin/main..HEAD
```

If any path under `app/lib/`, `app/test/`, `app/ios/`, `app/android/`,
`app/pubspec.yaml`, or `app/pubspec.lock` shows up in that diff — i.e. the
Flutter app will be rebuilt — you MUST bump `app/pubspec.yaml` before the
push.

1. Read the current `version: X.Y.Z+B` line.
2. Bump the **patch** and the **build number** by one (e.g., `1.0.7+20` →
   `1.0.8+21`). Keep them aligned; never skip either. (Major/minor bumps
   are only for user-visible release coordination — ask the user if it
   feels like that kind of ship.)
3. If `app/pubspec.lock` also changed during dev (new deps), stage it
   too.
4. Commit as a **single final commit** separate from the story commits:
   ```
   chore(app): bump to <new version> to ship <short epic summary>

   <1–2 sentences describing the user-visible outcome of the epic>

   Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
   ```
   (match existing convention: see `git log --oneline` for `chore(app): bump to…`)

If the diff has NO app-path changes (pure backend / infra / docs): skip
this step entirely — no version bump needed.

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
the epic is shipped. Waiting is **not optional** — do NOT ask the user
whether to wait; just do it. The epic isn't shipped until remote CI is
green on the HEAD commit.

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
