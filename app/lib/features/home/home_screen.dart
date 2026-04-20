import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../shared/widgets/buttons.dart';
import '../../shared/widgets/empty_state.dart';
import '../../shared/widgets/shimmer_loading.dart';
import '../recipes/add_recipe/add_recipe_sheet.dart';
import '../meals/models/meal.dart';
import '../meals/widgets/meal_tile.dart';
import 'widgets/batch_import_status_widget.dart';
import 'widgets/filter_bottom_sheet.dart';
import 'widgets/filter_pill.dart';
import 'widgets/meal_filter_bar.dart';
import '../../core/theme/theme.dart';
import 'widgets/recipe_card.dart';
import '../../core/services/error_reporter.dart';
import '../../core/services/shared_state_service.dart';
import '../../shared/widgets/error_banner.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final _apiClient = getIt<ApiClient>();

  List<dynamic> _recipes = [];
  List<dynamic> _favorites = [];
  Set<String> _favoriteIds = {};
  // Favorited-meal ids populated from /v1/favorites.favorited_meals.
  // Separate from _favoriteIds because meal favorites hit a different
  // endpoint (favoriteMeal / unfavoriteMeal) and are never conflated
  // with recipe favorites.
  Set<String> _favoriteMealIds = {};
  final Set<String> _togglingFavoriteIds = {};
  bool _isLoading = true;
  String? _error;
  String? _errorDetail;

  MealFilter _mealFilter = MealFilter.all;
  String? _vibeFilter;
  SortOption _sortOption = SortOption.best;

  dynamic _todayMealEvent; // null = no planned meal today
  List<dynamic> _recentlyCooked = [];

  @override
  void initState() {
    super.initState();
    _loadRecipes();
    _loadHomeContext();
  }

  Future<void> _loadRecipes() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      // Load recipes and favorites in parallel
      final booksResponse = await _apiClient.getRecipeBooks();
      final books = List<dynamic>.from(booksResponse.data['items'] ?? []);

      // Mirror the book list into the iOS App Group so the Share Extension's
      // book picker has something to show. Debounced inside the service.
      getIt<SharedStateService>().syncRecipeBooks(
        books
            .whereType<Map>()
            .map((m) => SharedRecipeBook.fromMap(Map<String, dynamic>.from(m)))
            .toList(),
      );

      final recipesFuture = _loadAllRecipesFromBooks(books);
      final favFuture = _apiClient.getFavorites();
      // md-4: parallel Meal fetch. A failure here must NOT block the grid
      // — a zero-Meal render is bit-identical to pre-epic, so we swallow
      // the error and keep recipes rendering.
      final mealsFuture = _loadMealsForHome();

      final results = await Future.wait([recipesFuture, favFuture, mealsFuture]);
      List<dynamic> allRecipes = results[0] as List<dynamic>;
      final favResponse = results[1];
      final mealItems = results[2] as List<dynamic>;
      final favData = (favResponse as dynamic).data as Map<String, dynamic>;
      final favItems = (favData['items'] as List<dynamic>?) ?? [];
      final favIds = favItems.map((f) => f['id'].toString()).toSet();

      // md-3 additive response key: favorited Meals render alongside
      // favorited recipes in the same carousel.
      final favMealItems = ((favData['favorited_meals'] as List<dynamic>?) ?? [])
          .map((m) => _tagMeal(m as Map<String, dynamic>))
          .toList();
      final favMealIds = favMealItems
          .map((m) => (m as Map)['id']?.toString())
          .whereType<String>()
          .toSet();

      // Merge is_favorite into recipes
      for (final recipe in allRecipes) {
        recipe['is_favorite'] = favIds.contains(recipe['id']?.toString());
        recipe['kind'] = 'recipe';
      }

      // Apply filters and sorting
      allRecipes = _applyFilters(allRecipes);
      allRecipes = _applySorting(allRecipes);

      // md-4: merge meals in. When meals is empty, the merge is a no-op
      // and the existing filter+sort ordering is preserved bit-identically.
      final mergedGrid = _mergeRecipesAndMeals(allRecipes, mealItems);
      final mergedFavorites = <dynamic>[...favItems, ...favMealItems];

      if (mounted) {
        setState(() {
          _recipes = mergedGrid;
          _favorites = mergedFavorites;
          _favoriteIds = favIds;
          _favoriteMealIds = favMealIds;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Failed to load recipes: $e';
          _errorDetail = ErrorReporter.detail(e);
          _isLoading = false;
        });
      }
    }
  }

  /// Fetch Meals for the home grid. Swallows errors — a failed Meal
  /// fetch must never block recipe rendering (zero-regression contract).
  Future<List<dynamic>> _loadMealsForHome() async {
    try {
      final resp = await _apiClient.listMeals(scope: 'home');
      final items = ((resp.data as Map<String, dynamic>)['items'] as List? ?? [])
          .cast<Map<String, dynamic>>();
      return items.map(_tagMeal).toList();
    } catch (_) {
      return <dynamic>[];
    }
  }

  /// Decorate a meal summary payload with `kind:'meal'` so the grid's
  /// itemBuilder can discriminate without a second lookup table.
  Map<String, dynamic> _tagMeal(Map<String, dynamic> meal) {
    return {...meal, 'kind': 'meal'};
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
      if (wasFav) {
        await _apiClient.unfavoriteMeal(mealId);
      } else {
        await _apiClient.favoriteMeal(mealId);
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

  Future<List<dynamic>> _loadAllRecipesFromBooks(List<dynamic> books) async {
    // Fetch all books in parallel instead of sequentially
    final results = await Future.wait(
      books.map((book) async {
        try {
          final bookDetail = await _apiClient.getRecipeBook(book['id']);
          final recipes = List<dynamic>.from(bookDetail.data['recipes'] ?? []);
          for (final recipe in recipes) {
            recipe['recipe_book_id'] = book['id'];
            recipe['recipe_book_name'] = book['name'];
          }
          return recipes;
        } catch (_) {
          return <dynamic>[]; // One book failure doesn't block others
        }
      }),
    );
    return results.expand((r) => r).toList();
  }

  Future<void> _loadHomeContext() async {
    // Load each section independently so one failure doesn't drop the other
    dynamic todayMeal;
    List<dynamic> recentlyCooked = [];

    await Future.wait([
      _apiClient.getMealEventsForToday().then((r) {
        final items = r.data['items'] as List?;
        if (items != null && items.isNotEmpty && items[0]['recipe'] != null) {
          todayMeal = items[0];
        }
      }).catchError((_) {}),
      _apiClient.getRecentlyCookedRecipes().then((r) {
        recentlyCooked = (r.data['items'] as List?) ?? [];
      }).catchError((_) {}),
    ]);

    if (!mounted) return;
    setState(() {
      _todayMealEvent = todayMeal;
      _recentlyCooked = recentlyCooked;
    });
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
      await _apiClient.toggleFavorite(recipeId);
    } catch (e) {
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
              _recipes = _applySorting(List.from(_recipes));
            });
            _reapplyFilters();
          },
        ),
      ),
    );
  }

  void _reapplyFilters() {
    // Reload recipes to re-apply filters
    _loadRecipes();
  }

  void _showAddRecipeSheet() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => const AddRecipeSheet(),
    );
  }

  void _showRecipeActions(dynamic recipe) {
    final colorScheme = Theme.of(context).colorScheme;
    showModalBottomSheet(
      context: context,
      builder: (context) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.restaurant),
              title: const Text('Start Cooking'),
              onTap: () {
                Navigator.pop(context);
                _quickStartCooking(recipe);
              },
            ),
            if (recipe['can_edit'] != false)
              ListTile(
                leading: Icon(Icons.archive_outlined, color: colorScheme.error),
                title: Text('Archive', style: TextStyle(color: colorScheme.error)),
                onTap: () {
                  Navigator.pop(context);
                  _archiveRecipe(recipe);
                },
              ),
          ],
        ),
      ),
    );
  }

  void _quickStartCooking(dynamic recipe) {
    context.push('/recipes/${recipe['id']}/cook');
  }

  Future<void> _archiveRecipe(dynamic recipe) async {
    final recipeId = recipe['id']?.toString();
    if (recipeId == null) return;

    final confirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Archive Recipe?'),
        content: const Text(
          'This recipe will be moved to your archive. You can restore it anytime.',
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

    try {
      HapticFeedback.selectionClick();
      await _apiClient.deleteRecipe(recipeId);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Recipe archived')),
        );
        _loadRecipes();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not archive recipe. Please try again.')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            // Search Header
            _buildSearchHeader(),

            // Contextual sections — capped to ensure recipe grid always gets space
            if (_todayMealEvent != null || _recentlyCooked.isNotEmpty)
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
            const BatchImportStatusWidget(),

            // Favorites Section
            if (_favorites.isNotEmpty) _buildFavoritesSection(),

            // Recipe Grid
            Expanded(
              child: _buildRecipeGrid(),
            ),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _showAddRecipeSheet,
        child: const Icon(Icons.add),
      ),
    );
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
    if (_isLoading) {
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

    if (_error != null) {
      return _buildErrorState();
    }

    if (_recipes.isEmpty) {
      return _buildEmptyState();
    }

    return RefreshIndicator(
      onRefresh: _loadRecipes,
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
          if (item is Map && item['kind'] == 'meal') {
            final meal = _mealSummaryFrom(item);
            return MealTile(
              meal: meal,
              onTap: () => context.push('/meals/${meal.id}'),
              componentNameResolver: _resolveComponentName,
              isFavorited: _favoriteMealIds.contains(meal.id),
              onFavoriteToggle: () => _toggleMealFavorite(meal),
            );
          }
          return RecipeCard(
            recipe: item,
            onTap: () {
              context.push('/recipes/${item['id']}');
            },
            onLongPress: () => _showRecipeActions(item),
            onFavoriteToggle: () => _toggleFavorite(item),
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

  Widget _buildErrorState() {
    final colorScheme = Theme.of(context).colorScheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            ErrorBanner(message: _error!, detail: _errorDetail),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _loadRecipes,
              child: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }
}
