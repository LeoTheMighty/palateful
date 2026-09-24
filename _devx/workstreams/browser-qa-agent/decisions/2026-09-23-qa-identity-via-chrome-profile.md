# Decision — the QA identity authenticates via a dedicated Chrome profile

Date: 2026-09-23
Status: locked (Leo executed it; the superseded design was never built)
Scope: this workstream; supersedes the `storageState` capture design
Reported by: palateful-3b. Recorded here by palateful-4f — see *Provenance*.

## Decision

The browser QA agent signs in as the prod QA identity through a **dedicated
`Palateful QA` Chrome profile**, signed in once by hand. No credential file,
no capture script, no token on disk.

Four steps, done once, already done:

1. Create a separate Chrome profile named `Palateful QA`.
2. **Enable the Claude-in-Chrome extension inside that profile.** Extensions
   are per-profile — this is the step people skip, and the symptom is the
   agent silently attaching to the wrong profile.
3. Sign in to prod once, by hand, as the QA identity.
4. Point the agent at that profile.

## What this replaces, and why

The specified design was a Playwright `storageState` captured by a script
reading a credential from an env file, with permission checks on the token
file and redacted error paths.

**It has no consumer.** Verified rather than taken on report:

- **No Playwright dependency exists.** Counted on `origin/main`:
  **105 files** mention "playwright", **90 of them under `_bmad/`** —
  framework documentation and manifests describing a harness this repo does
  not install. **Zero `package.json` files depend on it**, and no
  `pyproject.toml` declares it. The single hit in
  `services/parser/poetry.lock` is `nbconvert`'s optional `webpdf` extra,
  which is not installed.
  *(3b's report said "no Playwright anywhere in the repo". That is loose —
  a reader disproves it with one grep and then distrusts the rest. The
  accurate claim is that there is no Playwright **harness**, only docs that
  name one, and the argument never needed the sweeping version.)*
- **The actual e2e suite is `flutter drive` + ChromeDriver**
  (`services/e2e/scripts/run_all.sh`), which does not consume a
  `storageState`.
- **The QA agent is Claude-in-Chrome**, which attaches to a *running*
  Chrome and cannot load a `storageState` at all. This workstream's own
  design says so (`design/agent.md:14,22`), and at `:48` records that
  `claude-in-chrome` is rejected by the load-time validator because
  `qa.browser_harness` is `enum: [playwright, cypress, none]`.

### The argument worth keeping is the security one

> The env-file plus capture-script design had the credential transiting a
> script we wrote, an environment we read, and error paths we'd have to
> prove don't print it. The profile design has none of those surfaces.

**Fewer moving parts is the lesser reason. Fewer places a credential can
appear is the real one.** A design that needs redaction proofs is worse than
one with nothing to redact — and the redaction, the `chmod`, the gitignore
entry and the Auth0-rotation handling all disappear together, because they
were all consequences of writing the credential down.

## What it costs — a boundary, not an omission

**Headless and unattended runs.** A Chrome profile needs a live Chrome with
a human-initiated session. That is consistent with this workstream's
existing split (`2026-07-27-hybrid-qa-driver.md`): Claude-in-Chrome was
always the **attended** path, and unattended QA was always governed by the
2026-04-23 decision and out of scope.

If CI-style automation is wanted later, `storageState` acquires a real
caller and the capture script gets written **then** — with the permission
checks and redaction, because at that point they protect something that
exists.

## Constraint: the QA identity is not yet reversible

**`deluser1` — the script that would remove a prod user — does not exist.**
PR #84 is the **spec**, not the script. **Merging #84 does not make the
identity reversible**; only an implemented script does, and that needs an
implementer and a second reader before anyone starts.

Until it lands:

- every prod walkthrough under the QA identity **accretes rows nobody can
  delete**;
- the identity appears in `admin/list_users`;
- it **skews `admin/get_stats`**.

That is a real limit on how freely the agent should be pointed at prod, and
it belongs next to "we have a QA identity now" rather than in a separate
ticket. **Treat prod walkthroughs as append-only until the `deluser1`
script exists and has been run successfully** — not until its spec merges.

## Provenance

palateful-3b established all of the above and passed it here rather than
editing this workstream themselves.

**A correction to the premise, recorded because it affects who should own
this next:** 3b was told this area's recent work was mine. It isn't. The
only recent commit touching `_devx/workstreams/browser-qa-agent/` is
`64c8b7f5`, the flat-era layout migration I ran during backlog hygiene —
I moved these files, I did not author them. Every artifact here is from the
2026-07-27 planning run.

So this record is filed by the person who happened to touch the directory
last, which is a weak claim to it. **The workstream has no agent owner.** If
someone picks it up, the decision above is theirs to revisit — nothing here
was designed by its recorder.
