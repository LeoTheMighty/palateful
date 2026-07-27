"""Fixture/manifest consistency for the vision eval suite (bugs-imp-pho-7).

These tests never call OpenAI — they guard the *dataset*, so a broken
fixture pair is caught in CI instead of burning a live vision run.
"""

import functools
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml
from PIL import Image, ImageFont

SERVICE_DIR = Path(__file__).resolve().parent.parent
MANIFEST_PATH = SERVICE_DIR / "datasets" / "vision_extraction" / "manifest.yaml"
SUITE_DIR = MANIFEST_PATH.parent
IMAGE_DIR = SERVICE_DIR / "fixtures" / "images"


@functools.cache
def _load_generator():
    """Import scripts/generate_image_fixtures.py without making it a package.

    The module must land in ``sys.modules`` *before* exec: it defines a
    dataclass, and ``dataclasses`` resolves annotations by looking the
    defining module up there.
    """
    name = "generate_image_fixtures"
    path = SERVICE_DIR / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MANIFEST = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
CASES = MANIFEST["cases"]
CASE_IDS = [c["id"] for c in CASES]


def _expected_recipe_count(case: dict) -> int:
    expected = json.loads((SUITE_DIR / case["expected"]).read_text(encoding="utf-8"))
    recipes = expected.get("recipes")
    return len(recipes) if isinstance(recipes, list) else 1


# ---------- manifest <-> filesystem ----------


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_case_files_exist(case):
    assert (SUITE_DIR / case["image"]).is_file(), f"missing image for {case['id']}"
    assert (SUITE_DIR / case["expected"]).is_file(), f"missing expected for {case['id']}"


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_image_is_readable_and_large_enough(case):
    """A truncated or thumbnail-sized fixture would silently tank the suite."""
    with Image.open(SUITE_DIR / case["image"]) as img:
        img.verify()
    with Image.open(SUITE_DIR / case["image"]) as img:
        assert img.width >= 600 and img.height >= 400, f"{case['id']} is too small to read"


def test_no_orphan_images():
    """Every PNG in fixtures/images/ is claimed by the manifest."""
    on_disk = {p.name for p in IMAGE_DIR.glob("*.png")}
    in_manifest = {Path(c["image"]).name for c in CASES}
    assert on_disk == in_manifest


# ---------- tags <-> ground truth ----------


def test_suite_covers_both_single_and_multi_recipe():
    tags = [set(c.get("tags", [])) for c in CASES]
    assert any("single_recipe" in t for t in tags)
    assert any("multi_recipe" in t for t in tags)


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_tag_matches_expected_recipe_count(case):
    """`multi_recipe` must mean N>=2 — the tag drives the 0.8 count gate, so a
    mislabelled single-recipe case would quietly dilute it."""
    n = _expected_recipe_count(case)
    tags = case.get("tags", [])
    if "multi_recipe" in tags:
        assert n >= 2, f"{case['id']} tagged multi_recipe but expects {n} recipe(s)"
    if "single_recipe" in tags:
        assert n == 1, f"{case['id']} tagged single_recipe but expects {n} recipes"


# ---------- generator <-> manifest ----------


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_every_case_is_regenerable(case):
    """Each fixture must have a LAYOUTS entry, else it can't be rebuilt when
    its source text changes."""
    generator = _load_generator()
    layout = generator.LAYOUTS.get(case["id"])
    assert layout is not None, f"no LAYOUTS entry for {case['id']}"
    assert (generator.TEXT_DIR / layout.source).is_file()
    assert set(layout.tags) <= set(case.get("tags", []))


def test_generator_section_count_matches_expected_recipe_count():
    """The renderer must lay out exactly as many recipe blocks as the ground
    truth claims — otherwise the image and its expected JSON disagree."""
    generator = _load_generator()
    for case in CASES:
        layout = generator.LAYOUTS[case["id"]]
        source = (generator.TEXT_DIR / layout.source).read_text(encoding="utf-8")
        sections = generator._split_sections(source, layout.separator)
        assert len(sections) == _expected_recipe_count(case), case["id"]


def test_missing_glyph_guard_flags_uncovered_characters():
    """The fixtures contain `jalapeño`; Pillow's bundled face has no `ñ` and
    would render a tofu box, corrupting the ground truth silently."""
    generator = _load_generator()
    bundled = ImageFont.load_default(size=generator.BODY_SIZE)
    assert generator._missing_glyphs(bundled, "jalapeño") == {"ñ"}
    assert generator._missing_glyphs(bundled, "jalapeno") == set()
