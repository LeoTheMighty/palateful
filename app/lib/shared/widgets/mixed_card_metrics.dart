/// Uniform geometry for the mixed recipe + meal card grids (rbv101).
///
/// Recipe cards and meal tiles are interleaved in the same grid on the
/// book-detail screen and on home. Before rbv101 each tile sized itself
/// to its own content, so a meal (name + description + chip line) and a
/// recipe (name + metadata chips + tag chips) rendered at different
/// heights whenever the layout let children pick their own extent —
/// most visibly the single-column phone layout on book detail, which
/// stacked the cards in a plain `Column`.
///
/// Both card widgets now size the same way: a fixed [kMixedCardHeroHeight]
/// hero plus an info block that *fills whatever height the parent gives
/// it*, falling back to [kMixedCardInfoHeight] only when the parent
/// leaves the height unbounded. So two cards in the same grid always
/// match, whatever their content — and a card dropped into a plain
/// `Column` still picks the same default height as its neighbour.
///
/// The book-detail grid pins its cells to [kMixedCardExtent] so the
/// bounded and unbounded cases agree. Home keeps its own aspect-ratio
/// delegate (its `RecipeCard` has an aspect-ratio hero that a fixed
/// extent would overflow at wide widths) — the fill-the-box behaviour
/// is what keeps meals and recipes uniform there.
library;

/// Height of the hero/collage area at the top of every mixed card.
const double kMixedCardHeroHeight = 180;

/// Height of the text block under the hero. Fixed so meals and recipes
/// agree even though their content differs. Content taller than this is
/// clipped rather than overflowing (see the cards' info sections).
///
/// Sized off the taller of the two: a recipe with a name, all three
/// metadata chips and a tag row needs 116pt of content plus the 12pt
/// bottom padding. A meal (name + description + chip line) needs ~90pt
/// and simply gets trailing whitespace. Shrinking this silently clips
/// recipe tags — `book_card_sizing_test.dart` pins the arithmetic.
const double kMixedCardInfoHeight = 128;

/// Bottom margin baked into each card, so consecutive cards in a plain
/// `Column` still get breathing room.
const double kMixedCardBottomMargin = 12;

/// Total intrinsic height of a mixed card, margin included.
const double kMixedCardHeight =
    kMixedCardHeroHeight + kMixedCardInfoHeight + kMixedCardBottomMargin;

/// Main-axis extent a grid must give each mixed card. Identical to
/// [kMixedCardHeight] — named separately because it is a layout knob,
/// not a widget-internal one.
const double kMixedCardExtent = kMixedCardHeight;
