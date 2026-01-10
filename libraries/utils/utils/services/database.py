import logging
import pkgutil
from typing import Optional, Union
from sqlalchemy import and_, desc as sa_desc, asc as sa_asc, create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.orm.exc import ObjectDeletedError
from utils.constants import DATABASE_URL, DB_POOL_SIZE, DB_MAX_OVERFLOW
from utils.services.advisory_lock import AdvisoryLock
from utils import models as models_package

logger = logging.getLogger(__name__)


def import_models(package):
    """Import all models in the given package"""
    for _, module_name, is_pkg in pkgutil.walk_packages(
        package.__path__,
        package.__name__ + '.'
    ):
        __import__(module_name)
        if is_pkg:
            next_package = __import__(module_name, fromlist=["dummy"])
            import_models(next_package)  # Recursive call to handle sub-packages


if DATABASE_URL:
    db_engine = create_engine(
        DATABASE_URL,
        pool_size=DB_POOL_SIZE,
        max_overflow=DB_MAX_OVERFLOW,
        pool_pre_ping=True,
        pool_recycle=3600
    )

    # Dynamically import all models from the models directory
    import_models(models_package)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
else:
    db_engine = None
    SessionLocal = None


class Database:
    """Database class to manage database connection and common operations."""

    def __init__(self, db: Session = None, engine: Engine = None):
        if engine is None:
            self.engine = db_engine
            self.SessionLocal = SessionLocal
        else:
            self.engine = engine
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        if db is None:
            self.db = self.SessionLocal()
        else:
            self.db = db

    # pylint: disable=too-many-arguments, too-many-branches
    def find_by(
        self,
        model_class,
        desc: Optional[Union[str, list]] = None,
        asc: Optional[Union[str, list]] = None,
        include_archived: Optional[bool] = False,
        **kwargs
    ):
        """Find the first record that matches the filters from the database."""
        return self.where(
            model=model_class,
            desc=desc,
            asc=asc,
            include_archived=include_archived,
            **kwargs
        ).first()

    def find_or_create_by(
        self,
        model_class,
        defaults: Optional[dict] = None,
        desc: Optional[Union[str, list]] = None,
        asc: Optional[Union[str, list]] = None,
        include_archived: Optional[bool] = False,
        **kwargs
    ):
        """Find a record in the database based on params or create it if it does not exist."""
        if defaults is None:
            defaults = {}

        lock_key = f"{model_class.__name__}_{'_'.join([f'{k}_{v}' for k, v in kwargs.items()])}"

        with self.lock(lock_key):
            query = self.where(
                model=model_class,
                desc=desc,
                asc=asc,
                include_archived=include_archived,
                **kwargs
            )
            instance = query.first()
            if instance:
                return instance

            instance = model_class(**defaults, **kwargs)
            return self.create(instance)

    # This can't handle OR conditions, will need to extend if needed
    def where(
        self,
        model,
        desc: Optional[Union[str, list]] = None,
        asc: Optional[Union[str, list]] = None,
        include_archived: Optional[bool] = False,
        **kwargs
    ):
        """Builds complex queries based on the conditions and ordering provided."""
        query = self.db.query(model)
        filter_conditions = []

        # Build filters based on conditions
        for attr, value in kwargs.items():
            if isinstance(value, dict):
                # Handle special operators like 'in', '!=', etc.
                for op, val in value.items():
                    column = getattr(model, attr)
                    if op == 'in':
                        filter_conditions.append(column.in_(val))
                    elif op == 'notin':
                        filter_conditions.append(column.notin_(val))
                    elif op == '!=':
                        filter_conditions.append(column != val)
                    else:
                        raise ValueError(f"Unsupported operator: {op}")
                    # Add more operators as needed
            else:
                # Assume equality if value is not a dict
                filter_conditions.append(getattr(model, attr) == value)

        if filter_conditions:
            query = query.filter(and_(*filter_conditions))

        # Filter out archived records
        if not include_archived:
            # If archived_at is None, then the record is not archived
            query = query.filter(model.archived_at.is_(None))

        # Handle ascending order
        if asc:
            if not isinstance(asc, list):
                asc = [asc]
            asc_order = [sa_asc(getattr(model, col)) for col in asc]
            query = query.order_by(*asc_order)

        # Handle descending order
        if desc:
            if not isinstance(desc, list):
                desc = [desc]
            desc_order = [sa_desc(getattr(model, col)) for col in desc]
            query = query.order_by(*desc_order)

        return query

    def create(self, model):
        """Create a new record in the database."""
        try:
            self.db.add(model)
            self.db.commit()
            self.db.refresh(model)
            return model
        except Exception as e:
            self.db.rollback()
            raise e

    def create_all(self, models):
        """Create multiple records in the database."""
        try:
            self.db.add_all(models)
            self.db.commit()
            return models
        except Exception as e:
            self.db.rollback()
            raise e

    def update(self, model, **kwargs):
        """Update a record in the database."""
        for key, value in kwargs.items():
            setattr(model, key, value)
        return self.save(model)

    def update_all(self, models, **kwargs):
        """Update multiple records in the database."""
        for model in models:
            for key, value in kwargs.items():
                setattr(model, key, value)
        return self.save_all(models)

    def bulk_update(self, query, **kwargs):
        """Bulk update records from a query without loading them into memory.

        Args:
            query: A SQLAlchemy Query object (typically from where())
            **kwargs: Field updates to apply

        Example:
            query = database.where(Chat, parent_user_chat_id=user_chat_id, thread_id=thread_id)
            database.bulk_update(query, regeneration_count=5)
        """
        try:
            query.update(kwargs, synchronize_session=False)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise e

    def find_and_bulk_update(
        self,
        model_class,
        updates: dict,
        include_archived: Optional[bool] = False,
        **filters
    ):
        """Find records matching filters and bulk update them without loading into memory.

        Args:
            model_class: The model class to query
            updates: Dictionary of field updates to apply
            include_archived: Whether to include archived records (default: False)
            **filters: Filter conditions (same format as where())

        Example:
            database.find_and_bulk_update(
                Chat,
                {'regeneration_count': 5},
                parent_user_chat_id=user_chat_id,
                thread_id=thread_id
            )
        """
        query = self.where(model_class, include_archived=include_archived, **filters)
        self.bulk_update(query, **updates)

    def save(self, model):
        """Save a record in the database."""
        try:
            self.db.add(model)
            self.db.commit()
            self.db.refresh(model)
            return model
        except Exception as e:
            self.db.rollback()
            raise e

    def save_all(self, models):
        """Save multiple records in the database."""
        try:
            self.db.add_all(models)
            self.db.commit()
            for model in models:
                self.db.refresh(model)
            return models
        except Exception as e:
            self.db.rollback()
            raise e

    def delete(self, model):
        """
        Delete a record from the database.
        
        If the record is already deleted, it will return the record.
        """
        try:
            self.db.delete(model)
            self.db.commit()
            return model
        except ObjectDeletedError:
            logger.warning("Object already deleted.")
            return model
        except Exception as e:
            self.db.rollback()
            raise e

    def lock(self, key):
        """Acquire an advisory lock on the database."""
        return AdvisoryLock(self.engine, key)

    def close(self):
        """Close the database connection."""
        self.db.close()
