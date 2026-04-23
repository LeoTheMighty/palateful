"""AsyncDatabase (aam-2) — mirror of `Database` with `async` I/O.

Public surface matches `Database` method-for-method so the dual-surface
epic can flip callers incrementally without signature churn. Sync
`Database` stays frozen for the duration of the migration — worker +
parser + scripts depend on it unchanged.

Call semantics (matches sync twin):
- Every write (`create*`, `update*`, `save*`, `delete`, `bulk_update`)
  commits on success, rolls back on exception, and re-raises.
- Every read (`find_by`, `where`) returns an `await`able builder — see
  `AsyncQuery` below — so callers can chain `.filter(...)` → `.first()`
  / `.all()` etc. against an async session without re-implementing
  SQLAlchemy's query surface.
- `find_or_create_by` acquires the same advisory-lock key the sync twin
  uses, so sync + async callers contending for the same unique-key row
  serialize correctly against each other.
- `lock(key)` returns an async context manager backed by
  `AsyncAdvisoryLock`.

Landing dark in Phase 1; Phase 3 stories flip domain endpoints one at a
time.
"""

import logging

from sqlalchemy import and_, select
from sqlalchemy import asc as sa_asc
from sqlalchemy import delete as sa_delete
from sqlalchemy import desc as sa_desc
from sqlalchemy import update as sa_update
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm.exc import ObjectDeletedError

from utils.services.async_advisory_lock import AsyncAdvisoryLock

logger = logging.getLogger(__name__)


class AsyncQuery:
    """Lightweight async-friendly query builder.

    Wraps a SQLAlchemy `Select` statement + the `AsyncSession` that will
    execute it. Chainable (`.filter(...)`, `.order_by(...)`, `.limit(...)`,
    etc.) and terminals (`.first()`, `.all()`, `.one_or_none()`, `.count()`)
    await the session so callers don't have to reach for `select(...)`
    directly. Keeps `Database.where(...)` ergonomic for single-model
    filter+order cases.
    """

    def __init__(self, session: AsyncSession, stmt, model):
        self._session = session
        self._stmt = stmt
        self._model = model

    def filter(self, *clauses) -> "AsyncQuery":
        return AsyncQuery(self._session, self._stmt.where(*clauses), self._model)

    def filter_by(self, **kwargs) -> "AsyncQuery":
        return AsyncQuery(
            self._session, self._stmt.filter_by(**kwargs), self._model
        )

    def order_by(self, *cols) -> "AsyncQuery":
        return AsyncQuery(
            self._session, self._stmt.order_by(*cols), self._model
        )

    def limit(self, n: int) -> "AsyncQuery":
        return AsyncQuery(self._session, self._stmt.limit(n), self._model)

    def offset(self, n: int) -> "AsyncQuery":
        return AsyncQuery(self._session, self._stmt.offset(n), self._model)

    def options(self, *opts) -> "AsyncQuery":
        return AsyncQuery(
            self._session, self._stmt.options(*opts), self._model
        )

    async def all(self) -> list:
        result = await self._session.execute(self._stmt)
        return list(result.scalars().all())

    async def first(self):
        result = await self._session.execute(self._stmt.limit(1))
        return result.scalars().first()

    async def one_or_none(self):
        result = await self._session.execute(self._stmt)
        return result.scalars().one_or_none()

    async def one(self):
        result = await self._session.execute(self._stmt)
        try:
            return result.scalars().one()
        except NoResultFound as exc:
            raise exc

    async def count(self) -> int:
        # Wrap in a subquery and count; mirrors the sync `Query.count()`
        # behavior (order_by/limit/offset dropped).
        from sqlalchemy import func

        stmt = select(func.count()).select_from(self._stmt.subquery())
        result = await self._session.execute(stmt)
        return int(result.scalar_one())


