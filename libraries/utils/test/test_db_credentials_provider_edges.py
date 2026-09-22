"""Edge cases for the rsh105 provider surface in `db_credentials`.

`test_db_credential_provider.py` is the E-6 acceptance artifact (retry
contract, TTL, inert path). This file covers the branches it does not
reach — secret parsing, TTL config, the fallback ladder, client
construction, idempotent registration — which the T2.8 100% gate in the
nx `test` target requires.
"""

from __future__ import annotations

import logging

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from utils.services import db_credentials

# Names are looked up on the module at call time, never from-imported:
# `test_db_credential_provider.py` reloads the module, which would leave a
# from-imported `CredentialResolutionError` a different class from the
# one the reloaded code raises.

SECRET_ARN = "arn:aws:secretsmanager:eu-west-2:123456789012:secret:rds!db-x"
ENV_PASSWORD = "password-from-env"


class Client:
    """`get_secret_value` returning queued responses or raising."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = 0

    def get_secret_value(self, **kwargs):
        self.calls += 1
        outcome = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def secret(password_json):
    """A secret whose `password` field is the given raw JSON value."""
    return {"SecretString": f'{{"username": "u", "password": {password_json}}}'}


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def clock(monkeypatch):
    c = Clock()
    monkeypatch.setattr(db_credentials.time, "monotonic", c)
    return c


# --- ARN / TTL parsing ------------------------------------------------------


def test_region_is_read_from_a_well_formed_arn():
    assert db_credentials._region_from_arn(SECRET_ARN) == "eu-west-2"


@pytest.mark.parametrize(
    "arn", ["not-an-arn", "arn:aws:secretsmanager::1:secret:x", "x:aws:sm:r:1:s"]
)
def test_region_is_none_for_malformed_arns(arn):
    assert db_credentials._region_from_arn(arn) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, 300.0), ("", 300.0), ("  ", 300.0), ("60", 60.0), ("0", 0.0), ("2.5", 2.5)],
)
def test_ttl_from_env(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("DB_SECRET_TTL_S", raising=False)
    else:
        monkeypatch.setenv("DB_SECRET_TTL_S", raw)
    assert db_credentials._ttl_from_env() == expected


@pytest.mark.parametrize("raw", ["abc", "-1", "nan", "inf"])
def test_invalid_ttl_warns_and_uses_default(monkeypatch, caplog, raw):
    monkeypatch.setenv("DB_SECRET_TTL_S", raw)
    with caplog.at_level(logging.WARNING):
        assert db_credentials._ttl_from_env() == db_credentials.DEFAULT_SECRET_TTL_S
    assert "DB_SECRET_TTL_S" in caplog.text


def test_resolver_strips_whitespace_arn_to_none(monkeypatch):
    monkeypatch.setenv("DB_PASSWORD_SECRET_ARN", "   ")
    assert db_credentials.resolve_password_provider() is None


def test_resolver_applies_ttl_env(monkeypatch, clock):
    monkeypatch.setenv("DB_PASSWORD_SECRET_ARN", SECRET_ARN)
    monkeypatch.setenv("DB_SECRET_TTL_S", "10")
    provider = db_credentials.resolve_password_provider()
    client = Client(secret('"a"'))
    provider._client = client

    provider.current()
    clock.now += 9.9
    provider.current()
    assert client.calls == 1
    clock.now += 0.2
    provider.current()
    assert client.calls == 2


# --- client construction ----------------------------------------------------


def test_client_is_built_lazily_once_with_its_own_config(monkeypatch):
    built = []

    def fake_client(service, **kwargs):
        built.append((service, kwargs))
        return Client(secret('"p"'))

    monkeypatch.setattr(db_credentials.boto3, "client", fake_client)
    provider = db_credentials.SecretPasswordProvider(SECRET_ARN)
    assert built == []

    provider.current()
    provider.invalidate()
    provider.current()

    assert len(built) == 1
    service, kwargs = built[0]
    assert service == "secretsmanager"
    assert kwargs["region_name"] == "eu-west-2"
    assert kwargs["config"] is db_credentials._SECRETS_MANAGER_CONFIG


# --- secret parsing ---------------------------------------------------------


@pytest.mark.parametrize(
    "response",
    [
        {"SecretString": "not json"},
        {"SecretString": '{"username": "u"}'},
        secret('""'),
        secret("123"),
        {},
    ],
    ids=["not-json", "no-password", "empty", "non-string", "no-secret-string"],
)
def test_unusable_secret_is_a_fetch_failure(monkeypatch, response):
    monkeypatch.setenv("DB_PASSWORD", ENV_PASSWORD)
    provider = db_credentials.SecretPasswordProvider(SECRET_ARN, client=Client(response))
    assert provider.current() == ENV_PASSWORD
    with pytest.raises(db_credentials.CredentialResolutionError):
        provider.invalidate()
        provider.current(strict=True)


# --- the fallback ladder ----------------------------------------------------


def test_first_failure_without_env_password_raises(monkeypatch, caplog):
    monkeypatch.delenv("DB_PASSWORD", raising=False)
    provider = db_credentials.SecretPasswordProvider(
        SECRET_ARN, client=Client(RuntimeError("down"))
    )
    with caplog.at_level(logging.ERROR), pytest.raises(db_credentials.CredentialResolutionError):
        provider.current()
    assert "no fallback password" in caplog.text


def test_env_fallback_is_cached_for_the_ttl(monkeypatch, clock):
    monkeypatch.setenv("DB_PASSWORD", ENV_PASSWORD)
    client = Client(RuntimeError("down"))
    provider = db_credentials.SecretPasswordProvider(SECRET_ARN, ttl_s=30, client=client)

    assert provider.current() == ENV_PASSWORD
    assert provider.current() == ENV_PASSWORD
    assert client.calls == 1


def test_refresh_failure_serves_last_known_good_not_env(monkeypatch, clock, caplog):
    monkeypatch.setenv("DB_PASSWORD", ENV_PASSWORD)
    client = Client(secret('"from-sm"'), RuntimeError("down"))
    provider = db_credentials.SecretPasswordProvider(SECRET_ARN, ttl_s=30, client=client)

    assert provider.current() == "from-sm"
    clock.now += 31
    with caplog.at_level(logging.WARNING):
        assert provider.current() == "from-sm"
    assert "serving the cached password" in caplog.text
    assert "from-sm" not in caplog.text

    assert provider.current() == "from-sm"
    assert client.calls == 2, "the stale value is re-cached for a TTL, not refetched per call"


def test_non_strict_after_invalidate_does_not_fall_back_to_env(monkeypatch):
    """The env fallback is for the first resolution only."""
    monkeypatch.setenv("DB_PASSWORD", ENV_PASSWORD)
    provider = db_credentials.SecretPasswordProvider(
        SECRET_ARN, client=Client(secret('"from-sm"'), RuntimeError("down"))
    )
    provider.current()
    provider.invalidate()
    with pytest.raises(db_credentials.CredentialResolutionError):
        provider.current()


def test_strict_failure_chains_the_cause_and_logs_no_secret(monkeypatch, caplog):
    monkeypatch.setenv("DB_PASSWORD", ENV_PASSWORD)
    cause = RuntimeError("down")
    provider = db_credentials.SecretPasswordProvider(SECRET_ARN, client=Client(cause))
    with caplog.at_level(logging.ERROR), pytest.raises(db_credentials.CredentialResolutionError) as info:
        provider.current(strict=True)
    assert info.value.__cause__ is cause
    assert ENV_PASSWORD not in caplog.text


# --- registration -----------------------------------------------------------


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", poolclass=NullPool)
    yield eng
    eng.dispose()


def test_repeat_registration_adds_no_second_listener(monkeypatch, engine):
    monkeypatch.setenv("DB_PASSWORD_SECRET_ARN", SECRET_ARN)
    assert db_credentials.register_rotating_credentials(engine) is True
    assert db_credentials.register_rotating_credentials(engine) is True
    assert len(engine.dialect.dispatch.do_connect) == 1


def test_async_engine_registers_on_its_sync_engine(monkeypatch, engine):
    monkeypatch.setenv("DB_PASSWORD_SECRET_ARN", SECRET_ARN)

    class AsyncLike:
        sync_engine = engine

    assert db_credentials.register_rotating_credentials(AsyncLike()) is True
    assert len(engine.dialect.dispatch.do_connect) == 1


class AuthError(Exception):
    def __init__(self):
        super().__init__('password authentication failed for user "u"')


def test_non_auth_failure_on_the_retry_propagates_quietly(monkeypatch, engine, caplog):
    """Only an auth failure on the retry earns the "rejected too" verdict."""
    monkeypatch.setenv("DB_PASSWORD_SECRET_ARN", SECRET_ARN)
    monkeypatch.setattr(
        db_credentials.boto3, "client", lambda *a, **kw: Client(secret('"p"'))
    )
    outcomes = [AuthError(), TimeoutError("timed out")]

    def connect(*args, **kwargs):
        raise outcomes.pop(0)

    monkeypatch.setattr(engine.dialect, "connect", connect)
    db_credentials.register_rotating_credentials(engine)

    with caplog.at_level(logging.ERROR), pytest.raises(TimeoutError):
        engine.pool._creator()
    assert "rejected the freshly re-resolved password" not in caplog.text


def test_second_auth_failure_is_logged_as_a_verdict(monkeypatch, engine, caplog):
    monkeypatch.setenv("DB_PASSWORD_SECRET_ARN", SECRET_ARN)
    monkeypatch.setattr(
        db_credentials.boto3, "client", lambda *a, **kw: Client(secret('"p"'))
    )

    def connect(*args, **kwargs):
        raise AuthError()

    monkeypatch.setattr(engine.dialect, "connect", connect)
    db_credentials.register_rotating_credentials(engine)

    with caplog.at_level(logging.ERROR), pytest.raises(AuthError):
        engine.pool._creator()
    assert "rejected the freshly re-resolved password" in caplog.text


def test_sm_outage_on_retry_is_not_classified_as_an_auth_failure(
    monkeypatch, engine
):
    """The health probe must fail open here, not 503.

    A replacement task cannot fix a Secrets Manager outage, so the
    rejecting auth error is kept out of the raised error's chain.
    """
    monkeypatch.setenv("DB_PASSWORD_SECRET_ARN", SECRET_ARN)
    monkeypatch.setattr(
        db_credentials.boto3,
        "client",
        lambda *a, **kw: Client(secret('"p"'), RuntimeError("down")),
    )

    def connect(*args, **kwargs):
        raise AuthError()

    monkeypatch.setattr(engine.dialect, "connect", connect)
    db_credentials.register_rotating_credentials(engine)

    with pytest.raises(db_credentials.CredentialResolutionError) as info:
        engine.pool._creator()
    assert db_credentials.is_auth_error(info.value) is False
