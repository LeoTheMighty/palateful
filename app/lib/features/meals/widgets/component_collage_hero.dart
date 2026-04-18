import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../models/meal.dart';

/// Collage hero for a Meal's components.
///
/// Layouts (from epic spec):
///   1 component : single full-bleed image + "1 of N" chip when some
///                 components are unavailable (legal only post-save —
///                 the sheet guards creation below 2).
///   2 components: split vertically (each 50% width).
///   3 components: left 50% full, right column split into 2.
///   4+ components: 2×2 grid; 4th cell gets "+N" overlay when total > 4.
///
/// Missing images render the same `Icons.restaurant` placeholder used
/// by `_RecipeCard`, so mixed-media meals (with/without images) look
/// cohesive.
class ComponentCollageHero extends StatelessWidget {
  final List<MealComponent> components;

  /// Aspect ratio of the outer box. Pass null to fill available height
  /// (e.g., inside a SliverAppBar's FlexibleSpaceBar).
  final double? aspectRatio;

  const ComponentCollageHero({
    super.key,
    required this.components,
    this.aspectRatio,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final total = components.length;
    final unavailable = components.where((c) => !c.available).length;
    final visible = components.take(4).toList();
    final overflow = total > 4 ? total - 4 : 0;

    Widget body;
    if (total == 0) {
      body = _placeholder(colorScheme);
    } else if (total == 1) {
      body = _cell(visible[0]);
    } else if (total == 2) {
      body = Row(
        children: [
          Expanded(child: _cell(visible[0])),
          const SizedBox(width: 2),
          Expanded(child: _cell(visible[1])),
        ],
      );
    } else if (total == 3) {
      body = Row(
        children: [
          Expanded(child: _cell(visible[0])),
          const SizedBox(width: 2),
          Expanded(
            child: Column(
              children: [
                Expanded(child: _cell(visible[1])),
                const SizedBox(height: 2),
                Expanded(child: _cell(visible[2])),
              ],
            ),
          ),
        ],
      );
    } else {
      body = Column(
        children: [
          Expanded(
            child: Row(
              children: [
                Expanded(child: _cell(visible[0])),
                const SizedBox(width: 2),
                Expanded(child: _cell(visible[1])),
              ],
            ),
          ),
          const SizedBox(height: 2),
          Expanded(
            child: Row(
              children: [
                Expanded(child: _cell(visible[2])),
                const SizedBox(width: 2),
                Expanded(
                  child: Stack(
                    children: [
                      Positioned.fill(child: _cell(visible[3])),
                      if (overflow > 0)
                        Positioned(
                          right: 8,
                          bottom: 8,
                          child: _OverlayChip(text: '+$overflow'),
                        ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      );
    }

    Widget wrapped = body;
    if (aspectRatio != null) {
      wrapped = AspectRatio(aspectRatio: aspectRatio!, child: body);
    }

    // Overlay "all unavailable" / "partial unavailable" chip on top-
    // right. "1 of N" when exactly one is available.
    final unavailableChip = _buildUnavailableChip(total, unavailable);
    if (unavailableChip == null) return wrapped;
    return Stack(
      children: [
        Positioned.fill(child: wrapped),
        Positioned(top: 8, right: 8, child: unavailableChip),
      ],
    );
  }

  Widget? _buildUnavailableChip(int total, int unavailable) {
    if (total == 0 || unavailable == 0) return null;
    if (unavailable == total) {
      return const _OverlayChip(text: 'All components unavailable');
    }
    final available = total - unavailable;
    return _OverlayChip(text: '$available of $total');
  }

  Widget _cell(MealComponent c) {
    if (!c.available) {
      return _UnavailableCell();
    }
    final url = c.imageUrl;
    if (url == null || url.isEmpty) {
      return const _PlaceholderCell();
    }
    return CachedNetworkImage(
      imageUrl: url,
      fit: BoxFit.cover,
      placeholder: (context, _) => const _PlaceholderCell(),
      errorWidget: (context, _, _) => const _PlaceholderCell(),
    );
  }

  Widget _placeholder(ColorScheme colorScheme) => Container(
        color: colorScheme.surfaceContainerHighest,
        child: Icon(
          Icons.restaurant,
          size: 48,
          color: colorScheme.onSurfaceVariant,
        ),
      );
}

class _OverlayChip extends StatelessWidget {
  final String text;
  const _OverlayChip({required this.text});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.65),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        text,
        style: const TextStyle(
          color: Colors.white,
          fontSize: 12,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

class _PlaceholderCell extends StatelessWidget {
  const _PlaceholderCell();
  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Container(
      color: colorScheme.surfaceContainerHighest,
      child: Icon(
        Icons.restaurant,
        size: 36,
        color: colorScheme.onSurfaceVariant,
      ),
    );
  }
}

class _UnavailableCell extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Container(
      color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.6),
      child: Center(
        child: Icon(
          Icons.hide_image_outlined,
          size: 32,
          color: colorScheme.outline,
        ),
      ),
    );
  }
}
