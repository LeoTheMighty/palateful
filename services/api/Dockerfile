# syntax=docker/dockerfile:1
# Keep this syntax directive! It's used to enable Docker BuildKit

################################
# PYTHON-BASE
# Sets up all our shared environment variables
################################
FROM python:3.13-slim AS python-base

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
    POETRY_VERSION=2.1.1 \
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
    DOCKER_SERVICE_ROOT="/services/api" \
    LOCAL_SERVICE_ROOT="services/api" \
    VENV_PATH="/services/api/.venv"


# prepend poetry and venv to path
ENV PATH="$POETRY_HOME/bin:$VENV_PATH/bin:$PATH"

################################
# BUILDER-BASE
# Used to build deps + create our virtual environment
################################
FROM python-base AS builder-base
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        # deps for installing poetry
        curl \
        # deps for building python deps
        build-essential \
        # deps for building psycopg2 from source if needed
        libpq-dev

# install poetry - respects $POETRY_VERSION & $POETRY_HOME
RUN curl -sSL https://install.python-poetry.org | python3 -

# Copy library dependencies for path-based dependencies
COPY ./libraries/utils /libraries/utils
COPY ./libraries/agent /libraries/agent
WORKDIR $DOCKER_SERVICE_ROOT
COPY $LOCAL_SERVICE_ROOT/poetry.lock $LOCAL_SERVICE_ROOT/pyproject.toml ./

# install runtime deps - uses $POETRY_VIRTUALENVS_IN_PROJECT internally
RUN poetry install --only main --no-root


################################
# DEVELOPMENT
# Image used during development / testing
################################
FROM python-base AS development
ENV FASTAPI_ENV=development
WORKDIR $DOCKER_SERVICE_ROOT

# copy in our built poetry + venv
COPY --from=builder-base $POETRY_HOME $POETRY_HOME
COPY --from=builder-base $DOCKER_SERVICE_ROOT $DOCKER_SERVICE_ROOT
COPY --from=builder-base /libraries/utils /libraries/utils
COPY --from=builder-base /libraries/agent /libraries/agent

# quicker install as runtime deps are already installed
# Use --only main to exclude test dependencies that have path references
RUN poetry install --only main --no-root

# will become mountpoint of our code
WORKDIR ./src

ENV PYTHONPATH="$DOCKER_SERVICE_ROOT/src"

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]


################################
# PRODUCTION
# Final image used for runtime
################################
FROM python-base AS production
ENV FASTAPI_ENV=production

WORKDIR $DOCKER_SERVICE_ROOT

# Copy only the virtual environment (contains all runtime dependencies)
COPY --from=builder-base $VENV_PATH $VENV_PATH
# Copy library dependencies needed for editable installs
COPY --from=builder-base /libraries/utils /libraries/utils
COPY --from=builder-base /libraries/agent /libraries/agent

# Copy application code
COPY $LOCAL_SERVICE_ROOT/src $DOCKER_SERVICE_ROOT/src/

WORKDIR $DOCKER_SERVICE_ROOT/src

ENV PYTHONPATH="$DOCKER_SERVICE_ROOT/src"

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
