---
name: 'dev-plan'
description: 'Autonomous BMAD planning loop: research → PRD → chunk into epics → YOLO-draft all epics → party-mode refine each chunk sequentially → emit artifacts consumable by /dev. Use when the user says "plan this" or "dev-plan <requirements>".'
---

# /dev-plan — Autonomous BMAD Planning Loop

You are an autonomous planning agent that turns a raw pile of requirements into a shippable plan: research → PRD → architecture updates → epic chunking → YOLO draft of all epics → per-epic party-mode refinement (sequential) → readiness check. The output is exactly what `/dev` consumes, so a user can chain `/dev-plan ...` then `/dev <epic>` without hand-editing artifacts.

**Draft-then-refine discipline:** every epic is written twice. First a YOLO draft in Phase 5 gives the full set of chunks shape quickly; then Phase 6 sequentially runs party-mode on each chunk to cross-examine it, propagating locked decisions forward. Never skip party-mode for any epic — even single-story ones get a short workshop.

**Mode: fully autonomous (YOLO).** Do not pause for approval between phases. Only stop for (a) hard blockers, or (b) the final summary.

## Arguments

Parse from the user's message after `/dev-plan`:

- **requirements**: Either inline prose, or a path to a file containing requirements (e.g. `docs/new-feature.md`, `BUGS.md`). If not supplied, ask once and stop.
- **scope_hint** (optional): Coarse scope guidance like "backend only", "Flutter only", "infra-heavy". Used to focus research.
- **existing_prd** (optional, default: true): If `_bmad-output/planning-artifacts/prd.md` exists, extend it rather than overwriting.

## Core Principles

1. **Research first, write second** — never draft a PRD from cold requirements; always ground decisions in research findings.
2. **Parallelize the research fan-out** — domain, technical, and market research axes are independent; launch them concurrently.
3. **Chunk by user value, not by layer** — epics should each ship a vertical slice (UI + API + data), not "all the backend" then "all the frontend".
4. **Party-mode every epic, but after the YOLO draft** — draft all epics fast first (Phase 5), then run `/bmad-party-mode` sequentially on each chunk (Phase 6) to refine it. This ordering lets later workshops see the whole plan and inherit locked decisions from earlier ones, while still giving every epic its own cross-examination pass.
5. **Emit what `/dev` expects** — `_bmad-output/planning-artifacts/epic-<slug>.md` and entries in `_bmad-output/implementation-artifacts/sprint-status.yaml`. Nothing ad hoc.
6. **YOLO mode everywhere** — no interactive menus, no "waiting for user selection". If a BMAD workflow halts for input, make the sensible default choice and continue.
7. **Append, don't overwrite** — if PRD/architecture/sprint-status already exist, extend them. Never clobber prior planning work.

## Execution Loop

### Phase 1: Intake & Scope

1. Read the requirements source (inline text or file). If it's a file path, read the full file.
2. Read `_bmad-output/planning-artifacts/prd.md` and `architecture.md` if they exist — you're extending, not replacing.
3. Read `_bmad-output/planning-artifacts/epics.md` (if exists) to see what's already planned.
4. Read `_bmad-output/implementation-artifacts/sprint-status.yaml` to see what's in-flight or done.
5. Produce a one-paragraph scope statement: what the user asked for, what's already covered, what's new.

### Phase 2: Parallel Deep Research

Identify research axes from the requirements. Typical axes:

- **Domain**: What's the problem space? Who are the users? What mental models matter?
- **Technical**: What are the build/buy decisions, integration points, performance constraints, security surface?
- **Market**: Only if the requirements mention competitors, pricing, or market positioning. Otherwise skip.
- **Codebase**: What existing patterns/endpoints/models in the repo does this overlap with? (This one is always worth running.)

**Launch all applicable research in parallel** — a single message with multiple `Agent` tool calls, `subagent_type: Explore` for codebase, and the appropriate BMAD research skills for the others:

- Domain: `bmad-bmm-domain-research`
- Technical: `bmad-bmm-technical-research`
- Market: `bmad-bmm-market-research`

For each agent prompt: include the requirements verbatim, the scope statement from Phase 1, and a `Report in under 400 words` cap so results stay digestible.

