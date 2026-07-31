import 'package:flutter/widgets.dart';

import 'mixed_card_metrics.dart';

/// Shared body layout for the mixed recipe/meal cards (rbv101): a
/// fixed-height hero with an info block underneath.
///
/// The info block **fills whatever height the parent gives the card**,
/// and falls back to [kMixedCardInfoHeight] when the parent leaves the
/// height unbounded. That single rule is what makes meals and recipes
/// come out the same size: in a grid both cards stretch to the cell, and
/// in a plain `Column` both pick the same default — instead of each one
/// sizing to its own text.
///
/// The info block is clipped rather than allowed to overflow, so a card
/// squeezed into a short cell trims its trailing content instead of
/// throwing a `RenderFlex` overflow.
class MixedCardBody extends StatelessWidget {
  /// Hero/collage area. Always [kMixedCardHeroHeight] tall.
  final Widget hero;

  /// Text block under the hero.
  final Widget info;

  const MixedCardBody({super.key, required this.hero, required this.info});

  @override
  Widget build(BuildContext context) {
    final clippedInfo = ClipRect(
      child: OverflowBox(
        alignment: Alignment.topLeft,
        maxHeight: double.infinity,
        child: info,
      ),
    );

    return LayoutBuilder(
      builder: (context, constraints) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            height: kMixedCardHeroHeight,
            width: double.infinity,
            child: hero,
          ),
          if (constraints.maxHeight.isFinite)
            Expanded(
              child: SizedBox(width: double.infinity, child: clippedInfo),
            )
          else
            SizedBox(
              height: kMixedCardInfoHeight,
              width: double.infinity,
              child: clippedInfo,
            ),
        ],
      ),
    );
  }
}
