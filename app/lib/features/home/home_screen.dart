import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/state/mutation_failure_copy.dart';
import '../../core/state/mutation_snackbar.dart';
import '../recipes/providers/recipe_provider.dart';
import '../recipes/services/recipe_service.dart';
import '../../shared/widgets/buttons.dart';
import '../../shared/widgets/empty_state.dart';
import '../../shared/widgets/shimmer_loading.dart';
import '../recipes/add_recipe/add_recipe_sheet.dart';
import '../meals/models/meal.dart';
import '../meals/providers/meals_provider.dart';
import '../meals/services/meal_service.dart';
import '../meals/widgets/create_meal_sheet.dart';
import '../meals/widgets/meal_tile.dart';
import 'providers/home_content_provider.dart';
import 'widgets/batch_import_status_widget.dart';
import 'widgets/bulk_dispatcher.dart';
import 'widgets/bulk_partial_failure_dialog.dart';
import 'widgets/filter_bottom_sheet.dart';
import 'widgets/filter_pill.dart';
import 'widgets/home_bulk_action_bar.dart';
import 'widgets/home_selection_controller.dart';
import 'widgets/meal_filter_bar.dart';
import 'widgets/selection_app_bar.dart';
import '../../core/theme/theme.dart';
import 'widgets/recipe_card.dart';
import '../../core/services/error_reporter.dart';
import '../../shared/widgets/error_banner.dart';

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  /// rf-3: `_allRecipes`, `_allMeals`, `_favorites`, `_favoriteIds`,
  /// `_favoriteMealIds`, `_todayMealEvent`, `_recentlyCooked` are mirrors
  /// of the pristine data `homeContentProvider` emits. They're kept as
  /// local state so the existing optimistic-mutation paths (favorite,
  /// bulk-archive, meal-favorite) can patch them in-place without waiting
  /// for a refetch — per epic Locked Decision #6 (reconcile-only: old
  /// optimistic paths stay). Filter/sort state stays local too (pfc-4
  /// guarantee — filter flips do not refetch).
  List<dynamic> _recipes = [];
  List<dynamic> _allRecipes = [];
  List<dynamic> _allMeals = [];
  List<dynamic> _favorites = [];
  Set<String> _favoriteIds = {};
  Set<String> _favoriteMealIds = {};
  final Set<String> _togglingFavoriteIds = {};
  bool _isBulkOperating = false;

  /// True once the first [HomeContent] frame has been copied into local
  /// state. Guards the loading-flicker path — during an `invalidateSelf`
  /// refetch we keep the stale grid visible rather than flashing to the
  /// skeleton (epic AC #5).
  bool _hasContent = false;

  MealFilter _mealFilter = MealFilter.all;
  String? _vibeFilter;
  SortOption _sortOption = SortOption.best;
  ShowTypeFilter _showTypeFilter = ShowTypeFilter.all;
  bool _hideComponentsOfMeals = false;

  dynamic _todayMealEvent;
  List<dynamic> _recentlyCooked = [];

  /// Copy the freshest [HomeContent] into local state and reapply
  /// filters. Called from `ref.listen` in `build()` — fires once per new
  /// `AsyncData`, and is idempotent on identical content (Riverpod emits
  /// one `AsyncData` per fetch, not per watch).
  void _applyHomeContent(HomeContent content) {
    if (!mounted) return;
    setState(() {
      _allRecipes = content.recipes;
      _allMeals = content.meals;
      _favorites = List<dynamic>.from(content.favorites);
      _favoriteIds = Set<String>.from(content.favoriteIds);
      _favoriteMealIds = Set<String>.from(content.favoriteMealIds);
      _todayMealEvent = content.todayMealEvent;
      _recentlyCooked = List<dynamic>.from(content.recentlyCooked);
      _recipes = _buildFilteredGrid(_allRecipes, _allMeals);
      _hasContent = true;
    });
  }

  /// Merge recipes + meals for the grid. Zero-meal → recipes unchanged
  /// (load-bearing zero-regression guarantee). Non-empty → union sorted
  /// by `updated_at DESC` per the epic.
  List<dynamic> _mergeRecipesAndMeals(
    List<dynamic> recipes,
    List<dynamic> meals,
  ) {
    if (meals.isEmpty) return recipes;
    final merged = <dynamic>[...recipes, ...meals];
    merged.sort((a, b) {
      final aUpdated = (a['updated_at'] ?? '').toString();
      final bUpdated = (b['updated_at'] ?? '').toString();
      return bUpdated.compareTo(aUpdated);
    });
    return merged;
  }

  MealSummary _mealSummaryFrom(dynamic item) {
    final map = Map<String, dynamic>.from(item as Map);
    return MealSummary.fromJson(map);
  }

  /// In-memory recipeId → name map built from the home's loaded recipe
  /// list. Passed into `MealTile` so the component-chips row resolves
  /// names client-side without an N+1 detail fetch (hmp-1 / escape
  /// hatch for the missing `component_recipe_ids` field — shipped
  /// here additively).
  String? _resolveComponentName(String recipeId) {
    for (final r in _recipes) {
      if (r is Map && r['kind'] == 'recipe') {
        if (r['id']?.toString() == recipeId) {
          final name = r['name']?.toString();
          return (name == null || name.isEmpty) ? null : name;
        }
      }
    }
    return null;
  }

  Future<void> _toggleMealFavorite(MealSummary meal) async {
    final mealId = meal.id;
    if (_togglingFavoriteIds.contains(mealId)) return;
    _togglingFavoriteIds.add(mealId);
    final wasFav = _favoriteMealIds.contains(mealId);

    // Optimistic update — flip the id set and sync the favorites
    // carousel so the heart icon + carousel chip both update in one
    // frame.
    setState(() {
      if (wasFav) {
        _favoriteMealIds.remove(mealId);
        _favorites.removeWhere((f) =>
            f is Map && f['kind'] == 'meal' && f['id']?.toString() == mealId);
      } else {
        _favoriteMealIds.add(mealId);
        final existing = _recipes.firstWhere(
          (r) =>
              r is Map && r['kind'] == 'meal' && r['id']?.toString() == mealId,
          orElse: () => null,
        );
        if (existing is Map) {
          _favorites.insert(0, Map<String, dynamic>.from(existing));
        }
      }
    });

    try {
      final mealService = getIt<MealService>();
      if (wasFav) {
        await mealService.unfavoriteMeal(mealId, bookId: meal.recipeBookId);
      } else {
        await mealService.favoriteMeal(mealId, bookId: meal.recipeBookId);
      }
    } catch (_) {
      if (!mounted) return;
      setState(() {
        if (wasFav) {
          _favoriteMealIds.add(mealId);
        } else {
          _favoriteMealIds.remove(mealId);
          _favorites.removeWhere((f) =>
              f is Map && f['kind'] == 'meal' && f['id']?.toString() == mealId);
        }
      });
    } finally {
      _togglingFavoriteIds.remove(mealId);
    }
  }

  Future<void> _toggleFavorite(dynamic recipe) async {
    final recipeId = recipe['id']?.toString();
    if (recipeId == null) return;
    if (_togglingFavoriteIds.contains(recipeId)) return;
    _togglingFavoriteIds.add(recipeId);

    // Optimistic update
    final wasFavorite = _favoriteIds.contains(recipeId);
    setState(() {
      recipe['is_favorite'] = !wasFavorite;
      if (wasFavorite) {
        _favoriteIds.remove(recipeId);
        _favorites.removeWhere((f) => f['id']?.toString() == recipeId);
      } else {
        _favoriteIds.add(recipeId);
        _favorites.insert(0, recipe);
      }
    });

    try {
      await getIt<RecipeService>().toggleFavorite(recipeId);
      // pfc-3: bust cached recipe payload so detail reopen sees new flag.
      invalidateRecipe(ref, recipeId);
    } catch (_) {
      // Revert on failure
      if (mounted) {
        setState(() {
          recipe['is_favorite'] = wasFavorite;
          if (wasFavorite) {
            _favoriteIds.add(recipeId);
            _favorites.insert(0, recipe);
          } else {
            _favoriteIds.remove(recipeId);
            _favorites.removeWhere((f) => f['id']?.toString() == recipeId);
          }
        });
        showMutationFailureSnackbar(
          context,
          wasFavorite
              ? MutationType.unfavoriteRecipe
              : MutationType.favoriteRecipe,
          () => _toggleFavorite(recipe),
        );
      }
    } finally {
      _togglingFavoriteIds.remove(recipeId);
    }
  }

  List<dynamic> _applyFilters(List<dynamic> recipes) {
    var filtered = recipes;

    if (_mealFilter != MealFilter.all) {
      final mealName = _mealFilter.name;
      filtered = filtered.where((r) {
        final meal = r['meal_type']?.toString().toLowerCase();
        return meal == mealName;
      }).toList();
    }

    if (_vibeFilter != null) {
      filtered = filtered.where((r) {
        return r['primary_vibe'] == _vibeFilter ||
            r['secondary_vibe'] == _vibeFilter;
      }).toList();
    }

    return filtered;
  }

  /// hmp-4: client-side kind filters applied to the merged grid.
  /// `showType` filters out the wrong kind; `hideComponentsOfMeals`
  /// hides any recipe whose id is in a Meal's component list. Meals
  /// are never hidden by the hide-components toggle.
  List<dynamic> _applyKindFilters(
    List<dynamic> items,
    List<dynamic> meals,
  ) {
    var filtered = items;
    if (_showTypeFilter == ShowTypeFilter.recipesOnly) {
      filtered = filtered
          .where((i) => !(i is Map && i['kind'] == 'meal'))
          .toList();
    } else if (_showTypeFilter == ShowTypeFilter.mealsOnly) {
      filtered = filtered
          .where((i) => i is Map && i['kind'] == 'meal')
          .toList();
    }
    if (_hideComponentsOfMeals) {
      final componentIds = <String>{};
      for (final m in meals) {
        if (m is! Map) continue;
        final ids = (m['component_recipe_ids'] as List?) ?? const [];
        for (final id in ids) {
          componentIds.add(id.toString());
        }
      }
      filtered = filtered.where((i) {
        if (i is! Map) return true;
        if (i['kind'] == 'meal') return true;
        final id = i['id']?.toString();
        return id == null || !componentIds.contains(id);
      }).toList();
    }
    return filtered;
  }

  List<dynamic> _applySorting(List<dynamic> recipes) {
    final sorted = List<dynamic>.from(recipes);
    switch (_sortOption) {
      case SortOption.best:
        sorted.sort((a, b) =>
            (b['times_cooked'] ?? 0).compareTo(a['times_cooked'] ?? 0));
        break;
      case SortOption.newest:
        sorted.sort((a, b) =>
            (b['created_at'] ?? '').compareTo(a['created_at'] ?? ''));
        break;
      case SortOption.popular:
        sorted.sort(
            (a, b) => (b['popularity'] ?? 0).compareTo(a['popularity'] ?? 0));
        break;
      case SortOption.quickest:
        sorted.sort((a, b) {
          final aTime = (a['prep_time'] ?? 0) + (a['cook_time'] ?? 0);
          final bTime = (b['prep_time'] ?? 0) + (b['cook_time'] ?? 0);
          return aTime.compareTo(bTime);
        });
        break;
      case SortOption.random:
        sorted.shuffle();
        break;
    }
    return sorted;
  }

  Future<void> _openFilterSheet() async {
    HapticFeedback.selectionClick();
    final preState = HomeFilterState(
      meal: _mealFilter,
      vibe: _vibeFilter,
      sort: _sortOption,
      showType: _showTypeFilter,
      hideComponentsOfMeals: _hideComponentsOfMeals,
    );
    await FilterBottomSheet.show(
      context: context,
      initialState: preState,
      onApply: (state) {
        final clearedAll = !preState.isDefault && state.isDefault;
        setState(() {
          _mealFilter = state.meal;
          _vibeFilter = state.vibe;
          _sortOption = state.sort;
          _showTypeFilter = state.showType;
          _hideComponentsOfMeals = state.hideComponentsOfMeals;
          _recipes = _applySorting(List.from(_recipes));
        });
        _reapplyFilters();
        if (clearedAll) _showClearAllUndo(preState);
      },
    );
  }

  void _showClearAllUndo(HomeFilterState restoreTo) {
    final messenger = ScaffoldMessenger.of(context);
    messenger.hideCurrentSnackBar();
    messenger.showSnackBar(
      SnackBar(
        duration: const Duration(seconds: 3),
        content: const Text('Sort & filters cleared'),
        action: SnackBarAction(
          label: 'Undo',
          onPressed: () {
            if (!mounted) return;
            setState(() {
              _mealFilter = restoreTo.meal;
              _vibeFilter = restoreTo.vibe;
              _sortOption = restoreTo.sort;
              _showTypeFilter = restoreTo.showType;
              _hideComponentsOfMeals = restoreTo.hideComponentsOfMeals;
              _recipes = _applySorting(List.from(_recipes));
            });
            _reapplyFilters();
          },
        ),
      ),
    );
  }

  /// pfc-4: rebuild `_recipes` from the pristine `_allRecipes` +
  /// `_allMeals` in-memory. No network. Filters + sort + merge +
  /// kind-filters run top-to-bottom so a flip of any filter state is
  /// zero-network regardless of which dial the user touched.
  List<dynamic> _buildFilteredGrid(
    List<dynamic> sourceRecipes,
    List<dynamic> sourceMeals,
  ) {
    var recipes = _applyFilters(sourceRecipes);
    recipes = _applySorting(recipes);
    var merged = _mergeRecipesAndMeals(recipes, sourceMeals);
    merged = _applyKindFilters(merged, sourceMeals);
    return merged;
  }

  /// pfc-4: in-memory rebuild. Filter flips never refetch — network
  /// reloads come from [homeContentProvider] (initial fetch + pull-to-
  /// refresh + MutationBus-driven invalidations).
  void _reapplyFilters() {
    if (!mounted) return;
    setState(() {
      _recipes = _buildFilteredGrid(_allRecipes, _allMeals);
    });
  }

  void _showAddRecipeSheet() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => const AddRecipeSheet(),
    );
  }

  void _quickStartCooking(dynamic recipe) {
    context.push('/recipes/${recipe['id']}/cook');
  }

  @override
  Widget build(BuildContext context) {
    // rf-3: mirror the provider's latest AsyncData into local state.
    // Runs once per fresh fetch; Riverpod's `ref.listen` fires for the
    // initial loading→data transition too, so no synchronous bootstrap
    // is needed (which would have risked a `setState` during build).
    ref.listen<AsyncValue<HomeContent>>(homeContentProvider,
        (_, next) => next.whenData(_applyHomeContent));

    final selection = ref.watch(homeSelectionProvider);
    // Keep the selection set in sync with the loaded recipe/meal ids —
    // anything that vanished mid-session (archived elsewhere, unshared
    // book) is dropped silently. If the whole selection goes away, surf
    // a brief "content changed" note.
    WidgetsBinding.instance.addPostFrameCallback((_) => _reconcileSelection());

    final selectedMealName = _selectedMealName(selection);

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            if (selection.isActive)
              const SelectionAppBar()
            else
              _buildSearchHeader(),

            // Contextual sections — capped to ensure recipe grid always gets space
            if (!selection.isActive &&
                (_todayMealEvent != null || _recentlyCooked.isNotEmpty))
              ConstrainedBox(
                constraints: BoxConstraints(
                  maxHeight: MediaQuery.of(context).size.height * 0.42,
                ),
                child: SingleChildScrollView(
                  physics: const NeverScrollableScrollPhysics(),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      if (_todayMealEvent != null) _buildHeroCard(),
                      if (_recentlyCooked.isNotEmpty) _buildRecentlyCookedSection(),
                    ],
                  ),
                ),
              ),

            // Batch Import Status
            if (!selection.isActive) const BatchImportStatusWidget(),

            // Favorites Section
            if (!selection.isActive && _favorites.isNotEmpty)
              _buildFavoritesSection(),

            // Recipe Grid
            Expanded(
              child: _buildRecipeGrid(),
            ),
          ],
        ),
      ),
      floatingActionButton: selection.isActive
          ? null
          : FloatingActionButton(
              onPressed: _showAddRecipeSheet,
              child: const Icon(Icons.add),
            ),
      bottomNavigationBar: selection.isActive
          ? HomeBulkActionBar(
              selectedMealName: selectedMealName,
              isWorking: _isBulkOperating,
              onCreateMeal: _handleCreateMeal,
              onAddToMeal: _handleAddToMeal,
              onArchive: _handleArchive,
            )
          : null,
    );
  }

  /// Look up the display name of the selection's single Meal (if the
  /// selection holds exactly one). Home owns the meal list, so this is
  /// the cleanest place to resolve the name for the bulk bar.
  String? _selectedMealName(HomeSelectionState selection) {
    if (selection.selectedMealIds.length != 1) return null;
    final id = selection.selectedMealIds.first;
    for (final item in _recipes) {
      if (item is Map &&
          item['kind'] == 'meal' &&
          item['id']?.toString() == id) {
        return item['name']?.toString();
      }
    }
    return null;
  }

  void _reconcileSelection() {
    if (!mounted) return;
    final controller = ref.read(homeSelectionProvider.notifier);
    final knownRecipes = <String>{};
    final knownMeals = <String>{};
    for (final item in _recipes) {
      if (item is Map) {
        final id = item['id']?.toString();
        if (id == null) continue;
        if (item['kind'] == 'meal') {
          knownMeals.add(id);
        } else {
          knownRecipes.add(id);
        }
      }
    }
    final emptied = controller.reconcile(
      knownRecipeIds: knownRecipes,
      knownMealIds: knownMeals,
    );
    if (emptied) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Selection cleared — content changed'),
        ),
      );
    }
  }

  // ---------------------------------------------------------------------
  // Bulk-action handlers. hmp-3 wires the three real dispatches:
  //   • Create Meal  → opens CreateMealSheet pre-filled with the
  //     selection's recipes + the first-selected recipe's book.
  //   • Add to Meal  → client-side dedup against the target Meal's
  //     component ids, parallel addRecipeToMeal, partial-failure
  //     snackbar + dialog.
  //   • Archive      → confirmation dialog, parallel bulkArchiveRecipes
  //     + per-Meal archiveMeal, same partial-failure surface.
  // ---------------------------------------------------------------------

  dynamic _findRecipe(String recipeId) {
    for (final r in _recipes) {
      if (r is Map &&
          r['kind'] == 'recipe' &&
          r['id']?.toString() == recipeId) {
        return r;
      }
    }
    return null;
  }

  dynamic _findMealItem(String mealId) {
    for (final r in _recipes) {
      if (r is Map &&
          r['kind'] == 'meal' &&
          r['id']?.toString() == mealId) {
        return r;
      }
    }
    return null;
  }

  Future<void> _handleCreateMeal() async {
    if (_isBulkOperating) return;
    final selection = ref.read(homeSelectionProvider);
    final recipeIds = selection.selectedRecipeIds.toList();
    if (recipeIds.length < 2) return;

    final components = <DraftMealComponent>[];
    String? bookId;
    String? bookName;
    for (final id in recipeIds) {
      final match = _findRecipe(id);
      if (match is! Map) continue;
      bookId ??= match['recipe_book_id']?.toString();
      bookName ??= match['recipe_book_name']?.toString();
      components.add(DraftMealComponent(
        recipeId: id,
        name: match['name']?.toString() ?? '',
        imageUrl: match['image_url']?.toString(),
        bookName: match['recipe_book_name']?.toString(),
      ));
    }
    if (bookId == null || bookName == null || components.length < 2) return;

    await CreateMealSheet.show(
      context,
      bookId: bookId,
      bookName: bookName,
      initialComponents: components,
      onCreated: (meal) {
        invalidateMeal(ref, meal.id, bookId: meal.recipeBookId);
        ref.read(homeSelectionProvider.notifier).exit();
        ref.invalidate(homeContentProvider);
      },
    );
  }

  Future<void> _handleAddToMeal() async {
    if (_isBulkOperating) return;
    final selection = ref.read(homeSelectionProvider);
    if (selection.selectedMealIds.length != 1) return;
    final mealId = selection.selectedMealIds.first;
    final recipeIds = selection.selectedRecipeIds.toList();
    if (recipeIds.isEmpty) return;

    final mealItem = _findMealItem(mealId);
    if (mealItem is! Map) return;
    final meal = _mealSummaryFrom(mealItem);
    final mealName = meal.name;

    final existing = meal.componentRecipeIds.toSet();
    final toAdd = recipeIds.where((id) => !existing.contains(id)).toList();
    if (toAdd.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('All selected recipes are already in this Meal'),
        ),
      );
      ref.read(homeSelectionProvider.notifier).exit();
      return;
    }

    final mealService = getIt<MealService>();
    final targets = toAdd.map((rid) {
      final match = _findRecipe(rid);
      final name = (match is Map) ? (match['name']?.toString() ?? rid) : rid;
      return _AddToMealTarget(rid, name);
    }).toList();

    setState(() => _isBulkOperating = true);
    try {
      final results = await runBulkOperations<_AddToMealTarget>(
        items: targets,
        operation: (t) async {
          await mealService.addRecipeToMeal(mealId, recipeId: t.recipeId);
        },
        nameOf: (t) => t.name,
        bulkOp: BulkOperation.addToMeal,
      );
      if (!mounted) return;
      final successes = results.where((r) => r.success).length;
      final total = results.length;
      _surfaceBulkResult(
        results: results,
        operation: BulkOperation.addToMeal,
        total: total,
        successes: successes,
        allSuccessMessage:
            'Added $successes ${successes == 1 ? 'recipe' : 'recipes'} '
            'to $mealName',
        partialMessage: 'Added $successes of $total — see details',
        allFailMessage: 'Could not add recipes — see details',
      );
      invalidateMeal(ref, mealId, bookId: meal.recipeBookId);
      ref.read(homeSelectionProvider.notifier).exit();
      ref.invalidate(homeContentProvider);
    } finally {
      if (mounted) setState(() => _isBulkOperating = false);
    }
  }

  Future<void> _handleArchive() async {
    if (_isBulkOperating) return;
    final selection = ref.read(homeSelectionProvider);
    final recipeIds = selection.selectedRecipeIds.toList();
    final mealIds = selection.selectedMealIds.toList();
    final totalCount = recipeIds.length + mealIds.length;
    if (totalCount == 0) return;

    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Archive selected?'),
        content: Text(_archivePromptBody(
          recipeCount: recipeIds.length,
          mealCount: mealIds.length,
        )),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Archive'),
          ),
        ],
      ),
    );
    if (confirm != true) return;
    if (!mounted) return;

    setState(() => _isBulkOperating = true);
    try {
      final futures = <Future<List<BulkOperationResult>>>[];
      if (recipeIds.isNotEmpty) {
        futures.add(_runRecipeBulkArchive(recipeIds));
      }
      if (mealIds.isNotEmpty) {
        final mealTargets = mealIds.map((id) {
          final item = _findMealItem(id);
          final name = (item is Map) ? (item['name']?.toString() ?? id) : id;
          final bookId = (item is Map)
              ? (item['recipe_book_id']?.toString() ?? '')
              : '';
          return _ArchiveMealTarget(id, name, bookId);
        }).toList();
        final mealService = getIt<MealService>();
        futures.add(runBulkOperations<_ArchiveMealTarget>(
          items: mealTargets,
          operation: (t) =>
              mealService.archiveMeal(t.mealId, bookId: t.bookId),
          nameOf: (t) => t.name,
          bulkOp: BulkOperation.archive,
        ));
      }
      final nested = await Future.wait(futures);
      final allResults = <BulkOperationResult>[
        for (final list in nested) ...list,
      ];
      if (!mounted) return;
      final successes = allResults.where((r) => r.success).length;
      final total = allResults.length;
      _surfaceBulkResult(
        results: allResults,
        operation: BulkOperation.archive,
        total: total,
        successes: successes,
        allSuccessMessage:
            'Archived $successes ${successes == 1 ? 'item' : 'items'}',
        partialMessage: 'Archived $successes of $total — see details',
        allFailMessage: 'Could not archive — see details',
      );
      ref.read(homeSelectionProvider.notifier).exit();
      ref.invalidate(homeContentProvider);
    } finally {
      if (mounted) setState(() => _isBulkOperating = false);
    }
  }

  String _archivePromptBody({
    required int recipeCount,
    required int mealCount,
  }) {
    String recipeLabel() =>
        recipeCount == 1 ? '1 recipe' : '$recipeCount recipes';
    String mealLabel() => mealCount == 1 ? '1 Meal' : '$mealCount Meals';
    const tail = 'You can restore them later from Archive.';
    if (recipeCount == 0) return 'Archive ${mealLabel()}? $tail';
    if (mealCount == 0) return 'Archive ${recipeLabel()}? $tail';
    return 'Archive ${recipeLabel()} and ${mealLabel()}? $tail';
  }

  /// Recipe bulk archive is a single atomic API call; the dialog still
  /// needs per-recipe rows so this synthesises one BulkOperationResult
  /// per recipe with the same outcome.
  Future<List<BulkOperationResult>> _runRecipeBulkArchive(
    List<String> recipeIds,
  ) async {
    final names = <String, String>{};
    for (final id in recipeIds) {
      final item = _findRecipe(id);
      names[id] = (item is Map) ? (item['name']?.toString() ?? id) : id;
    }
    // The selection may span multiple books; derive the best-guess
    // anchor from the first recipe so subscribers that scope by book
    // see a coherent event. Home uses the type-level filter anyway
    // (coarse-key rule).
    final first = recipeIds.isEmpty ? null : _findRecipe(recipeIds.first);
    final bookId = (first is Map)
        ? (first['recipe_book_id']?.toString() ?? '')
        : '';
    try {
      await getIt<RecipeService>().bulkArchiveRecipes(
        recipeIds,
        bookId: bookId,
      );
      // pfc-3: drop each archived recipe's cached detail payload.
      for (final id in recipeIds) {
        invalidateRecipe(ref, id);
      }
      return [
        for (final id in recipeIds)
          BulkOperationResult(targetName: names[id]!, success: true),
      ];
    } catch (e) {
      final reason = explainBulkError(e, BulkOperation.archive);
      return [
        for (final id in recipeIds)
          BulkOperationResult(
            targetName: names[id]!,
            success: false,
            errorReason: reason,
          ),
      ];
    }
  }

  void _surfaceBulkResult({
    required List<BulkOperationResult> results,
    required BulkOperation operation,
    required int total,
    required int successes,
    required String allSuccessMessage,
    required String partialMessage,
    required String allFailMessage,
  }) {
    final messenger = ScaffoldMessenger.of(context);
    messenger.hideCurrentSnackBar();
    if (successes == total) {
      messenger.showSnackBar(SnackBar(content: Text(allSuccessMessage)));
      return;
    }
    final body = successes > 0 ? partialMessage : allFailMessage;
    messenger.showSnackBar(SnackBar(
      content: Text(body),
      action: SnackBarAction(
        label: 'View',
        onPressed: () => BulkPartialFailureDialog.show(
          context,
          operation: operation,
          results: results,
        ),
      ),
    ));
  }

  Widget _buildSearchHeader() {
    final colorScheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
      child: Row(
        children: [
          // Recipe Books button — primary "where do I go" destination, sits
          // to the left of the search bar so it's the first thing thumb hits.
          CircleIconButton(
            icon: Icons.menu_book_outlined,
            onPressed: () => context.push('/recipe-books'),
            backgroundColor: colorScheme.surfaceContainerHighest,
            tooltip: 'Recipe Books',
          ),
          const SizedBox(width: 12),

          // Search Field
          Expanded(
            child: GestureDetector(
              onTap: () => context.push('/search'),
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                decoration: BoxDecoration(
                  color: colorScheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  children: [
                    Icon(Icons.search, color: colorScheme.onSurfaceVariant, size: 20),
                    const SizedBox(width: 12),
                    Text(
                      'Search recipes...',
                      style: TextStyle(color: colorScheme.onSurfaceVariant),
                    ),
                  ],
                ),
              ),
            ),
          ),
          const SizedBox(width: 12),

          // Nav group: destinations the user can jump to.
          // Pantry Button
          CircleIconButton(
            icon: Icons.kitchen_outlined,
            onPressed: () => context.push('/pantry'),
            backgroundColor: colorScheme.surfaceContainerHighest,
            tooltip: 'Pantry',
          ),
          const SizedBox(width: 8),

          // Sort & filter funnel — consolidated sort + filter
          // behind one icon + bottom sheet (bugs-home-2).
          FilterPill(
            isActive: !HomeFilterState(
              meal: _mealFilter,
              vibe: _vibeFilter,
              sort: _sortOption,
              showType: _showTypeFilter,
              hideComponentsOfMeals: _hideComponentsOfMeals,
            ).isDefault,
            onTap: _openFilterSheet,
          ),
        ],
      ),
    );
  }


  Widget _buildFavoritesSection() {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
          child: Row(
            children: [
              Icon(Icons.favorite, size: 18, color: AppColors.favorite),
              const SizedBox(width: 8),
              Text(
                'Favorites',
                style: textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
        SizedBox(
          height: 140,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            itemCount: _favorites.length,
            separatorBuilder: (_, __) => const SizedBox(width: 12),
            itemBuilder: (context, index) {
              final item = _favorites[index];
              final isMeal = item is Map && item['kind'] == 'meal';
              // md-4: Meals use their first component image as the carousel
              // thumbnail. Falling back to a restaurant icon keeps the tile
              // from collapsing when a Meal has no image-bearing components.
              final imageUrl = isMeal
                  ? (((item['component_image_urls'] as List?) ?? []).isNotEmpty
                      ? (item['component_image_urls'] as List).first as String?
                      : null)
                  : item['image_url'];
              final name = item['name'] ?? 'Untitled';

              return GestureDetector(
                onTap: () {
                  final id = item['id'];
                  if (isMeal) {
                    context.push('/meals/$id');
                  } else {
                    context.push('/recipes/$id');
                  }
                },
                child: SizedBox(
                  width: 120,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      ClipRRect(
                        borderRadius: BorderRadius.circular(12),
                        child: SizedBox(
                          height: 100,
                          width: 120,
                          child: imageUrl != null
                              ? CachedNetworkImage(
                                  imageUrl: imageUrl,
                                  fit: BoxFit.cover,
                                  placeholder: (context, url) => const Center(child: CircularProgressIndicator(strokeWidth: 2)),
                                  errorWidget: (context, url, error) => Container(
                                    color: colorScheme.surfaceContainerHighest,
                                    child: Icon(Icons.restaurant,
                                        color: colorScheme.onSurfaceVariant),
                                  ),
                                )
                              : Container(
                                  color: colorScheme.surfaceContainerHighest,
                                  child: Icon(Icons.restaurant,
                                      color: colorScheme.onSurfaceVariant),
                                ),
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        name,
                        style: textTheme.bodySmall?.copyWith(
                          fontWeight: FontWeight.w500,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
        Divider(color: colorScheme.outlineVariant, height: 1),
      ],
    );
  }

  Widget _buildHeroCard() {
    final colorScheme = Theme.of(context).colorScheme;
    final recipe = _todayMealEvent!['recipe'];
    final imageUrl = recipe['image_url'] as String?;
    final name = recipe['name'] as String? ?? 'Tonight\'s Recipe';
    final prepTime = recipe['prep_time'] as int? ?? 0;
    final cookTime = recipe['cook_time'] as int? ?? 0;
    final totalMinutes = prepTime + cookTime;

    return SizedBox(
      height: 220,
      width: double.infinity,
      child: Stack(
          fit: StackFit.expand,
          children: [
            // Background image or placeholder
            imageUrl != null
                ? CachedNetworkImage(
                    imageUrl: imageUrl,
                    fit: BoxFit.cover,
                    placeholder: (context, url) => const Center(child: CircularProgressIndicator(strokeWidth: 2)),
                    errorWidget: (context, url, error) => Container(
                      color: colorScheme.surfaceContainerHighest,
                      child: Icon(Icons.restaurant,
                          size: 64, color: colorScheme.onSurfaceVariant),
                    ),
                  )
                : Container(
                    color: colorScheme.surfaceContainerHighest,
                    child: Icon(Icons.restaurant,
                        size: 64, color: colorScheme.onSurfaceVariant),
                  ),

            // Gradient overlay
            DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [
                    Colors.transparent,
                    colorScheme.onSurface.withValues(alpha: 0.7),
                  ],
                  stops: const [0.4, 1.0],
                ),
              ),
            ),

            // Recipe name and CTA
            Positioned(
              left: 16,
              right: 16,
              bottom: 16,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    name,
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.bold,
                      color: const Color(0xFFFFFFFF),
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (totalMinutes > 0) ...[
                    const SizedBox(height: 6),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: const Color(0xFFFFFFFF).withValues(alpha: 0.25),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        '$totalMinutes min',
                        style: const TextStyle(
                          color: Color(0xFFFFFFFF),
                          fontSize: 12,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                  ],
                  const SizedBox(height: 10),
                  FilledButton(
                    onPressed: () => _quickStartCooking(recipe),
                    child: const Text('Start Cooking'),
                  ),
                ],
              ),
            ),
          ],
        ),
    );
  }

  Widget _buildRecentlyCookedSection() {
    final textTheme = Theme.of(context).textTheme;
    final colorScheme = Theme.of(context).colorScheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
          child: Text(
            'Recently Cooked',
            style: textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
          ),
        ),
        SizedBox(
          height: 110,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            itemCount: _recentlyCooked.length,
            separatorBuilder: (_, __) => const SizedBox(width: 10),
            itemBuilder: (context, index) {
              final item = _recentlyCooked[index];
              final imageUrl = item['recipe_image_url'] as String?;
              final name = item['recipe_name'] as String? ?? 'Recipe';
              final cookedAt = item['cooked_at'] as String?;
              final dateLabel = _formatRelativeDate(cookedAt);

              return GestureDetector(
                onTap: () => context.push('/recipes/${item['recipe_id']}'),
                child: SizedBox(
                  width: 80,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      ClipRRect(
                        borderRadius: BorderRadius.circular(10),
                        child: SizedBox(
                          height: 72,
                          width: 80,
                          child: imageUrl != null
                              ? CachedNetworkImage(
                                  imageUrl: imageUrl,
                                  fit: BoxFit.cover,
                                  placeholder: (context, url) => const Center(child: CircularProgressIndicator(strokeWidth: 2)),
                                  errorWidget: (context, url, error) => Container(
                                    color: colorScheme.surfaceContainerHighest,
                                    child: Icon(Icons.restaurant,
                                        size: 28,
                                        color: colorScheme.onSurfaceVariant),
                                  ),
                                )
                              : Container(
                                  color: colorScheme.surfaceContainerHighest,
                                  child: Icon(Icons.restaurant,
                                      size: 28,
                                      color: colorScheme.onSurfaceVariant),
                                ),
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        name,
                        style: textTheme.bodySmall
                            ?.copyWith(fontWeight: FontWeight.w500),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      Text(
                        dateLabel,
                        style: textTheme.bodySmall?.copyWith(
                          color: colorScheme.onSurfaceVariant,
                          fontSize: 10,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
        Divider(color: colorScheme.outlineVariant, height: 1),
      ],
    );
  }

  String _formatRelativeDate(String? isoDate) {
    if (isoDate == null) return '';
    try {
      final dt = DateTime.parse(isoDate);
      final diff = DateTime.now().difference(dt);
      if (diff.inDays == 0) return 'Today';
      if (diff.inDays == 1) return 'Yesterday';
      if (diff.inDays < 7) return '${diff.inDays} days ago';
      if (diff.inDays < 30) return '${(diff.inDays / 7).floor()} wk ago';
      return '${(diff.inDays / 30).floor()} mo ago';
    } catch (_) {
      return '';
    }
  }

  Widget _buildRecipeGrid() {
    final async = ref.watch(homeContentProvider);
    // rf-3 AC #5: while refetching, keep showing the stale grid rather
    // than flashing to the skeleton. Only show the shimmer before the
    // very first content frame lands.
    if (async.isLoading && !_hasContent) {
      return GridView.builder(
        padding: const EdgeInsets.all(16),
        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: 2,
          mainAxisSpacing: 16,
          crossAxisSpacing: 16,
          childAspectRatio: 0.7,
        ),
        itemCount: 6,
        itemBuilder: (context, index) => const ShimmerCard(),
      );
    }

    if (async.hasError && !_hasContent) {
      return _buildErrorState(async.error);
    }

    if (_recipes.isEmpty) {
      return _buildEmptyState();
    }

    return RefreshIndicator(
      onRefresh: () => ref.refresh(homeContentProvider.future),
      color: Theme.of(context).colorScheme.primary,
      child: GridView.builder(
        padding: const EdgeInsets.all(16),
        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: 2,
          mainAxisSpacing: 16,
          crossAxisSpacing: 16,
          childAspectRatio: 0.7,
        ),
        itemCount: _recipes.length,
        itemBuilder: (context, index) {
          final item = _recipes[index];
          final selection = ref.watch(homeSelectionProvider);
          if (item is Map && item['kind'] == 'meal') {
            final meal = _mealSummaryFrom(item);
            final isSelected = selection.isMealSelected(meal.id);
            return MealTile(
              meal: meal,
              onTap: selection.isActive
                  ? () => ref
                      .read(homeSelectionProvider.notifier)
                      .toggleMeal(meal.id)
                  : () => context.push('/meals/${meal.id}'),
              onLongPress: () {
                HapticFeedback.selectionClick();
                ref
                    .read(homeSelectionProvider.notifier)
                    .enterWith(kind: 'meal', id: meal.id);
              },
              componentNameResolver: _resolveComponentName,
              isFavorited: _favoriteMealIds.contains(meal.id),
              onFavoriteToggle: selection.isActive
                  ? null
                  : () => _toggleMealFavorite(meal),
              selected: isSelected,
            );
          }
          final recipeId = item['id']?.toString();
          final isSelected =
              recipeId != null && selection.isRecipeSelected(recipeId);
          return RecipeCard(
            recipe: item,
            selected: isSelected,
            onTap: selection.isActive && recipeId != null
                ? () => ref
                    .read(homeSelectionProvider.notifier)
                    .toggleRecipe(recipeId)
                : () => context.push('/recipes/${item['id']}'),
            onLongPress: recipeId == null
                ? null
                : () {
                    HapticFeedback.selectionClick();
                    ref.read(homeSelectionProvider.notifier).enterWith(
                          kind: 'recipe',
                          id: recipeId,
                        );
                  },
            onFavoriteToggle: selection.isActive
                ? null
                : () => _toggleFavorite(item),
          );
        },
      ),
    );
  }

  Widget _buildEmptyState() {
    return EmptyStateWidget(
      icon: Icons.restaurant_menu,
      title: 'No recipes yet',
      subtitle: 'Add your first recipe to get started',
      actionLabel: 'Add Recipe',
      onAction: _showAddRecipeSheet,
      actionIcon: Icons.add,
    );
  }

  Widget _buildErrorState(Object? error) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            ErrorBanner(
              message: 'Failed to load recipes: $error',
              detail: ErrorReporter.detail(error ?? ''),
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: () => ref.invalidate(homeContentProvider),
              child: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }
}

class _AddToMealTarget {
  final String recipeId;
  final String name;
  const _AddToMealTarget(this.recipeId, this.name);
}

class _ArchiveMealTarget {
  final String mealId;
  final String name;
  final String bookId;
  const _ArchiveMealTarget(this.mealId, this.name, this.bookId);
}
