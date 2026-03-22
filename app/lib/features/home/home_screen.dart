import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../core/services/auth_service.dart';
import '../../shared/widgets/buttons.dart';
import '../../shared/widgets/empty_state.dart';
import '../../shared/widgets/shimmer_loading.dart';
import '../chat/chat_provider.dart';
import '../chat/chat_service.dart';
import '../recipes/add_recipe/add_recipe_sheet.dart';
import '../recipes/add_recipe/batch_parser_service.dart';
import 'widgets/batch_import_status_widget.dart';
import 'widgets/meal_filter_bar.dart';
import 'widgets/sort_chips.dart';
import '../../core/theme/theme.dart';
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
  List<dynamic> _books = [];
  List<dynamic> _favorites = [];
  Set<String> _favoriteIds = {};
  final Set<String> _togglingFavoriteIds = {};
  bool _isLoading = true;
  String? _error;

  MealFilter _mealFilter = MealFilter.all;
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
          _books = books;
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
    // Filter applied client-side in _getFilteredRecipes() — no refetch needed
  }

  void _onSortChanged(SortOption sort) {
    HapticFeedback.selectionClick();
    setState(() {
      _sortOption = sort;
      _recipes = _applySorting(List.from(_recipes));
    });
  }

  Future<void> _openChat() async {
    try {
      final chatService = ChatService(_apiClient.dio);
      final thread = await chatService.createThread();
      if (mounted) {
        context.push('/chat/${thread.id}');
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to open chat: $e')),
        );
      }
    }
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

            // My Books horizontal scroll
            if (_books.isNotEmpty) _buildBooksSection(),

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

          // AI Chat Button
          CircleIconButton(
            icon: Icons.chat_bubble_outline,
            onPressed: _openChat,
            backgroundColor: colorScheme.surfaceContainerHighest,
            tooltip: 'AI Assistant',
          ),
          const SizedBox(width: 8),

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

  Widget _buildBooksSection() {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final defaultBookId = getIt<AuthService>().defaultRecipeBookId;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Section header
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'My Books',
                style: textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
              GestureDetector(
                onTap: () => context.push('/recipe-books'),
                child: Text(
                  'See All',
                  style: textTheme.bodyMedium?.copyWith(
                    color: colorScheme.primary,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
            ],
          ),
        ),
        // Horizontal scroll
        SizedBox(
          height: 130,
          child: ListView.builder(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 12),
            itemCount: _books.length + 1, // +1 for "New Book" card
            itemBuilder: (context, index) {
              if (index == _books.length) {
                // "+ New Book" card
                return Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  child: GestureDetector(
                    onTap: _createRecipeBook,
                    child: Container(
                      width: 120,
                      decoration: BoxDecoration(
                        color: colorScheme.surfaceContainerHighest,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: colorScheme.outlineVariant,
                          style: BorderStyle.solid,
                        ),
                      ),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.add, size: 32, color: colorScheme.primary),
                          const SizedBox(height: 8),
                          Text(
                            'New Book',
                            style: textTheme.bodySmall?.copyWith(
                              color: colorScheme.primary,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                );
              }

              final book = _books[index];
              final bookId = book['id']?.toString();
              final isDefault = bookId != null && bookId == defaultBookId;
              final recipeCount = book['recipe_count'] ?? 0;

              return Padding(
                padding: const EdgeInsets.symmetric(horizontal: 4),
                child: GestureDetector(
                  onTap: () async {
                    await context.push('/recipe-books/$bookId');
                    if (mounted) _loadRecipes();
                  },
                  child: Container(
                    width: 140,
                    decoration: BoxDecoration(
                      color: colorScheme.surfaceContainerLow,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: colorScheme.outlineVariant),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(10),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          // Thumbnail mosaic area
                          Expanded(
                            child: ClipRRect(
                              borderRadius: BorderRadius.circular(8),
                              child: Container(
                                color: colorScheme.surfaceContainerHighest,
                                child: Center(
                                  child: Icon(
                                    Icons.book,
                                    size: 28,
                                    color: colorScheme.onSurfaceVariant.withValues(alpha: 0.5),
                                  ),
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(height: 8),
                          // Book name + default star
                          Row(
                            children: [
                              if (isDefault)
                                Padding(
                                  padding: const EdgeInsets.only(right: 4),
                                  child: Icon(
                                    Icons.star,
                                    size: 14,
                                    color: colorScheme.tertiary,
                                  ),
                                ),
                              Expanded(
                                child: Text(
                                  book['name'] ?? '',
                                  style: textTheme.bodySmall?.copyWith(
                                    fontWeight: FontWeight.w600,
                                  ),
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                            ],
                          ),
                          Text(
                            '$recipeCount recipe${recipeCount == 1 ? '' : 's'}',
                            style: textTheme.bodySmall?.copyWith(
                              color: colorScheme.onSurfaceVariant,
                              fontSize: 11,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              );
            },
          ),
        ),
      ],
    );
  }

  Future<void> _createRecipeBook() async {
    final nameController = TextEditingController();
    final name = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('New Recipe Book'),
        content: TextField(
          controller: nameController,
          autofocus: true,
          decoration: const InputDecoration(
            hintText: 'Book name',
          ),
          onSubmitted: (value) => Navigator.pop(ctx, value.trim()),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, nameController.text.trim()),
            child: const Text('Create'),
          ),
        ],
      ),
    );
    nameController.dispose();

    if (name == null || name.isEmpty) return;

    try {
      await _apiClient.createRecipeBook({'name': name});
      if (mounted) _loadRecipes();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to create book')),
        );
      }
    }
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
              final recipe = _favorites[index];
              final imageUrl = recipe['image_url'];
              final name = recipe['name'] ?? 'Untitled';

              return GestureDetector(
                onTap: () {
                  context.push('/recipes/${recipe['id']}');
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
          final recipe = _recipes[index];
          return RecipeCard(
            recipe: recipe,
            onTap: () {
              context.push('/recipes/${recipe['id']}');
            },
            onLongPress: () => _showRecipeActions(recipe),
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
