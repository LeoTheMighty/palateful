"""pyproject/test-target consistency for the eval service (bugs-imp-pho-7).

`nx run eval:test` was dead on arrival: `addopts` asks pytest for an HTML
report, but `pytest-html` was the one dev dependency eval never declared —
alone among the nine Python projects in the monorepo. It went unnoticed
because CI runs eval's tests inside the *root* virtualenv, which does
declare `pytest-html`, so only the sanctioned local command was broken.

These tests parse `pyproject.toml` and check the environment actually
running them, so both halves of that drift are caught.
"""

import importlib.util
import tomllib
from pathlib import Path

import pytest

SERVICE_DIR = Path(__file__).resolve().parent.parent
PYPROJECT = SERVICE_DIR / "pyproject.toml"

# pytest flag -> (distribution declared in pyproject, module pytest imports)
PLUGIN_FLAGS = {
    "--cov": ("pytest-cov", "pytest_cov"),
    "--html": ("pytest-html", "pytest_html"),
}


def _pyproject() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def _addopts() -> str:
    return _pyproject()["tool"]["pytest"]["ini_options"]["addopts"]


def _dev_dependencies() -> dict:
    return _pyproject()["tool"]["poetry"]["group"]["dev"]["dependencies"]


def _required_plugins() -> list[tuple[str, str]]:
    addopts = _addopts()
    return [plugin for flag, plugin in PLUGIN_FLAGS.items() if flag in addopts]


@pytest.mark.parametrize("distribution,module", _required_plugins())
def test_addopts_plugins_are_declared_dev_dependencies(distribution: str, module: str):
    """A plugin flag in addopts is a hard requirement: pytest exits before
    collection if the plugin is absent, so it must be a declared dep."""
    assert distribution in _dev_dependencies(), (
        f"addopts uses a {distribution} flag but the package is not in "
        f"[tool.poetry.group.dev.dependencies]"
    )


@pytest.mark.parametrize("distribution,module", _required_plugins())
def test_addopts_plugins_are_installed(distribution: str, module: str):
    """Declared but unlocked/uninstalled fails the same way as undeclared."""
    assert importlib.util.find_spec(module) is not None, (
        f"{distribution} is declared but not importable — run `poetry install`"
    )


def test_html_report_is_still_requested():
    """Guards the test above from being trivially satisfied: if someone drops
    --html instead of adding the dep, the reports/ artifact CI uploads for
    every other project silently stops existing for eval."""
    assert "--html=" in _addopts()


def test_lockfile_pins_the_declared_plugins():
    lock = (SERVICE_DIR / "poetry.lock").read_text(encoding="utf-8")
    for distribution, _ in _required_plugins():
        assert f'name = "{distribution}"' in lock, f"{distribution} missing from poetry.lock"
