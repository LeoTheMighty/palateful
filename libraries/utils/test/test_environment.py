"""Environment predicates (envspell1).

The point of these tests is the **asymmetry**: the two predicates are not
inverses, and each one's behaviour on an unrecognised value is a deliberate
safety decision rather than an implementation detail. A future refactor that
"simplifies" them into one canonical string would pass a test suite that
only checked the recognised spellings.
"""

from __future__ import annotations

import pytest
from utils.environment import (
    BYPASS_ELIGIBLE,
    NON_PRODUCTION,
    canonical_environment,
    is_local_bypass_allowed,
    is_recording_environment,
)

# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param("prod", "prod", id="plain"),
        pytest.param("PROD", "prod", id="upper"),
        pytest.param("  prod  ", "prod", id="padded"),
        pytest.param("prod\n", "prod", id="newline — a secret-interpolation artifact"),
        pytest.param("", None, id="empty"),
        pytest.param("   ", None, id="whitespace-only"),
        pytest.param(None, None, id="missing"),
        pytest.param(object(), None, id="not-a-string"),
    ],
)
def test_canonical_environment(raw, expected):
    assert canonical_environment(raw) == expected


# ---------------------------------------------------------------------------
# is_production — unknown must mean YES
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw", ["prod", "production", "PROD", " prod\n", "staging", "preprod", "banana"]
)
def test_unrecognised_and_prod_spellings_record(raw):
    """A recorder must never be switched off by a spelling nobody reviewed.

    `production` is here because the root `SETUP.md`'s template used it; the
    nonsense values are here because the rule is "unknown means yes", not
    "this specific typo means yes".
    """
    assert is_recording_environment(raw) is True


@pytest.mark.parametrize("raw", sorted(NON_PRODUCTION))
def test_recognised_non_production_spellings_do_not_record(raw):
    assert is_recording_environment(raw) is False


@pytest.mark.parametrize("raw", [None, "", "   ", object()])
def test_a_missing_environment_records(raw):
    """The local default. `docker-compose.yml` and `.env.example` set no
    `ENVIRONMENT`, so this is the value a developer actually runs with, and
    the consequence — a local stack records what prod records — is chosen,
    not accidental."""
    assert is_recording_environment(raw) is True


def test_dev_does_not_record_because_it_never_did():
    """The deployed dev environment has always been excluded from the
    prod-only audit writer (`endpoint.py`'s `!= "prod"`). envspell1 changes
    which *spellings* are recognised, not which environments record."""
    assert is_recording_environment("dev") is False


# ---------------------------------------------------------------------------
# is_local_bypass_allowed — unknown must mean NO
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw", sorted(BYPASS_ELIGIBLE))
def test_local_spellings_may_arm_the_bypass(raw):
    assert is_local_bypass_allowed(raw) is True


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param("prod", id="prod"),
        pytest.param("production", id="production"),
        pytest.param("dev", id="dev — DEPLOYED, reachable from the internet"),
        pytest.param("staging", id="staging"),
        pytest.param("banana", id="unrecognised"),
        pytest.param(None, id="missing"),
        pytest.param("", id="empty"),
        pytest.param(object(), id="not-a-string"),
    ],
)
def test_everything_else_denies_the_bypass(raw):
    """An auth bypass is armed only by positive identification."""
    assert is_local_bypass_allowed(raw) is False


def test_the_two_predicates_are_not_inverses():
    """The load-bearing property, and the one a "simplification" would break.

    `staging` is neither a recognised local environment nor a recognised
    non-production one: it records like production AND refuses the bypass.
    Both answers are the safe one for their own question, which is only
    possible because the defaults differ.
    """
    assert is_recording_environment("staging") is True
    assert is_local_bypass_allowed("staging") is False

    # `dev` is the mirror case: it does not record, and it must still never
    # be allowed to bypass authentication.
    assert is_recording_environment("dev") is False
    assert is_local_bypass_allowed("dev") is False


def test_dev_is_not_bypass_eligible():
    """Pinned separately from the parametrisation above because it is the
    one entry whose absence from `BYPASS_ELIGIBLE` is load-bearing: `dev` is
    a deployed environment behind a public ALB, not a laptop."""
    assert "dev" not in BYPASS_ELIGIBLE


def test_bypass_eligible_is_a_subset_of_non_production():
    """Anything allowed to bypass auth must also be a non-production
    environment. The converse does not hold (`dev`), which is the asymmetry."""
    assert BYPASS_ELIGIBLE < NON_PRODUCTION


# ---------------------------------------------------------------------------
# The bypass predicate does NOT normalise — the review finding that mattered
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param("TEST", id="upper"),
        pytest.param("Test", id="title"),
        pytest.param("DEVELOPMENT", id="upper-development"),
        pytest.param(" test ", id="padded"),
        pytest.param("test\n", id="newline"),
        pytest.param("\xa0test", id="nbsp — str.strip() removes it"),
        pytest.param("test\x0b", id="vertical-tab"),
    ],
)
def test_near_miss_spellings_never_arm_the_bypass(raw):
    """envspell1's first draft shared one normaliser between both predicates,
    which made these six inputs arm a bypass that byte-exact comparison had
    denied. Normalisation is directional: tolerating a stray newline is right
    when a mismatch costs a silent recorder and wrong when it costs an
    authentication bypass. Caught by adversarial review, not by me.
    """
    assert is_local_bypass_allowed(raw) is False


def test_the_bypass_predicate_is_byte_exact():
    """Stated as a property rather than a list, so a future `.strip()` fails
    here rather than in production."""
    for eligible in BYPASS_ELIGIBLE:
        assert is_local_bypass_allowed(eligible) is True
        assert is_local_bypass_allowed(eligible.upper()) is False
        assert is_local_bypass_allowed(f" {eligible}") is False
        assert is_local_bypass_allowed(f"{eligible} ") is False
        assert is_local_bypass_allowed(f"{eligible}\n") is False


def test_casefold_widening_is_not_used():
    """`canonical_environment` uses `.lower()`, not `.casefold()`.

    Casefold maps U+017F (long s) onto `s`, so `"teſt".casefold() == "test"`.
    That is a widening, and widening is the unsafe direction for recognising
    a privileged environment. A "more correct, use casefold" cleanup fails
    here.
    """
    assert "te\u017ft".casefold() == "test"  # the hazard is real
    assert canonical_environment("te\u017ft") != "test"  # and not taken
    assert is_local_bypass_allowed("te\u017ft") is False
