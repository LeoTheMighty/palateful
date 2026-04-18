import 'dart:async';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../../../core/di/injection.dart';
import '../../../core/services/error_reporter.dart';
import '../../../shared/widgets/error_banner.dart';
import '../models/meal.dart';
import '../services/meal_service.dart';
import 'recipe_multiselect_picker.dart';

/// Minimal component shape the sheet needs for preview + payload.
/// Shared with mcv-6's edit-mode picker.
class DraftMealComponent {
  final String recipeId;
  final String name;
  final String? imageUrl;
  final String? bookName;

  const DraftMealComponent({
    required this.recipeId,
    required this.name,
    this.imageUrl,
    this.bookName,
  });

  factory DraftMealComponent.fromPicked(PickedRecipe r) => DraftMealComponent(
        recipeId: r.id,
        name: r.name,
        imageUrl: r.imageUrl,
        bookName: r.bookName,
      );
}

/// Modal sheet for creating a Meal. Used from two entry points in
/// `recipe_book_detail_screen.dart`:
///
///   1. **Multi-select bulk bar** — caller supplies pre-selected
///      recipes in [initialComponents]. The picker is NOT auto-opened.
///   2. **"+ New Meal" overflow** — caller passes `null`, the sheet
///      auto-opens [RecipeMultiselectPicker] on first frame so the
///      standalone flow starts with recipe selection.
///
/// On success: [onCreated] fires with the server Meal, the sheet
/// dismisses itself. Callers handle navigation + provider
/// invalidation.
class CreateMealSheet extends StatefulWidget {
  final String bookId;
  final String bookName;
  final List<DraftMealComponent>? initialComponents;
  final void Function(Meal meal) onCreated;

  const CreateMealSheet({
    super.key,
    required this.bookId,
    required this.bookName,
    required this.onCreated,
    this.initialComponents,
  });

  static Future<void> show(
    BuildContext context, {
    required String bookId,
    required String bookName,
    required void Function(Meal meal) onCreated,
    List<DraftMealComponent>? initialComponents,
  }) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (ctx) => SizedBox(
        height: MediaQuery.of(ctx).size.height * 0.85,
        child: CreateMealSheet(
          bookId: bookId,
          bookName: bookName,
          initialComponents: initialComponents,
          onCreated: onCreated,
        ),
      ),
    );
  }

  @override
  State<CreateMealSheet> createState() => _CreateMealSheetState();
}

class _CreateMealSheetState extends State<CreateMealSheet> {
  final _nameController = TextEditingController();
  final _descriptionController = TextEditingController();
  final _mealService = getIt<MealService>();

  List<DraftMealComponent> _components = const [];

  /// Ids the backend flagged as unavailable on the last submit.
  /// Remove affordance shows on these rows until Create re-runs.
  Set<String> _unavailableIds = const {};

  bool _isSubmitting = false;
  String? _submitError;

  static const _maxPrefillChars = 60;

