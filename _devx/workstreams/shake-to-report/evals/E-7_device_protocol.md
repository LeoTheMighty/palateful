---
id: E-7
priority: P1
covers: [G-2, G-3, G-4, FR-1, FR-3, FR-4]
expectation: 'When the app is used through a normal cooking session on a real phone, the system SHALL show no prompt, and when the user shakes deliberately, the system SHALL prompt.'
status: red      # red | green — last result of the non-deferred steps
last_run: null   # stamped on every Runs row
---

# E-7: The device protocol

<!-- Human procedure: real phones, release builds. Run by Leo after Phase 6
     and the release that carries it (plan external gate X-2), before the
     ring moves past `admins` (G-2). Leo may run steps 1–4 and 6 after
     Phase 5 and widen the ring then; step 5 waits for Phase 6. -->

## Preconditions

- A version-bumped release with Phases 2–6 installed from TestFlight on 1
  iPhone and from the Play internal track on 1 Android phone, fresh
  installs (delete the app first).
- Signed in on each phone as a **non-admin** test user for steps 1–4 and as
  an admin for step 5.
- Ring at `everyone` for the duration (prod ring stays `admins`: use a
  build pointed at staging, or a temporary terraform change Leo owns).
- The device switch on; screen readers off unless a step says otherwise.

## Steps

### 1. human — fresh install asks for no motion permission

- **Run:** Install, open, sign in, finish onboarding, open three screens.
- **Expected:** 0 system permission dialogs about motion or fitness on
  either phone.
- **RED today because:** nothing reads motion; there is no build to install.

### 2. human — a 20-minute scripted kitchen session prompts 0 times

- **Run:** Per phone, with the app open on a recipe in cook mode, then on
  Home, then on Profile: 5 min in a trouser pocket while walking around the
  kitchen; 5 min propped on a stand on the counter while chopping and
  stirring beside it, with 10 knocks on the counter and 5 hard set-downs of
  the phone; 5 min in an apron pocket while whisking; 5 min carried in hand
  between rooms. Count every prompt.
- **Threshold:** 0 prompts per phone across the 20 minutes.
- **RED today because:** nothing reads motion; there is no build to run.

### 3. human — deliberate shakes prompt

- **Run:** Per phone, 10 times, on 10 different screens: hold the phone and
  shake it firmly back and forth for about a second. Wait 5 s between
  tries.
- **Threshold:** at least 9 of 10 prompt, per phone.
- **RED today because:** nothing reads motion.

### 4. human — busy states and the tap paths

- **Run:** Per phone: shake while typing in a recipe's title (expect
  nothing, and note whether iOS shows its own "Undo Typing" alert); shake
  with the feedback sheet open (expect nothing); turn `Shake to report` off
  in Profile and shake (expect nothing); with it off, send feedback from
  Profile → Send Feedback.
- **Threshold:** 0 prompts in the three busy cases; 1 feedback row from the
  tap path.
- **RED today because:** none of it exists.

### 5. human — an admin files a dev request by shaking

- **Run:** Signed in as an admin on one phone, open a recipe, shake, tap
  `Request`, file a request, close the form.
- **Threshold:** 1 dev request filed; the phone is back on the recipe.
- **RED today because:** neither the shake nor arq103's route is on `main`.

### 6. human — the ring switches it off without a release

- **Run:** Set the ring to `off` (terraform variable, applied by CI's
  terraform-prod), note when the API deploy finishes, then shake each phone
  every minute.
- **Threshold:** 0 prompts on both phones within 10 minutes of the deploy
  finishing (G-3).
- **RED today because:** there is no ring.

## Runs

<!-- One row per phone per run. Record step 4's iOS "Undo Typing"
     observation in Evidence: it answers design's open question. -->

| Date | Run by | Result | Evidence |
|---|---|---|---|
