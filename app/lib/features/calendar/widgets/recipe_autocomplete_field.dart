import 'dart:async';

import 'package:flutter/material.dart';

import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';

/// Result shape exposed to the plan-meal sheet: a picked recipe (with
/// metadata needed to render the Linked chip) or a free-text meal.
/// `isFreeText` is true when `recipeId` is null.
class PickedMeal {
  final String? recipeId;
  final String? recipeBookName;
  final String? imageUrl;
  final String title;

  const PickedMeal.recipe({
    required String id,
    required this.title,
    this.recipeBookName,
    this.imageUrl,
  }) : recipeId = id;

  const PickedMeal.freeText(this.title)
      : recipeId = null,
        recipeBookName = null,
        imageUrl = null;

  bool get isFreeText => recipeId == null;
}

/// Recipe autocomplete field for the plan-meal sheet (bugs-cal-2).
///
/// Behaviour (story ACs):
///  - Recent chips on empty input.
///  - 300ms debounce on typing; up to 8 results from unified_search with
///    `scope=recipes`.
///  - 2s timeout → fall back to local recent-meals matches.
///  - No-match row: "Save '<typed text>' as free-text meal".
///  - Tap a match → fill the field + render "Linked to [Recipe]" chip.
///  - Tap the chip → detach (preserve typed text, clear recipeId).
class RecipeAutocompleteField extends StatefulWidget {
  final TextEditingController controller;
  final List<String> recentMeals;
  final ValueChanged<PickedMeal> onPicked;

  /// Optional override for tests — if null, the widget uses the registered
  /// [ApiClient] singleton.
  final ApiClient? apiClient;

  /// Search debounce. Kept adjustable for tests; defaults to 300ms to match
  /// the app-wide search debounce (locked decision reference).
  final Duration debounce;

  /// Network timeout before falling back to local recent-meals matches.
  final Duration networkTimeout;

  const RecipeAutocompleteField({
    super.key,
    required this.controller,
    required this.recentMeals,
    required this.onPicked,
    this.apiClient,
    this.debounce = const Duration(milliseconds: 300),
    this.networkTimeout = const Duration(seconds: 2),
  });

  @override
  State<RecipeAutocompleteField> createState() =>
      _RecipeAutocompleteFieldState();
}

class _RecipeAutocompleteFieldState extends State<RecipeAutocompleteField> {
  Timer? _debounceTimer;
  bool _isSearching = false;
  List<_RecipeHit> _matches = const [];
  _RecipeHit? _linked;

  ApiClient get _apiClient => widget.apiClient ?? getIt<ApiClient>();

  @override
  void initState() {
    super.initState();
    widget.controller.addListener(_onTextChanged);
  }

  @override
  void dispose() {
    _debounceTimer?.cancel();
    widget.controller.removeListener(_onTextChanged);
    super.dispose();
  }

  void _onTextChanged() {
    // Typing while a recipe is linked detaches it: the title is "owned"
    // by the user again, so we drop the association to avoid shipping a
    // stale linkage.
    if (_linked != null && widget.controller.text.trim() != _linked!.name) {
      setState(() => _linked = null);
      widget.onPicked(PickedMeal.freeText(widget.controller.text));
    }

    _debounceTimer?.cancel();
    final text = widget.controller.text.trim();
    if (text.isEmpty) {
      setState(() => _matches = const []);
      return;
    }
    if (text.length < 2) return;

    _debounceTimer = Timer(widget.debounce, () => _runSearch(text));
  }

  Future<void> _runSearch(String query) async {
    if (!mounted) return;
    setState(() => _isSearching = true);

    try {
      final response = await _apiClient
          .search(query, scope: 'recipes', limit: 8)
          .timeout(widget.networkTimeout);
      if (!mounted || _textEmpty) return;

      final myRecipes =
          List<Map<String, dynamic>>.from(response.data['my_recipes'] ?? []);
      final hits = myRecipes.take(8).map((m) => _RecipeHit.fromJson(m)).toList();
      setState(() {
        _matches = hits;
        _isSearching = false;
      });
    } on TimeoutException {
      if (!mounted) return;
      // Fallback per AC #6: local recent-meals that prefix-match the query.
      final fallback = widget.recentMeals
          .where((m) => m.toLowerCase().contains(query.toLowerCase()))
          .take(8)
          .map(_RecipeHit.fromRecent)
          .toList();
      setState(() {
        _matches = fallback;
        _isSearching = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _matches = const [];
        _isSearching = false;
      });
    }
  }

  bool get _textEmpty => widget.controller.text.trim().isEmpty;

