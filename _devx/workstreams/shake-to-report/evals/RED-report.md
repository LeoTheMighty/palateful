---
gate: PASS
status_reason: 'Every runnable expectation observed RED for the right reason (4 run(s), 6 deferred).'
reviewer: 'devx gate evals'
updated: 2026-11-25
waiver: { active: false, approver: null, reason: null }
---

# RED report — _devx/workstreams/shake-to-report — 2026-11-25

## Runs

### E-1: A deliberate shake opens feedback over the current screen (P0)

- **Artifact**: _devx/workstreams/shake-to-report/evals/E-1_user_path.sh
- **Command**: `bash run-eval.sh shake-to-report/evals/E-1_user_path.sh`
- **Exit code**: 1
- **Failure quote**:
  ```
    SHAKE-DIAG booted at /; motion listeners so far: 0  [control: the real app boots signed in, no exception]
    SHAKE-DIAG booted at /; motion listeners so far: 0  [control: a prompt-shaped snackbar is found and its action taps]
    SHAKE-DIAG booted at /; motion listeners so far: 0  [control: the sheet finder sees the sheet Profile's tile opens]
    SHAKE-DIAG booted at /; motion listeners so far: 0  [E-1: shake → prompt → Report → sheet over the same screen → submits route and trigger shake]
    SHAKE-DIAG after shake: listeners=0 subscribed=false prompts=0 sheets=0 location=/  [E-1: shake → prompt → Report → sheet over the same screen → submits route and trigger shake]
    SHAKE-DIAG booted at /; motion listeners so far: 0  [E-1: an ignored prompt fades in 4 s and leaves the screen as it was]
    SHAKE-DIAG after shake: listeners=0 subscribed=false prompts=0 sheets=0 location=/  [E-1: an ignored prompt fades in 4 s and leaves the screen as it was]
  EVAL E-1: tests=6 passed=4 red=2 blind=0 wrong=0 flutter_exit=1
  EVAL-RED E-1: E-1: shake → prompt → Report → sheet over the same screen → submits route and trigger shake -> SHAKE-RED[E-1:no-prompt]
  EVAL-RED E-1: E-1: an ignored prompt fades in 4 s and leaves the screen as it was -> SHAKE-RED[E-1:no-prompt]
  ```
- **RED verdict**: right-reason

### E-2: Everyday kitchen motion never prompts (P0)

- **Artifact**: _devx/workstreams/shake-to-report/evals/E-2_everyday_motion.sh
- **Command**: `bash run-eval.sh shake-to-report/evals/E-2_everyday_motion.sh`
- **Exit code**: 1
- **Failure quote**:
  ```
    SHAKE-DIAG booted at /; motion listeners so far: 0  [control: the real app boots signed in, no exception]
    SHAKE-DIAG booted at /; motion listeners so far: 0  [control: a prompt-shaped snackbar is found and its action taps]
    SHAKE-DIAG booted at /; motion listeners so far: 0  [control: the sheet finder sees the sheet Profile's tile opens]
    SHAKE-DIAG booted at /; motion listeners so far: 0  [E-2: eight everyday traces prompt 0 times; a deliberate shake in the same session prompts once]
    SHAKE-DIAG everyday motion 60 s, false triggers: [], motion listeners=0  [E-2: eight everyday traces prompt 0 times; a deliberate shake in the same session prompts once]
    SHAKE-DIAG after shake: listeners=0 subscribed=false prompts=0 sheets=0 location=/  [E-2: eight everyday traces prompt 0 times; a deliberate shake in the same session prompts once]
  EVAL E-2: tests=5 passed=4 red=1 blind=0 wrong=0 flutter_exit=1
  EVAL-RED E-2: E-2: eight everyday traces prompt 0 times; a deliberate shake in the same session prompts once -> SHAKE-RED[E-2:positive-control-no-prompt]
  ```
- **RED verdict**: right-reason

### E-3: A shake never interrupts what the user is doing (P0)