  @override
  void initState() {
    super.initState();
    final initial = widget.initialComponents;
    if (initial != null && initial.isNotEmpty) {
      _components = List.of(initial);
      _nameController.text = _prefillName(initial);
    } else {
      // Standalone mode — auto-open the picker after first frame so
      // the user lands in the selection surface, not an empty sheet.
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          unawaited(_openPicker());
        }
      });
    }
  }

  @override
  void dispose() {
    _nameController.dispose();
    _descriptionController.dispose();
    super.dispose();
  }

  static String _prefillName(List<DraftMealComponent> components) {
    if (components.isEmpty) return '';
    if (components.length == 1) return components.first.name;
    final joined = '${components[0].name} + ${components[1].name}';
    if (joined.length <= _maxPrefillChars) return joined;
    return '${joined.substring(0, _maxPrefillChars - 1)}…';
  }

  bool get _canSubmit {
    if (_isSubmitting) return false;
    if (_nameController.text.trim().isEmpty) return false;
    final available =
        _components.where((c) => !_unavailableIds.contains(c.recipeId));
    return available.length >= 2;
  }

  Future<void> _openPicker() async {
    final picked = await RecipeMultiselectPicker.show(
      context,
      bookId: widget.bookId,
      bookName: widget.bookName,
      initiallyPickedIds:
          _components.map((c) => c.recipeId).toSet(),
    );
    if (picked.isEmpty && _components.isEmpty) {
      // Standalone mode, user cancelled the very first picker — close
      // the sheet so they aren't stranded on an empty surface.
      if (mounted) Navigator.of(context).maybePop();
      return;
    }
    if (picked.isEmpty) return;
    setState(() {
      final keptIds = picked.map((p) => p.id).toSet();
      // Merge: keep existing order for components already picked;
      // append newcomers; drop anything unpicked.
      final kept = _components.where((c) => keptIds.contains(c.recipeId));
      final existingIds = _components.map((c) => c.recipeId).toSet();
      final newcomers = picked
          .where((p) => !existingIds.contains(p.id))
          .map(DraftMealComponent.fromPicked);
      _components = [...kept, ...newcomers];
      _unavailableIds = _unavailableIds
          .where((id) => _components.any((c) => c.recipeId == id))
          .toSet();
      if (_nameController.text.trim().isEmpty) {
        _nameController.text = _prefillName(_components);
      }
    });
  }

  Future<void> _removeComponent(
    DraftMealComponent c, {
    bool silent = false,
  }) async {
    final idx = _components.indexWhere((x) => x.recipeId == c.recipeId);
    if (idx < 0) return;
    setState(() {
      _components = List.of(_components)..removeAt(idx);
      _unavailableIds = _unavailableIds
          .where((id) => id != c.recipeId)
          .toSet();
    });
    if (silent) return;
    ScaffoldMessenger.of(context).hideCurrentSnackBar();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Removed ${c.name}'),
        action: SnackBarAction(
          label: 'Undo',
          onPressed: () {
            if (!mounted) return;
            setState(() {
              _components = List.of(_components)..insert(idx, c);
            });
          },
        ),
      ),
    );
  }

  Future<void> _submit() async {
    if (!_canSubmit) return;
    setState(() {
      _isSubmitting = true;
      _submitError = null;
    });
    try {
      final description = _descriptionController.text.trim();
      final meal = await _mealService.createMeal(
        bookId: widget.bookId,
        name: _nameController.text.trim(),
        description: description.isEmpty ? null : description,
        componentRecipeIds: _components.map((c) => c.recipeId).toList(),
      );
      if (!mounted) return;
      widget.onCreated(meal);
      Navigator.of(context).maybePop();
    } on MealComponentUnavailableException catch (e) {
      if (!mounted) return;
      setState(() {
        _isSubmitting = false;
        _unavailableIds = e.recipeIds.toSet();
        _submitError = 'Some recipes are no longer available. '
            'Remove them to continue.';
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isSubmitting = false;
        _submitError = 'Could not create meal. Please try again.';
      });
      ErrorReporter.report(
        e,
        StackTrace.current,
        area: 'meals.create',
        operation: 'createMeal',
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final keyboardInset = MediaQuery.of(context).viewInsets.bottom;
    final availableCount = _components
        .where((c) => !_unavailableIds.contains(c.recipeId))
        .length;

    return Padding(
      padding: EdgeInsets.only(bottom: keyboardInset),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 8, 4),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    'New meal',
                    style: textTheme.titleLarge,
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: _isSubmitting
                      ? null
                      : () => Navigator.of(context).maybePop(),
                ),
              ],
            ),
          ),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
              children: [
                TextField(
                  controller: _nameController,
                  autofocus: widget.initialComponents != null,
                  enabled: !_isSubmitting,
                  decoration: InputDecoration(
                    labelText: 'Name',
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  onChanged: (_) => setState(() {}),
                  maxLength: 200,
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: _descriptionController,
                  enabled: !_isSubmitting,
                  decoration: InputDecoration(
                    labelText: 'Description (optional)',
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  maxLength: 2000,
                  maxLines: 2,
                ),
                const SizedBox(height: 12),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'Recipes ($availableCount)',
                      style: textTheme.titleSmall,
                    ),
                    TextButton.icon(
                      onPressed: _isSubmitting ? null : _openPicker,
                      icon: const Icon(Icons.add),
                      label: Text(
                        _components.isEmpty
                            ? 'Add recipes'
                            : 'Add / change recipes',
                      ),
                    ),
                  ],
                ),
                if (availableCount < 2 && _components.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 4, bottom: 4),
                    child: Text(
                      'A meal needs at least 2 recipes.',
                      style: textTheme.bodySmall?.copyWith(
                        color: colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ),
                if (_submitError != null) ...[
                  const SizedBox(height: 8),
                  ErrorBanner(message: _submitError!),
                ],
                if (_components.isEmpty)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 24),
                    child: Text(
                      'Pick at least 2 recipes to combine into a meal.',
                      style: textTheme.bodyMedium?.copyWith(
                        color: colorScheme.onSurfaceVariant,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  )
                else
                  SizedBox(
                    height: 180,
                    child: ListView.separated(
                      scrollDirection: Axis.horizontal,
                      itemCount: _components.length,
                      separatorBuilder: (_, _) => const SizedBox(width: 12),
                      itemBuilder: (context, i) {
                        final c = _components[i];
                        final isUnavailable =
                            _unavailableIds.contains(c.recipeId);
                        return _ComponentPreviewCard(
                          component: c,
                          isUnavailable: isUnavailable,
                          enabled: !_isSubmitting,
                          onRemove: () => _removeComponent(c),
                        );
                      },
                    ),
                  ),
              ],
            ),
          ),
          SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 12),
              child: Row(
                children: [
                  TextButton(
                    onPressed: _isSubmitting
                        ? null
                        : () => Navigator.of(context).maybePop(),
                    child: const Text('Cancel'),
                  ),
                  const Spacer(),
                  FilledButton(
                    onPressed: _canSubmit ? _submit : null,
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        _isSubmitting
                            ? const SizedBox(
                                width: 16,
                                height: 16,
                                child: CircularProgressIndicator(
                                    strokeWidth: 2),
                              )
                            : const Icon(Icons.check),
                        const SizedBox(width: 8),
                        Text(_isSubmitting ? 'Creating…' : 'Create'),
                      ],
                    ),
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

class _ComponentPreviewCard extends StatelessWidget {
  final DraftMealComponent component;
  final bool isUnavailable;
  final bool enabled;
  final VoidCallback onRemove;

  const _ComponentPreviewCard({
    required this.component,
    required this.isUnavailable,
    required this.enabled,
    required this.onRemove,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    return SizedBox(
      width: 120,
      child: GestureDetector(
        onLongPress: enabled ? onRemove : null,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Stack(
              children: [
                ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: SizedBox(
                    width: 120,
                    height: 120,
                    child: component.imageUrl != null
                        ? CachedNetworkImage(
                            imageUrl: component.imageUrl!,
                            fit: BoxFit.cover,
                            errorWidget: (context, url, error) =>
                                _placeholder(colorScheme),
                          )
                        : _placeholder(colorScheme),
                  ),
                ),
                if (isUnavailable)
                  Positioned.fill(
                    child: Container(
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(12),
                        color: Colors.black.withValues(alpha: 0.45),
                      ),
                      child: const Center(
                        child: Text(
                          'Unavailable',
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ),
                  ),
                Positioned(
                  top: 4,
                  right: 4,
                  child: Material(
                    color: Colors.black54,
                    shape: const CircleBorder(),
                    child: InkWell(
                      customBorder: const CircleBorder(),
                      onTap: enabled ? onRemove : null,
                      child: const Padding(
                        padding: EdgeInsets.all(4),
                        child: Icon(
                          Icons.close,
                          size: 14,
                          color: Colors.white,
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              component.name,
              style: textTheme.bodySmall,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
            if (isUnavailable)
              TextButton(
                onPressed: enabled ? onRemove : null,
                style: TextButton.styleFrom(
                  foregroundColor: colorScheme.error,
                  padding: EdgeInsets.zero,
                  minimumSize: const Size(0, 24),
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
                child: const Text('Remove'),
              ),
          ],
        ),
      ),
    );
  }

  Widget _placeholder(ColorScheme colorScheme) => Container(
        color: colorScheme.surfaceContainerHighest,
        child: Icon(
          Icons.restaurant,
          size: 32,
          color: colorScheme.onSurfaceVariant,
        ),
      );
}
