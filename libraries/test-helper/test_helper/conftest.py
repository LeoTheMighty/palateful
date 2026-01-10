import os
from test_helper.environment import setup_environment
# from test_helper.factories.chat_factory import ChatFactory
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text
from sqlalchemy import event


def pytest_configure():
    """Configure Pytest, runs before any tests are run."""
    setup_environment()



@pytest.fixture
def api_exception_matcher():
    """Fixture that returns a matcher for APIException."""
    def _matcher(expected_exception):
        return APIExceptionMatcher(expected_exception)
    return _matcher


@pytest.fixture(scope='session')
def postgres_engine():
    """Create postgres engine once per testing session."""
    engine = create_engine(
        os.environ.get('DATABASE_URL'),
        pool_size=10,
        max_overflow=20
    )
    return engine


# pylint: disable=redefined-outer-name, unused-argument
@pytest.fixture
def db_session(postgres_engine):
    """Fixture to establish database session."""
    connection = postgres_engine.connect()

    # Begin an explicit outer transaction.  Everything that happens in the
    # test will be contained inside this transaction and will be rolled back
    # in the fixture's teardown, keeping the database pristine between tests.
    transaction = connection.begin()

    session = sessionmaker(bind=connection)()

    # Start a SAVEPOINT for the test.
    session.begin_nested()

    # Whenever the SAVEPOINT ends (because the application code called
    # `commit()` or `rollback()`), open a new SAVEPOINT so that the next
    # operation continues to be isolated.
    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, _tx):  # pylint: disable=unused-argument
        # If this is the end of the nested transaction, open a new one.
        if not sess.in_nested_transaction():
            sess.begin_nested()

    # UNCOMMENT TO DEBUG TRANSACTIONS AND SAVEPOINTS =====
    # def tx_event(sess, trans, label):
    #     print(f"{label:>8} id={id(trans)} nested={trans.nested} "
    #           f"parent={id(trans._parent) if trans._parent else None}")

    # @event.listens_for(session, "after_transaction_create")
    # def _dbg_tx_begin(sess, trans):  # pylint: disable=unused-argument
    #     tx_event(sess, trans, "BEGIN")

    # @event.listens_for(session, "after_transaction_end")
    # def _dbg_tx_end(sess, trans):  # pylint: disable=unused-argument
    #     tx_event(sess, trans, "END")

    # @event.listens_for(session, "after_commit")
    # def _dbg_after_commit(sess):  # pylint: disable=unused-argument
    #     print("SESSION COMMIT")

    # @event.listens_for(session, "after_rollback")
    # def _dbg_after_rollback(sess):  # pylint: disable=unused-argument
    #     print("SESSION ROLLBACK")
    # ================================================

    orig_commit = session.commit
    orig_rollback = session.rollback

    def _safe_commit():
        """
        If we're inside a save-point just flush; don't close it.
        Otherwise fall back to the real commit (this should never
        happen inside the test harness, but keeps the override safe).
        """
        try:
            if session.get_transaction() and session.get_transaction().nested:
                session.flush()           # keep SAVEPOINT alive
            else:
                orig_commit()
        except Exception as _:
            # make sure the Session isn't left in failed state
            orig_rollback()
            # listener will open a fresh SAVEPOINT
            raise

    def _safe_rollback():
        """
        Roll back only the *current* save-point if we are in one,
        otherwise roll back the root (used by the fixture's teardown).
        """
        # pylint: disable=protected-access
        nested_tx = getattr(session, "get_nested_transaction", None)
        if nested_tx is not None:
            nested_tx = session.get_nested_transaction()
        # Fallback for SQLAlchemy <1.4 where get_nested_transaction doesn't exist
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
        # Ignore cases where the transaction we intended to roll back
        # has already been closed or is otherwise inactive.
        except Exception:  # pylint: disable=broad-except
            pass

    session.commit   = _safe_commit
    session.rollback = _safe_rollback

    try:
        yield session

        # Delete all locks
        session.execute(text('SELECT pg_advisory_unlock_all();'))
    finally:
        # Roll back the outer transaction so the database is returned to a
        # clean state for the next test run.
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
    from hal_utils.services.database import Database
    return Database(db=db_session)


@pytest.fixture
def _cleanup_db(database):
    """Fixture to clean up the database after each test."""
    yield
    # Rollback always cleans up the database, though this is not necessary
    database.db.rollback()


