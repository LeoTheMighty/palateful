# Story 13.7: Prompt Optimization

## Status: Complete

## What Was Done

### 1. Wired Vision Extractor into Eval Strategies
**File:** `services/eval/src/strategies.py`

- Replaced the `run_vision_extraction` stub with a working implementation that:
  - Loads the image from disk using PIL
  - Calls `extract_recipe_from_image` from the production vision extractor
  - Converts the result to a dict via `_recipe_to_dict`
  - Supports optional `openai_client` kwarg for testing
  - Raises `FileNotFoundError` for missing images, `RuntimeError` for extraction failures

### 2. Wired OCR-Then-Text Strategy
**File:** `services/eval/src/strategies.py`

- Replaced the `run_ocr_then_text` stub with a sidecar-based implementation that:
  - Looks for a `.ocr.txt` sidecar file next to the image (e.g. `potato_quiche.ocr.txt` for `potato_quiche.jpg`)
  - Reads the pre-extracted OCR text from the sidecar
  - Feeds it through the production `extract_recipe_from_text`
  - Raises `FileNotFoundError` with a helpful message if the sidecar is missing
  - Enables eval comparison of "OCR raw text -> GPT-4o-mini" vs "GPT-4o-mini vision direct" without running the parser service

### 3. Optimized Text Extractor Prompt
**File:** `libraries/utils/utils/services/recipe_extractors/text_extractor.py`

Changes to the prompt:
- **Explicit OCR artifact catalog:** enumerates character substitutions, coordinate noise, line break issues, garbled text, and extraneous headers/footers
- **Full JSON schema with types:** every field has an example value and expected type, eliminating ambiguity
- **Detailed ingredient format spec:** explicit rules for text (corrected original), quantity (as number with fraction conversion), unit (standard strings), name (without prep notes), notes (preparation details), is_optional
- **Vibe assignment section:** dedicated block with valid values and null-when-uncertain guidance
- **Null over guessing:** explicit instruction to set missing fields to null rather than fabricating values
- **total_time_minutes added:** included in the schema for consistency with the data model
- **System message enhanced:** mentions OCR artifact correction and structured output specifically

### 4. Optimized Vision Extractor Prompt
**File:** `libraries/utils/utils/services/recipe_extractors/vision_extractor.py`

Changes to the prompt:
- **Edge case handling section:** explicit guidance for handwritten text, partial/cropped images, blurry photos, multiple recipes on a page, decorative fonts and watermarks
- **Three worked ingredient examples:** shows exact decomposition for count items ("3 large eggs"), measured items ("1/2 cup diced onion"), and informal amounts ("salt to taste")
- **Same schema structure as text extractor:** both extractors now produce identical JSON shape for clean eval comparison
- **Ingredient decomposition rules:** same detailed spec as text extractor for consistency
- **Dedicated vibe section:** matching format with text extractor
- **System message enhanced:** mentions handling printed text, handwritten notes, and low-quality photos

### 5. Documented Prompt Best Practices
**File:** `services/eval/PROMPTS.md`

Created comprehensive documentation covering:
- All three extraction strategies with descriptions
- Design decisions and rationale for each prompt
- What works well and known limitations
- Recommendations by input type (printed, handwritten, screenshots, noisy photos)
- Prompt iteration guide with eval workflow

## Design Decisions

- **Sidecar pattern for OCR-then-text:** Rather than requiring the parser service for eval, we use `.ocr.txt` files placed next to image fixtures. This keeps the eval suite self-contained and runnable without GPU infrastructure.
- **Identical schema across extractors:** Both text and vision prompts now request the exact same JSON structure, making it straightforward to score and compare outputs.
- **Explicit over implicit:** Both prompts now enumerate edge cases and provide worked examples rather than relying on the model to infer formatting rules.
- **Null over fabrication:** Both prompts instruct the model to use null for missing fields rather than guessing, which improves precision at the cost of recall.

## Files Changed

| File | Change |
|---|---|
| `services/eval/src/strategies.py` | Wired vision_extractor and ocr_then_text stubs |
| `libraries/utils/utils/services/recipe_extractors/text_extractor.py` | Optimized prompt and system message |
| `libraries/utils/utils/services/recipe_extractors/vision_extractor.py` | Optimized prompt and system message |
| `services/eval/PROMPTS.md` | New -- prompt documentation and best practices |
