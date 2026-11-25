"""rshred1 — keep registered RED artifacts out of default collection.

The registry and the full policy live in `tools/red-artifacts.txt`; the
loader lives in `utils.testing.red_registry`. See either for the
`PYTEST_RUN_RED=1` opt-in that drives an artifact from RED to GREEN.
"""

from utils.testing.red_registry import collect_ignore_for

collect_ignore = collect_ignore_for(__file__)
