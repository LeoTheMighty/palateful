# syntax=docker/dockerfile:1

################################
# PYTHON-BASE
# Sets up all our shared environment variables
################################
FROM python:3.13-slim as python-base

    # python
ENV PYTHONUNBUFFERED=1 \
    # prevents python creating .pyc files
    PYTHONDONTWRITEBYTECODE=1 \
    \
    # pip
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    \
    # poetry
    # https://python-poetry.org/docs/configuration/#using-environment-variables
    POETRY_VERSION=2.2.1 \
    # make poetry install to this location
    POETRY_HOME="/opt/poetry" \
    # make poetry create the virtual environment in the project's root
    # it gets named `.venv`
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    # do not ask any interactive question
    POETRY_NO_INTERACTION=1 \
    \
    # paths
    # this is where our requirements + virtual environment will live
    DOCKER_SERVICE_ROOT="/services/migrator" \
    LOCAL_SERVICE_ROOT="services/migrator" \
    VENV_PATH="/services/migrator/.venv"


# prepend poetry and venv to path
ENV PATH="$POETRY_HOME/bin:$VENV_PATH/bin:$PATH"


################################
# BUILDER-BASE
# Used to build deps + create our virtual environment
################################
FROM python-base as builder-base
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        # deps for installing poetry
        curl \
        # deps for building python deps
        build-essential \
        # deps for building psycopg2 from source (required for Python 3.14)
        libpq-dev

# install poetry - respects $POETRY_VERSION & $POETRY_HOME
RUN curl -sSL https://install.python-poetry.org | python3 -

# Copy library dependencies for path-based dependencies
COPY ./libraries/utils /libraries/utils
WORKDIR $DOCKER_SERVICE_ROOT
COPY $LOCAL_SERVICE_ROOT/poetry.lock $LOCAL_SERVICE_ROOT/pyproject.toml ./

# install runtime deps - uses $POETRY_VIRTUALENVS_IN_PROJECT internally
RUN poetry install --only main --no-root


################################
# MIGRATOR
# Image used for performing migrations
################################
FROM python-base as migrator

COPY --from=builder-base $DOCKER_SERVICE_ROOT $DOCKER_SERVICE_ROOT
# Copy library dependencies needed for editable installs
COPY --from=builder-base /libraries/utils /libraries/utils

COPY $LOCAL_SERVICE_ROOT/migrations $DOCKER_SERVICE_ROOT/migrations
COPY $LOCAL_SERVICE_ROOT/alembic.ini $DOCKER_SERVICE_ROOT/

WORKDIR $DOCKER_SERVICE_ROOT

ENTRYPOINT ["alembic"]
CMD ["upgrade", "head"]
