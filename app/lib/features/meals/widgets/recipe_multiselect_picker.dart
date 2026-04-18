import 'dart:async';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';

/// Lightweight payload returned from the picker. Mirrors the subset of
/// fields [CreateMealSheet] and [MealEditScreen] need to render a
/// component preview without a follow-up fetch.
class PickedRecipe {
  final String id;
  final String name;
  final String? imageUrl;
  final String? bookId;
  final String? bookName;

  const PickedRecipe({
    required this.id,
    required this.name,
    this.imageUrl,
    this.bookId,
    this.bookName,
  });
}

/// Modal bottom sheet that lets the user pick 2+ recipes for a new
/// Meal (mcv-5) or add a recipe to an existing Meal (mcv-6).
///
/// Defaults to the [bookId]'s recipe list; as soon as the user types,
/// swaps to `/v1/search?scope=recipes` for a cross-book search.
///
/// Returns via [Navigator.pop] with the selected [PickedRecipe] list
/// (empty if cancelled).
class RecipeMultiselectPicker extends StatefulWidget {
  final String bookId;
  final String bookName;

  /// Recipes already attached to a Meal — render with an "Added"
  /// badge and disabled tap. Used by mcv-6's Add-Recipe flow.
  final Set<String> alreadySelectedIds;

  /// Initial selection (for resuming the picker with existing draft
  /// components). Defaults to empty.
  final Set<String> initiallyPickedIds;

  const RecipeMultiselectPicker({
    super.key,
    required this.bookId,
    required this.bookName,
    this.alreadySelectedIds = const {},
    this.initiallyPickedIds = const {},
  });

  static Future<List<PickedRecipe>> show(
    BuildContext context, {
    required String bookId,
    required String bookName,
    Set<String> alreadySelectedIds = const {},
    Set<String> initiallyPickedIds = const {},
  }) async {
    final picked = await showModalBottomSheet<List<PickedRecipe>>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (ctx) => SizedBox(
        height: MediaQuery.of(ctx).size.height * 0.85,
        child: RecipeMultiselectPicker(
          bookId: bookId,
          bookName: bookName,
          alreadySelectedIds: alreadySelectedIds,
          initiallyPickedIds: initiallyPickedIds,
        ),
      ),
    );
    return picked ?? const [];
  }

  @override
  State<RecipeMultiselectPicker> createState() =>
      _RecipeMultiselectPickerState();
}

class _RecipeMultiselectPickerState extends State<RecipeMultiselectPicker> {
  final _apiClient = getIt<ApiClient>();
  final _queryController = TextEditingController();
  Timer? _debounce;

