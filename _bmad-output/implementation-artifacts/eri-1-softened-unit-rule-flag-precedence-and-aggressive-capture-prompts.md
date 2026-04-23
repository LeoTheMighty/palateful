# Story eri-1 — Softened unit rule + flag precedence + aggressive-capture prompts

**Status:** done
**Epic:** epic-extractor-richer-ingredients
**Branch:** main

## Goal

Relax the riip-3 "use EXACTLY one of these 19 tokens" rule so the LLM
stops folding accurate unit words (`clove`, `stalk`, `bunch`, `head`,
`can`, etc.) into the ingredient `name` field. Keep the 19 canonical
tokens as the *preferred* hint, allow a pinned freeform-allowed list
for words the source uses literally, and bias toward convertible units
(`cup`, `tbsp`, `tsp`, `ml`, `l`, `g`, `kg`, `oz`, `lb`, `fl oz`) when
the choice is ambiguous. Per-extractor prompts also get aggressive
qty/unit/notes capture instructions plus worked examples for the
historically-broken cases (clove, stalk, gram, range, substring).

## Acceptance Criteria — status

| AC | Description | Status |
|----|-------------|--------|
| AC1 | `_SOFTENED_RULE` lives in `unit_prompt.py`; lists 19 canonical tokens as preferred + 15 freeform-allowed words + convertible-unit bias | ✅ Done |
| AC2 | `EXTRACTOR_SOFTEN_UNIT_RULE` flag (default on) read at call time via `soften_unit_rule()` | ✅ Done |
| AC3 | `unit_rule()` precedence: SOFTEN > CANONICAL > freeform (coded, not implied) | ✅ Done |
| AC4 | 4-case matrix test in `test_unit_prompt_precedence.py` — both on, SOFTEN-only, CANONICAL-only, both-off | ✅ Done |
| AC5 | `ai_extractor.py`, `vision_extractor.py`, `text_extractor.py` each gain aggressive-capture language + worked examples for clove/stalk/gram | ✅ Done |
| AC6 | Range example (`"1-2 cups water"` → q=1, notes="to 2 cups") in all three prompts | ✅ Done |
| AC7 | Substring example (`"a pinchful of salt"` → unit: null, notes: "pinchful") in all three prompts | ✅ Done |
| AC8 | "Do not hallucinate notes" rule explicit in all three prompts | ✅ Done |
| AC9 | Flutter grep confirms no client-side enum-validation rejects non-canonical units on save | ✅ Done (no such check exists; `_shouldOfferCustom` only decides whether to offer the custom-picker chip) |
| AC10 | Existing riip-3 test suite (`test_extractor_unit_prompt.py`) stays green under the new default (SOFTEN on) via updated fixtures | ✅ Done |

## File List

### New
- `libraries/utils/test/test_unit_prompt_precedence.py` — 4-case matrix + default-unset + call-time-read + softened-rule-content tests

### Modified
- `libraries/utils/utils/services/recipe_extractors/unit_prompt.py`
  - Added `_SOFTENED_RULE`, `_CONVERTIBLE_UNITS`, `_FREEFORM_ALLOWED`
  - Added `soften_unit_rule()` (reads `EXTRACTOR_SOFTEN_UNIT_RULE`, default on)
  - Rewrote `unit_rule()` to implement SOFTEN > CANONICAL > freeform precedence
  - `_CANONICAL_RULE` preserved verbatim for rollback
- `libraries/utils/utils/services/recipe_extractors/ai_extractor.py`
  - Aggressive-capture paragraph above ingredient rules
  - "Do not hallucinate notes" on the notes rule
  - 6 new worked examples: clove, stalk, gram, range, pinchful, 2-cups-flour
- `libraries/utils/utils/services/recipe_extractors/vision_extractor.py` — same three additions
- `libraries/utils/utils/services/recipe_extractors/text_extractor.py` — same three additions
- `libraries/utils/test/test_extractor_unit_prompt.py`
  - `flag_off` / `flag_on` fixtures now set BOTH env vars so existing
    CANONICAL-vs-freeform assertions test the intended path unshadowed
    by SOFTEN's new default-on

## Flag precedence matrix

| `EXTRACTOR_SOFTEN_UNIT_RULE` | `EXTRACTOR_EMIT_CANONICAL_UNITS` | Rule emitted |
|---|---|---|
| on (default) | * | `_SOFTENED_RULE` |
| off | on (default) | `_CANONICAL_RULE` |
| off | off | `freeform_fallback` (per-extractor legacy) |

## Implementation notes

- **Prompt vocabulary ≠ data-model vocabulary.** The 19-token
  `CANONICAL_UNIT_TOKENS` is still the hint list. The 15
  `_FREEFORM_ALLOWED` words are what we explicitly enumerate so the
  LLM knows they are acceptable; these words will be seeded into the
  `units` table by eri-4a so the downstream FK stays intact.
- **Range rule:** `"1-2 cups"` → `quantity=1, notes="to 2 cups"`. The
  first value is the safe lower bound; the full range is captured in
  notes for reviewer context.
- **Substring rule:** `"a pinchful of salt"` must NOT coerce to
  `unit: "pinch"`. Prompt now calls this out explicitly: "Respect
  word boundaries for units: 'a pinchful' is NOT 'pinch'".
- **Anti-hallucination:** notes MUST be null when the source has no
  qualifier. The `"2 cups flour"` worked example pins this.
- **Flutter AC9:** grep for `kCuratedUnits`, `CANONICAL_UNITS`,
  `assert.*unit`, `throw.*unit` across `app/lib/` — only `kCuratedUnits`
  appears, and it drives dropdown filtering + `_shouldOfferCustom`, not
  save-blocking validation. `SessionAliasMap.coerce` on blur coerces
  plurals/full-words but lets freeform values through. Belt-and-
  suspenders guard confirmed — no change needed.

## Verification

- `npx nx run utils:test` — 480 passed
- `npx nx run utils:lint` — all checks passed
- `npx nx run api:lint` — all checks passed
- `npx nx run api:test` — 2257 passed, coverage 100%
