import enum
import inspect
import os
import importlib
import pkgutil
from pprint import pprint

from sqlalchemy.orm import sessionmaker
from sqlalchemy import (
    create_engine,
    inspect as sqlalchemy_inspect,
)

# Load env vars
from dotenv import load_dotenv

# Load environment variables from .env.dev
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../../../.env.dev'))

# pylint: disable=wrong-import-position
from utils.constants import DATABASE_URL

# Dynamically import all models from the models directory before importing the
# Base class that stores all the metadata for the database
from utils import classes as enums_package
from utils import models as models_package


def get_imported_objects(package, object_type, predicate, context=None):
    """
    Import all objects in the given package and return them in a
    context dictionary.
    """
    if context is None:
        context = {}

    package_name = package.__name__
    print(f'Importing {object_type} files from {package_name}')

    for _, module_name, is_pkg in pkgutil.walk_packages(
        package.__path__,
        f'{package_name}.'
    ):
        print(f'Importing module: {module_name}')
        module = importlib.import_module(module_name)
        if is_pkg:
            # Recursive call to handle sub-packages
            get_imported_objects(
                module,
                object_type,
                predicate,
                context=context
            )
        else:
            members = inspect.getmembers(module)
            for name, obj in members:
                if (
                    inspect.isclass(obj)
                    and obj.__module__ == module_name
                    and predicate(obj)
                ):
                    print(f'Adding {object_type}: {name}')
                    context[name] = obj
    return context


def main():
    """
    Imports the SQLAlchemy models, enums, and starts the interactive shell.
    """
    # Create the engine and session
    engine = create_engine(DATABASE_URL)
    session = sessionmaker(bind=engine)()

    # Import models
    imported_models = get_imported_objects(
        models_package,
        'model',
        lambda obj: hasattr(obj, '__table__')
    )

    # Import enums
    imported_enums = get_imported_objects(
        enums_package,
        'enum',
        lambda obj: issubclass(obj, enum.Enum)
    )

    # pylint: disable=import-outside-toplevel
    from utils.services.database import Database

    database = Database(db=session)

    # Inject the session and models into the shell context
    context = {
        'db': session,
        'database': database,
        'inspector': sqlalchemy_inspect(engine),
        **imported_models,
        **imported_enums,
    }

    print('\nContext:\n')
    pprint(context)

    # pylint: disable=import-outside-toplevel
    try:
        from IPython import start_ipython
        startup_code = (
            """
            from sqlalchemy import select, func, asc, desc, and_, or_
            from sqlalchemy.orm import load_only, defer
            """
        )
        print(f'\nImports:\n{startup_code}')
        start_ipython(
            argv=['--InteractiveShellApp.exec_lines', startup_code],
            user_ns=context
        )
    except ImportError:
        import code
        code.interact(local=context)


if __name__ == '__main__':
    main()
