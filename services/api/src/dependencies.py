from hal_utils.services.database import Database, SessionLocal


def get_db():
    """Gets the database session as a FastAPI dependency."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_database():
    """Gets the high level database object as a FastAPI dependency."""

    database = Database()
    try:
        yield database
    finally:
        database.close()
