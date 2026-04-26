import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Compact list-row representation of a recipe (or meal, when the home
/// list mixes them). Renders thumbnail · title · books-pill · trailing
/// dynamic-column slot. Story 4 fills the trailing slot via
/// `dynamicColumnFor(SortKey)`; Story 3 leaves it as an opaque widget
/// passed in by the parent so the tile stays sort-agnostic.
class RecipeTableTile extends StatelessWidget {
  /// Raw recipe or meal map from the home/book payload. Maps are typed
  /// `dynamic` to match the surrounding code which historically uses
  /// untyped JSON-shaped maps.
  final dynamic item;
  final VoidCallback onTap;
  final VoidCallback? onLongPress;

  /// True while multi-select mode shows this row as selected; the tile
  /// dims and a checkmark replaces the chevron.
  final bool selected;

  /// Right-aligned trailing region. Story 4 renders the dynamic column
  /// here; pass `null` to render no trailing content (Story 3 default).
  final Widget? trailing;

  const RecipeTableTile({
    super.key,
    required this.item,
    required this.onTap,
    this.onLongPress,
    this.selected = false,
    this.trailing,
  });

  bool get _isMeal => item is Map && item['kind'] == 'meal';

  String? get _imageUrl {
    if (item is! Map) return null;
    if (_isMeal) {
      final urls = (item['component_image_urls'] as List?) ?? const [];
      if (urls.isEmpty) return null;
      final first = urls.first;
      return first is String ? first : null;
    }
    final url = item['image_url'];
    return url is String ? url : null;
  }

  String get _title => (item['name'] ?? 'Untitled').toString();

  String? get _bookName {
    if (item is! Map) return null;
    final v = item['recipe_book_name'];
    return v is String && v.isNotEmpty ? v : null;
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Material(
      color: selected
          ? colorScheme.primary.withValues(alpha: 0.12)
          : colorScheme.surface,
      child: InkWell(
        key: ValueKey('recipe_table_tile_${item['id']}'),
        onTap: () {
          HapticFeedback.selectionClick();
          onTap();
        },
        onLongPress: onLongPress == null
            ? null
            : () {
                HapticFeedback.mediumImpact();
                onLongPress!();
              },
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          child: Row(
            children: [
              _Thumbnail(imageUrl: _imageUrl, isMeal: _isMeal),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      _title,
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: colorScheme.onSurface,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    if (_bookName != null) ...[
                      const SizedBox(height: 4),
                      _BooksPill(name: _bookName!),
                    ],
                  ],
                ),
              ),
              if (trailing != null) ...[
                const SizedBox(width: 8),
                DefaultTextStyle.merge(
                  style: TextStyle(
                    fontSize: 13,
                    color: colorScheme.onSurfaceVariant,
                  ),
                  child: trailing!,
                ),
              ] else ...[
                const SizedBox(width: 4),
                Icon(
                  Icons.chevron_right,
                  size: 20,
                  color: colorScheme.onSurfaceVariant,
                ),
              ],
              if (selected)
                Padding(
                  padding: const EdgeInsets.only(left: 4),
                  child: Icon(
                    Icons.check_circle,
                    size: 20,
                    color: colorScheme.primary,
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Thumbnail extends StatelessWidget {
  final String? imageUrl;
  final bool isMeal;

  const _Thumbnail({required this.imageUrl, required this.isMeal});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return ClipRRect(
      borderRadius: BorderRadius.circular(6),
      child: SizedBox(
        height: 40,
        width: 40,
        child: imageUrl != null
            ? CachedNetworkImage(
                imageUrl: imageUrl!,
                fit: BoxFit.cover,
                placeholder: (_, _) => Container(
                  color: colorScheme.surfaceContainerHighest,
                ),
                errorWidget: (_, _, _) => _Placeholder(isMeal: isMeal),
              )
            : _Placeholder(isMeal: isMeal),
      ),
    );
  }
}

class _Placeholder extends StatelessWidget {
  final bool isMeal;
  const _Placeholder({required this.isMeal});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Container(
      color: colorScheme.surfaceContainerHighest,
      child: Icon(
        isMeal ? Icons.layers_outlined : Icons.restaurant,
        size: 20,
        color: colorScheme.onSurfaceVariant,
      ),
    );
  }
}

class _BooksPill extends StatelessWidget {
  final String name;
  const _BooksPill({required this.name});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        name,
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w500,
          color: colorScheme.onSurfaceVariant,
        ),
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      ),
    );
  }
}
