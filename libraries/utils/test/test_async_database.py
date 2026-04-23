"""Unit tests for AsyncDatabase (aam-2).

Mocks AsyncSession end-to-end — no real asyncpg. Real-driver parity is
exercised downstream when Phase 3 handlers run against the async test
engine (aam-4 adds that fixture).
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm.exc import ObjectDeletedError

from utils.models.calendar import Calendar
from utils.services.async_database import AsyncDatabase, AsyncQuery


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _new_calendar(**kwargs):
    defaults = {
        "id": uuid.uuid4(),
        "name": "Test Calendar",
        "owner_id": uuid.uuid4(),
        "is_shared": False,
        "is_default": False,
    }
    defaults.update(kwargs)
    return Calendar(**defaults)


@pytest.fixture
def fake_session():
    """AsyncSession double with the methods AsyncDatabase touches."""
    s = MagicMock()
    s.execute = AsyncMock()
    s.commit = AsyncMock()
    s.rollback = AsyncMock()
    s.refresh = AsyncMock()
    s.delete = AsyncMock()
    s.close = AsyncMock()
    s.add = MagicMock()
    s.add_all = MagicMock()
    return s


@pytest.fixture
def adb(fake_session):
    return AsyncDatabase(db=fake_session, engine=MagicMock())


# ---------------------------------------------------------------------------
# Result helpers
# ---------------------------------------------------------------------------


def _result_scalars(items):
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=items)
    scalars.first = MagicMock(return_value=items[0] if items else None)
    scalars.one_or_none = MagicMock(
        return_value=items[0] if len(items) == 1 else None
    )

    class _OneImpl:
        def one(self_inner):
            from sqlalchemy.exc import NoResultFound

            if not items:
                raise NoResultFound
            return items[0]

    scalars.one = _OneImpl().one
    return scalars


def _fake_result(items):
    r = MagicMock()
    r.scalars = MagicMock(return_value=_result_scalars(items))
    r.scalar_one = MagicMock(return_value=len(items))
    return r


# ---------------------------------------------------------------------------
# where() / AsyncQuery
# ---------------------------------------------------------------------------


async def test_where_builds_query_with_archived_filter(adb):
    query = adb.where(Calendar)
    assert isinstance(query, AsyncQuery)


async def test_where_filter_by_equality(adb, fake_session):
    fake_session.execute.return_value = _fake_result([_new_calendar()])
    result = await adb.where(Calendar, owner_id=uuid.uuid4()).first()
    assert result is not None
    assert fake_session.execute.await_count == 1


async def test_where_filter_with_in_operator(adb, fake_session):
    fake_session.execute.return_value = _fake_result([])
    await adb.where(Calendar, owner_id={"in": [uuid.uuid4(), uuid.uuid4()]}).all()
    assert fake_session.execute.await_count == 1


async def test_where_filter_with_notin_operator(adb, fake_session):
    fake_session.execute.return_value = _fake_result([])
    await adb.where(Calendar, name={"notin": ["x"]}).all()
    assert fake_session.execute.await_count == 1


async def test_where_filter_with_neq_operator(adb, fake_session):
    fake_session.execute.return_value = _fake_result([])
    await adb.where(Calendar, name={"!=": "archived"}).all()
    assert fake_session.execute.await_count == 1


async def test_where_rejects_unknown_operator(adb):
    with pytest.raises(ValueError, match="Unsupported operator"):
        adb.where(Calendar, owner_id={"~~": "x"})


async def test_where_include_archived_skips_archived_filter(adb, fake_session):
    fake_session.execute.return_value = _fake_result([])
    await adb.where(Calendar, include_archived=True).all()
    assert fake_session.execute.await_count == 1


async def test_where_asc_single_and_list(adb, fake_session):
    fake_session.execute.return_value = _fake_result([])
    await adb.where(Calendar, asc="id").all()
    await adb.where(Calendar, asc=["id", "owner_id"]).all()
    assert fake_session.execute.await_count == 2


async def test_where_desc_single_and_list(adb, fake_session):
    fake_session.execute.return_value = _fake_result([])
    await adb.where(Calendar, desc="id").all()
    await adb.where(Calendar, desc=["id", "owner_id"]).all()
    assert fake_session.execute.await_count == 2


async def test_async_query_chainables(adb, fake_session):
    fake_session.execute.return_value = _fake_result([_new_calendar()])
    q = adb.where(Calendar)
    q2 = (
        q.filter(Calendar.id == uuid.uuid4())
        .filter_by(name="active")
        .order_by(Calendar.id)
        .limit(10)
        .offset(5)
        .options()
    )
    assert isinstance(q2, AsyncQuery)
    result = await q2.first()
    assert result is not None


async def test_async_query_all(adb, fake_session):
    fake_session.execute.return_value = _fake_result(
        [_new_calendar(), _new_calendar()]
    )
    items = await adb.where(Calendar).all()
    assert len(items) == 2


async def test_async_query_one_or_none(adb, fake_session):
    fake_session.execute.return_value = _fake_result([_new_calendar()])
    result = await adb.where(Calendar).one_or_none()
    assert result is not None


async def test_async_query_one_success(adb, fake_session):
    fake_session.execute.return_value = _fake_result([_new_calendar()])
    result = await adb.where(Calendar).one()
    assert result is not None


async def test_async_query_one_raises_when_empty(adb, fake_session):
    from sqlalchemy.exc import NoResultFound

    fake_session.execute.return_value = _fake_result([])
    with pytest.raises(NoResultFound):
        await adb.where(Calendar).one()


async def test_async_query_count(adb, fake_session):
    fake_session.execute.return_value = _fake_result([1, 2, 3])
    count = await adb.where(Calendar).count()
    assert count == 3


# ---------------------------------------------------------------------------
# find_by + find_or_create_by
# ---------------------------------------------------------------------------


async def test_find_by_returns_first(adb, fake_session):
    fake_session.execute.return_value = _fake_result([_new_calendar()])
    result = await adb.find_by(Calendar, owner_id=uuid.uuid4())
    assert result is not None


async def test_find_or_create_by_returns_existing(adb, fake_session):
    existing = _new_calendar()
    fake_session.execute.return_value = _fake_result([existing])

    class _NoopLock:
        async def __aenter__(self_inner):
            return True

        async def __aexit__(self_inner, *a):
            return None

    with patch.object(adb, "lock", return_value=_NoopLock()):
        result = await adb.find_or_create_by(
            Calendar, defaults={"name": "new"}, owner_id=existing.owner_id
        )

    assert result is existing
    fake_session.add.assert_not_called()


async def test_find_or_create_by_creates_when_missing(adb, fake_session):
    fake_session.execute.return_value = _fake_result([])

    class _NoopLock:
        async def __aenter__(self_inner):
            return True

        async def __aexit__(self_inner, *a):
            return None

    with patch.object(adb, "lock", return_value=_NoopLock()):
        result = await adb.find_or_create_by(
            Calendar, defaults={"name": "new"}, owner_id=uuid.uuid4()
        )

    assert result is not None
    fake_session.add.assert_called_once()
    fake_session.commit.assert_awaited()


async def test_find_or_create_by_empty_defaults(adb, fake_session):
    fake_session.execute.return_value = _fake_result([])

    class _NoopLock:
        async def __aenter__(self_inner):
            return True

        async def __aexit__(self_inner, *a):
            return None

    with patch.object(adb, "lock", return_value=_NoopLock()):
        await adb.find_or_create_by(Calendar, owner_id=uuid.uuid4(), name="n")

    fake_session.add.assert_called_once()


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


async def test_create_commits(adb, fake_session):
    m = _new_calendar()
    result = await adb.create(m)
    fake_session.add.assert_called_once_with(m)
    fake_session.commit.assert_awaited_once()
    fake_session.refresh.assert_awaited_once_with(m)
    assert result is m


async def test_create_rolls_back_on_exception(adb, fake_session):
    fake_session.commit.side_effect = RuntimeError("boom")
    with pytest.raises(RuntimeError):
        await adb.create(_new_calendar())
    fake_session.rollback.assert_awaited_once()


async def test_create_all(adb, fake_session):
    models = [_new_calendar(), _new_calendar()]
    result = await adb.create_all(models)
    fake_session.add_all.assert_called_once_with(models)
    fake_session.commit.assert_awaited_once()
    assert result == models


async def test_create_all_rolls_back(adb, fake_session):
    fake_session.commit.side_effect = RuntimeError
    with pytest.raises(RuntimeError):
        await adb.create_all([_new_calendar()])
    fake_session.rollback.assert_awaited_once()


async def test_update_sets_kwargs_and_saves(adb, fake_session):
    m = _new_calendar(name="a")
    result = await adb.update(m, name="b")
    assert m.name == "b"
    assert result is m


async def test_update_all(adb, fake_session):
    ms = [_new_calendar(name="a"), _new_calendar(name="a")]
    result = await adb.update_all(ms, name="b")
    assert all(m.name == "b" for m in ms)
    assert result == ms


async def test_save(adb, fake_session):
    m = _new_calendar()
    result = await adb.save(m)
    fake_session.add.assert_called_once_with(m)
    fake_session.commit.assert_awaited_once()
    assert result is m


async def test_save_rolls_back(adb, fake_session):
    fake_session.commit.side_effect = RuntimeError
    with pytest.raises(RuntimeError):
        await adb.save(_new_calendar())
    fake_session.rollback.assert_awaited_once()


async def test_save_all(adb, fake_session):
    ms = [_new_calendar(), _new_calendar()]
    result = await adb.save_all(ms)
    fake_session.commit.assert_awaited_once()
    assert fake_session.refresh.await_count == 2
    assert result == ms


async def test_save_all_rolls_back(adb, fake_session):
    fake_session.commit.side_effect = RuntimeError
    with pytest.raises(RuntimeError):
        await adb.save_all([_new_calendar()])
    fake_session.rollback.assert_awaited_once()


async def test_delete(adb, fake_session):
    m = _new_calendar()
    result = await adb.delete(m)
    fake_session.delete.assert_awaited_once_with(m)
    fake_session.commit.assert_awaited_once()
    assert result is m


async def test_delete_already_gone_returns_silently(adb, fake_session):
    m = _new_calendar()
    fake_session.delete.side_effect = ObjectDeletedError(None)
    result = await adb.delete(m)
    assert result is m


async def test_delete_rolls_back_on_other_exception(adb, fake_session):
    fake_session.delete.side_effect = RuntimeError
    with pytest.raises(RuntimeError):
        await adb.delete(_new_calendar())
    fake_session.rollback.assert_awaited_once()


async def test_bulk_update(adb, fake_session):
    await adb.bulk_update(Calendar, [Calendar.owner_id == uuid.uuid4()], name="new")
    fake_session.execute.assert_awaited_once()
    fake_session.commit.assert_awaited_once()


async def test_bulk_update_rolls_back(adb, fake_session):
    fake_session.execute.side_effect = RuntimeError
    with pytest.raises(RuntimeError):
        await adb.bulk_update(Calendar, [Calendar.owner_id == uuid.uuid4()], name="y")
    fake_session.rollback.assert_awaited_once()


async def test_find_and_bulk_update_with_eq(adb, fake_session):
    await adb.find_and_bulk_update(Calendar, {"name": "new"}, owner_id=uuid.uuid4())
    fake_session.execute.assert_awaited_once()


async def test_find_and_bulk_update_with_in(adb, fake_session):
    await adb.find_and_bulk_update(
        Calendar, {"name": "new"}, owner_id={"in": [uuid.uuid4()]}
    )
    fake_session.execute.assert_awaited_once()


async def test_find_and_bulk_update_with_notin(adb, fake_session):
    await adb.find_and_bulk_update(
        Calendar, {"name": "new"}, owner_id={"notin": [uuid.uuid4()]}
    )
    fake_session.execute.assert_awaited_once()


async def test_find_and_bulk_update_with_neq(adb, fake_session):
    await adb.find_and_bulk_update(
        Calendar, {"name": "new"}, owner_id={"!=": uuid.uuid4()}
    )
    fake_session.execute.assert_awaited_once()


async def test_find_and_bulk_update_rejects_unknown_operator(adb):
    with pytest.raises(ValueError, match="Unsupported operator"):
        await adb.find_and_bulk_update(
            Calendar, {"name": "new"}, owner_id={"~~": "x"}
        )


async def test_find_and_bulk_update_include_archived(adb, fake_session):
    await adb.find_and_bulk_update(
        Calendar, {"name": "new"}, include_archived=True, owner_id=uuid.uuid4()
    )
    fake_session.execute.assert_awaited_once()


async def test_delete_by(adb, fake_session):
    await adb.delete_by(Calendar, [Calendar.owner_id == uuid.uuid4()])
    fake_session.execute.assert_awaited_once()
    fake_session.commit.assert_awaited_once()


async def test_delete_by_rolls_back(adb, fake_session):
    fake_session.execute.side_effect = RuntimeError
    with pytest.raises(RuntimeError):
        await adb.delete_by(Calendar, [])
    fake_session.rollback.assert_awaited_once()


# ---------------------------------------------------------------------------
# Locking & lifecycle
# ---------------------------------------------------------------------------


async def test_lock_returns_async_advisory_lock(adb):
    from utils.services.async_advisory_lock import AsyncAdvisoryLock

    lock = adb.lock("key")
    assert isinstance(lock, AsyncAdvisoryLock)


async def test_close_closes_owned_session():
    fake_s = MagicMock()
    fake_s.close = AsyncMock()
    fake_sessionmaker = MagicMock(return_value=fake_s)

    with (
        patch("utils.services.database.AsyncSessionLocal", fake_sessionmaker),
        patch("utils.services.database.async_db_engine", MagicMock()),
    ):
        db = AsyncDatabase()
        await db.close()
        fake_s.close.assert_awaited_once()


async def test_close_skips_external_session(fake_session, adb):
    await adb.close()
    fake_session.close.assert_not_awaited()


async def test_init_without_engine_without_sessionmaker_raises():
    with (
        patch("utils.services.database.AsyncSessionLocal", None),
        patch("utils.services.database.async_db_engine", None),
    ):
        with pytest.raises(RuntimeError, match="requires an AsyncSessionLocal"):
            AsyncDatabase()


async def test_init_with_explicit_engine_builds_sessionmaker():
    fake_engine = MagicMock()
    db = AsyncDatabase(engine=fake_engine)
    assert db.engine is fake_engine
    assert db.db is not None
