import 'dart:async';

import 'package:flutter/material.dart';

import '../../../core/di/injection.dart';
import '../../meals/models/meal.dart';
import '../../meals/services/meal_service.dart';
import '../../meals/widgets/meal_tile.dart' show kMealComponentCountLabel;

/// Picked-meal wire shape for the plan-meal sheet Meal path.
class MealPick {
  final String mealId;
  final String name;
  final int componentCount;
  final List<String> componentImageUrls;

  const MealPick({
    required this.mealId,
    required this.name,
    required this.componentCount,
    this.componentImageUrls = const [],
  });

  factory MealPick.fromSummary(MealSummary s) => MealPick(
        mealId: s.id,
        name: s.name,
        componentCount: s.componentCount,
        componentImageUrls: s.componentImageUrls,
      );
}

/// Meal autocomplete for the plan-meal sheet Meal path (mcal-7).
///
/// Behaviour mirrors `RecipeAutocompleteField` (300ms debounce, 2s
/// network timeout) but hits `GET /v1/meals?q=...` via [MealService]. No
/// free-text fallback — Meal mode always requires a picked Meal (the
/// sheet's Save button is disabled until [onPicked] fires with a real
/// [MealPick]).
///
/// [initialMeal] seeds the "Linked to `MealName`" chip for entry points
/// that pre-select a Meal (e.g. Plan-for-Date from Meal detail).
class MealAutocompleteField extends StatefulWidget {
  final ValueChanged<MealPick?> onPicked;

  final MealPick? initialMeal;

  /// Optional override for tests — null uses the registered singleton.
  final MealService? mealService;

  final Duration debounce;
  final Duration networkTimeout;

  const MealAutocompleteField({
    super.key,
    required this.onPicked,
    this.initialMeal,
    this.mealService,
    this.debounce = const Duration(milliseconds: 300),
    this.networkTimeout = const Duration(seconds: 2),
  });

  @override
  State<MealAutocompleteField> createState() => _MealAutocompleteFieldState();
}

class _MealAutocompleteFieldState extends State<MealAutocompleteField> {
  late final TextEditingController _controller;
  Timer? _debounceTimer;
  bool _isSearching = false;
  List<MealSummary> _matches = const [];
  MealPick? _linked;

  MealService get _service => widget.mealService ?? getIt<MealService>();

  @override
  void initState() {
    super.initState();
    _linked = widget.initialMeal;
    _controller = TextEditingController(text: _linked?.name ?? '');
    _controller.addListener(_onTextChanged);
  }

  @override
  void dispose() {
    _debounceTimer?.cancel();
    _controller.removeListener(_onTextChanged);
    _controller.dispose();
    super.dispose();
  }

  void _onTextChanged() {
    // Typing after a pick detaches the linkage — Meal mode has no
    // free-text fallback, so detach fires onPicked(null) to disable the
    // sheet's Save button until the user re-picks.
    if (_linked != null && _controller.text.trim() != _linked!.name) {
      setState(() => _linked = null);
      widget.onPicked(null);
    }

    _debounceTimer?.cancel();
    final text = _controller.text.trim();
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
      final results = await _service
          .searchMeals(query, limit: 8)
          .timeout(widget.networkTimeout);
      if (!mounted || _controller.text.trim().isEmpty) return;
      setState(() {
        _matches = results;
        _isSearching = false;
      });
    } on TimeoutException {
      if (!mounted) return;
      // No recent-meals local fallback in Meal mode — surface the empty
      // state so the user can retry when connectivity returns.
      setState(() {
        _matches = const [];
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

  void _pick(MealSummary meal) {
    final picked = MealPick.fromSummary(meal);
    _controller.value = TextEditingValue(
      text: meal.name,
      selection: TextSelection.collapsed(offset: meal.name.length),
    );
    setState(() {
      _linked = picked;
      _matches = const [];
    });
    widget.onPicked(picked);
  }

  void _detach() {
    if (_linked == null) return;
    setState(() {
      _linked = null;
      _controller.clear();
      _matches = const [];
    });
    widget.onPicked(null);
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final query = _controller.text.trim();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        TextField(
          controller: _controller,
          decoration: InputDecoration(
            hintText: 'Search your meals',
            border:
                OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
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
        if (_linked != null) ...[
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerLeft,
            child: InputChip(
              avatar: const Icon(Icons.layers, size: 16),
              label: Text('Linked to ${_linked!.name}'),
              onDeleted: _detach,
              deleteIconColor: colorScheme.error,
            ),
          ),
        ],
        if (query.isNotEmpty && !_isSearching && _linked == null) ...[
          const SizedBox(height: 8),
          if (_matches.isEmpty)
            Padding(
              padding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              child: Text(
                'No meals match "$query"',
                style: textTheme.bodyMedium?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                ),
              ),
            )
          else
            ..._matches.map((m) => _MealRow(meal: m, onTap: () => _pick(m))),
        ],
      ],
    );
  }
}

class _MealRow extends StatelessWidget {
  final MealSummary meal;
  final VoidCallback onTap;

  const _MealRow({required this.meal, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final thumb = meal.componentImageUrls.isNotEmpty
        ? meal.componentImageUrls.first
        : null;
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
              child: thumb != null
                  ? Image.network(
                      thumb,
                      fit: BoxFit.cover,
                      errorBuilder: (_, _, _) =>
                          Icon(Icons.layers, color: colorScheme.secondary),
                    )
                  : Icon(Icons.layers, color: colorScheme.secondary),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    meal.name,
                    style: textTheme.bodyMedium
                        ?.copyWith(fontWeight: FontWeight.w500),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  Text(
                    kMealComponentCountLabel(meal.componentCount),
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
