"""Render the text fixtures into image fixtures for the vision eval suite.

The vision extractor (`extract_recipe_from_image`) needs *image* inputs, but
authoring photographs by hand is neither reproducible nor reviewable in a
diff. Instead we render the existing `fixtures/text/*.txt` sources into
page-like PNGs, so an image fixture and its text twin describe exactly the
same recipe(s) and share one `fixtures/expected/<stem>.json` ground truth.
That makes `--compare text_extractor,vision_extractor` an apples-to-apples
modality comparison rather than two unrelated datasets.

The generated PNGs are committed. This script only needs to run when a
fixture is added or its source text changes:

    poetry run python scripts/generate_image_fixtures.py            # all
    poetry run python scripts/generate_image_fixtures.py banana_bread

Fonts: the first face in `FONT_CANDIDATES` that exists on the machine wins;
pass `--font /path/to/font.ttf` to pin one. Coverage is asserted before
anything is written — Pillow's bundled Aileron has no `ñ`, and silently
rendering `jalape<tofu>o` would corrupt the ground truth the expected JSON
promises, so a missing glyph is a hard error rather than a warning.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
TEXT_DIR = FIXTURES_DIR / "text"
IMAGE_DIR = FIXTURES_DIR / "images"

# Layout geometry (pixels).
COLUMN_WIDTH = 620
COLUMN_PADDING = 44
GUTTER = 56
MARGIN = 48
TITLE_SIZE = 34
BODY_SIZE = 22
TITLE_GAP = 22
LINE_GAP = 9
BLANK_LINE_HEIGHT = 14

# Palette — deliberately low-contrast-free: dark ink on light paper, the
# easy case for OCR. Fixture difficulty lives in the *layout* (how many
# recipes share a page), not in image quality.
INK = (32, 30, 28)
PAPER = (252, 250, 245)
CARD = (255, 255, 255)
BACKDROP = (226, 222, 214)
RULE = (196, 190, 180)

# Faces tried in order. All of these cover Latin-1 (the fixtures contain
# `jalapeño`); Pillow's bundled Aileron does not, so it is only reached as a
# last resort and the coverage check below will reject it.
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
]


@dataclass
class Layout:
    """How one fixture stem is rendered."""

    source: str
    style: str  # page | facing_pages | cards_row | panels_row
    separator: str | None = None
    tags: list[str] = field(default_factory=list)


# Stems match `fixtures/text/<stem>.txt` and `fixtures/expected/<stem>.json`.
LAYOUTS: dict[str, Layout] = {
    "banana_bread": Layout(
        source="banana_bread.txt",
        style="page",
        tags=["single_recipe"],
    ),
    "simple_pasta": Layout(
        source="simple_pasta.txt",
        style="page",
        tags=["single_recipe"],
    ),
    "multi_recipe_facing_pages": Layout(
        source="multi_recipe_facing_pages.txt",
        style="facing_pages",
        separator="-----",
        tags=["multi_recipe"],
    ),
    "multi_recipe_side_by_side": Layout(
        source="multi_recipe_side_by_side.txt",
        style="cards_row",
        separator="=====",
        tags=["multi_recipe"],
    ),
    "multi_recipe_three_panel": Layout(
        source="multi_recipe_three_panel.txt",
        style="panels_row",
        separator="***",
        tags=["multi_recipe"],
    ),
}


# ---------------------------------------------------------------------------
# Text preparation
# ---------------------------------------------------------------------------

def _split_sections(text: str, separator: str | None) -> list[list[str]]:
    """Split source text into per-recipe sections of raw lines."""
    if separator is None:
        return [text.strip().splitlines()]

    sections: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.strip() == separator:
            sections.append(current)
            current = []
        else:
            current.append(line)
    sections.append(current)

    # Drop leading/trailing blank lines in each section.
    cleaned = []
    for section in sections:
        while section and not section[0].strip():
            section.pop(0)
        while section and not section[-1].strip():
            section.pop()
        if section:
            cleaned.append(section)
    return cleaned


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    """Greedy word wrap against measured pixel width."""
    words = text.split()
    if not words:
        return [""]

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _resolve_font_path(font_path: str | None) -> str | None:
    """Pick the font face to render with. ``None`` means Pillow's bundled one."""
    if font_path:
        return font_path
    for candidate in FONT_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    return None


def _load_fonts(font_path: str | None) -> tuple[object, object]:
    if font_path:
        return (
            ImageFont.truetype(font_path, TITLE_SIZE),
            ImageFont.truetype(font_path, BODY_SIZE),
        )
    return (
        ImageFont.load_default(size=TITLE_SIZE),
        ImageFont.load_default(size=BODY_SIZE),
    )


def _missing_glyphs(font, text: str) -> set[str]:
    """Characters in *text* the face renders as `.notdef` (the tofu box).

    Detected by rendering U+E000 — a private-use codepoint no real face
    defines — and byte-comparing each candidate glyph's bitmap against it.
    """
    def bitmap(ch: str) -> bytes:
        canvas = Image.new("L", (4 * TITLE_SIZE, 4 * TITLE_SIZE), 0)
        ImageDraw.Draw(canvas).text((TITLE_SIZE, TITLE_SIZE), ch, font=font, fill=255)
        return canvas.tobytes()

    tofu = bitmap(chr(0xE000))
    return {ch for ch in set(text) if not ch.isspace() and bitmap(ch) == tofu}


