import os
from test_helper.environment import setup_environment
from test_helper.factories.user_factory import UserFactory
from test_helper.factories.pantry_factory import PantryFactory
from test_helper.factories.ingredient_factory import IngredientFactory
from test_helper.factories.thread_factory import ThreadFactory
from test_helper.factories.recipe_book_factory import RecipeBookFactory
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text
from sqlalchemy import event


def pytest_configure():
    """Configure Pytest, runs before any tests are run."""
    setup_environment()


@pytest.fixture(scope='session')
def postgres_engine():
    """Create postgres engine once per testing session."""
    engine = create_engine(
        os.environ.get('DATABASE_URL'),
        pool_size=10,
        max_overflow=20
    )
    return engine


@pytest.fixture
def db_session(postgres_engine):
    """Fixture to establish database session with transaction rollback."""
    connection = postgres_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, _tx):
        if not sess.in_nested_transaction():
            sess.begin_nested()

    orig_commit = session.commit
    orig_rollback = session.rollback

    def _safe_commit():
        try:
            if session.get_transaction() and session.get_transaction().nested:
                session.flush()
            else:
                orig_commit()
        except Exception:
            orig_rollback()
            raise

    def _safe_rollback():
        nested_tx = getattr(session, "get_nested_transaction", None)
        if nested_tx is not None:
            nested_tx = session.get_nested_transaction()
        if nested_tx is None:
            tx = session.get_transaction()
            while tx is not None and not tx.nested and tx._parent is not None:
                tx = tx._parent
            if tx and tx.nested:
                nested_tx = tx

        try:
            if nested_tx is not None and nested_tx.is_active:
                nested_tx.rollback()
            else:
                orig_rollback()
        except Exception:
            pass

    session.commit = _safe_commit
    session.rollback = _safe_rollback

    try:
        yield session
        session.execute(text('SELECT pg_advisory_unlock_all();'))
    finally:
        transaction.rollback()
        session.close()
        connection.close()


@pytest.fixture
def new_transaction(db_session):
    """Fixture to create a new transaction when called."""
    def _new_transaction():
        db_session.commit()
        return db_session.begin_nested()
    return _new_transaction


@pytest.fixture
def database(db_session):
    """Fixture to establish database session."""
    from utils.services.database import Database
    return Database(db=db_session)


@pytest.fixture
def _cleanup_db(database):
    """Fixture to clean up the database after each test."""
    yield
    database.db.rollback()


# Model Helpers and Factories
def create_model_instance(db_session, factory_class, **kwargs):
    """Helper function for model factory fixtures to create model instances."""
    factory_class._meta.sqlalchemy_session = db_session
    instance = factory_class(**kwargs)
    db_session.add(instance)
    db_session.commit()
    return instance


@pytest.fixture
def user_factory(db_session):
    """Factory to create User instances."""
    return lambda **kwargs: create_model_instance(
        db_session,
        UserFactory,
        **kwargs
    )


@pytest.fixture
def pantry_factory(db_session):
    """Factory to create Pantry instances."""
    return lambda **kwargs: create_model_instance(
        db_session,
        PantryFactory,
        **kwargs
    )


@pytest.fixture
def ingredient_factory(db_session):
    """Factory to create Ingredient instances."""
    return lambda **kwargs: create_model_instance(
        db_session,
        IngredientFactory,
        **kwargs
    )


@pytest.fixture
def thread_factory(db_session, user_factory):
    """Factory to create Thread instances."""
    return lambda **kwargs: create_model_instance(
        db_session,
        ThreadFactory,
        **{
            'user_id': user_factory().id,
            **kwargs
        }
    )


@pytest.fixture
def recipe_book_factory(db_session):
    """Factory to create RecipeBook instances."""
    return lambda **kwargs: create_model_instance(
        db_session,
        RecipeBookFactory,
        **kwargs
    )
