---
id: E-8
priority: P1
covers: [G-1, G-2, UC-1, UC-2, UC-3, UC-4, UC-5, FR-13, FR-14]
expectation: 'When Leo files a request in production with the bridge running, the system SHALL put the decision question in front of him within 10 minutes, and after he adopts it SHALL show the row as `accepted` with the quarantine file''s hash equal to the row''s.'
status: red      # red | green — last result of the non-deferred steps
last_run: null
---

# E-8: The live path works in production

<!-- Human procedure, validation type `human` in plan/agent.md, so Gate 4
     defers it (legal at P1). It is the vertical slice's acceptance: run it
     once Phases 1–3 are deployed and external gate X-1 (the bridge) is
     installed. Phases 4–6 start only after it passes.

     Every command runs in a PLAIN TERMINAL, never inside a Claude session
     (not even with `!`): steps 4 and 7 print request text. -->

## Preconditions

- Phases 1–3 merged and deployed (`main` deploys automatically on merge).
- The bridge installed and loaded:
  `launchctl list | grep -i palateful` shows its job.
- Leo signed in to the web admin as an admin.
- Pick a canary word for this run, e.g. `WALKCANARY` plus 6 random letters.

## Steps

### 1. human — file a request from the panel

- **Run:** In the web admin, open "Request a change"; title `Walkthrough <canary>`, body `Walkthrough body <canary>`, done-when `Seen in quarantine`. Submit; note the id8 shown and the clock time.
- **Expected:** the form shows an id8 and "Leo will be asked about it on his laptop."

### 2. human — the question arrives in time

- **Run:** Wait for the orchestrator's question about that id8; note the clock time.
- **Threshold:** at most 600 seconds after step 1.
- **Expected:** the question names the id8 and a submitter alias, and no part of the title or body.

### 3. script — the row is `received` and the poll carries no text

- **Run:** `bin/prod-script services/api/scripts/dev_requests_read.py poll | tee /tmp/e8-poll.txt | grep -c <canary>`
- **Expected:** `0`, and `/tmp/e8-poll.txt` shows the id8 with `"status":"received"`.

### 4. human — read it outside any LLM session

- **Run:** `bin/prod-script services/api/scripts/dev_requests_read.py show <id>`
- **Expected:** the title, body and done-when exactly as typed in step 1.

### 5. human — adopt it

- **Run:** Answer the orchestrator's question: Adopt.
- **Expected:** the bridge reports the quarantine path.

### 6. script — accepted, and the quarantine hash matches

- **Run:** `bin/prod-script services/api/scripts/dev_requests_read.py poll | grep <id8>`, then read the `content_sha256` in the quarantine file's header.
- **Expected:** the record shows `"status":"accepted"`, and its `content_sha256` equals the quarantine header's.

### 7. script — nothing leaked into the orchestrator's surfaces

- **Run:** `grep -c <canary> ~/.claude/orchestrator/personal/events.ndjson ~/.claude/orchestrator/personal/ledger.json ~/.claude/orchestrator/personal/TODO.md ~/.claude/orchestrator/personal/TODO_CONTEXT.md`
- **Expected:** `0` for every file that exists.

### 8. human — decline a second request

- **Run:** File a second request (step 1), wait for the question, answer Decline · duplicate.
- **Expected:** `poll` no longer lists it; `show <id>` reports status `declined`.

### 9. metric — prompt latency `(measured at outcome)`

- **Run:** `bin/prod-script services/api/scripts/dev_requests_read.py metrics`
- **Window:** first production request → 2027-02-28
- **Expected:** `received_lag_s_max` ≤ 600
- **Result:** _(measured at outcome)_

## Runs

| Date | Who | Steps passed | Verdict | Notes |
| --- | --- | --- | --- | --- |
