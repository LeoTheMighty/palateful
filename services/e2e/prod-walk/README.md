# prod-walk — Playwright against palateful.app (production)

A second mode beside the `flutter drive` suite in `services/e2e`. That suite
builds its **own** app with `E2E_MODE=true` (Auth0 bypassed) against a local
stack; it cannot reach the deployed build or real Auth0. This one drives the
**deployed** `palateful.app` in a real browser, signed in as a real account,
to find bugs users actually hit.

It reuses the `flutter drive` flows (`app/integration_test/0*_test.dart`) and
`archive/e2e-maestro/flows` as its **feature inventory** — what to walk and in
what order — but not their code: those run in-process and target widget
`Key`s, which never reach the browser's DOM.

## How the canvas becomes testable

palateful.app renders to a canvas (Flutter 3.41 has no HTML renderer), so a
browser sees no widgets. Each script turns on Flutter's **semantics tree** from
the outside by clicking the engine's own hidden `flt-semantics-placeholder`
("Enable accessibility"). No app change, no deploy, no cost to real users —
unlike always-on `SemanticsBinding.instance.ensureSemantics()`, which would tax
every page load for every user. See `lib/flutter.ts`.

## One-time: capture a signed-in session

```bash
npx nx run e2e:prod-capture-session
```

A Chrome window opens on palateful.app. **You** sign in, normally. The script
waits until the app leaves the login screen, saves the browser session to
`~/.config/palateful-e2e/prod-session.json` (mode 600, **outside the repo**),
prints the auth cookies' expiry dates (never their values), and closes.

- The password is never typed into, stored by, or visible to this code.
- If Google says the browser "may not be secure", that is Google refusing an
  automated window; close it and say so rather than working around it.
- When a run starts failing on `did not restore`, the session expired: that
  timestamp is data for the auth track. Capture again.

## Run

```bash
npx nx run e2e:prod-walk                          # every script
npx nx run e2e:prod-walk --test=tests/00-session.spec.ts
```

## Rules every script follows (real account)

- `workers: 1`, `retries: 0` — no concurrency against one account, and no
  retry turning an intermittent bug into a green run.
- **Writes are gated in code.** Any script that creates data calls
  `requireWriteOptIn()` and **skips** unless the run sets
  `PALATEFUL_E2E_ALLOW_WRITES=1` — set it only with the account owner's
  go-ahead for that run:
  `PALATEFUL_E2E_ALLOW_WRITES=1 npx playwright test tests/10-cart.spec.ts`
- **Read-only unless stated.** A script that creates data tags everything it
  makes with the prefix `[e2e-walk]` and deletes it in a `finally`, including
  on failure. It never edits, deletes or reorders anything that existed before.
  A feature that cannot be exercised without touching real data is skipped and
  listed, not improvised.
- Every assertion must be one that **fails when the feature is broken** — "no
  error thrown" proves nothing. `00-session.spec.ts` is negative-controlled:
  run with an empty session it fails with `did not restore`.
- Tracing is **off** by default: a trace records live bearer tokens. Opt in
  with `PALATEFUL_E2E_TRACE=1` only while debugging, then delete
  `test-results/`. App console lines mentioning tokens are redacted before
  they reach a report.

## Scripts

| script | writes? | proves | expected today |
|---|---|---|---|
| `00-session.spec.ts` | no | a saved session opens the signed-in app **and survives a reload**; records auth log, cookie expiries, any Auth0 `?error=` | unknown — measures Leo's "credentials don't hold" (repro: palateful-2d) |
| `10-cart.spec.ts` | **yes, gated** | an item **with a quantity** is still shown when its list is re-opened (an empty list passes on the broken cart) | **FAIL** at the re-open step until cc's quantity-parse fix deploys; green after is the verification (repro: palateful-cc) |

Not scripted, deliberately:
- **Account linking** (sign in with a second provider on the same email) — it
  links identities on the real account. Needs the owner's explicit go-ahead.
- **Access-token expiry mid-session** (~24h with the tab left open) — hours
  long; not a Playwright test.
- **Native "Login failed. Please try again."** — phone only; out of reach.
