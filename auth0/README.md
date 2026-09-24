# auth0/

Code that runs **inside Auth0**, not in this app, kept here so there is one
source of truth instead of a copy in someone's chat history.

## Actions

| File | Trigger | What it does |
|---|---|---|
| `actions/post-login-account-linking.js` | Login / post-login | Links a second provider to an existing account with the same verified email, then asks the user to sign in again. Best-effort: it can never fail a login. |

### Deploying a change

1. Edit the file here, and run `node auth0/actions/post-login-account-linking.test.js`.
2. Merge it (CI runs the same test in `ci.yml`'s `lint` job).
3. **Open the file and copy its contents directly.** Don't copy it from a
   chat message or from terminal output.
4. Auth0 → Actions → Library → the Action → paste → **Deploy**.

**Why step 3 matters.** A post-login Action with a syntax error rejects
**every** login the moment it's deployed, and the dashboard will deploy it
anyway. On 2026-09-22 a terminal paste collapsed the Action's newlines, its
`//` comments commented out the code after them, and every login failed
(`ACTION_MALFORMED`) until it was redeployed. The file now uses only `/* */`
comments, so it survives a collapsed paste. The test checks exactly that, and
checks that the old `//` form would *not* have.

### Coupled to the app

The deny string `Your account has been linked. Please sign in again.` is
matched by the app to show a friendly message instead of "Login failed".
It's pinned on both sides:

- here: `actions/post-login-account-linking.test.js`
- in the app: `app/test/core/services/auth_service_login_test.dart`

If you change it, change both.
