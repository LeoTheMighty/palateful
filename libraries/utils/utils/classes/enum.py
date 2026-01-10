"""
Custom enum type decorators for SQLAlchemy.

This module provides TypeDecorator implementations for handling Python enums in the database.
Instead of using PostgreSQL native ENUM types (which are difficult to migrate), we store
enum values as VARCHAR/INTEGER and use TypeDecorators to handle conversion.

References:
- SQLAlchemy TypeDecorator: https://docs.sqlalchemy.org/en/20/core/custom_types.html
- Enum best practices: https://michaelcho.me/article/using-python-enums-in-sqlalchemy-models/
- PostgreSQL ARRAY type: https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#array-types
"""
from enum import Enum
from typing import Type, Optional
from sqlalchemy import Integer, String
from sqlalchemy.types import TypeDecorator


class BaseEnum(Enum):
    """
    The base class for all enums in the microservice. Used for serialization.

    Provides a `from_value()` method to look up enum members by their value.
    """

    @classmethod
    def from_value(cls, value):
        """
        Gets the enum member using the value of the enum.

        Args:
            value: The value to look up

        Returns:
            The enum member with the matching value

        Raises:
            ValueError: If no enum member has the given value
        """
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(f"{value} is not a valid value for {cls.__name__}")


class IntEnum(TypeDecorator):  # pylint: disable=too-many-ancestors
    """
    SQLAlchemy type decorator for integer-based enums.

    Stores enum values as integers in the database but returns enum instances
    in Python code. Used for enums like ErrorCode where values are integers.

    This approach avoids PostgreSQL native ENUM types which are difficult to migrate.
    Instead, we store integer values directly and handle conversion in Python.

    Example:
        class ErrorCode(BaseEnum):
            INTERNAL_ERROR = 1
            DOCUMENT_TOO_LARGE = 2

        class Document(Base):
            error_code: Mapped[Optional[ErrorCode]] = mapped_column(
                IntEnum(ErrorCode),
                nullable=True
            )

    References:
        - TypeDecorator docs: https://docs.sqlalchemy.org/en/20/core/custom_types.html
        - process_bind_param: Converts Python values to database format
        - process_result_value: Converts database values back to Python objects
    """
    impl = Integer
    cache_ok = True

    def __init__(self, enum_class: Type[Enum], *args, **kwargs):
        self.enum_class = enum_class
        super().__init__(*args, **kwargs)

    def process_bind_param(self, value: Optional[Enum], dialect) -> Optional[int]:
        """
        Convert Python enum to integer for database storage.

        Called when writing to the database. Accepts either an enum instance
        or an integer value directly.

        Args:
            value: Python enum member or integer
            dialect: SQLAlchemy dialect (unused)

        Returns:
            Integer value for database storage, or None

        Raises:
            ValueError: If value is not an enum, int, or None
        """
        if value is None:
            return None
        if isinstance(value, self.enum_class):
            return value.value
        if isinstance(value, int):
            return value
        raise ValueError(f"Expected {self.enum_class.__name__} or int, got {type(value)}")

    def process_result_value(self, value: Optional[int], dialect) -> Optional[Enum]:
        """
        Convert integer from database to Python enum.

        Called when reading from the database. Converts the stored integer
        back into a Python enum instance.

        Args:
            value: Integer from database
            dialect: SQLAlchemy dialect (unused)

        Returns:
            Python enum member, or None

        Raises:
            ValueError: If integer doesn't map to a valid enum member
        """
        if value is None:
            return None
        return self.enum_class(value)


