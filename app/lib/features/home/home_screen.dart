import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../shared/widgets/buttons.dart';
import '../../shared/widgets/empty_state.dart';
import '../../shared/widgets/shimmer_loading.dart';
import '../recipes/add_recipe/add_recipe_sheet.dart';
import '../recipes/add_recipe/batch_parser_service.dart';
import 'widgets/batch_import_status_widget.dart';
import 'widgets/meal_filter_bar.dart';
import 'widgets/sort_chips.dart';
import 'widgets/recipe_card.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final _apiClient = getIt<ApiClient>();
  final _batchService = getIt<BatchParserService>();
  final _imagePicker = ImagePicker();

  List<dynamic> _recipes = [];
  List<dynamic> _favorites = [];
  Set<String> _favoriteIds = {};
  final Set<String> _togglingFavoriteIds = {};
  bool _isLoading = true;
  String? _error;

  MealFilter _mealFilter = MealFilter.all;
  SortOption _sortOption = SortOption.best;

  @override
  void initState() {
    super.initState();
    _loadRecipes();
  }

  Future<void> _loadRecipes() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      // Load recipes and favorites in parallel
      final booksResponse = await _apiClient.getRecipeBooks();
      final books = booksResponse.data['items'] ?? [];

      final recipesFuture = _loadAllRecipesFromBooks(books);
      final favFuture = _apiClient.getFavorites();

      final results = await Future.wait([recipesFuture, favFuture]);
      List<dynamic> allRecipes = results[0] as List<dynamic>;
      final favResponse = results[1];
      final favItems = ((favResponse as dynamic).data['items'] as List<dynamic>?) ?? [];
      final favIds = favItems.map((f) => f['id'].toString()).toSet();

      // Merge is_favorite into recipes
      for (final recipe in allRecipes) {
        recipe['is_favorite'] = favIds.contains(recipe['id']?.toString());
      }

      // Apply filters and sorting
      allRecipes = _applyFilters(allRecipes);
      allRecipes = _applySorting(allRecipes);

      if (mounted) {
        setState(() {
          _recipes = allRecipes;
          _favorites = favItems;
          _favoriteIds = favIds;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Failed to load recipes: $e';
          _isLoading = false;
        });
      }
    }
  }

  Future<List<dynamic>> _loadAllRecipesFromBooks(List<dynamic> books) async {
    List<dynamic> allRecipes = [];
    for (final book in books) {
      final bookDetail = await _apiClient.getRecipeBook(book['id']);
      final recipes = bookDetail.data['recipes'] ?? [];
      for (final recipe in recipes) {
        recipe['recipe_book_id'] = book['id'];
        recipe['recipe_book_name'] = book['name'];
      }
      allRecipes.addAll(recipes);
    }
    return allRecipes;
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
    if (_mealFilter == MealFilter.all) return recipes;

    final mealName = _mealFilter.name;
    return recipes.where((r) {
      final meal = r['meal_type']?.toString().toLowerCase();
      return meal == mealName;
    }).toList();
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

  void _onMealFilterChanged(MealFilter filter) {
    HapticFeedback.selectionClick();
    setState(() {
      _mealFilter = filter;
    });
    _loadRecipes();
  }

  void _onSortChanged(SortOption sort) {
    HapticFeedback.selectionClick();
    setState(() {
      _sortOption = sort;
      _recipes = _applySorting(List.from(_recipes));
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

  Future<void> _pickMultiplePhotos() async {
    try {
      final images = await _imagePicker.pickMultiImage(
        maxWidth: 2048,
        imageQuality: 85,
      );
      if (images.isEmpty) return;

      if (images.length == 1) {
        _batchService.submitBatch(images);
      } else {
        _showBatchConfirmDialog(images);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to pick images: $e')),
        );
      }
    }
  }

  void _showBatchConfirmDialog(List<XFile> images) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('${images.length} photos selected'),
        content: const Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'All different recipes?',
              style: TextStyle(fontWeight: FontWeight.w600),
            ),
            SizedBox(height: 8),
            Text('Each photo will be processed as a separate recipe.'),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Grouping coming soon!')),
              );
            },
            child: const Text('Edit grouping'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              _batchService.submitBatch(images);
            },
            // Uses theme's elevated button style (primary color)
            child: const Text('Process all'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            // Search Header
            _buildSearchHeader(),

            // Meal Filter Bar
            MealFilterBar(
              selected: _mealFilter,
              onChanged: _onMealFilterChanged,
            ),

            // Sort Chips
            SortChips(
              selected: _sortOption,
              onChanged: _onSortChanged,
              recipeCount: _recipes.length,
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

          // Batch Photo Import Button
          CircleIconButton(
            icon: Icons.add_photo_alternate_outlined,
            onPressed: _pickMultiplePhotos,
            backgroundColor: colorScheme.surfaceContainerHighest,
            tooltip: 'Import Photos',
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
              Icon(Icons.favorite, size: 18, color: Colors.red.shade400),
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
              final recipe = _favorites[index];
              final imageUrl = recipe['image_url'];
              final name = recipe['name'] ?? 'Untitled';

              return GestureDetector(
                onTap: () async {
                  await context.push('/recipes/${recipe['id']}');
                  _loadRecipes();
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
                              ? Image.network(
                                  imageUrl,
                                  fit: BoxFit.cover,
                                  errorBuilder: (_, __, ___) => Container(
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
          final recipe = _recipes[index];
          return RecipeCard(
            recipe: recipe,
            onTap: () async {
              await context.push('/recipes/${recipe['id']}');
              _loadRecipes();
            },
            onLongPress: () => _quickStartCooking(recipe),
            onFavoriteToggle: () => _toggleFavorite(recipe),
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
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: colorScheme.errorContainer,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(
                _error!,
                style: TextStyle(color: colorScheme.onErrorContainer),
                textAlign: TextAlign.center,
              ),
            ),
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