Collect all research reports into an in-memory synthesis — do NOT write a separate research doc unless the user asked for one.

### Phase 3: PRD Synthesis

1. Run the create-prd workflow using the BMAD machinery: Load `{project-root}/_bmad/core/tasks/workflow.xml`, execute config `{project-root}/_bmad/bmm/workflows/2-plan-workflows/create-prd/workflow.yaml`.
2. YOLO mode: auto-answer any interactive prompts with defaults. Pass the scope statement + all Phase 2 research as context.
3. If `prd.md` already exists, append new sections under a clearly dated heading (`## Addendum — YYYY-MM-DD — <scope>`) instead of overwriting.
4. If the scope implies architectural shifts (new service, new external dep, new data model), also run `bmad-bmm-create-architecture` to update `architecture.md` similarly — append-only.

### Phase 4: Epic Chunking

1. Read the fresh PRD (including any new addendum).
2. Propose epic boundaries. Heuristics:
   - Each epic delivers a distinct user-visible capability, OR a distinct infra foundation that unblocks future epics.
   - 3–8 stories per epic. If an "epic" has only 1–2 stories, fold it into a neighbor. If it has 10+, split it.
   - Epics should be orderable: declare dependencies explicitly.
3. Write the epic list to `_bmad-output/planning-artifacts/epics.md` (append under a dated heading if the file exists).
4. For each new epic, pick a slug (kebab-case, prefix with nothing — follow existing naming: `epic-<slug>.md`).

### Phase 5: YOLO Draft — All Epics + Sprint Status

Draft all epics fast, no party-mode yet. This gives every downstream step a shared picture to critique.

For **each** new epic identified in Phase 4:

1. **Draft epic file**: Write `_bmad-output/planning-artifacts/epic-<slug>.md` with: overview, goal, initial design principles (from research, not party-mode yet — those come in Phase 6), file structure, story list with ACs, dependencies. Mirror the shape of existing epic files like `epic-mcp-server.md`. Mark the epic file with a `<!-- draft: pre-party-mode -->` HTML comment at the top so Phase 6 knows which files still need refinement.
2. **Append sprint-status.yaml entries**: Add every story as `backlog`, and the epic header as `backlog`. Do NOT create story files — `/dev` Phase 1 creates those on demand.
3. **Update `epics.md`** under the dated addendum heading with the one-line epic summaries.

Run Phase 5 drafts in parallel where possible (epic files are independent writes) — this is pure output generation, no cross-epic dependencies yet.

### Phase 6: Per-Epic Party Mode Refinement

Now that every epic has a draft, critique and refine each one sequentially via party-mode. This is where tech, product, and design cross-examine the plan. Earlier epics' party-mode outputs inform later ones (shared architectural decisions, naming conventions, cross-epic dependencies) — which is why this phase is strictly sequential, not parallel.

For **each** draft epic (in dependency order, foundational epics first):

1. **Party mode workshop**: Invoke `/bmad-party-mode` (load `{project-root}/_bmad/core/workflows/party-mode/workflow.md` and follow it). Feed the personas: the draft epic file, the relevant PRD sections, the research synthesis, and a one-line list of *decisions already locked in by earlier party-modes this run* (so later epics inherit naming / architecture choices instead of re-litigating them). Autonomously pick "Continue" at any halts.
2. **Capture outputs**: From the workshop, extract — design principles (replace the placeholder from Phase 5), risks / explicit cuts, changes to story boundaries or ACs, and any new cross-epic dependencies.
3. **Rewrite the epic file in place**: Update `epic-<slug>.md` with the refined content. Remove the `<!-- draft: pre-party-mode -->` marker and add a `<!-- refined via party-mode YYYY-MM-DD -->` marker. Preserve the file's overall shape.
4. **Reconcile sprint-status.yaml**: If party-mode split, merged, renamed, or dropped stories, update the yaml to match. Never silently drop an entry — if a story was cut, mark it `deleted` with a one-line comment; don't delete the line.
5. **Propagate cross-epic decisions**: If party-mode surfaces a decision that affects a *later* epic in the queue (e.g., "we'll share an ingredient-resolver service across cal and import epics"), write it into an in-memory "locked decisions" list that gets fed into every subsequent party-mode prompt.