# Model Helpers and Factories
def create_model_instance(db_session, factory_class, **kwargs):
    """Helper function for model factory fixtures to create model instances."""
    # pylint: disable=protected-access
    factory_class._meta.sqlalchemy_session = db_session
    instance = factory_class(**kwargs)
    db_session.add(instance)
    db_session.commit()
    return instance


@pytest.fixture
def prompt_factory(db_session):
    """Factory to create Prompt instances."""
    return lambda **kwargs: create_model_instance(
        db_session,
        PromptFactory,
        **kwargs
    )


@pytest.fixture
def generation_factory(db_session, prompt_factory):
    """Factory to create Generation instances."""
    return lambda **kwargs: create_model_instance(
        db_session,
        GenerationFactory,
        **{
            'prompt_id': prompt_factory().id,
            **kwargs
        }
    )


@pytest.fixture
def summarized_item_factory(db_session):
    """Factory to create SummarizedItem instances."""
    return lambda **kwargs: create_model_instance(
        db_session,
        SummarizedItemFactory,
        **kwargs
    )


@pytest.fixture
def summary_factory(db_session, generation_factory, summarized_item_factory):
    """Factory to create Summary instances."""
    return lambda **kwargs: create_model_instance(
        db_session,
        SummaryFactory,
        **{
            'generation_id': generation_factory().id,
            'summarized_item_id': summarized_item_factory().id,
            **kwargs
        }
    )


@pytest.fixture
def text_edit_suggestion_factory(db_session, generation_factory):
    """Factory to create TextEditSuggestion instances."""
    return lambda **kwargs: create_model_instance(
        db_session,
        TextEditSuggestionFactory,
        **{
            'generation_id': generation_factory().id,
            **kwargs
        }
    )

@pytest.fixture
def thread_factory(db_session):
    """Factory to create Thread instances."""
    return lambda **kwargs: create_model_instance(
        db_session,
        ThreadFactory,
        **kwargs
    )

@pytest.fixture
def chat_factory(db_session, generation_factory, thread_factory):
    """Factory to create Chat instances."""
    return lambda **kwargs: create_model_instance(
        db_session,
        ChatFactory,
        **{
            'thread_id': thread_factory().id,
            'generation_id': generation_factory().id,
            **kwargs
        }
    )

@pytest.fixture
def chat_generation_factory(db_session, chat_factory, generation_factory):
    """Factory to create ChatGeneration instances."""
    return lambda **kwargs: create_model_instance(
        db_session,
        ChatGenerationFactory,
        **{
            'chat_id': chat_factory().id,
            'generation_id': generation_factory().id,
            **kwargs
        }
    )


@pytest.fixture
def context_status_factory(db_session):
    """Factory to create ContextStatus instances."""
    return lambda **kwargs: create_model_instance(
        db_session,
        ContextStatusFactory,
        **kwargs
    )


@pytest.fixture
def document_factory(db_session):
    """Factory to create Document instances."""
    return lambda **kwargs: create_model_instance(
        db_session,
        DocumentFactory,
        **kwargs
    )


@pytest.fixture
def context_status_document_factory(db_session, context_status_factory, document_factory):
    """Factory to create ContextStatusDocument instances."""
    return lambda **kwargs: create_model_instance(
        db_session,
        ContextStatusDocumentFactory,
        **{
            'context_status_id': context_status_factory().id,
            'document_id': document_factory().id,
            **kwargs
        }
    )


@pytest.fixture
def tenant_factory(db_session):
    """Factory to create Tenant instances."""
    return lambda **kwargs: create_model_instance(
        db_session,
        TenantFactory,
        **kwargs
    )


@pytest.fixture
def merchant_factory(db_session, tenant_factory):
    """Factory to create Merchant instances."""
    return lambda **kwargs: create_model_instance(
        db_session,
        MerchantFactory,
        **{
            'tenant_id': tenant_factory().id,
            **kwargs
        }
    )


@pytest.fixture
def merchant_document_factory(db_session, merchant_factory):
    """Factory to create MerchantDocument instances."""
    return lambda **kwargs: create_model_instance(
        db_session,
        MerchantDocumentFactory,
        **{
            'merchant_id': merchant_factory().id,
            **kwargs
        }
    )


@pytest.fixture
def parsing_run_factory(db_session, merchant_document_factory):
    """Factory to create ParsingRun instances."""
    return lambda **kwargs: create_model_instance(
        db_session,
        ParsingRunFactory,
        **{
            'document_id': merchant_document_factory().id,
            **kwargs
        }
    )