class AsyncDatabase:
    """Async mirror of `Database`.

    Signature parity with sync `Database` is intentional — callers
    migrate by flipping the dep + prefixing `await`, not by relearning
    the surface.
    """

    def __init__(
        self,
        db: AsyncSession | None = None,
        engine: AsyncEngine | None = None,
    ):
        # aam-1 lazy-imports: keep async_database.py importable from
        # tooling that doesn't ship asyncpg (e.g. worker image smoke
        # tests). Pool gets resolved at first use, not at import.
        from utils.services.database import AsyncSessionLocal as _Default
        from utils.services.database import async_db_engine as _DefaultEngine

        if engine is None:
            self.engine = _DefaultEngine
            self._SessionLocal = _Default
        else:
            from sqlalchemy.ext.asyncio import async_sessionmaker

            self.engine = engine
            self._SessionLocal = async_sessionmaker(
                bind=engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )

        if db is None:
            if self._SessionLocal is None:
                raise RuntimeError(
                    "AsyncDatabase requires an AsyncSessionLocal — "
                    "no engine configured and no session passed."
                )
            self.db = self._SessionLocal()
            self._owns_session = True
        else:
            self.db = db
            self._owns_session = False

    # ─────────────────────────── Reads ───────────────────────────

    def where(
        self,
        model,
        desc: str | list | None = None,
        asc: str | list | None = None,
        include_archived: bool | None = False,
        **kwargs,
    ) -> AsyncQuery:
        """Build an `AsyncQuery` for `model` with the sync `where` sugar.

        Semantics match `Database.where`: `kwargs` as equality filters
        (plus the `{op: val}` operator-dict form for `in`/`notin`/`!=`),
        `archived_at IS NULL` by default, optional `asc`/`desc` ordering
        by column name(s).
        """
        stmt = select(model)
        filter_conditions = []

        for attr, value in kwargs.items():
            if isinstance(value, dict):
                for op, val in value.items():
                    column = getattr(model, attr)
                    if op == "in":
                        filter_conditions.append(column.in_(val))
                    elif op == "notin":
                        filter_conditions.append(column.notin_(val))
                    elif op == "!=":
                        filter_conditions.append(column != val)
                    else:
                        raise ValueError(f"Unsupported operator: {op}")
            else:
                filter_conditions.append(getattr(model, attr) == value)

        if filter_conditions:
            stmt = stmt.where(and_(*filter_conditions))

        if not include_archived:
            stmt = stmt.where(model.archived_at.is_(None))

        if asc:
            cols = asc if isinstance(asc, list) else [asc]
            stmt = stmt.order_by(*(sa_asc(getattr(model, c)) for c in cols))
        if desc:
            cols = desc if isinstance(desc, list) else [desc]
            stmt = stmt.order_by(*(sa_desc(getattr(model, c)) for c in cols))

        return AsyncQuery(self.db, stmt, model)

    async def find_by(
        self,
        model_class,
        desc: str | list | None = None,
        asc: str | list | None = None,
        include_archived: bool | None = False,
        **kwargs,
    ):
        return await self.where(
            model=model_class,
            desc=desc,
            asc=asc,
            include_archived=include_archived,
            **kwargs,
        ).first()

    async def find_or_create_by(
        self,
        model_class,
        defaults: dict | None = None,
        desc: str | list | None = None,
        asc: str | list | None = None,
        include_archived: bool | None = False,
        **kwargs,
    ):
        if defaults is None:
            defaults = {}

        lock_key = f"{model_class.__name__}_" + "_".join(
            [f"{k}_{v}" for k, v in kwargs.items()]
        )

        async with self.lock(lock_key):
            existing = await self.where(
                model=model_class,
                desc=desc,
                asc=asc,
                include_archived=include_archived,
                **kwargs,
            ).first()
            if existing:
                return existing
            instance = model_class(**defaults, **kwargs)
            return await self.create(instance)

    # ─────────────────────────── Writes ───────────────────────────

    async def create(self, model):
        try:
            self.db.add(model)
            await self.db.commit()
            await self.db.refresh(model)
            return model
        except Exception:
            await self.db.rollback()
            raise

    async def create_all(self, models):
        try:
            self.db.add_all(models)
            await self.db.commit()
            return models
        except Exception:
            await self.db.rollback()
            raise

    async def update(self, model, **kwargs):
        for key, value in kwargs.items():
            setattr(model, key, value)
        return await self.save(model)

    async def update_all(self, models, **kwargs):
        for model in models:
            for key, value in kwargs.items():
                setattr(model, key, value)
        return await self.save_all(models)

    async def bulk_update(self, model_class, filters: list, **updates):
        """Bulk update via SQL UPDATE without loading rows.

        Signature intentionally differs from sync `bulk_update(query, **kwargs)`:
        AsyncQuery is not directly UPDATEable (it wraps Select, not
        Query), so we take (model_class, filters, **updates) and build
        the `update(...).where(...)` statement inline.
        """
        try:
            stmt = sa_update(model_class).where(*filters).values(**updates)
            await self.db.execute(stmt)
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

    async def find_and_bulk_update(
        self,
        model_class,
        updates: dict,
        include_archived: bool | None = False,
        **filters,
    ):
        """Apply bulk update to rows matching the sync `where`-style filters."""
        where_clauses = []
        for attr, value in filters.items():
            if isinstance(value, dict):
                for op, val in value.items():
                    column = getattr(model_class, attr)
                    if op == "in":
                        where_clauses.append(column.in_(val))
                    elif op == "notin":
                        where_clauses.append(column.notin_(val))
                    elif op == "!=":
                        where_clauses.append(column != val)
                    else:
                        raise ValueError(f"Unsupported operator: {op}")
            else:
                where_clauses.append(getattr(model_class, attr) == value)
        if not include_archived:
            where_clauses.append(model_class.archived_at.is_(None))
        await self.bulk_update(model_class, where_clauses, **updates)

    async def save(self, model):
        try:
            self.db.add(model)
            await self.db.commit()
            await self.db.refresh(model)
            return model
        except Exception:
            await self.db.rollback()
            raise

    async def save_all(self, models):
        try:
            self.db.add_all(models)
            await self.db.commit()
            for model in models:
                await self.db.refresh(model)
            return models
        except Exception:
            await self.db.rollback()
            raise

    async def delete(self, model):
        try:
            await self.db.delete(model)
            await self.db.commit()
            return model
        except ObjectDeletedError:
            logger.warning("Object already deleted.")
            return model
        except Exception:
            await self.db.rollback()
            raise

    async def delete_by(self, model_class, filters: list):
        """Async-only helper for SQL DELETE without loading rows.

        No sync twin — callers that need this today go through
        `database.db.query(...).delete()`. Exposed here so the async
        path doesn't have to reach into the raw session.
        """
        try:
            stmt = sa_delete(model_class).where(*filters)
            await self.db.execute(stmt)
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

    # ─────────────────────────── Locking ──────────────────────────

    def lock(self, key: str) -> AsyncAdvisoryLock:
        return AsyncAdvisoryLock(self.engine, key)

    # ─────────────────────────── Lifecycle ────────────────────────

    async def close(self):
        if self._owns_session:
            await self.db.close()
