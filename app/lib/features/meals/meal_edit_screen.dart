import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/di/injection.dart';
import '../../core/services/error_reporter.dart';
import '../../core/state/mutation_failure_copy.dart';
import '../../core/state/mutation_snackbar.dart';
import '../../shared/widgets/error_banner.dart';
import 'models/meal.dart';
import 'providers/meals_provider.dart';
import 'services/meal_service.dart';
import 'widgets/component_row.dart';
import 'widgets/recipe_multiselect_picker.dart';

class MealEditScreen extends ConsumerStatefulWidget {
  final String mealId;
  const MealEditScreen({super.key, required this.mealId});

  @override
  ConsumerState<MealEditScreen> createState() => _MealEditScreenState();
}

class _MealEditScreenState extends ConsumerState<MealEditScreen> {
  final _service = getIt<MealService>();
  final _nameController = TextEditingController();
  final _descriptionController = TextEditingController();
  bool _initialized = false;
  bool _saving = false;
  List<MealComponent> _components = const [];
  String _bookId = '';
  // Display-only: the Meal model doesn't carry the book name, so pass a
  // placeholder to the picker. The picker only uses this for its search
  // hint text.
  static const _bookNamePlaceholder = 'this book';

  @override
  void dispose() {
    _nameController.dispose();
    _descriptionController.dispose();
    super.dispose();
  }

  void _hydrateOnce(Meal meal) {
    if (_initialized) return;
    _initialized = true;
    _nameController.text = meal.name;
    _descriptionController.text = meal.description ?? '';
    _components = [...meal.components]
      ..sort((a, b) => a.orderIndex.compareTo(b.orderIndex));
    _bookId = meal.recipeBookId;
  }

