import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../core/theme/theme.dart';
import '../../core/utils/responsive.dart';
import '../../services/share_service.dart';
import '../../shared/widgets/mixed_card_metrics.dart';
import '../../shared/widgets/vibe_filter_bar.dart';
import '../home/recipe_list_view.dart';
import '../home/widgets/dynamic_column.dart';
import '../home/widgets/hide_in_meals_chip.dart';
import '../home/widgets/recipe_list_view_toggle_button.dart';
import '../home/widgets/recipe_table_tile.dart';
import '../meals/models/meal.dart';
import '../meals/services/meal_service.dart';
import '../meals/widgets/create_meal_sheet.dart';
import '../meals/widgets/meal_tile.dart';
import '../recipes/providers/recipe_provider.dart';
import '../recipes/services/recipe_service.dart';
import 'providers/recipe_books_provider.dart';
import 'services/recipe_book_service.dart';
import 'services/recipe_book_sync_service.dart';
import 'widgets/book_recipe_card.dart';
import '../../core/services/error_reporter.dart';
import '../../core/state/mutation_failure_copy.dart';
import '../../core/state/mutation_snackbar.dart';
import '../../shared/widgets/error_banner.dart';

class RecipeBookDetailScreen extends ConsumerStatefulWidget {
  final String recipeBookId;

  const RecipeBookDetailScreen({super.key, required this.recipeBookId});

  @override
  ConsumerState<RecipeBookDetailScreen> createState() =>
      _RecipeBookDetailScreenState();
}