- **Artifact**: _devx/workstreams/shake-to-report/evals/E-3_no_interruption.sh
- **Command**: `bash run-eval.sh shake-to-report/evals/E-3_no_interruption.sh`
- **Exit code**: 1
- **Failure quote**:
  ```
    SHAKE-DIAG booted at /; motion listeners so far: 0  [E-3: with the feedback sheet already open, a second shake adds nothing]
    SHAKE-DIAG after shake: listeners=0 subscribed=false prompts=0 sheets=0 location=/  [E-3: with the feedback sheet already open, a second shake adds nothing]
    SHAKE-DIAG booted at /; motion listeners so far: 0  [E-3: the screen beneath keeps its State, timer and text through an ignored prompt and an opened-and-closed sheet]
    SHAKE-DIAG after shake: listeners=0 subscribed=false prompts=0 sheets=0 location=/  [E-3: the screen beneath keeps its State, timer and text through an ignored prompt and an opened-and-closed sheet]
  EVAL E-3: tests=9 passed=4 red=5 blind=0 wrong=0 flutter_exit=1
  EVAL-RED E-3: E-3: typing — a focused field with text gets no prompt and keeps its text and focus -> SHAKE-RED[E-3:typing:positive-control-no-prompt]
  EVAL-RED E-3: E-3: a dialog on the root navigator gets no prompt -> SHAKE-RED[E-3:dialog:positive-control-no-prompt]
  EVAL-RED E-3: E-3: a bottom sheet on a tab's navigator gets no prompt -> SHAKE-RED[E-3:tab-sheet:positive-control-no-prompt]
  EVAL-RED E-3: E-3: with the feedback sheet already open, a second shake adds nothing -> SHAKE-RED[E-3:sheet-open:no-first-prompt]
  EVAL-RED E-3: E-3: the screen beneath keeps its State, timer and text through an ignored prompt and an opened-and-closed sheet -> SHAKE-RED[E-3:timer:no-prompt]
  ```
- **RED verdict**: right-reason

### E-4: Admins get the dev-request form; anyone uncertain gets the user path (P0)

- **Artifact**: _devx/workstreams/shake-to-report/evals/E-4_role_and_ring.sh
- **Command**: `bash run-eval.sh shake-to-report/evals/E-4_role_and_ring.sh`
- **Exit code**: 1
- **Failure quote**:
  ```
    SHAKE-DIAG after shake: listeners=0 subscribed=false prompts=0 sheets=0 location=/  [E-4: flags never answer → no prompt for a non-admin (default admins)]
    SHAKE-DIAG after shake: listeners=0 subscribed=false prompts=0 sheets=0 location=/  [E-4: flags never answer → no prompt for a non-admin (default admins)]
  EVAL E-4: tests=12 passed=5 red=7 blind=0 wrong=0 flutter_exit=1
  EVAL-RED E-4: E-4: the dev-request route is registered (external gate X-1) -> SHAKE-RED[E-4:x1-route-missing]
  EVAL-RED E-4: E-4: admin, ring admins → Request → the dev-request form → back -> SHAKE-RED[E-4:admin:no-prompt]
  EVAL-RED E-4: E-4: non-admin, ring everyone → Report → feedback, never the form -> SHAKE-RED[E-4:user:no-prompt]
  EVAL-RED E-4: E-4: admin at the prompt, not at the tap → the user path -> SHAKE-RED[E-4:flipped:no-admin-prompt]
  EVAL-RED E-4: E-4: ring off → no prompt, even for an admin -> SHAKE-RED[E-4:ring-off:positive-control-no-prompt]
  EVAL-RED E-4: E-4: ring admins → no prompt for a non-admin -> SHAKE-RED[E-4:ring-admins:positive-control-no-prompt]
  EVAL-RED E-4: E-4: flags never answer → no prompt for a non-admin (default admins) -> SHAKE-RED[E-4:no-flags:positive-control-no-prompt]
  ```
- **RED verdict**: right-reason

## Deferred stubs

- E-5: not-run (deferred: tests-after) (P1)
- E-6: not-run (deferred: tests-after) (P1)
- E-7: not-run (deferred: human) (P1)
- E-8: not-run (deferred: tests-after) (P1)
- E-9: not-run (deferred: tests-after) (P2)
- E-10: not-run (deferred: tests-after) (P1)
