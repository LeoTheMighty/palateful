import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../shared/widgets/empty_state.dart';
import '../../core/services/error_reporter.dart';
import '../../shared/widgets/error_banner.dart';
import '../meals/models/meal.dart';
import 'providers/recipe_provider.dart';
import '../meals/services/meal_service.dart';

class ArchivedRecipesScreen extends StatefulWidget {
  const ArchivedRecipesScreen({super.key});

  @override
  State<ArchivedRecipesScreen> createState() => _ArchivedRecipesScreenState();
}

class _ArchivedRecipesScreenState extends State<ArchivedRecipesScreen> {
  final _apiClient = getIt<ApiClient>();
  final _mealService = getIt<MealService>();
  List<dynamic> _archivedRecipes = [];
  List<MealSummary> _archivedMeals = const [];
  bool _isLoading = true;
  String? _error;
  String? _errorDetail;
  final Set<String> _restoringIds = {};
  final TextEditingController _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadArchivedRecipes();
    _searchController.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  List<dynamic> get _filteredRecipes {
    final query = _searchController.text.toLowerCase().trim();
    if (query.isEmpty) return _archivedRecipes;
    return _archivedRecipes
        .where((r) => (r['name'] as String? ?? '').toLowerCase().contains(query))
        .toList();
  }

  List<MealSummary> get _filteredMeals {
    final query = _searchController.text.toLowerCase().trim();
    if (query.isEmpty) return _archivedMeals;
    return _archivedMeals
        .where((m) => m.name.toLowerCase().contains(query))
        .toList();
  }

  Future<void> _loadArchivedRecipes() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final results = await Future.wait([
        _apiClient.getArchivedRecipes(),
        _mealService
            .listMeals(includeArchived: true, limit: 100)
            .then<List<MealSummary>?>((v) => v)
            .catchError((_) => null),
      ]);
      final response = results[0] as dynamic;
      final meals = results[1] as List<MealSummary>?;
      if (mounted) {
        setState(() {
          _archivedRecipes = response.data['items'] ?? [];
          _archivedMeals = (meals ?? const [])
              .where((m) => m.isArchived)
              .toList();
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Could not load archived recipes. Please try again.';
          _errorDetail = ErrorReporter.detail(e);
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _restoreMeal(MealSummary meal) async {
    if (_restoringIds.contains(meal.id)) return;
    _restoringIds.add(meal.id);
    try {
      HapticFeedback.selectionClick();
      await _mealService.restoreMeal(meal.id);
      if (mounted) {
        setState(() {
          _archivedMeals =
              _archivedMeals.where((m) => m.id != meal.id).toList();
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Meal restored')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Could not restore meal. Please try again.'),
          ),
        );
      }
    } finally {
      _restoringIds.remove(meal.id);
    }
  }

  Future<void> _restoreRecipe(dynamic recipe) async {
    final recipeId = recipe['id']?.toString();
    if (recipeId == null) return;
    if (_restoringIds.contains(recipeId)) return;
    _restoringIds.add(recipeId);

    try {
      HapticFeedback.selectionClick();
      await _apiClient.restoreRecipe(recipeId);
      if (mounted) invalidateRecipe(context, recipeId);
      if (mounted) {
        setState(() {
          _archivedRecipes.removeWhere((r) => r['id']?.toString() == recipeId);
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Recipe restored')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not restore recipe. Please try again.')),
        );
      }
    } finally {
      _restoringIds.remove(recipeId);
    }
  }

  /// md-7: merge recipes + meals into a single list sorted by
  /// `archived_at DESC`. When meals is empty, the ordering of recipes is
  /// preserved bit-identically — that's the zero-regression guarantee
  /// for users with only archived recipes.
  List<Widget> _buildMergedRows() {
    final recipes = _filteredRecipes;
    final meals = _filteredMeals;
    if (meals.isEmpty) {
      return [
        for (final recipe in recipes)
          _ArchivedRecipeRow(
            recipe: recipe,
            onRestore: () => _restoreRecipe(recipe),
            archivedDateFormatter: _formatArchivedDate,
          ),
      ];
    }
    DateTime? asDate(dynamic raw) {
      if (raw == null) return null;
      if (raw is DateTime) return raw;
      try {
        return DateTime.parse(raw as String);
      } catch (_) {
        return null;
      }
    }

    final entries = <_ArchiveEntry>[
      for (final r in recipes)
        _ArchiveEntry.recipe(r, asDate(r['archived_at'])),
      for (final m in meals) _ArchiveEntry.meal(m, m.archivedAt),
    ];
    entries.sort((a, b) {
      final aAt = a.archivedAt;
      final bAt = b.archivedAt;
      if (aAt == null && bAt == null) return 0;
      if (aAt == null) return 1; // null archived_at goes last
      if (bAt == null) return -1;
      return bAt.compareTo(aAt); // newest archived first
    });
    return [
      for (final entry in entries)
        entry.isMeal
            ? _ArchivedMealRow(
                meal: entry.meal!,
                onRestore: () => _restoreMeal(entry.meal!),
                archivedDateFormatter: _formatArchivedDate,
              )
            : _ArchivedRecipeRow(
                recipe: entry.recipe,
                onRestore: () => _restoreRecipe(entry.recipe),
                archivedDateFormatter: _formatArchivedDate,
              ),
    ];
  }

  String _formatArchivedDate(String? dateStr) {
    if (dateStr == null) return '';
    try {
      final date = DateTime.parse(dateStr);
      return 'Archived ${date.month}/${date.day}/${date.year}';
    } catch (_) {
      return '';
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Archived Recipes'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
      ),
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
                          onPressed: _loadArchivedRecipes,
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                )
              : (_archivedRecipes.isEmpty && _archivedMeals.isEmpty)
                  ? EmptyStateWidget(
                      icon: Icons.archive_outlined,
                      title: 'No archived items',
                      subtitle:
                          'Recipes and meals you archive will appear here',
                    )
                  : RefreshIndicator(
                      onRefresh: _loadArchivedRecipes,
                      child: Column(
                        children: [
                          Padding(
                            padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
                            child: TextField(
                              controller: _searchController,
                              decoration: const InputDecoration(
                                hintText: 'Search archived...',
                                prefixIcon: Icon(Icons.search),
                                border: OutlineInputBorder(),
                              ),
                            ),
                          ),
                          Expanded(
                            child: (_filteredRecipes.isEmpty &&
                                        _filteredMeals.isEmpty) &&
                                    _searchController.text.trim().isNotEmpty
                                ? LayoutBuilder(
                                    builder: (context, constraints) =>
                                        SingleChildScrollView(
                                      physics:
                                          const AlwaysScrollableScrollPhysics(),
                                      child: SizedBox(
                                        height: constraints.maxHeight,
                                        child: EmptyStateWidget(
                                          icon: Icons.search_off,
                                          title: 'No results',
                                          subtitle:
                                              'No archived items match your search',
                                        ),
                                      ),
                                    ),
                                  )
                                : ListView(
                                    padding: const EdgeInsets.fromLTRB(
                                        16, 0, 16, 16),
                                    children: _buildMergedRows(),
                                  ),
                          ),
                        ],
                      ),
                    ),
    );
  }
}