  List<PickedRecipe> _results = const [];
  final Map<String, PickedRecipe> _pickedById = {};
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    for (final id in widget.initiallyPickedIds) {
      _pickedById[id] = PickedRecipe(id: id, name: '');
    }
    _queryController.addListener(_onQueryChanged);
    unawaited(_loadBookRecipes());
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _queryController.dispose();
    super.dispose();
  }

  void _onQueryChanged() {
    _debounce?.cancel();
    final text = _queryController.text.trim();
    if (text.isEmpty) {
      unawaited(_loadBookRecipes());
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 250), () {
      unawaited(_runSearch(text));
    });
  }

  Future<void> _loadBookRecipes() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final response = await _apiClient.getRecipes(widget.bookId, limit: 100);
      final data = response.data;
      final List raw;
      if (data is List) {
        raw = data;
      } else if (data is Map<String, dynamic>) {
        raw = (data['recipes'] as List?) ?? (data['items'] as List?) ?? const [];
      } else {
        raw = const [];
      }
      if (!mounted) return;
      setState(() {
        _results = raw
            .whereType<Map<String, dynamic>>()
            .map(
              (r) => PickedRecipe(
                id: r['id'] as String,
                name: r['name'] as String? ?? 'Untitled',
                imageUrl: r['image_url'] as String?,
                bookId: widget.bookId,
                bookName: widget.bookName,
              ),
            )
            .toList();
        _isLoading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Could not load recipes. Please try again.';
        _isLoading = false;
      });
    }
  }

  Future<void> _runSearch(String query) async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final response =
          await _apiClient.search(query, scope: 'recipes', limit: 50);
      final data = response.data as Map<String, dynamic>? ?? const {};
      final raw = (data['my_recipes'] as List?) ?? const [];
      if (!mounted) return;
      setState(() {
        _results = raw.whereType<Map<String, dynamic>>().map((r) {
          return PickedRecipe(
            id: r['id'] as String,
            name: r['name'] as String? ?? 'Untitled',
            imageUrl: r['image_url'] as String?,
            bookId: r['recipe_book_id'] as String?,
            bookName: r['recipe_book_name'] as String?,
          );
        }).toList();
        _isLoading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Search failed. Please try again.';
        _isLoading = false;
      });
    }
  }

  void _toggle(PickedRecipe r) {
    if (widget.alreadySelectedIds.contains(r.id)) return;
    setState(() {
      if (_pickedById.containsKey(r.id)) {
        _pickedById.remove(r.id);
      } else {
        _pickedById[r.id] = r;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final pickedCount = _pickedById.length;

    return SafeArea(
      top: false,
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.fromLTRB(16, 16, 8, 8),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    'Select recipes',
                    style: textTheme.titleLarge,
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () => Navigator.of(context).pop<List<PickedRecipe>>(const []),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: TextField(
              controller: _queryController,
              decoration: InputDecoration(
                hintText: 'Search ${widget.bookName} or any book',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _queryController.text.isEmpty
                    ? null
                    : IconButton(
                        icon: const Icon(Icons.close),
                        onPressed: () => _queryController.clear(),
                      ),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
            ),
          ),
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                    ? Center(
                        child: Padding(
                          padding: const EdgeInsets.all(24),
                          child: Text(
                            _error!,
                            style: textTheme.bodyMedium?.copyWith(
                              color: colorScheme.error,
                            ),
                            textAlign: TextAlign.center,
                          ),
                        ),
                      )
                    : _results.isEmpty
                        ? Center(
                            child: Text(
                              'No recipes match your search.',
                              style: textTheme.bodyMedium?.copyWith(
                                color: colorScheme.onSurfaceVariant,
                              ),
                            ),
                          )
                        : ListView.builder(
                            itemCount: _results.length,
                            itemBuilder: (context, i) {
                              final r = _results[i];
                              final alreadyAttached =
                                  widget.alreadySelectedIds.contains(r.id);
                              final picked = _pickedById.containsKey(r.id);
                              return _RecipeRow(
                                recipe: r,
                                picked: picked,
                                alreadyAttached: alreadyAttached,
                                onTap: () => _toggle(r),
                              );
                            },
                          ),
          ),
          SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      pickedCount == 0
                          ? 'None selected'
                          : '$pickedCount selected',
                      style: textTheme.bodyMedium,
                    ),
                  ),
                  TextButton(
                    onPressed: () => Navigator.of(context).pop<List<PickedRecipe>>(const []),
                    child: const Text('Cancel'),
                  ),
                  const SizedBox(width: 8),
                  FilledButton(
                    onPressed: pickedCount == 0
                        ? null
                        : () => Navigator.of(context)
                            .pop<List<PickedRecipe>>(_pickedById.values.toList()),
                    child: const Text('Done'),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _RecipeRow extends StatelessWidget {
  final PickedRecipe recipe;
  final bool picked;
  final bool alreadyAttached;
  final VoidCallback onTap;

  const _RecipeRow({
    required this.recipe,
    required this.picked,
    required this.alreadyAttached,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final disabled = alreadyAttached;

    return InkWell(
      onTap: disabled ? null : onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: Opacity(
          opacity: disabled ? 0.5 : 1.0,
          child: Row(
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: SizedBox(
                  width: 56,
                  height: 56,
                  child: recipe.imageUrl != null
                      ? CachedNetworkImage(
                          imageUrl: recipe.imageUrl!,
                          fit: BoxFit.cover,
                          errorWidget: (context, url, error) => Container(
                            color: colorScheme.surfaceContainerHighest,
                            child: Icon(
                              Icons.restaurant,
                              color: colorScheme.onSurfaceVariant,
                              size: 24,
                            ),
                          ),
                        )
                      : Container(
                          color: colorScheme.surfaceContainerHighest,
                          child: Icon(
                            Icons.restaurant,
                            color: colorScheme.onSurfaceVariant,
                            size: 24,
                          ),
                        ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      recipe.name,
                      style: textTheme.bodyLarge,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    if (recipe.bookName != null)
                      Text(
                        recipe.bookName!,
                        style: textTheme.bodySmall?.copyWith(
                          color: colorScheme.onSurfaceVariant,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              if (alreadyAttached)
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: colorScheme.surfaceContainerHighest,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    'Added',
                    style: textTheme.labelSmall?.copyWith(
                      color: colorScheme.onSurfaceVariant,
                    ),
                  ),
                )
              else
                Icon(
                  picked ? Icons.check_circle : Icons.radio_button_unchecked,
                  color:
                      picked ? colorScheme.primary : colorScheme.outline,
                ),
            ],
          ),
        ),
      ),
    );
  }
}