class _RecipeBookDetailScreenState
    extends ConsumerState<RecipeBookDetailScreen> {
  final _apiClient = getIt<ApiClient>();
  final _mealService = getIt<MealService>();
  final _bookService = getIt<RecipeBookService>();
  late final RecipeBookSyncService _syncService;
  Map<String, dynamic>? _recipeBook;
  List<dynamic> _recipes = [];
  List<MealSummary> _meals = const [];
  bool _isLoading = true;
  String? _error;
  String? _errorDetail;
  bool _mealsLoadFailed = false;
  bool _isMovingOrCopying = false;
  String _userRole = 'owner';
  bool _isShared = false;

  // Real-time sync state
  StreamSubscription? _addedSub;
  StreamSubscription? _updatedSub;
  StreamSubscription? _removedSub;
  StreamSubscription? _stateSub;
  bool _wsConnected = false;
  bool _subscribed = false;

  // Vibe filter
  String? _vibeFilter;

  // Multi-select state
  bool _isSelectMode = false;
  final Set<String> _selectedRecipeIds = {};
  bool _isBulkOperating = false;

  // Story 5: hide-in-meals filter (default ON). Local to the detail
  // screen — the home screen has its own toggle that lives on home's
  // state. The chip + empty-state mirror home's surface.
  bool _hideInMeals = true;

  @override
  void initState() {
    super.initState();
    _syncService = getIt<RecipeBookSyncService>();
    _loadRecipeBook();
  }

  @override
  void dispose() {
    _addedSub?.cancel();
    _updatedSub?.cancel();
    _removedSub?.cancel();
    _stateSub?.cancel();
    _syncService.disconnectWebSocket();
    super.dispose();
  }

  void _subscribeToRealTime() {
    if (_subscribed) return;
    _subscribed = true;
    _syncService.connectWebSocket(widget.recipeBookId);

    _addedSub = _syncService.onRecipeAdded.listen((_) {
      if (mounted) _loadRecipeBook();
    });
    _updatedSub = _syncService.onRecipeUpdated.listen((_) {
      if (mounted) _loadRecipeBook();
    });
    _removedSub = _syncService.onRecipeRemoved.listen((recipeId) {
      if (!mounted) return;
      setState(() {
        _recipes.removeWhere((r) => r['id']?.toString() == recipeId);
      });
    });
    _stateSub = _syncService.onConnectionStateChange.listen((state) {
      if (!mounted) return;
      setState(() {
        _wsConnected = state == RecipeBookWebSocketState.connected;
      });
    });
  }

  Future<void> _loadRecipeBook() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      // Fetch book + meals in parallel. Meals failure is non-fatal;
      // the book still renders with a banner above the grid.
      final results = await Future.wait([
        _apiClient.getRecipeBook(widget.recipeBookId),
        _mealService
            .listMealsInBook(widget.recipeBookId)
            .then<List<MealSummary>?>((v) => v)
            .catchError((_) => null),
      ]);
      final response = results[0] as dynamic;
      final meals = results[1] as List<MealSummary>?;
      if (mounted) {
        final isShared = response.data['is_shared'] as bool? ?? false;
        setState(() {
          _recipeBook = response.data;
          _recipes = response.data['recipes'] ?? [];
          _meals = meals ?? const [];
          _mealsLoadFailed = meals == null;
          _userRole = response.data['user_role'] as String? ?? 'owner';
          _isShared = isShared;
          _isLoading = false;
        });
        if (isShared) _subscribeToRealTime();
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Could not load recipe book. Please try again.';
          _errorDetail = ErrorReporter.detail(e);
          _isLoading = false;
        });
      }
    }
  }

  void _exitSelectMode() {
    setState(() {
      _isSelectMode = false;
      _selectedRecipeIds.clear();
    });
  }

  void _enterSelectMode({String? initialRecipeId}) {
    setState(() {
      _isSelectMode = true;
      _selectedRecipeIds.clear();
      if (initialRecipeId != null) {
        _selectedRecipeIds.add(initialRecipeId);
      }
    });
  }

  void _toggleRecipeSelection(String recipeId) {
    setState(() {
      if (_selectedRecipeIds.contains(recipeId)) {
        _selectedRecipeIds.remove(recipeId);
        if (_selectedRecipeIds.isEmpty) {
          _isSelectMode = false;
        }
      } else {
        _selectedRecipeIds.add(recipeId);
      }
    });
  }

  /// Build DraftMealComponent list from the currently-selected recipe
  /// ids, preserving the order the recipes appear in `_recipes` so
  /// the name pre-fill is deterministic.
  List<DraftMealComponent> _selectedAsDraftComponents() {
    final result = <DraftMealComponent>[];
    for (final r in _recipes) {
      final id = r['id']?.toString();
      if (id == null || !_selectedRecipeIds.contains(id)) continue;
      result.add(DraftMealComponent(
        recipeId: id,
        name: r['name'] as String? ?? 'Untitled',
        imageUrl: r['image_url'] as String?,
        bookName: _recipeBook?['name'] as String?,
      ));
    }
    return result;
  }

  Future<void> _bulkCreateMeal() async {
    if (_selectedRecipeIds.length < 2) return;
    final components = _selectedAsDraftComponents();
    await _openCreateMealSheet(initialComponents: components);
    if (mounted) _exitSelectMode();
  }

  /// Story 5: collapse the vibe + hide-in-meals filters into the
  /// recipe list both grid and table render. Hide-in-meals reads
  /// `is_in_meal` (added per-row by the Story 2 backend); falls back
  /// to checking the loaded `_meals`' component lists if the field
  /// is missing (older payloads / rolling deploy).
  List<dynamic> _filteredRecipesForRender() {
    var out = _recipes;
    if (_vibeFilter != null) {
      out = out
          .where((r) =>
              r['primary_vibe'] == _vibeFilter ||
              r['secondary_vibe'] == _vibeFilter)
          .toList();
    }
    if (_hideInMeals) {
      final fallbackComponentIds = <String>{};
      final hasIsInMeal =
          out.isNotEmpty && (out.first as Map).containsKey('is_in_meal');
      if (!hasIsInMeal) {
        for (final m in _meals) {
          for (final id in m.componentRecipeIds) {
            fallbackComponentIds.add(id);
          }
        }
      }
      out = out.where((r) {
        if (r is! Map) return true;
        if (r['is_in_meal'] == true) return false;
        if (!hasIsInMeal) {
          final id = r['id']?.toString();
          if (id != null && fallbackComponentIds.contains(id)) return false;
        }
        return true;
      }).toList();
    }
    return out;
  }

  /// Story 5: meal-attached recipe count for the chip. Prefers the
  /// `total_in_meals` field on the response (Story 2 backend); falls
  /// back to deriving from the loaded recipes' `is_in_meal` flag, or
  /// finally the union of `_meals` component lists.
  int _hiddenInMealsCount() {
    final fromResponse = _recipeBook?['total_in_meals'];
    if (fromResponse is num) return fromResponse.toInt();
    var count = 0;
    var sawFlag = false;
    for (final r in _recipes) {
      if (r is! Map) continue;
      if (r.containsKey('is_in_meal')) {
        sawFlag = true;
        if (r['is_in_meal'] == true) count++;
      }
    }
    if (sawFlag) return count;
    final ids = <String>{};
    for (final m in _meals) {
      for (final id in m.componentRecipeIds) {
        ids.add(id);
      }
    }
    return ids.length;
  }

  /// Build the mixed recipe + meal card list, sorted by `updated_at`
  /// DESC. Recipe widgets are `BookRecipeCard`; meals are `MealTile`.
  /// Vibe filter applies to recipes only — meals have no vibe field,
  /// so they are hidden when a filter is active.
  List<Widget> _buildMixedCards() {
    final filteredRecipes = _filteredRecipesForRender();
    final meals = _vibeFilter == null ? _meals : const <MealSummary>[];

    // Pack into a unified list with `updated_at` for sort, then emit
    // the appropriate tile widget for each entry.
    final entries = <_GridEntry>[];
    for (final recipe in filteredRecipes) {
      final raw = recipe['updated_at'] as String? ??
          recipe['created_at'] as String?;
      final updatedAt = raw != null
          ? DateTime.tryParse(raw) ?? DateTime(1970)
          : DateTime(1970);
      entries.add(_GridEntry.recipe(recipe, updatedAt));
    }
    for (final meal in meals) {
      entries.add(_GridEntry.meal(meal, meal.updatedAt));
    }
    entries.sort((a, b) => b.updatedAt.compareTo(a.updatedAt));

    return entries.map((e) {
      if (e.isRecipe) {
        final recipe = e.recipe!;
        final recipeId = recipe['id']?.toString();
        final isSelected =
            recipeId != null && _selectedRecipeIds.contains(recipeId);
        return BookRecipeCard(
          recipe: recipe,
          isSelectMode: _isSelectMode,
          isSelected: isSelected,
          onTap: _isSelectMode
              ? () {
                  if (recipeId != null) _toggleRecipeSelection(recipeId);
                }
              : () async {
                  await context.push('/recipes/${recipe['id']}');
                  _loadRecipeBook();
                },
          onLongPress: _isSelectMode || _userRole == 'viewer'
              ? null
              : () {
                  if (recipeId != null) {
                    _enterSelectMode(initialRecipeId: recipeId);
                  }
                },
        );
      }
      final meal = e.meal!;
      return MealTile(
        meal: meal,
        onTap: _isSelectMode
            ? () {
                // Meals aren't part of multi-select (you can't combine a
                // meal into another meal via the bulk bar). Tap is a
                // no-op while selection is active.
              }
            : () async {
                await context.push('/meals/${meal.id}');
                if (mounted) _loadRecipeBook();
              },
      );
    }).toList();
  }

  /// Story 3 + 4: table-density alternative to `_buildMixedCards`.
  /// Same recipe + meal merge + sort as the grid path, rendered as
  /// one row per entry. Each row's trailing slot shows the entry's
  /// `updated_at` as a relative date so the user sees the lens the
  /// book is sorted on. The header is informational — book-detail
  /// has no sort menu (always `updated_at DESC`), so tap-to-flip is
  /// suppressed here.
  Widget _buildMixedTable() {
    final filteredRecipes = _filteredRecipesForRender();
    final meals = _vibeFilter == null ? _meals : const <MealSummary>[];

    final entries = <_GridEntry>[];
    for (final recipe in filteredRecipes) {
      final raw = recipe['updated_at'] as String? ??
          recipe['created_at'] as String?;
      final updatedAt = raw != null
          ? DateTime.tryParse(raw) ?? DateTime(1970)
          : DateTime(1970);
      entries.add(_GridEntry.recipe(recipe, updatedAt));
    }
    for (final meal in meals) {
      entries.add(_GridEntry.meal(meal, meal.updatedAt));
    }
    entries.sort((a, b) => b.updatedAt.compareTo(a.updatedAt));

    final colorScheme = Theme.of(context).colorScheme;
    final tiles = <Widget>[
      _BookDetailColumnHeader(label: 'Updated'),
    ];
    for (var i = 0; i < entries.length; i++) {
      if (i > 0) {
        tiles.add(Divider(
          height: 1,
          thickness: 1,
          color: colorScheme.outlineVariant,
        ));
      }
      final e = entries[i];
      if (e.isRecipe) {
        final recipe = e.recipe!;
        // Surface the active book name on the row pill (the home pulls
        // it from the cross-book payload; here we know it locally —
        // book detail is single-book by definition).
        final pillRecipe = {
          ...recipe,
          if (_recipeBook?['name'] is String)
            'recipe_book_name': _recipeBook!['name'],
        };
        final recipeId = recipe['id']?.toString();
        final isSelected =
            recipeId != null && _selectedRecipeIds.contains(recipeId);
        tiles.add(RecipeTableTile(
          item: pillRecipe,
          selected: isSelected,
          trailing: Text(
            formatDynamicColumnRelativeDate(e.updatedAt),
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w500,
            ),
          ),
          onTap: _isSelectMode
              ? () {
                  if (recipeId != null) _toggleRecipeSelection(recipeId);
                }
              : () async {
                  await context.push('/recipes/${recipe['id']}');
                  _loadRecipeBook();
                },
          onLongPress: _isSelectMode || _userRole == 'viewer'
              ? null
              : () {
                  if (recipeId != null) {
                    _enterSelectMode(initialRecipeId: recipeId);
                  }
                },
        ));
      } else {
        final meal = e.meal!;
        final mealMap = <String, dynamic>{
          'id': meal.id,
          'name': meal.name,
          'kind': 'meal',
          'component_image_urls': meal.componentImageUrls,
          if (_recipeBook?['name'] is String)
            'recipe_book_name': _recipeBook!['name'],
        };
        tiles.add(RecipeTableTile(
          item: mealMap,
          trailing: Text(
            formatDynamicColumnRelativeDate(e.updatedAt),
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w500,
            ),
          ),
          onTap: _isSelectMode
              ? () {}
              : () async {
                  await context.push('/meals/${meal.id}');
                  if (mounted) _loadRecipeBook();
                },
        ));
      }
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: tiles,
    );
  }

  Future<void> _openCreateMealSheet({
    required List<DraftMealComponent> initialComponents,
  }) async {
    final bookName = _recipeBook?['name'] as String? ?? 'Book';
    await CreateMealSheet.show(
      context,
      bookId: widget.recipeBookId,
      bookName: bookName,
      initialComponents: initialComponents.isEmpty ? null : initialComponents,
      onCreated: (meal) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).hideCurrentSnackBar();
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Meal “${meal.name}” created')),
        );
        context.push('/meals/${meal.id}').then((_) {
          if (mounted) _loadRecipeBook();
        });
      },
    );
  }

  Future<void> _archiveRecipeBook() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Archive Recipe Book?'),
        content: const Text(
          'This book and its recipes will be moved to your archive. You can restore it anytime.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Archive'),
          ),
        ],
      ),
    );

    if (confirm == true) {
      try {
        HapticFeedback.selectionClick();
        await _bookService.archiveRecipeBook(widget.recipeBookId);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Recipe book archived')),
          );
          context.pop();
        }
      } catch (e) {
        if (mounted) {
          showMutationFailureSnackbar(
            context,
            MutationType.archiveRecipeBook,
            _archiveRecipeBook,
          );
        }
      }
    }
  }

  Future<void> _renameRecipeBook() async {
    final nameController = TextEditingController(text: _recipeBook?['name'] ?? '');
    final descriptionController = TextEditingController(text: _recipeBook?['description'] ?? '');

    try {
      final result = await showDialog<bool>(
        context: context,
        builder: (context) {
          return StatefulBuilder(
            builder: (context, setDialogState) {
              final nameIsEmpty = nameController.text.trim().isEmpty;
              return AlertDialog(
                title: const Text('Edit Recipe Book'),
                content: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    TextField(
                      controller: nameController,
                      decoration: const InputDecoration(
                        labelText: 'Name',
                      ),
                      autofocus: true,
                      onChanged: (_) => setDialogState(() {}),
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: descriptionController,
                      decoration: const InputDecoration(
                        labelText: 'Description (optional)',
                      ),
                      maxLines: 2,
                    ),
                  ],
                ),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.pop(context, false),
                    child: const Text('Cancel'),
                  ),
                  ElevatedButton(
                    onPressed: nameIsEmpty
                        ? null
                        : () => Navigator.pop(context, true),
                    child: const Text('Save'),
                  ),
                ],
              );
            },
          );
        },
      );

      if (result == true) {
        try {
          await _bookService.updateRecipeBook(widget.recipeBookId, {
            'name': nameController.text,
            'description': descriptionController.text.isEmpty
                ? null
                : descriptionController.text,
          });
          _loadRecipeBook();
        } catch (e) {
          if (mounted) {
            showMutationFailureSnackbar(
              context,
              MutationType.updateRecipeBook,
              _renameRecipeBook,
            );
          }
        }
      }
    } finally {
      nameController.dispose();
      descriptionController.dispose();
    }
  }

  Future<Map<String, dynamic>?> _showBookPicker({String? excludeBookId}) async {
    try {
      final allBooks = await readRecipeBooks(context);
      final books = allBooks
          .where((b) => b['id']?.toString() != excludeBookId)
          .toList();

      if (!mounted) return null;
      if (books.isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('No other books available')),
        );
        return null;
      }

      return showModalBottomSheet<Map<String, dynamic>>(
        context: context,
        isScrollControlled: true,
        builder: (context) => ConstrainedBox(
          constraints: BoxConstraints(
            maxHeight: MediaQuery.of(context).size.height * 0.6,
          ),
          child: SafeArea(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
                  child: Text(
                    'Choose a book',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                Flexible(
                  child: ListView(
                    shrinkWrap: true,
                    children: books.map((book) => ListTile(
                          leading: const Icon(Icons.menu_book_outlined),
                          title: Text(book['name'] ?? 'Untitled'),
                          subtitle: Text('${book['recipe_count'] ?? 0} recipes'),
                          onTap: () => Navigator.pop(context, book),
                        )).toList(),
                  ),
                ),
                const SizedBox(height: 8),
              ],
            ),
          ),
        ),
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not load books. Please try again.')),
        );
      }
      return null;
    }
  }

  // Bulk action handlers
  Future<void> _bulkMove() async {
    if (_isBulkOperating || _selectedRecipeIds.isEmpty) return;

    final book = await _showBookPicker(excludeBookId: widget.recipeBookId);
    if (book == null) return;

    setState(() => _isBulkOperating = true);
    try {
      HapticFeedback.selectionClick();
      final count = _selectedRecipeIds.length;
      final movedIds = _selectedRecipeIds.toList();
      await _bookService.bulkMoveRecipes(
        movedIds,
        book['id'] as String,
        sourceBookId: widget.recipeBookId,
      );
      // pfc-3: drop each moved recipe's cached detail payload
      // (recipe_book_id changed).
      if (mounted) {
        for (final id in movedIds) {
          invalidateRecipe(context, id);
        }
      }
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('$count recipes moved to ${book['name']}')),
        );
        _exitSelectMode();
        _loadRecipeBook();
      }
    } catch (e) {
      if (mounted) {
        showMutationFailureSnackbar(
          context,
          MutationType.bulkMoveRecipes,
          _bulkMove,
        );
      }
    } finally {
      if (mounted) setState(() => _isBulkOperating = false);
    }
  }

  Future<void> _bulkArchive() async {
    if (_isBulkOperating || _selectedRecipeIds.isEmpty) return;

    final count = _selectedRecipeIds.length;
    final confirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Archive $count recipes?'),
        content: const Text(
          'These recipes will be moved to your archive. You can restore them anytime.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Archive'),
          ),
        ],
      ),
    );

    if (confirm != true) return;

    setState(() => _isBulkOperating = true);
    try {
      HapticFeedback.selectionClick();
      final archivedIds = _selectedRecipeIds.toList();
      await getIt<RecipeService>().bulkArchiveRecipes(
        archivedIds,
        bookId: widget.recipeBookId,
      );
      if (mounted) {
        for (final id in archivedIds) {
          invalidateRecipe(context, id);
        }
      }
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('$count recipes archived')),
        );
        _exitSelectMode();
        _loadRecipeBook();
      }
    } catch (_) {
      if (mounted) {
        showMutationFailureSnackbar(
          context,
          MutationType.bulkArchiveRecipes,
          _bulkArchive,
        );
      }
    } finally {
      if (mounted) setState(() => _isBulkOperating = false);
    }
  }

  Future<void> _bulkTags() async {
    if (_isBulkOperating || _selectedRecipeIds.isEmpty) return;

    final tagController = TextEditingController();
    bool isAddMode = true;

    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              title: const Text('Update Tags'),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  SegmentedButton<bool>(
                    segments: const [
                      ButtonSegment(value: true, label: Text('Add Tags')),
                      ButtonSegment(value: false, label: Text('Remove Tags')),
                    ],
                    selected: {isAddMode},
                    onSelectionChanged: (selected) {
                      setDialogState(() => isAddMode = selected.first);
                    },
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: tagController,
                    decoration: InputDecoration(
                      labelText: isAddMode ? 'Tags to add' : 'Tags to remove',
                      hintText: 'e.g. quick, easy, italian',
                    ),
                    autofocus: true,
                  ),
                ],
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Cancel'),
                ),
                ElevatedButton(
                  onPressed: () {
                    final tags = tagController.text
                        .split(',')
                        .map((t) => t.trim())
                        .where((t) => t.isNotEmpty)
                        .toList();
                    if (tags.isEmpty) return;
                    Navigator.pop(context, {
                      'isAdd': isAddMode,
                      'tags': tags,
                    });
                  },
                  child: const Text('Apply'),
                ),
              ],
            );
          },
        );
      },
    );

    if (result == null) {
      tagController.dispose();
      return;
    }

    tagController.dispose();

    setState(() => _isBulkOperating = true);
    try {
      HapticFeedback.selectionClick();
      final tags = result['tags'] as List<String>;
      final count = _selectedRecipeIds.length;
      await _bookService.bulkUpdateTags(
        _selectedRecipeIds.toList(),
        addTags: result['isAdd'] == true ? tags : null,
        removeTags: result['isAdd'] == false ? tags : null,
      );
      if (mounted) {
        final action = result['isAdd'] == true ? 'added to' : 'removed from';
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Tags $action $count recipes')),
        );
        _exitSelectMode();
        _loadRecipeBook();
      }
    } catch (e) {
      if (mounted) {
        showMutationFailureSnackbar(
          context,
          MutationType.bulkUpdateTags,
          _bulkTags,
        );
      }
    } finally {
      if (mounted) setState(() => _isBulkOperating = false);
    }
  }

  Future<void> _shareBook() async {
    try {
      final shareService = ShareService();
      await shareService.shareRecipeBook(
        recipeBookId: widget.recipeBookId,
        recipeBookName: _recipeBook?['name'] ?? 'Recipe Book',
        context: context,
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to share — please try again')),
        );
      }
    }
  }

  Future<void> _addRecipe() async {
    await context.push('/recipes/add/wizard', extra: {
      'recipeBookId': widget.recipeBookId,
    });
    if (mounted) _loadRecipeBook();
  }

  Widget _buildBookEmptyState() {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final bookId = widget.recipeBookId;

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(24),
              ),
              child: Icon(
                Icons.restaurant_menu,
                size: 56,
                color: colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 24),
            Text(
              'Add your first recipe',
              style: textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.w600,
                color: colorScheme.onSurface,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            Text(
              'Get started by importing or creating a recipe',
              style: textTheme.bodyMedium?.copyWith(
                color: colorScheme.onSurfaceVariant,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 24),
            _EmptyStateCta(
              icon: Icons.link,
              label: 'Import from URL',
              onTap: () async {
                await context.push('/recipes/add/url', extra: {
                  'recipeBookId': bookId,
                });
                if (mounted) _loadRecipeBook();
              },
            ),
            const SizedBox(height: 8),
            _EmptyStateCta(
              icon: Icons.camera_alt,
              label: 'Take a Photo',
              onTap: () async {
                await context.push('/recipes/add/photo', extra: {
                  'recipeBookId': bookId,
                });
                if (mounted) _loadRecipeBook();
              },
            ),
            const SizedBox(height: 8),
            _EmptyStateCta(
              icon: Icons.edit,
              label: 'Create Manually',
              onTap: () async {
                await context.push('/recipes/add/wizard', extra: {
                  'recipeBookId': bookId,
                });
                if (mounted) _loadRecipeBook();
              },
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      appBar: _isSelectMode
          ? AppBar(
              leading: IconButton(
                icon: const Icon(Icons.close),
                onPressed: _exitSelectMode,
              ),
              title: Text('${_selectedRecipeIds.length} selected'),
              actions: [
                IconButton(
                  icon: Icon(
                    _selectedRecipeIds.length == _recipes.length
                        ? Icons.deselect
                        : Icons.select_all,
                  ),
                  onPressed: () {
                    setState(() {
                      if (_selectedRecipeIds.length == _recipes.length) {
                        _selectedRecipeIds.clear();
                      } else {
                        _selectedRecipeIds.clear();
                        for (final recipe in _recipes) {
                          final id = recipe['id']?.toString();
                          if (id != null) _selectedRecipeIds.add(id);
                        }
                      }
                    });
                  },
                ),
              ],
            )
          : AppBar(
              title: _isShared
                  ? Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Flexible(
                          child: Text(
                            _recipeBook?['name'] ?? 'Recipe Book',
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        const SizedBox(width: 8),
                        Container(
                          width: 8,
                          height: 8,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: _wsConnected ? context.appColors.success : context.appColors.textDisabled,
                          ),
                        ),
                      ],
                    )
                  : Text(_recipeBook?['name'] ?? 'Recipe Book'),
              leading: IconButton(
                icon: const Icon(Icons.arrow_back),
                onPressed: () => context.pop(),
              ),
              actions: [
                if (_userRole == 'owner' || _userRole == 'editor')
                  IconButton(
                    icon: const Icon(Icons.ios_share),
                    tooltip: 'Share',
                    onPressed: _shareBook,
                  ),
                if (_isShared && _userRole == 'owner')
                  IconButton(
                    icon: const Icon(Icons.group),
                    tooltip: 'Members',
                    onPressed: () async {
                      await context.push(
                        '/recipe-books/${widget.recipeBookId}/members?role=$_userRole',
                      );
                    },
                  ),
                const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 4),
                  child: Center(child: RecipeListViewToggleButton()),
                ),
                if (_recipes.isNotEmpty && _userRole != 'viewer')
                  IconButton(
                    icon: const Icon(Icons.checklist),
                    onPressed: () => _enterSelectMode(),
                  ),
                if (_userRole != 'viewer')
                  PopupMenuButton<String>(
                    onSelected: (value) {
                      if (value == 'edit') {
                        _renameRecipeBook();
                      } else if (value == 'new_meal') {
                        _openCreateMealSheet(
                          initialComponents: const [],
                        );
                      } else if (value == 'import_url') {
                        context.push('/recipes/add/url', extra: {
                          'recipeBookId': widget.recipeBookId,
                        }).then((_) => _loadRecipeBook());
                      } else if (value == 'import_photo') {
                        context.push('/recipes/add/photo', extra: {
                          'recipeBookId': widget.recipeBookId,
                        }).then((_) => _loadRecipeBook());
                      } else if (value == 'bulk_import') {
                        context.push('/recipes/add/bulk-urls', extra: {
                          'recipeBookId': widget.recipeBookId,
                        }).then((_) => _loadRecipeBook());
                      } else if (value == 'archive') {
                        _archiveRecipeBook();
                      }
                    },
                    itemBuilder: (context) => [
                      // recipe-defaults-3: hide Edit on system books — the
                      // backend (recipe-defaults-1) returns 400 on PUT.
                      if (_recipeBook?['is_system'] != true)
                        const PopupMenuItem(
                          value: 'edit',
                          child: Row(
                            children: [
                              Icon(Icons.edit_outlined),
                              SizedBox(width: 8),
                              Text('Edit'),
                            ],
                          ),
                        ),
                      const PopupMenuItem(
                        value: 'new_meal',
                        child: Row(
                          children: [
                            Icon(Icons.set_meal_outlined),
                            SizedBox(width: 8),
                            Text('New Meal'),
                          ],
                        ),
                      ),
                      const PopupMenuItem(
                        value: 'import_url',
                        child: Row(
                          children: [
                            Icon(Icons.link),
                            SizedBox(width: 8),
                            Text('Import from URL'),
                          ],
                        ),
                      ),
                      const PopupMenuItem(
                        value: 'import_photo',
                        child: Row(
                          children: [
                            Icon(Icons.camera_alt),
                            SizedBox(width: 8),
                            Text('Import from Photo'),
                          ],
                        ),
                      ),
                      const PopupMenuItem(
                        value: 'bulk_import',
                        child: Row(
                          children: [
                            Icon(Icons.playlist_add),
                            SizedBox(width: 8),
                            Text('Bulk Import URLs'),
                          ],
                        ),
                      ),
                      // recipe-defaults-3: hide Archive on system books —
                      // backend returns 400.
                      if (_userRole == 'owner' &&
                          _recipeBook?['is_system'] != true)
                        PopupMenuItem(
                          value: 'archive',
                          child: Row(
                            children: [
                              Icon(Icons.archive_outlined, color: colorScheme.error),
                              const SizedBox(width: 8),
                              Text('Archive', style: TextStyle(color: colorScheme.error)),
                            ],
                          ),
                        ),
                    ],
                  ),
              ],
            ),
      floatingActionButton: _isSelectMode || _userRole == 'viewer'
          ? null
          : FloatingActionButton(
              heroTag: null, // avoid hero conflict during push to wizard
              onPressed: _addRecipe,
              child: const Icon(Icons.add),
            ),
      bottomNavigationBar: _isSelectMode && _selectedRecipeIds.isNotEmpty
          ? SafeArea(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                  children: [
                    _BulkActionButton(
                      icon: Icons.set_meal_outlined,
                      label: 'Create Meal',
                      onTap: (_selectedRecipeIds.length >= 2 &&
                              !_isBulkOperating)
                          ? _bulkCreateMeal
                          : null,
                    ),
                    _BulkActionButton(
                      icon: Icons.drive_file_move_outlined,
                      label: 'Move',
                      onTap: _isBulkOperating ? null : _bulkMove,
                    ),
                    _BulkActionButton(
                      icon: Icons.label_outlined,
                      label: 'Tags',
                      onTap: _isBulkOperating ? null : _bulkTags,
                    ),
                    _BulkActionButton(
                      icon: Icons.archive_outlined,
                      label: 'Archive',
                      color: colorScheme.error,
                      onTap: _isBulkOperating ? null : _bulkArchive,
                    ),
                  ],
                ),
              ),
            )
          : null,
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        ErrorBanner(message: _error!, detail: _errorDetail),
                        const SizedBox(height: 16),
                        ElevatedButton(
                          onPressed: _loadRecipeBook,
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _loadRecipeBook,
                  child: Center(
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 720),
                      child: ListView(
                        padding: const EdgeInsets.all(16),
                        children: [
                          // Description
                          if (_recipeBook?['description'] != null) ...[
                            Text(
                              _recipeBook!['description'],
                              style: textTheme.bodyLarge?.copyWith(
                                color: colorScheme.onSurfaceVariant,
                              ),
                            ),
                            const SizedBox(height: 16),
                          ],

                          // Recipes + meals header
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(
                                _meals.isEmpty
                                    ? 'Recipes (${_recipes.length})'
                                    : 'Recipes & Meals (${_recipes.length + _meals.length})',
                                style: textTheme.titleMedium,
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),

                          if (_mealsLoadFailed)
                            Padding(
                              padding: const EdgeInsets.only(bottom: 8),
                              child: ErrorBanner(
                                message:
                                    "Couldn't load meals in this book.",
                              ),
                            ),

                          // Vibe filter
                          VibeFilterBar(
                            selected: _vibeFilter,
                            onChanged: (v) => setState(() => _vibeFilter = v),
                          ),
                          const SizedBox(height: 8),

                          // Story 5: hide-in-meals chip + counter,
                          // visible only outside select mode so the
                          // bulk bar surface is unobstructed.
                          if (!_isSelectMode)
                            HideInMealsChip(
                              visibleCount:
                                  _filteredRecipesForRender().length,
                              hiddenCount: _hiddenInMealsCount(),
                              active: _hideInMeals,
                              onTap: () => setState(() {
                                _hideInMeals = !_hideInMeals;
                              }),
                            ),

                          // Grid — mixed recipe + meal tiles, sorted by
                          // updated_at DESC.
                          if (_recipes.isEmpty && _meals.isEmpty)
                            SizedBox(
                              height: MediaQuery.of(context).size.height * 0.4,
                              child: _buildBookEmptyState(),
                            )
                          else
                            Builder(
                              builder: (context) {
                                final filtered = _filteredRecipesForRender();
                                final mealsForRender = _vibeFilter == null
                                    ? _meals
                                    : const <MealSummary>[];
                                if (filtered.isEmpty &&
                                    mealsForRender.isEmpty &&
                                    _hideInMeals &&
                                    _hiddenInMealsCount() > 0) {
                                  return SizedBox(
                                    height: MediaQuery.of(context)
                                            .size
                                            .height *
                                        0.4,
                                    child: HideInMealsEmptyState(
                                      onShowAll: () => setState(() {
                                        _hideInMeals = false;
                                      }),
                                    ),
                                  );
                                }
                                final view =
                                    ref.watch(recipeListViewProvider);
                                if (view == RecipeListView.table) {
                                  return _buildMixedTable();
                                }
                                final columns =
                                    ResponsiveUtils.recipeGridColumns(context);
                                final cards = _buildMixedCards();

                                // rbv101: one layout for every column
                                // count, with a fixed main-axis extent
                                // so meals and recipes get identical
                                // boxes. The old single-column branch
                                // stacked cards in a plain `Column`,
                                // which let each card pick its own
                                // height, and the multi-column branch
                                // used an aspect ratio, so the cell
                                // height drifted with screen width.
                                return GridView(
                                  gridDelegate:
                                      SliverGridDelegateWithFixedCrossAxisCount(
                                    crossAxisCount: columns,
                                    crossAxisSpacing: 8,
                                    // Cards carry their own bottom
                                    // margin, so no extra main-axis gap.
                                    mainAxisSpacing: 0,
                                    mainAxisExtent: kMixedCardExtent,
                                  ),
                                  shrinkWrap: true,
                                  physics:
                                      const NeverScrollableScrollPhysics(),
                                  children: cards,
                                );
                              },
                            ),
                        ],
                      ),
                    ),
                  ),
                ),
    );
  }
}