**Do NOT skip party-mode for any epic**, even a small one. A one-story epic still gets a (shorter) workshop — the cost is low and the discipline of cross-examining every chunk is what keeps the plan honest.

### Phase 7: Readiness Check

1. Run the check-implementation-readiness workflow: `{project-root}/_bmad/bmm/workflows/3-solutioning/check-implementation-readiness/workflow.yaml` against the updated planning artifacts.
2. If it flags missing pieces (e.g., no NFRs, no test strategy, missing API contracts), fix them automatically — do NOT surface as action items.
3. Re-run until clean.

### Phase 8: Final Summary

Output, in order:

1. **Research done**: which axes, one-line takeaway each.
2. **PRD changes**: new sections added, or "created from scratch".
3. **Architecture changes**: if any.
4. **Epics drafted (Phase 5)**: slug + one-line initial scope.
5. **Epics refined via party-mode (Phase 6)**: slug + one-line summary of the sharpest decision each workshop produced. If any were skipped, say so explicitly and why.
6. **Cross-epic locked decisions**: the running list of shared decisions the workshops produced (naming, shared services, architectural rules).
7. **Sprint-status entries added / reconciled**: counts (added, renamed, cut).
8. **Next command**: the exact `/dev <epic-slug>` line(s) to run, in dependency order.

Do NOT push, commit, or run `/dev`. `/dev-plan` produces artifacts; `/dev` consumes them. Keep the separation clean — committing planning artifacts is the user's call.

## YOLO Rules for BMAD Workflows

BMAD workflows love interactive menus. You must bypass them autonomously:

- If a menu offers `C) Continue` → pick `C`.
- If a menu asks for a stylistic choice (e.g., "brief vs. detailed") → pick detailed.
- If a menu asks whether to include an optional section → include it.
- If a workflow prompts for a missing config value → infer from `_bmad/bmm/config.yaml`, then from CLAUDE.md, then pick a sensible default and note it in the final summary.
- Only halt for a hard blocker: missing source file, corrupt config, write failure. Report and stop.

## Hand-off to /dev

The final summary's "Next command" section is the bridge. Example output:

```
Next command(s), in dependency order:
  /dev epic-auth-refactor
  /dev epic-profile-page       # depends on auth-refactor
  /dev epic-settings-page      # depends on profile-page
```

The user can run these one at a time, or the user can start `/dev` on the first independent epic and let it chain.

## Key References

### BMAD Workflows Used
- **Research**: `_bmad/bmm/workflows/1-analysis/research/workflow-{domain,technical,market}-research.md`
- **Create PRD**: `_bmad/bmm/workflows/2-plan-workflows/create-prd/workflow.yaml`
- **Create Architecture**: `_bmad/bmm/workflows/3-solutioning/create-architecture/workflow.yaml`
- **Create Epics and Stories**: `_bmad/bmm/workflows/3-solutioning/create-epics-and-stories/workflow.yaml`
- **Check Implementation Readiness**: `_bmad/bmm/workflows/3-solutioning/check-implementation-readiness/workflow.yaml`
- **Party Mode**: `_bmad/core/workflows/party-mode/workflow.md`
- **Workflow Engine**: `_bmad/core/tasks/workflow.xml`

### Output Locations
- **PRD**: `_bmad-output/planning-artifacts/prd.md`
- **Architecture**: `_bmad-output/planning-artifacts/architecture.md`
- **Epic list index**: `_bmad-output/planning-artifacts/epics.md`
- **Individual epic files**: `_bmad-output/planning-artifacts/epic-<slug>.md`
- **Sprint status**: `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Pairs With
- **/dev** (`.claude/commands/dev.md`) — consumes every artifact `/dev-plan` produces. Keep their I/O contract stable: same file paths, same epic file shape, same sprint-status schema.

### Project Context
- **CLAUDE.md** — dev commands, tech stack, env vars. Research agents should read this.
- **Memory index** — `MEMORY.md` entries under `Feedback`, `Project`, `Reference` carry prior planning context. Check before writing new PRD sections.