  Future<void> _saveNameDescription() async {
    if (_saving) return;
    setState(() => _saving = true);
    try {
      await _service.updateMeal(
        widget.mealId,
        name: _nameController.text.trim(),
        description: _descriptionController.text.trim(),
      );
      invalidateMeal(ref, widget.mealId, bookId: _bookId);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Meal saved')),
        );
        context.pop();
      }
    } catch (e) {
      ErrorReporter.report(
        e,
        StackTrace.current,
        area: 'meals.edit',
        operation: 'saveNameDescription',
      );
      if (mounted) {
        setState(() => _saving = false);
        showMutationFailureSnackbar(
          context,
          MutationType.updateMeal,
          _saveNameDescription,
        );
      }
    }
  }

  Future<void> _reorderComponents(int oldIndex, int newIndex) async {
    if (newIndex > oldIndex) newIndex -= 1;
    final original = List<MealComponent>.of(_components);
    final moved = List<MealComponent>.of(_components);
    final item = moved.removeAt(oldIndex);
    moved.insert(newIndex, item);
    setState(() => _components = moved);

    try {
      await _service.reorderMealComponents(
        widget.mealId,
        moved.map((c) => c.recipeId).toList(),
      );
      invalidateMeal(ref, widget.mealId, bookId: _bookId);
    } catch (e) {
      ErrorReporter.report(
        e,
        StackTrace.current,
        area: 'meals.edit',
        operation: 'reorderComponents',
      );
      if (!mounted) return;
      setState(() => _components = original);
      showMutationFailureSnackbar(
        context,
        MutationType.reorderComponents,
        () => _reorderComponents(oldIndex, newIndex),
      );
    }
  }

  Future<void> _removeComponent(MealComponent c) async {
    if (_components.length <= 2) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'A meal needs at least 2 recipes. Remove this one only after '
            'adding a replacement.',
          ),
        ),
      );
      return;
    }
    final original = List<MealComponent>.of(_components);
    setState(() {
      _components = _components
          .where((x) => x.recipeId != c.recipeId)
          .toList();
    });
    try {
      await _service.removeRecipeFromMeal(widget.mealId, c.recipeId);
      invalidateMeal(ref, widget.mealId, bookId: _bookId);
    } on MealMinComponentsException {
      if (!mounted) return;
      setState(() => _components = original);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('A meal needs at least 2 recipes.'),
        ),
      );
    } catch (e) {
      ErrorReporter.report(
        e,
        StackTrace.current,
        area: 'meals.edit',
        operation: 'removeComponent',
      );
      if (!mounted) return;
      setState(() => _components = original);
      showMutationFailureSnackbar(
        context,
        MutationType.removeComponent,
        () => _removeComponent(c),
      );
    }
  }

  Future<void> _addRecipe() async {
    final picked = await RecipeMultiselectPicker.show(
      context,
      bookId: _bookId,
      bookName: _bookNamePlaceholder,
      alreadySelectedIds: _components.map((c) => c.recipeId).toSet(),
    );
    if (picked.isEmpty) return;
    for (final p in picked) {
      try {
        await _service.addRecipeToMeal(widget.mealId, recipeId: p.id);
      } on MealComponentDuplicateException {
        // silently skip — shouldn't happen because alreadySelectedIds
        // already disabled these rows, but safe to ignore.
        continue;
      } catch (e) {
        ErrorReporter.report(
          e,
          StackTrace.current,
          area: 'meals.edit',
          operation: 'addRecipe',
        );
        if (!mounted) return;
        showMutationFailureSnackbar(
          context,
          MutationType.addComponent,
          () => _service.addRecipeToMeal(widget.mealId, recipeId: p.id),
        );
        continue;
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final mealAsync = ref.watch(mealByIdProvider(widget.mealId));
    return mealAsync.when(
      data: _buildEditor,
      loading: () => const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      ),
      error: (err, _) => Scaffold(
        appBar: AppBar(title: const Text('Edit meal')),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: ErrorBanner(
              message: 'Could not load meal',
              detail: ErrorReporter.detail(err),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildEditor(Meal meal) {
    _hydrateOnce(meal);
    final unavailableCount = _components.where((c) => !c.available).length;
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Edit meal'),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => context.pop(),
        ),
        actions: [
          TextButton(
            onPressed: _saving ? null : _saveNameDescription,
            child: Text(_saving ? 'Saving…' : 'Save'),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        heroTag: null,
        onPressed: _addRecipe,
        icon: const Icon(Icons.add),
        label: const Text('Add Recipe'),
      ),
      body: Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            TextField(
              controller: _nameController,
              enabled: !_saving,
              decoration: const InputDecoration(labelText: 'Name'),
              maxLength: 200,
            ),
            const SizedBox(height: 8),
            TextField(
              controller: _descriptionController,
              enabled: !_saving,
              decoration: const InputDecoration(
                labelText: 'Description',
              ),
              maxLength: 2000,
              maxLines: 2,
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('Recipes (${_components.length})',
                    style: textTheme.titleSmall),
                if (unavailableCount > 0)
                  Text(
                    '$unavailableCount unavailable',
                    style: textTheme.bodySmall?.copyWith(
                      color: colorScheme.error,
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 8),
            Expanded(
              child: _components.isEmpty
                  ? const Center(
                      child: Text(
                          'Add recipes to make this a meal.'),
                    )
                  : ReorderableListView.builder(
                      buildDefaultDragHandles: true,
                      itemCount: _components.length,
                      onReorder: _reorderComponents,
                      itemBuilder: (context, i) {
                        final c = _components[i];
                        return Dismissible(
                          key: ValueKey('meal-comp-${c.recipeId}'),
                          direction: DismissDirection.endToStart,
                          confirmDismiss: (_) async {
                            if (_components.length <= 2) {
                              _removeComponent(c); // triggers snackbar
                              return false;
                            }
                            return true;
                          },
                          onDismissed: (_) {
                            _removeComponent(c);
                          },
                          background: Container(
                            color: colorScheme.errorContainer,
                            alignment: Alignment.centerRight,
                            padding: const EdgeInsets.only(right: 20),
                            child: Icon(Icons.delete,
                                color: colorScheme.onErrorContainer),
                          ),
                          child: ComponentRow(
                            component: c,
                            trailing: const Icon(Icons.drag_handle),
                          ),
                        );
                      },
                    ),
            ),
          ],
        ),
      ),
    );
  }
}
