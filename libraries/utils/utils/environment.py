"""Deployment-environment predicates (envspell1).

Why this is two predicates and not one canonical string
-------------------------------------------------------
`ENVIRONMENT` is compared against string literals in gates that fail in
**opposite** directions, and that is the whole reason a single
"canonicalise the spelling" helper is the wrong shape:

* `utils.api.endpoint` writes a 4xx audit row only in production. An
  unrecognised value silently **disables a recorder** — it fails quiet,
  which is the failure mode this codebase keeps paying for.
* `services/api/src/dependencies.py` (twice) and
  `services/api/src/mcp_server/auth.py` skip Auth0 and return a fixed test
  user when the environment is a local one. An unrecognised value must
  **deny the bypass**.

One helper with one default cannot serve both:

    is_recording_environment(...)  unknown -> True   (recorders stay on)
    is_local_bypass_allowed(...)   unknown -> False  (the bypass stays shut)

**Normalisation is directional too, and it is deliberately not shared.**
The first draft of this module gave both predicates the same
`.strip().lower()`, which made the bypass gates *looser* than the byte-exact
comparisons they replaced: `TEST`, `Test`, `" test "`, `"test\\n"` and
`"\\xa0test"` all denied the bypass before and armed it after. Tolerating a
stray newline is right when the cost of a mismatch is a silent recorder and
wrong when the cost is an authentication bypass. So:

* `is_recording_environment` normalises — a secret-interpolation artifact
  must not silence a recorder.
* `is_local_bypass_allowed` does **exact** membership, no strip, no case
  folding. Positive identification, byte for byte.

Two sources, which can disagree
-------------------------------
`utils.constants.ENVIRONMENT` reads `os.environ` directly.
`services/api/src/config.Settings.environment` is a pydantic field with a
default of `"dev"`, so in a process with no `ENVIRONMENT` set the two
disagree: one is `None`, the other is `"dev"`. Both are accepted here — pass
whichever the call site already uses rather than adding a third reading of
the same variable.

Known spellings, measured 2026-09-22
------------------------------------
`prod`         terraform/environments/prod/main.tf -> ECS (what prod runs)
`dev`          terraform/environments/dev/main.tf -> ECS (a *deployed* env,
               not a local one — this is the trap in the name)
`development`  docker-compose.e2e.yml (local e2e stack)
`test`         services/api/tests/conftest.py
`production`   the root `SETUP.md` production `.env` template, corrected to
               `prod` by envspell1. It is not a member of any set below —
               it is handled by `is_recording_environment`'s unknown -> True
               fallback, which is the point of that default.
"""

from __future__ import annotations

#: Values that mean "not production" for gates gating *recording*.
#: `dev` is here because the deployed dev environment has always been
#: excluded from the prod-only audit writer (`endpoint.py`'s `!= "prod"`),
#: and this module preserves that exactly.
#:
#: Adding a value here permanently **silences** a recorder for it, so
#: entries need a measured source — not a spelling someone might use.
NON_PRODUCTION: frozenset[str] = frozenset({"dev", "development", "test"})

#: Values that may arm the Auth0 e2e bypass. Compared **exactly**: no
#: stripping, no case folding. Deliberately excludes `dev`, which is a
#: deployed environment behind a public ALB.
#:
#: This is a security boundary. Widening it — including by "just" making the
#: comparison more forgiving — needs a security review, not a config PR.
BYPASS_ELIGIBLE: frozenset[str] = frozenset({"development", "test"})


def canonical_environment(value: object) -> str | None:
    """Normalise an environment value, or `None` when there isn't one.

    Strips and lowercases, so `"PROD"`, `" prod"` and a newline-padded value
    (a routine artifact of shell and secret interpolation) all read as
    `prod`. Non-strings and blanks return `None` — an absent value, not a
    guess.

    **`.lower()`, not `.casefold()`, and that is deliberate.** Casefolding
    maps `U+017F LATIN SMALL LETTER LONG S` onto `s`, so `"teſt".casefold()`
    is `"test"` — a widening, and widening is the unsafe direction for any
    caller that uses this to recognise a privileged environment. Pinned by
    `test_casefold_widening_is_not_used`.

    Only for the *recording* side. Bypass eligibility does not normalise at
    all; see `is_local_bypass_allowed`.
    """
    if not isinstance(value, str):
        return None
    normalised = value.strip().lower()
    return normalised or None


def is_recording_environment(value: object) -> bool:
    """Whether to record here as production does. **Unknown -> True.**

    Gates *recording* — audit rows, error capture, anything whose absence is
    silent. An unrecognised or missing value counts as production: a config
    typo should make a recorder noisier, never quieter.

    Named for what it decides rather than for a fact about the world, on
    purpose. A general-sounding `is_production()` invites reuse in the
    *permissive* direction — `if is_production(): use_real_payment_key()` —
    where "unknown means yes" is exactly backwards. If you need a production
    test for a permissive decision, write a predicate with the opposite
    default and name it for that.

    Consequence worth knowing: with `ENVIRONMENT` unset this returns True,
    so any process that does not set it records what prod records. The test
    suites and `.env.example` set it explicitly for that reason.
    """
    canonical = canonical_environment(value)
    if canonical is None:
        return True
    return canonical not in NON_PRODUCTION


def is_local_bypass_allowed(value: object) -> bool:
    """Whether a local-only auth bypass may be armed. **Unknown -> False.**

    **Exact** membership: no stripping, no lowercasing, no normalisation of
    any kind. `"TEST"`, `" test "` and `"test\\n"` all deny, exactly as the
    byte-exact comparisons this replaced did. Every relaxation here is a
    relaxation of an authentication boundary.

    This is one of three independent conditions — the caller must also check
    its explicit opt-in flag (`E2E_TEST_MODE`) and the fixed token.
    """
    return isinstance(value, str) and value in BYPASS_ELIGIBLE