/// Tiny discriminated-union-ish value for the mixed recipe/meal grid.
class _GridEntry {
  final Map<String, dynamic>? recipe;
  final MealSummary? meal;
  final DateTime updatedAt;

  _GridEntry.recipe(Map<String, dynamic> r, this.updatedAt)
      : recipe = r,
        meal = null;
  _GridEntry.meal(MealSummary m, this.updatedAt)
      : recipe = null,
        meal = m;

  bool get isRecipe => recipe != null;
}

/// Story 4: tight non-tappable column header rendered above book-
/// detail's table view. Mirrors home's `_DynamicColumnHeader` shape
/// minus the tap affordance — book detail has no sort menu, so
/// flipping direction has no UX surface here.
class _BookDetailColumnHeader extends StatelessWidget {
  final String label;

  const _BookDetailColumnHeader({required this.label});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
      child: Row(
        children: [
          const Spacer(),
          Text(
            label,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.4,
              color: colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(width: 4),
          Icon(
            Icons.arrow_downward,
            size: 14,
            color: colorScheme.onSurfaceVariant,
          ),
        ],
      ),
    );
  }
}

class _BulkActionButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color? color;
  final VoidCallback? onTap;

  const _BulkActionButton({
    required this.icon,
    required this.label,
    this.color,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final effectiveColor = color ?? Theme.of(context).colorScheme.primary;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: onTap != null ? effectiveColor : effectiveColor.withValues(alpha: 0.4)),
            const SizedBox(height: 4),
            Text(
              label,
              style: TextStyle(
                fontSize: 12,
                color: onTap != null ? effectiveColor : effectiveColor.withValues(alpha: 0.4),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _EmptyStateCta extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  const _EmptyStateCta({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return SizedBox(
      width: double.infinity,
      child: OutlinedButton.icon(
        onPressed: onTap,
        icon: Icon(icon, size: 18),
        label: Text(label),
        style: OutlinedButton.styleFrom(
          foregroundColor: colorScheme.primary,
          side: BorderSide(color: colorScheme.outlineVariant),
          padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
    );
  }
}
