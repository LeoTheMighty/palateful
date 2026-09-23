"""rshred1 — keep registered RED artifacts out of default collection.

The registry and the full policy live in `tools/red-artifacts.txt`; the
loader lives in `utils.testing.red_registry`. See either for the
`PYTEST_RUN_RED=1` opt-in that drives an artifact from RED to GREEN.
"""

import os

# envspell1: declare the environment rather than inheriting the unset
# default. `utils.environment.is_recording_environment` treats an absent
# value as production — deliberately, so a config typo cannot silence a
# recorder — which means an undeclared test process starts exercising the
# 4xx audit writer and emitting its failure tracebacks into the suite log.
# `services/api/tests/conftest.py` has always done this; this suite had not.
os.environ.setdefault("ENVIRONMENT", "test")

from utils.testing.red_registry import collect_ignore_for  # noqa: E402

collect_ignore = collect_ignore_for(__file__)