  void _pickRecent(String name) {
    widget.controller.value = TextEditingValue(
      text: name,
      selection: TextSelection.collapsed(offset: name.length),
    );
    widget.onPicked(PickedMeal.freeText(name));
  }

  void _pickRecipe(_RecipeHit hit) {
    widget.controller.value = TextEditingValue(
      text: hit.name,
      selection: TextSelection.collapsed(offset: hit.name.length),
    );
    setState(() {
      _linked = hit;
      _matches = const [];
    });
    widget.onPicked(PickedMeal.recipe(
      id: hit.id!,
      title: hit.name,
      recipeBookName: hit.bookName,
      imageUrl: hit.imageUrl,
    ));
  }

  void _detachLinked() {
    if (_linked == null) return;
    // Title stays; only the association is dropped.
    final text = widget.controller.text;
    setState(() => _linked = null);
    widget.onPicked(PickedMeal.freeText(text));
  }

  void _pickFreeText() {
    final text = widget.controller.text.trim();
    if (text.isEmpty) return;
    setState(() {
      _linked = null;
      _matches = const [];
    });
    widget.onPicked(PickedMeal.freeText(text));
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final query = widget.controller.text.trim();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        TextField(
          controller: widget.controller,
          decoration: InputDecoration(
            hintText: 'Search your recipes or type a meal',
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
            contentPadding:
                const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            suffixIcon: _isSearching
                ? const Padding(
                    padding: EdgeInsets.all(10),
                    child: SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                  )
                : null,
          ),
          textCapitalization: TextCapitalization.sentences,
        ),

        // Linked-recipe chip (tap to detach)
        if (_linked != null) ...[
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerLeft,
            child: InputChip(
              avatar: const Icon(Icons.link, size: 16),
              label: Text('Linked to ${_linked!.name}'),
              onDeleted: _detachLinked,
              deleteIconColor: colorScheme.error,
            ),
          ),
        ],

        // Results area
        const SizedBox(height: 8),
        if (query.isEmpty && widget.recentMeals.isNotEmpty)
          SizedBox(
            height: 36,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: widget.recentMeals.length,
              separatorBuilder: (_, _) => const SizedBox(width: 6),
              itemBuilder: (_, i) {
                final meal = widget.recentMeals[i];
                return ActionChip(
                  label: Text(meal, style: const TextStyle(fontSize: 12)),
                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  visualDensity: VisualDensity.compact,
                  onPressed: () => _pickRecent(meal),
                );
              },
            ),
          )
        else if (query.isNotEmpty && !_isSearching) ...[
          if (_matches.isEmpty)
            InkWell(
              onTap: _pickFreeText,
              child: Padding(
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                child: Row(
                  children: [
                    Icon(Icons.add, size: 18, color: colorScheme.primary),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        "Save '$query' as free-text meal",
                        style: textTheme.bodyMedium?.copyWith(
                          color: colorScheme.primary,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            )
          else
            ..._matches.map((hit) => _RecipeRow(
                  hit: hit,
                  onTap: () => hit.id == null ? _pickRecent(hit.name) : _pickRecipe(hit),
                )),
        ],
      ],
    );
  }
}

class _RecipeHit {
  final String? id;
  final String name;
  final String? bookName;
  final String? imageUrl;

  const _RecipeHit({
    required this.id,
    required this.name,
    this.bookName,
    this.imageUrl,
  });

  factory _RecipeHit.fromJson(Map<String, dynamic> json) {
    return _RecipeHit(
      id: json['id'] as String?,
      name: json['name'] as String? ?? '',
      bookName: json['recipe_book_name'] as String?,
      imageUrl: json['image_url'] as String?,
    );
  }

  factory _RecipeHit.fromRecent(String name) => _RecipeHit(id: null, name: name);
}

class _RecipeRow extends StatelessWidget {
  final _RecipeHit hit;
  final VoidCallback onTap;

  const _RecipeRow({required this.hit, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 8),
        child: Row(
          children: [
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(8),
                color: colorScheme.surfaceContainerHighest,
              ),
              clipBehavior: Clip.antiAlias,
              child: hit.imageUrl != null
                  ? Image.network(
                      hit.imageUrl!,
                      fit: BoxFit.cover,
                      errorBuilder: (_, _, _) =>
                          Icon(Icons.restaurant, color: colorScheme.secondary),
                    )
                  : Icon(Icons.restaurant, color: colorScheme.secondary),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    hit.name,
                    style: textTheme.bodyMedium?.copyWith(
                      fontWeight: FontWeight.w500,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (hit.bookName != null)
                    Text(
                      hit.bookName!,
                      style: textTheme.bodySmall?.copyWith(
                        color: colorScheme.onSurfaceVariant,
                      ),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
