# Prompt Engineering Reference

This document captures the current state of recipe extraction prompts, what has been tested, and recommendations for each input type.

## Extraction Strategies

| Strategy | Input | Model | Description |
|---|---|---|---|
| `text_extractor` | OCR text | GPT-4o-mini | Raw text from OCR -> structured recipe JSON |
| `vision_extractor` | Image | GPT-4o-mini (vision) | Image -> structured recipe JSON directly |
| `ocr_then_text` | Image + sidecar | HunyuanOCR + GPT-4o-mini | OCR image first, then feed text through text_extractor |

## Text Extractor Prompt

**File:** `libraries/utils/utils/services/recipe_extractors/text_extractor.py`

### Design Decisions

1. **Explicit OCR artifact handling** -- The prompt enumerates common OCR failure modes (character substitutions like "f1our" for "flour", coordinate noise from bounding boxes, merged/split words) so the model knows what to expect and correct.

2. **Full JSON schema with examples** -- Instead of a minimal schema, the prompt includes every field with its expected type and an example value. This reduces ambiguity about what "quantity" means (a number, not a string like "1/2").

3. **Ingredient decomposition rules** -- Explicit instructions to separate quantity (as a number), unit (standard string), name (without prep notes), and notes (preparation details). Example: "1/2 cup diced onion, sauteed" should produce `quantity: 0.5, unit: "cup", name: "onion", notes: "diced, sauteed"`.

4. **Vibe assignment instructions** -- Vibes are requested inline with clear valid values and the rule that secondary_vibe should be null if no second vibe clearly applies.

5. **System message tuning** -- The system message specifically mentions OCR artifact correction and structured output, priming the model for the task.

### What Works Well

- `response_format: {"type": "json_object"}` eliminates markdown wrapping issues
- `temperature: 0.1` gives consistent, deterministic output
- Framing as "corrected original text" in the `text` field produces clean ingredient lines
- Listing specific OCR error patterns (digit-for-letter) improves correction accuracy

### Known Limitations

- Very noisy OCR text (>50% garbled) may still produce partial or incorrect recipes
- Mixed-language recipes may not be handled well
- max_tokens of 2000 may truncate very long recipes (>20 ingredients + lengthy instructions)

## Vision Extractor Prompt

**File:** `libraries/utils/utils/services/recipe_extractors/vision_extractor.py`

### Design Decisions

1. **Edge case enumeration** -- The prompt explicitly lists challenging image types (handwritten, blurry, partial, multiple recipes on a page) with instructions for each.

2. **Concrete ingredient examples** -- Three worked examples show the model exactly how to decompose different ingredient formats (count items, measured items, "to taste" items).

3. **Same schema as text extractor** -- Both extractors produce identical JSON structure, making comparison straightforward in the eval framework.

4. **High detail mode** -- `detail: "high"` is used for the image to maximize OCR quality from the vision model.

5. **max_tokens: 4096** -- Higher token budget than text extractor because the model must both read the image and produce structured output.

### What Works Well

- GPT-4o-mini vision handles printed recipe cards and cookbook pages accurately
- Worked ingredient examples significantly reduce formatting inconsistencies
- High detail mode catches small text and fine print

### Known Limitations

- Handwritten recipes are hit-or-miss depending on handwriting clarity
- Very small text in large images may be missed even with high detail
- Cost is higher than text extraction due to image token overhead
- Cannot handle multi-page recipes (only single images)

## OCR-Then-Text Strategy

**File (strategy):** `services/eval/src/strategies.py`

This is an eval-only strategy that simulates the production pipeline:
1. HunyuanOCR extracts raw text from an image
2. The raw text is fed through the text extractor

For eval, step 1 is replaced by reading a pre-extracted `.ocr.txt` sidecar file placed alongside the image fixture.

### When to Use

- To compare the quality of "OCR + text extraction" vs "direct vision extraction"
- To evaluate how well the text extractor handles real OCR output (with all its artifacts)
- To benchmark pipeline improvements without running the parser service

### Sidecar Convention

For `fixtures/images/potato_quiche.jpg`, create `fixtures/images/potato_quiche.ocr.txt` containing the raw HunyuanOCR output.

## Recommendations by Input Type

### Printed recipes (cookbook pages, cards)
- **Best strategy:** `vision_extractor` -- direct vision produces the most accurate results since the model can see layout, formatting, and context simultaneously
- **Alternative:** `ocr_then_text` works well for clean printed text but loses layout context

### Handwritten recipes
- **Best strategy:** `vision_extractor` -- the vision model handles varied handwriting better than OCR engines
- **Caution:** Results vary significantly with handwriting quality

### Screenshots and digital text
- **Best strategy:** `text_extractor` if text is already available; `vision_extractor` for screenshots
- Both strategies perform well on clean digital text

### Noisy or low-quality photos
- **Best strategy:** `vision_extractor` with high detail mode
- **Fallback:** If vision fails, OCR-then-text may extract partial content

## Prompt Iteration Guide

When modifying prompts:

1. **Run the eval suite first** to establish a baseline:
   ```bash
   npx nx run eval:run-fixtures -- --strategy text_extractor
   ```

2. **Make one change at a time** and re-run to measure impact

3. **Add failing fixtures** for any new edge case before modifying the prompt

4. **Compare strategies** to see relative impact:
   ```bash
   npx nx run eval:run-fixtures -- --compare text_extractor,vision_extractor,ocr_then_text
   ```

5. **Key metrics to watch:**
   - `ingredients_precision` -- are all extracted ingredients correct?
   - `ingredients_recall` -- are all expected ingredients found?
   - `amounts_accuracy` -- are quantities and units parsed correctly?
   - `overall_f1` -- balanced aggregate score