class _ArchiveEntry {
  final bool isMeal;
  final dynamic recipe;
  final MealSummary? meal;
  final DateTime? archivedAt;

  _ArchiveEntry._({
    required this.isMeal,
    required this.archivedAt,
    this.recipe,
    this.meal,
  });

  factory _ArchiveEntry.recipe(dynamic recipe, DateTime? archivedAt) =>
      _ArchiveEntry._(isMeal: false, recipe: recipe, archivedAt: archivedAt);

  factory _ArchiveEntry.meal(MealSummary meal, DateTime? archivedAt) =>
      _ArchiveEntry._(isMeal: true, meal: meal, archivedAt: archivedAt);
}

class _ArchivedRecipeRow extends StatelessWidget {
  final dynamic recipe;
  final VoidCallback onRestore;
  final String Function(String?) archivedDateFormatter;

  const _ArchivedRecipeRow({
    required this.recipe,
    required this.onRestore,
    required this.archivedDateFormatter,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final imageUrl = recipe['image_url'] as String?;
    final name = recipe['name'] ?? 'Untitled';
    final archivedDate =
        archivedDateFormatter(recipe['archived_at']?.toString());

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      clipBehavior: Clip.antiAlias,
      child: Row(
        children: [
          SizedBox(
            width: 80,
            height: 80,
            child: imageUrl != null
                ? CachedNetworkImage(
                    imageUrl: imageUrl,
                    fit: BoxFit.cover,
                    placeholder: (c, u) => const Center(
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                    errorWidget: (c, u, e) => Container(
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
          Expanded(
            child: Padding(
              padding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    name,
                    style: textTheme.titleSmall
                        ?.copyWith(fontWeight: FontWeight.w600),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (archivedDate.isNotEmpty) ...[
                    const SizedBox(height: 4),
                    Text(
                      archivedDate,
                      style: textTheme.bodySmall?.copyWith(
                          color: colorScheme.onSurfaceVariant),
                    ),
                  ],
                ],
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: TextButton.icon(
              onPressed: onRestore,
              icon: const Icon(Icons.restore, size: 18),
              label: const Text('Restore'),
            ),
          ),
        ],
      ),
    );
  }
}

class _ArchivedMealRow extends StatelessWidget {
  final MealSummary meal;
  final VoidCallback onRestore;
  final String Function(String?) archivedDateFormatter;

  const _ArchivedMealRow({
    required this.meal,
    required this.onRestore,
    required this.archivedDateFormatter,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final firstImage = meal.componentImageUrls.isNotEmpty
        ? meal.componentImageUrls.first
        : null;
    final archivedDate =
        archivedDateFormatter(meal.archivedAt?.toIso8601String());

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      clipBehavior: Clip.antiAlias,
      child: Row(
        children: [
          SizedBox(
            width: 80,
            height: 80,
            child: firstImage != null
                ? CachedNetworkImage(
                    imageUrl: firstImage,
                    fit: BoxFit.cover,
                    errorWidget: (c, u, e) => Container(
                      color: colorScheme.surfaceContainerHighest,
                      child: Icon(Icons.set_meal_outlined,
                          color: colorScheme.onSurfaceVariant),
                    ),
                  )
                : Container(
                    color: colorScheme.surfaceContainerHighest,
                    child: Icon(Icons.set_meal_outlined,
                        color: colorScheme.onSurfaceVariant),
                  ),
          ),
          Expanded(
            child: Padding(
              padding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    meal.name,
                    style: textTheme.titleSmall
                        ?.copyWith(fontWeight: FontWeight.w600),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Meal · ${meal.componentCount} recipes',
                    style: textTheme.bodySmall?.copyWith(
                        color: colorScheme.onSurfaceVariant),
                  ),
                  if (archivedDate.isNotEmpty) ...[
                    const SizedBox(height: 2),
                    Text(
                      archivedDate,
                      style: textTheme.bodySmall?.copyWith(
                          color: colorScheme.onSurfaceVariant),
                    ),
                  ],
                ],
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: TextButton.icon(
              onPressed: onRestore,
              icon: const Icon(Icons.restore, size: 18),
              label: const Text('Restore'),
            ),
          ),
        ],
      ),
    );
  }
}