def _measure_column(
    draw: ImageDraw.ImageDraw,
    section: list[str],
    title_font,
    body_font,
    text_width: int,
) -> int:
    """Height in pixels the rendered column will occupy."""
    return _draw_column(draw, section, title_font, body_font, 0, 0, text_width, dry_run=True)


def _draw_column(
    draw: ImageDraw.ImageDraw,
    section: list[str],
    title_font,
    body_font,
    x: int,
    y: int,
    text_width: int,
    dry_run: bool = False,
) -> int:
    """Draw one recipe section; return the height consumed."""
    cursor = y
    title_drawn = False

    for raw_line in section:
        stripped = raw_line.strip()

        if not stripped:
            cursor += BLANK_LINE_HEIGHT
            continue

        if not title_drawn:
            for line in _wrap(draw, stripped, title_font, text_width):
                if not dry_run:
                    draw.text((x, cursor), line, font=title_font, fill=INK)
                cursor += TITLE_SIZE + LINE_GAP
            cursor += TITLE_GAP
            title_drawn = True
            continue

        for line in _wrap(draw, stripped, body_font, text_width):
            if not dry_run:
                draw.text((x, cursor), line, font=body_font, fill=INK)
            cursor += BODY_SIZE + LINE_GAP

    return cursor - y


def render(stem: str, layout: Layout, font_path: str | None) -> Image.Image:
    """Render one fixture stem to a PIL image."""
    source_path = TEXT_DIR / layout.source
    if not source_path.is_file():
        raise FileNotFoundError(f"Source text not found: {source_path}")

    source_text = source_path.read_text(encoding="utf-8")
    sections = _split_sections(source_text, layout.separator)
    if not sections:
        raise ValueError(f"No sections parsed from {source_path}")

    resolved_font = _resolve_font_path(font_path)
    title_font, body_font = _load_fonts(resolved_font)

    missing = _missing_glyphs(body_font, source_text)
    if missing:
        raise RuntimeError(
            f"Font {resolved_font or '(Pillow bundled)'} cannot render "
            f"{sorted(missing)} from {source_path.name}. Rendering anyway would "
            f"put tofu boxes in the fixture and silently break its expected JSON. "
            f"Pass --font with a Latin-1-capable face."
        )

    # Measure against a throwaway canvas so we can size the real one exactly.
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    text_width = COLUMN_WIDTH - 2 * COLUMN_PADDING
    heights = [
        _measure_column(probe, section, title_font, body_font, text_width)
        for section in sections
    ]

    n = len(sections)
    gutter = GUTTER if layout.style != "page" else 0
    width = 2 * MARGIN + n * COLUMN_WIDTH + max(0, n - 1) * gutter
    body_height = max(heights) + 2 * COLUMN_PADDING
    height = 2 * MARGIN + body_height

    background = PAPER if layout.style in ("page", "facing_pages") else BACKDROP
    image = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(image)

    for i, section in enumerate(sections):
        col_x = MARGIN + i * (COLUMN_WIDTH + gutter)
        col_box = (col_x, MARGIN, col_x + COLUMN_WIDTH, MARGIN + body_height)

        if layout.style == "cards_row":
            draw.rounded_rectangle(col_box, radius=18, fill=CARD, outline=RULE, width=2)
        elif layout.style == "panels_row":
            draw.rectangle(col_box, fill=CARD)
            if i > 0:
                rule_x = col_x - gutter // 2
                draw.line(
                    [(rule_x, MARGIN), (rule_x, MARGIN + body_height)],
                    fill=RULE,
                    width=2,
                )
        elif layout.style == "facing_pages" and i > 0:
            # Page gutter: the visual cue that these are two separate pages.
            gutter_x = col_x - gutter // 2
            draw.line(
                [(gutter_x, MARGIN // 2), (gutter_x, height - MARGIN // 2)],
                fill=RULE,
                width=3,
            )

        _draw_column(
            draw,
            section,
            title_font,
            body_font,
            col_x + COLUMN_PADDING,
            MARGIN + COLUMN_PADDING,
            text_width,
        )

    return image


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "stems",
        nargs="*",
        help="Fixture stems to regenerate (default: all).",
    )
    parser.add_argument(
        "--font",
        default=None,
        help="Path to a .ttf face (default: Pillow's bundled font).",
    )
    parser.add_argument(
        "--out-dir",
        default=str(IMAGE_DIR),
        help="Output directory (default: fixtures/images).",
    )
    args = parser.parse_args(argv)

    stems = args.stems or sorted(LAYOUTS)
    unknown = [s for s in stems if s not in LAYOUTS]
    if unknown:
        print(f"Unknown fixture stems: {unknown}", file=sys.stderr)
        print(f"Available: {sorted(LAYOUTS)}", file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for stem in stems:
        image = render(stem, LAYOUTS[stem], args.font)
        out_path = out_dir / f"{stem}.png"
        image.save(out_path, format="PNG", optimize=True)
        print(f"wrote {out_path} ({image.width}x{image.height})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