class StringEnum(TypeDecorator):  # pylint: disable=too-many-ancestors
    """
    SQLAlchemy type decorator for string-based enums.

    Stores enum values as VARCHAR strings in the database but returns enum instances
    in Python code. Used for enums like Status, Action, Service, Model, etc.

    This approach avoids PostgreSQL native ENUM types which are difficult to migrate.
    Instead, we store string values (e.g., 'gpt-4o-mini', 'pending') and handle
    conversion in Python.

    Example:
        class Status(BaseEnum):
            PENDING = 'pending'
            ACTIVE = 'active'
            FAILED = 'failed'

        class Summary(Base):
            status: Mapped[Status] = mapped_column(
                StringEnum(Status),
                default=Status.PENDING
            )

    References:
        - TypeDecorator docs: https://docs.sqlalchemy.org/en/20/core/custom_types.html
        - Enum migration guide: https://roman.pt/posts/alembic-enums/
    """
    impl = String
    cache_ok = True

    def __init__(self, enum_class: Type[Enum], *args, **kwargs):
        self.enum_class = enum_class
        super().__init__(*args, **kwargs)

    def process_bind_param(self, value: Optional[Enum], dialect) -> Optional[str]:
        """
        Convert Python enum to string for database storage.

        Called when writing to the database. Accepts either an enum instance
        or a string value directly.

        Args:
            value: Python enum member or string
            dialect: SQLAlchemy dialect (unused)

        Returns:
            String value for database storage, or None

        Raises:
            ValueError: If value is not an enum, str, or None
        """
        if value is None:
            return None
        if isinstance(value, self.enum_class):
            return value.value
        if isinstance(value, str):
            return value
        raise ValueError(f"Expected {self.enum_class.__name__} or str, got {type(value)}")

    def process_result_value(self, value: Optional[str], dialect) -> Optional[Enum]:
        """
        Convert string from database to Python enum.

        Called when reading from the database. Converts the stored string
        back into a Python enum instance by matching against enum values.

        Args:
            value: String from database
            dialect: SQLAlchemy dialect (unused)

        Returns:
            Python enum member, or None

        Raises:
            ValueError: If string doesn't match any enum member's value
        """
        if value is None:
            return None
        return self.enum_class(value)


class StringEnumArray(TypeDecorator):  # pylint: disable=too-many-ancestors
    """
    SQLAlchemy type decorator for arrays of string-based enums.

    Stores array of enum values as PostgreSQL VARCHAR[] in the database but returns
    list of Python enum instances in the code. Used for columns that need to store
    multiple enum values (e.g., a list of supported models).

    This uses PostgreSQL's native ARRAY type for efficient storage and querying,
    while maintaining type safety through Python enums.

    Example:
        class Model(BaseEnum):
            GPT_4_O = 'gpt-4o'
            GPT_4_O_MINI = 'gpt-4o-mini'
            GPT_3_5_TURBO_1106 = 'gpt-3.5-turbo-1106'

        class Prompt(Base):
            for_models: Mapped[list[Model]] = mapped_column(
                StringEnumArray(Model)
            )

        # Usage:
        prompt.for_models = [Model.GPT_4_O, Model.GPT_4_O_MINI]
        # Stored in DB as: ['gpt-4o', 'gpt-4o-mini']

    References:
        - PostgreSQL ARRAY:
          https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#array-types
        - ARRAY operations:
          https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#sqlalchemy.dialects.postgresql.ARRAY
    """
    impl = String
    cache_ok = True

    def __init__(self, enum_class: Type[Enum], *args, **kwargs):
        self.enum_class = enum_class
        # Import here to avoid circular imports
        from sqlalchemy.dialects.postgresql import ARRAY
        self.impl = ARRAY(String)
        super().__init__(*args, **kwargs)

    def process_bind_param(self, value: Optional[list], dialect) -> Optional[list]:
        """
        Convert Python enum list to string list for database storage.

        Called when writing to the database. Iterates through the list and
        converts each enum member to its string value.

        Args:
            value: List of Python enum members or strings
            dialect: SQLAlchemy dialect (unused)

        Returns:
            List of strings for database storage, or None

        Raises:
            ValueError: If any list item is not an enum or string
        """
        if value is None:
            return None
        result = []
        for item in value:
            if isinstance(item, self.enum_class):
                result.append(item.value)
            elif isinstance(item, str):
                result.append(item)
            else:
                raise ValueError(
                    f"Expected {self.enum_class.__name__} or str, got {type(item)}"
                )
        return result

    def process_result_value(self, value: Optional[list], dialect) -> Optional[list]:
        """
        Convert string list from database to Python enum list.

        Called when reading from the database. Converts each string in the
        array back to its corresponding Python enum instance.

        Args:
            value: List of strings from database
            dialect: SQLAlchemy dialect (unused)

        Returns:
            List of Python enum members, or None

        Raises:
            ValueError: If any string doesn't match a valid enum member
        """
        if value is None:
            return None
        return [self.enum_class(item) for item in value]
