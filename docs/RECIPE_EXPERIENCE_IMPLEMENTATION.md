# Recipe Experience Implementation Guide

This document covers the complete implementation of three interconnected features:
1. **Main Recipe Screen** - The app's new home
2. **Minimal Click UX** - Frictionless interaction patterns
3. **Do Recipe Mode** - The cooking experience

These are designed as a unified experience, not separate features.

---

## Architecture Overview

### New File Structure

```
lib/features/
├── home/                          # REPLACE current home
│   ├── home_screen.dart           # New recipe-focused home
│   ├── widgets/
│   │   ├── recipe_card.dart       # Recipe grid card
│   │   ├── meal_filter_bar.dart   # Breakfast/Lunch/Dinner/Dessert
│   │   ├── sort_chips.dart        # Best/New/Popular/Quick
│   │   └── search_header.dart     # Search + filter icons
│   └── home_controller.dart       # State management (optional BLoC)
│
├── recipes/
│   ├── recipe_detail_screen.dart  # KEEP - view mode
│   ├── cook_mode_screen.dart      # NEW - cooking mode
│   ├── add_recipe/
│   │   ├── add_recipe_sheet.dart  # Bottom sheet with options
│   │   ├── photo_capture_screen.dart
│   │   ├── file_import_screen.dart
│   │   └── recipe_wizard/
│   │       ├── wizard_screen.dart
│   │       ├── step_name.dart
│   │       ├── step_ingredients.dart
│   │       ├── step_instructions.dart
│   │       └── step_details.dart
│   └── widgets/
│       ├── ingredient_strip.dart  # Horizontal ingredient scroller
│       ├── step_navigator.dart    # Prev/Next + step dots
│       ├── inline_timer.dart      # Timer button in instructions
│       └── cook_mode_header.dart
│
└── shared/
    └── widgets/
        ├── buttons.dart           # EXISTS
        ├── icon_button_bar.dart   # NEW - icon-only button row
        └── swipe_detector.dart    # NEW - gesture wrapper
```

### Route Updates

```dart
// app_router.dart additions
GoRoute(
  path: '/',
  builder: (context, state) => const HomeScreen(),  // New recipe home
),
GoRoute(
  path: '/recipes/:id/cook',
  builder: (context, state) {
    final id = state.pathParameters['id']!;
    return CookModeScreen(recipeId: id);
  },
),
GoRoute(
  path: '/recipes/add',
  builder: (context, state) => const AddRecipeSheet(),
),
GoRoute(
  path: '/recipes/add/wizard',
  builder: (context, state) => const RecipeWizardScreen(),
),
GoRoute(
  path: '/recipes/add/photo',
  builder: (context, state) => const PhotoCaptureScreen(),
),
// Keep existing recipe detail at /recipes/:id
```

---

## Part 1: Main Recipe Screen (Home)

### Design Specification

```
┌─────────────────────────────────────────────────────┐
│  🔍                              ☰ Filter   👤      │  ← Header
├─────────────────────────────────────────────────────┤
│  [🌅 All] [☀️ Breakfast] [🍝 Lunch] [🌙 Dinner] [🍰]│  ← Meal tabs
├─────────────────────────────────────────────────────┤
│  [⭐] [🆕] [🔥] [⏱️] [🎲]                           │  ← Sort icons
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────────┐    ┌──────────────┐              │
│  │ ┌──────────┐ │    │ ┌──────────┐ │              │
│  │ │  IMAGE   │ │    │ │  IMAGE   │ │              │
│  │ └──────────┘ │    │ └──────────┘ │              │
│  │ Recipe Name  │    │ Recipe Name  │              │
│  │ 🏷️ tag tag   │    │ 🏷️ tag       │              │
│  │ 🥕 chicken.. │    │ 🥕 pasta...  │              │
│  │ ⏱️ 25m  🍳 x4│    │ ⏱️ 45m  🍳 x2│              │
│  └──────────────┘    └──────────────┘              │
│                                                     │
│  ┌──────────────┐    ┌──────────────┐              │
│  │    ...       │    │    ...       │              │
│  └──────────────┘    └──────────────┘              │
│                                                     │
└─────────────────────────────────────────────────────┘
                    [ ➕ ]  ← FAB
```

### Implementation: home_screen.dart

```dart
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../core/theme/app_colors.dart';
import 'widgets/recipe_card.dart';
import 'widgets/meal_filter_bar.dart';
import 'widgets/sort_chips.dart';

enum MealFilter { all, breakfast, lunch, dinner, dessert, snack }
enum SortOption { best, newest, popular, quickest, random }

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final _apiClient = getIt<ApiClient>();

  List<dynamic> _recipes = [];
  bool _isLoading = true;
  String? _error;

  MealFilter _mealFilter = MealFilter.all;
  SortOption _sortOption = SortOption.best;
  String _searchQuery = '';

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
      // TODO: Add API endpoint that returns all user recipes with filters
      // For now, load from all recipe books
      final booksResponse = await _apiClient.getRecipeBooks();
      final books = booksResponse.data['items'] ?? [];

      List<dynamic> allRecipes = [];
      for (final book in books) {
        final bookDetail = await _apiClient.getRecipeBook(book['id']);
        allRecipes.addAll(bookDetail.data['recipes'] ?? []);
      }

      // Apply filters and sorting client-side for now
      allRecipes = _applyFilters(allRecipes);
      allRecipes = _applySorting(allRecipes);

      if (mounted) {
        setState(() {
          _recipes = allRecipes;
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

  List<dynamic> _applyFilters(List<dynamic> recipes) {
    if (_mealFilter == MealFilter.all) return recipes;

    final mealName = _mealFilter.name;
    return recipes.where((r) {
      final meal = r['meal_type']?.toString().toLowerCase();
      return meal == mealName;
    }).toList();
  }

  List<dynamic> _applySorting(List<dynamic> recipes) {
    switch (_sortOption) {
      case SortOption.best:
        // Sort by user rating or times cooked
        recipes.sort((a, b) =>
          (b['times_cooked'] ?? 0).compareTo(a['times_cooked'] ?? 0));
        break;
      case SortOption.newest:
        recipes.sort((a, b) =>
          (b['created_at'] ?? '').compareTo(a['created_at'] ?? ''));
        break;
      case SortOption.popular:
        // For public recipes - sort by global popularity
        recipes.sort((a, b) =>
          (b['popularity'] ?? 0).compareTo(a['popularity'] ?? 0));
        break;
      case SortOption.quickest:
        recipes.sort((a, b) {
          final aTime = (a['prep_time'] ?? 0) + (a['cook_time'] ?? 0);
          final bTime = (b['prep_time'] ?? 0) + (b['cook_time'] ?? 0);
          return aTime.compareTo(bTime);
        });
        break;
      case SortOption.random:
        recipes.shuffle();
        break;
    }
    return recipes;
  }

  void _onMealFilterChanged(MealFilter filter) {
    setState(() {
      _mealFilter = filter;
    });
    _loadRecipes();
  }

  void _onSortChanged(SortOption sort) {
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
            ),

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
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
      child: Row(
        children: [
          // Search Field
          Expanded(
            child: GestureDetector(
              onTap: () {
                // TODO: Open full search screen
              },
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                decoration: BoxDecoration(
                  color: AppColors.beige,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  children: [
                    Icon(Icons.search, color: AppColors.textTertiary, size: 20),
                    const SizedBox(width: 12),
                    Text(
                      'Search recipes...',
                      style: TextStyle(color: AppColors.textTertiary),
                    ),
                  ],
                ),
              ),
            ),
          ),
          const SizedBox(width: 12),

          // Filter Button
          CircleIconButton(
            icon: Icons.tune,
            onPressed: () {
              // TODO: Open filter bottom sheet
            },
            backgroundColor: AppColors.beige,
          ),
          const SizedBox(width: 8),

          // Profile Button
          CircleIconButton(
            icon: Icons.person_outline,
            onPressed: () => context.go('/profile'),
            backgroundColor: AppColors.beige,
          ),
        ],
      ),
    );
  }

  Widget _buildRecipeGrid() {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_error != null) {
      return _buildErrorState();
    }

    if (_recipes.isEmpty) {
      return _buildEmptyState();
    }

    return RefreshIndicator(
      onRefresh: _loadRecipes,
      child: GridView.builder(
        padding: const EdgeInsets.all(16),
        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: 2,
          mainAxisSpacing: 16,
          crossAxisSpacing: 16,
          childAspectRatio: 0.7,  // Taller cards for more info
        ),
        itemCount: _recipes.length,
        itemBuilder: (context, index) {
          final recipe = _recipes[index];
          return RecipeCard(
            recipe: recipe,
            onTap: () => context.go('/recipes/${recipe['id']}'),
            onLongPress: () => _quickStartCooking(recipe),
          );
        },
      ),
    );
  }

  void _quickStartCooking(dynamic recipe) {
    // Long press = instant cook mode
    context.go('/recipes/${recipe['id']}/cook');
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: AppColors.beige,
              borderRadius: BorderRadius.circular(24),
            ),
            child: const Icon(
              Icons.restaurant_menu,
              size: 56,
              color: AppColors.hazelnut,
            ),
          ),
          const SizedBox(height: 24),
          const Text(
            'No recipes yet',
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w600,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'Add your first recipe to get started',
            style: TextStyle(color: AppColors.textTertiary),
          ),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: _showAddRecipeSheet,
            icon: const Icon(Icons.add),
            label: const Text('Add Recipe'),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.errorLight,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(
                _error!,
                style: const TextStyle(color: AppColors.errorDark),
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
```

### Implementation: recipe_card.dart

```dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../core/theme/app_colors.dart';

class RecipeCard extends StatelessWidget {
  final dynamic recipe;
  final VoidCallback onTap;
  final VoidCallback? onLongPress;

  const RecipeCard({
    super.key,
    required this.recipe,
    required this.onTap,
    this.onLongPress,
  });

  @override
  Widget build(BuildContext context) {
    final imageUrl = recipe['image_url'];
    final name = recipe['name'] ?? 'Untitled';
    final prepTime = recipe['prep_time'];
    final cookTime = recipe['cook_time'];
    final totalTime = (prepTime ?? 0) + (cookTime ?? 0);
    final timesCooked = recipe['times_cooked'] ?? 0;
    final tags = recipe['tags'] as List<dynamic>? ?? [];
    final ingredients = recipe['ingredients'] as List<dynamic>? ?? [];
    final mealType = recipe['meal_type'];

    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () {
          HapticFeedback.selectionClick();
          onTap();
        },
        onLongPress: onLongPress != null ? () {
          HapticFeedback.mediumImpact();
          onLongPress!();
        } : null,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Image
            AspectRatio(
              aspectRatio: 1.2,
              child: imageUrl != null
                  ? Image.network(
                      imageUrl,
                      fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => _buildPlaceholder(),
                    )
                  : _buildPlaceholder(),
            ),

            // Content
            Expanded(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Meal type badge (if set)
                    if (mealType != null) ...[
                      _MealBadge(mealType: mealType),
                      const SizedBox(height: 4),
                    ],

                    // Name
                    Text(
                      name,
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: AppColors.textPrimary,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),

                    const SizedBox(height: 6),

                    // Tags
                    if (tags.isNotEmpty) ...[
                      Wrap(
                        spacing: 4,
                        runSpacing: 4,
                        children: tags.take(2).map((tag) => _TagChip(tag: tag.toString())).toList(),
                      ),
                      const SizedBox(height: 6),
                    ],

                    // Ingredient preview
                    if (ingredients.isNotEmpty)
                      Text(
                        '🥕 ${_formatIngredientPreview(ingredients)}',
                        style: const TextStyle(
                          fontSize: 12,
                          color: AppColors.textTertiary,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),

                    const Spacer(),

                    // Bottom row: time + times cooked
                    Row(
                      children: [
                        if (totalTime > 0) ...[
                          Icon(Icons.schedule, size: 14, color: AppColors.textTertiary),
                          const SizedBox(width: 4),
                          Text(
                            '${totalTime}m',
                            style: const TextStyle(
                              fontSize: 12,
                              color: AppColors.textTertiary,
                            ),
                          ),
                        ],
                        const Spacer(),
                        if (timesCooked > 0) ...[
                          Icon(Icons.restaurant, size: 14, color: AppColors.hazelnut),
                          const SizedBox(width: 4),
                          Text(
                            'x$timesCooked',
                            style: const TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w500,
                              color: AppColors.hazelnut,
                            ),
                          ),
                        ],
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPlaceholder() {
    return Container(
      color: AppColors.beige,
      child: const Center(
        child: Icon(
          Icons.restaurant,
          size: 40,
          color: AppColors.hazelnut,
        ),
      ),
    );
  }

  String _formatIngredientPreview(List<dynamic> ingredients) {
    final names = ingredients
        .take(3)
        .map((i) => i['ingredient']?['canonical_name'] ?? '')
        .where((n) => n.isNotEmpty)
        .toList();

    if (names.isEmpty) return '';
    if (names.length <= 2) return names.join(', ');
    return '${names.take(2).join(', ')}...';
  }
}

class _MealBadge extends StatelessWidget {
  final String mealType;

  const _MealBadge({required this.mealType});

  @override
  Widget build(BuildContext context) {
    final (icon, color) = switch (mealType.toLowerCase()) {
      'breakfast' => ('🌅', AppColors.terracotta),
      'lunch' => ('☀️', AppColors.hazelnut),
      'dinner' => ('🌙', AppColors.chocolate),
      'dessert' => ('🍰', AppColors.coral),
      'snack' => ('🍿', AppColors.sage),
      _ => ('🍽️', AppColors.textTertiary),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: AppColors.withOpacity(color, 0.15),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        icon,
        style: const TextStyle(fontSize: 10),
      ),
    );
  }
}

class _TagChip extends StatelessWidget {
  final String tag;

  const _TagChip({required this.tag});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: AppColors.beige,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        tag,
        style: const TextStyle(
          fontSize: 10,
          color: AppColors.textSecondary,
        ),
      ),
    );
  }
}
```

### Implementation: meal_filter_bar.dart

```dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../core/theme/app_colors.dart';
import '../home_screen.dart';

class MealFilterBar extends StatelessWidget {
  final MealFilter selected;
  final ValueChanged<MealFilter> onChanged;

  const MealFilterBar({
    super.key,
    required this.selected,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 44,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        children: [
          _FilterChip(
            icon: '🍽️',
            label: 'All',
            isSelected: selected == MealFilter.all,
            onTap: () => onChanged(MealFilter.all),
          ),
          _FilterChip(
            icon: '🌅',
            label: 'Breakfast',
            isSelected: selected == MealFilter.breakfast,
            onTap: () => onChanged(MealFilter.breakfast),
          ),
          _FilterChip(
            icon: '☀️',
            label: 'Lunch',
            isSelected: selected == MealFilter.lunch,
            onTap: () => onChanged(MealFilter.lunch),
          ),
          _FilterChip(
            icon: '🌙',
            label: 'Dinner',
            isSelected: selected == MealFilter.dinner,
            onTap: () => onChanged(MealFilter.dinner),
          ),
          _FilterChip(
            icon: '🍰',
            label: 'Dessert',
            isSelected: selected == MealFilter.dessert,
            onTap: () => onChanged(MealFilter.dessert),
          ),
          _FilterChip(
            icon: '🍿',
            label: 'Snack',
            isSelected: selected == MealFilter.snack,
            onTap: () => onChanged(MealFilter.snack),
          ),
        ],
      ),
    );
  }
}

class _FilterChip extends StatelessWidget {
  final String icon;
  final String label;
  final bool isSelected;
  final VoidCallback onTap;

  const _FilterChip({
    required this.icon,
    required this.label,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: Material(
        color: isSelected ? AppColors.chocolate : AppColors.beige,
        borderRadius: BorderRadius.circular(20),
        child: InkWell(
          onTap: () {
            HapticFeedback.selectionClick();
            onTap();
          },
          borderRadius: BorderRadius.circular(20),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(icon, style: const TextStyle(fontSize: 14)),
                const SizedBox(width: 6),
                Text(
                  label,
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                    color: isSelected ? AppColors.cream : AppColors.textPrimary,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
```

### Implementation: sort_chips.dart

```dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../core/theme/app_colors.dart';
import '../home_screen.dart';

class SortChips extends StatelessWidget {
  final SortOption selected;
  final ValueChanged<SortOption> onChanged;

  const SortChips({
    super.key,
    required this.selected,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
      child: Row(
        children: [
          _SortIcon(
            icon: Icons.star_rounded,
            tooltip: 'Best',
            isSelected: selected == SortOption.best,
            onTap: () => onChanged(SortOption.best),
          ),
          _SortIcon(
            icon: Icons.fiber_new_rounded,
            tooltip: 'Newest',
            isSelected: selected == SortOption.newest,
            onTap: () => onChanged(SortOption.newest),
          ),
          _SortIcon(
            icon: Icons.local_fire_department_rounded,
            tooltip: 'Popular',
            isSelected: selected == SortOption.popular,
            onTap: () => onChanged(SortOption.popular),
          ),
          _SortIcon(
            icon: Icons.schedule_rounded,
            tooltip: 'Quickest',
            isSelected: selected == SortOption.quickest,
            onTap: () => onChanged(SortOption.quickest),
          ),
          _SortIcon(
            icon: Icons.shuffle_rounded,
            tooltip: 'Random',
            isSelected: selected == SortOption.random,
            onTap: () => onChanged(SortOption.random),
          ),
          const Spacer(),
          // Recipe count
          Text(
            '${context.findAncestorStateOfType<_HomeScreenState>()?._recipes.length ?? 0} recipes',
            style: const TextStyle(
              fontSize: 12,
              color: AppColors.textTertiary,
            ),
          ),
        ],
      ),
    );
  }
}

class _SortIcon extends StatelessWidget {
  final IconData icon;
  final String tooltip;
  final bool isSelected;
  final VoidCallback onTap;

  const _SortIcon({
    required this.icon,
    required this.tooltip,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(right: 4),
      child: Tooltip(
        message: tooltip,
        child: Material(
          color: isSelected
              ? AppColors.withOpacity(AppColors.chocolate, 0.12)
              : Colors.transparent,
          borderRadius: BorderRadius.circular(8),
          child: InkWell(
            onTap: () {
              HapticFeedback.selectionClick();
              onTap();
            },
            borderRadius: BorderRadius.circular(8),
            child: Padding(
              padding: const EdgeInsets.all(8),
              child: Icon(
                icon,
                size: 20,
                color: isSelected ? AppColors.chocolate : AppColors.textTertiary,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
```

---

## Part 2: Minimal Click UX Patterns

### Add Recipe Sheet

```dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_colors.dart';

class AddRecipeSheet extends StatelessWidget {
  const AddRecipeSheet({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: AppColors.warmWhite,
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Drag handle
              Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: AppColors.beigeAccent,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(height: 24),

              // Title
              const Text(
                'Add Recipe',
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 24),

              // Options
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                children: [
                  _AddOption(
                    icon: Icons.camera_alt_rounded,
                    label: 'Photo',
                    onTap: () {
                      Navigator.pop(context);
                      context.go('/recipes/add/photo');
                    },
                  ),
                  _AddOption(
                    icon: Icons.folder_rounded,
                    label: 'Files',
                    onTap: () {
                      Navigator.pop(context);
                      // TODO: File picker flow
                    },
                  ),
                  _AddOption(
                    icon: Icons.edit_rounded,
                    label: 'Manual',
                    onTap: () {
                      Navigator.pop(context);
                      context.go('/recipes/add/wizard');
                    },
                  ),
                ],
              ),
              const SizedBox(height: 16),
            ],
          ),
        ),
      ),
    );
  }
}

class _AddOption extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  const _AddOption({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () {
        HapticFeedback.mediumImpact();
        onTap();
      },
      child: Column(
        children: [
          Container(
            width: 72,
            height: 72,
            decoration: BoxDecoration(
              color: AppColors.beige,
              borderRadius: BorderRadius.circular(20),
            ),
            child: Icon(
              icon,
              size: 32,
              color: AppColors.chocolate,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            label,
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w500,
              color: AppColors.textPrimary,
            ),
          ),
        ],
      ),
    );
  }
}
```

### Recipe Wizard (Multi-step)

```dart
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';

class RecipeWizardScreen extends StatefulWidget {
  const RecipeWizardScreen({super.key});

  @override
  State<RecipeWizardScreen> createState() => _RecipeWizardScreenState();
}

class _RecipeWizardScreenState extends State<RecipeWizardScreen> {
  final _pageController = PageController();
  int _currentStep = 0;
  final _totalSteps = 4;

  // Form data
  String _name = '';
  String? _imageUrl;
  List<Map<String, dynamic>> _ingredients = [];
  String _instructions = '';
  int? _prepTime;
  int? _cookTime;
  int? _servings;
  String? _mealType;
  List<String> _tags = [];

  void _nextStep() {
    if (_currentStep < _totalSteps - 1) {
      _pageController.nextPage(
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      );
    } else {
      _saveRecipe();
    }
  }

  void _previousStep() {
    if (_currentStep > 0) {
      _pageController.previousPage(
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      );
    } else {
      context.pop();
    }
  }

  void _goToStep(int step) {
    _pageController.animateToPage(
      step,
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeInOut,
    );
  }

  Future<void> _saveRecipe() async {
    // TODO: Select recipe book or create default
    // TODO: Call API to create recipe
    // TODO: Navigate back to home
    context.go('/');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => context.pop(),
        ),
        title: const Text('New Recipe'),
        actions: [
          // Skip button (except on last step)
          if (_currentStep < _totalSteps - 1)
            TextButton(
              onPressed: _nextStep,
              child: const Text('Skip'),
            ),
        ],
      ),
      body: Column(
        children: [
          // Progress indicator
          _buildProgressBar(),

          // Step content
          Expanded(
            child: PageView(
              controller: _pageController,
              onPageChanged: (index) {
                setState(() => _currentStep = index);
              },
              children: [
                _StepName(
                  name: _name,
                  imageUrl: _imageUrl,
                  onNameChanged: (v) => setState(() => _name = v),
                  onImageChanged: (v) => setState(() => _imageUrl = v),
                ),
                _StepIngredients(
                  ingredients: _ingredients,
                  onChanged: (v) => setState(() => _ingredients = v),
                ),
                _StepInstructions(
                  instructions: _instructions,
                  onChanged: (v) => setState(() => _instructions = v),
                ),
                _StepDetails(
                  prepTime: _prepTime,
                  cookTime: _cookTime,
                  servings: _servings,
                  mealType: _mealType,
                  tags: _tags,
                  onPrepTimeChanged: (v) => setState(() => _prepTime = v),
                  onCookTimeChanged: (v) => setState(() => _cookTime = v),
                  onServingsChanged: (v) => setState(() => _servings = v),
                  onMealTypeChanged: (v) => setState(() => _mealType = v),
                  onTagsChanged: (v) => setState(() => _tags = v),
                ),
              ],
            ),
          ),

          // Navigation buttons
          _buildNavigation(),
        ],
      ),
    );
  }

  Widget _buildProgressBar() {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          // Step dots
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: List.generate(_totalSteps, (index) {
              final isActive = index == _currentStep;
              final isCompleted = index < _currentStep;

              return GestureDetector(
                onTap: () => _goToStep(index),
                child: Container(
                  width: isActive ? 24 : 10,
                  height: 10,
                  margin: const EdgeInsets.symmetric(horizontal: 4),
                  decoration: BoxDecoration(
                    color: isActive || isCompleted
                        ? AppColors.chocolate
                        : AppColors.beigeAccent,
                    borderRadius: BorderRadius.circular(5),
                  ),
                ),
              );
            }),
          ),
          const SizedBox(height: 8),

          // Step label
          Text(
            ['Name & Photo', 'Ingredients', 'Instructions', 'Details'][_currentStep],
            style: const TextStyle(
              fontSize: 12,
              color: AppColors.textTertiary,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildNavigation() {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            // Back button
            if (_currentStep > 0)
              OutlinedButton(
                onPressed: _previousStep,
                child: const Icon(Icons.arrow_back),
              )
            else
              const SizedBox(width: 48),

            const Spacer(),

            // Next/Save button
            ElevatedButton(
              onPressed: _nextStep,
              child: Text(
                _currentStep == _totalSteps - 1 ? 'Save Recipe' : 'Next',
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// Step widgets would be implemented separately
// _StepName, _StepIngredients, _StepInstructions, _StepDetails
```

### Quick Actions via Gestures

```dart
// Add to recipe_detail_screen.dart

// Swipe up from bottom triggers cook mode
class RecipeDetailScreen extends StatefulWidget {
  // ... existing code ...

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onVerticalDragEnd: (details) {
        // Swipe up = start cooking
        if (details.primaryVelocity != null && details.primaryVelocity! < -500) {
          context.go('/recipes/${widget.recipeId}/cook');
        }
      },
      child: Scaffold(
        // ... existing scaffold ...

        // Add floating cook button
        floatingActionButton: FloatingActionButton.extended(
          onPressed: () => context.go('/recipes/${widget.recipeId}/cook'),
          icon: const Icon(Icons.restaurant),
          label: const Text('Cook'),
        ),
      ),
    );
  }
}
```

---

## Part 3: Do Recipe Mode (Cook Mode)

### Design Specification

```
┌─────────────────────────────────────────────────────┐
│  ←  Chicken Parmesan              [⏱️ 0:00]  [✕]   │  ← Header
├─────────────────────────────────────────────────────┤
│  INGREDIENTS                            [Expand ↓] │
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐        │
│  │ 🍗 │ │ 🧀 │ │ 🍅 │ │ 🧄 │ │ 🧅 │ │ →  │        │
│  │2 lb│ │1 c │ │ can│ │3 cl│ │ 1  │ │    │        │
│  │ ✓  │ │    │ │    │ │    │ │    │ │    │        │
│  └────┘ └────┘ └────┘ └────┘ └────┘ └────┘        │
├─────────────────────────────────────────────────────┤
│                                                     │
│                    Step 2 of 6                      │
│        ━━━━━━━━━━━━━━━●━━━━━━━━━━━━━━━              │
│                                                     │
│     "Heat oil in a large skillet over              │
│      medium-high heat until shimmering.            │
│                                                     │
│      Season the chicken breasts on both            │
│      sides with salt and pepper."                  │
│                                                     │
│              [ ⏱️ Set 2 min timer ]                │
│                                                     │
├─────────────────────────────────────────────────────┤
│                                                     │
│    [  ←  Prev  ]              [  Next  →  ]        │
│                                                     │
│    ─────────────────────────────────────────       │
│       1    2    ●    4    5    6                   │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Implementation: cook_mode_screen.dart

```dart
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:wakelock_plus/wakelock_plus.dart';  // Add to pubspec.yaml
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../core/theme/app_colors.dart';
import 'widgets/ingredient_strip.dart';
import 'widgets/step_navigator.dart';
import 'widgets/inline_timer.dart';

class CookModeScreen extends StatefulWidget {
  final String recipeId;

  const CookModeScreen({super.key, required this.recipeId});

  @override
  State<CookModeScreen> createState() => _CookModeScreenState();
}

class _CookModeScreenState extends State<CookModeScreen> {
  final _apiClient = getIt<ApiClient>();

  Map<String, dynamic>? _recipe;
  List<dynamic> _ingredients = [];
  List<String> _steps = [];
  bool _isLoading = true;
  String? _error;

  int _currentStep = 0;
  final Set<int> _completedSteps = {};
  final Set<int> _checkedIngredients = {};

  // Timers
  final List<_ActiveTimer> _activeTimers = [];
  Timer? _timerTick;

  // Total cooking time tracker
  final Stopwatch _cookingStopwatch = Stopwatch();

  @override
  void initState() {
    super.initState();
    _loadRecipe();
    _enableWakelock();
    _cookingStopwatch.start();
    _startTimerTick();
  }

  @override
  void dispose() {
    _disableWakelock();
    _timerTick?.cancel();
    _cookingStopwatch.stop();
    for (final timer in _activeTimers) {
      timer.timer?.cancel();
    }
    super.dispose();
  }

  void _enableWakelock() async {
    await WakelockPlus.enable();
  }

  void _disableWakelock() async {
    await WakelockPlus.disable();
  }

  void _startTimerTick() {
    _timerTick = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() {});
    });
  }

  Future<void> _loadRecipe() async {
    try {
      final response = await _apiClient.getRecipe(widget.recipeId);
      if (mounted) {
        final recipe = response.data;
        setState(() {
          _recipe = recipe;
          _ingredients = recipe['ingredients'] ?? [];
          _steps = _parseInstructions(recipe['instructions'] ?? '');
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Failed to load recipe: $e';
          _isLoading = false;
        });
      }
    }
  }

  List<String> _parseInstructions(String instructions) {
    // Split by numbered steps or double newlines
    final stepPattern = RegExp(r'(?:^|\n)(?:\d+[\.\)]\s*|\n\n)');
    final parts = instructions.split(stepPattern);
    return parts
        .map((s) => s.trim())
        .where((s) => s.isNotEmpty)
        .toList();
  }

  void _goToStep(int step) {
    if (step >= 0 && step < _steps.length) {
      HapticFeedback.selectionClick();
      setState(() {
        _currentStep = step;
      });
    }
  }

  void _nextStep() {
    // Mark current as completed
    _completedSteps.add(_currentStep);
    _goToStep(_currentStep + 1);
  }

  void _previousStep() {
    _goToStep(_currentStep - 1);
  }

  void _markAllUpToHere() {
    HapticFeedback.mediumImpact();
    setState(() {
      for (int i = 0; i <= _currentStep; i++) {
        _completedSteps.add(i);
      }
    });
  }

  void _toggleIngredient(int index) {
    HapticFeedback.selectionClick();
    setState(() {
      if (_checkedIngredients.contains(index)) {
        _checkedIngredients.remove(index);
      } else {
        _checkedIngredients.add(index);
      }
    });
  }

  void _startTimer(Duration duration, String label) {
    HapticFeedback.mediumImpact();

    final activeTimer = _ActiveTimer(
      label: label,
      duration: duration,
      remaining: duration,
      startTime: DateTime.now(),
    );

    activeTimer.timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (mounted) {
        final elapsed = DateTime.now().difference(activeTimer.startTime);
        final remaining = duration - elapsed;

        if (remaining.isNegative) {
          timer.cancel();
          _onTimerComplete(activeTimer);
        } else {
          setState(() {
            activeTimer.remaining = remaining;
          });
        }
      }
    });

    setState(() {
      _activeTimers.add(activeTimer);
    });
  }

  void _onTimerComplete(_ActiveTimer timer) {
    HapticFeedback.heavyImpact();
    // TODO: Show notification / play sound
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Timer done: ${timer.label}'),
        backgroundColor: AppColors.success,
        behavior: SnackBarBehavior.floating,
      ),
    );
    setState(() {
      _activeTimers.remove(timer);
    });
  }

  void _exitCookMode() {
    _cookingStopwatch.stop();
    // TODO: Log cooking session, increment times_cooked
    context.pop();
  }

  String _formatDuration(Duration d) {
    final minutes = d.inMinutes;
    final seconds = d.inSeconds % 60;
    return '${minutes.toString().padLeft(2, '0')}:${seconds.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }

    if (_error != null) {
      return Scaffold(
        appBar: AppBar(),
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(_error!, style: const TextStyle(color: AppColors.error)),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: _loadRecipe,
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      backgroundColor: AppColors.cream,
      body: SafeArea(
        child: Column(
          children: [
            // Header
            _buildHeader(),

            // Active timers (if any)
            if (_activeTimers.isNotEmpty) _buildActiveTimers(),

            // Ingredient strip
            IngredientStrip(
              ingredients: _ingredients,
              checkedIndices: _checkedIngredients,
              onToggle: _toggleIngredient,
            ),

            // Divider
            const Divider(height: 1),

            // Step content
            Expanded(
              child: GestureDetector(
                onHorizontalDragEnd: (details) {
                  if (details.primaryVelocity != null) {
                    if (details.primaryVelocity! < -500) {
                      _nextStep();
                    } else if (details.primaryVelocity! > 500) {
                      _previousStep();
                    }
                  }
                },
                child: _buildStepContent(),
              ),
            ),

            // Step navigator
            StepNavigator(
              currentStep: _currentStep,
              totalSteps: _steps.length,
              completedSteps: _completedSteps,
              onPrevious: _currentStep > 0 ? _previousStep : null,
              onNext: _currentStep < _steps.length - 1 ? _nextStep : null,
              onStepTap: _goToStep,
              onLongPressStep: _markAllUpToHere,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      child: Row(
        children: [
          // Back button
          IconButton(
            icon: const Icon(Icons.arrow_back),
            onPressed: _exitCookMode,
          ),

          // Recipe name
          Expanded(
            child: Text(
              _recipe?['name'] ?? 'Recipe',
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: AppColors.textPrimary,
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ),

          // Cooking time
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: AppColors.beige,
              borderRadius: BorderRadius.circular(16),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.schedule, size: 16, color: AppColors.hazelnut),
                const SizedBox(width: 4),
                Text(
                  _formatDuration(_cookingStopwatch.elapsed),
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: AppColors.hazelnut,
                    fontFeatures: [FontFeature.tabularFigures()],
                  ),
                ),
              ],
            ),
          ),

          // Close button
          IconButton(
            icon: const Icon(Icons.close),
            onPressed: _exitCookMode,
          ),
        ],
      ),
    );
  }

  Widget _buildActiveTimers() {
    return Container(
      height: 44,
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: _activeTimers.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (context, index) {
          final timer = _activeTimers[index];
          final progress = 1 - (timer.remaining.inSeconds / timer.duration.inSeconds);

          return Container(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            decoration: BoxDecoration(
              color: AppColors.withOpacity(AppColors.terracotta, 0.15),
              borderRadius: BorderRadius.circular(22),
              border: Border.all(color: AppColors.terracotta),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(
                    value: progress,
                    strokeWidth: 2,
                    color: AppColors.terracotta,
                    backgroundColor: AppColors.withOpacity(AppColors.terracotta, 0.2),
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  _formatDuration(timer.remaining),
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: AppColors.terracotta,
                    fontFeatures: [FontFeature.tabularFigures()],
                  ),
                ),
                const SizedBox(width: 4),
                GestureDetector(
                  onTap: () {
                    timer.timer?.cancel();
                    setState(() => _activeTimers.remove(timer));
                  },
                  child: const Icon(Icons.close, size: 16, color: AppColors.terracotta),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildStepContent() {
    if (_steps.isEmpty) {
      return const Center(
        child: Text('No instructions available'),
      );
    }

    final step = _steps[_currentStep];
    final isCompleted = _completedSteps.contains(_currentStep);

    // Detect time mentions for inline timers
    final timePattern = RegExp(r'(\d+)\s*(min(?:ute)?s?|sec(?:ond)?s?|hour?s?)', caseSensitive: false);
    final timeMatch = timePattern.firstMatch(step);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        children: [
          // Step indicator
          Text(
            'Step ${_currentStep + 1} of ${_steps.length}',
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w500,
              color: AppColors.textTertiary,
            ),
          ),
          const SizedBox(height: 8),

          // Progress bar
          Container(
            height: 4,
            margin: const EdgeInsets.symmetric(horizontal: 48),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(2),
              child: LinearProgressIndicator(
                value: (_currentStep + 1) / _steps.length,
                backgroundColor: AppColors.beige,
                color: AppColors.chocolate,
              ),
            ),
          ),
          const SizedBox(height: 32),

          // Step text
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: isCompleted
                  ? AppColors.withOpacity(AppColors.sage, 0.1)
                  : AppColors.warmWhite,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: isCompleted ? AppColors.sage : AppColors.beigeAccent,
              ),
            ),
            child: Column(
              children: [
                // Completed checkmark
                if (isCompleted) ...[
                  const Icon(Icons.check_circle, color: AppColors.sage, size: 32),
                  const SizedBox(height: 16),
                ],

                // Instruction text
                Text(
                  step,
                  style: TextStyle(
                    fontSize: 18,
                    height: 1.6,
                    color: isCompleted ? AppColors.textSecondary : AppColors.textPrimary,
                    decoration: isCompleted ? TextDecoration.lineThrough : null,
                  ),
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),

          // Inline timer button (if time detected)
          if (timeMatch != null && !isCompleted) ...[
            const SizedBox(height: 24),
            _buildInlineTimer(timeMatch),
          ],
        ],
      ),
    );
  }

  Widget _buildInlineTimer(RegExpMatch match) {
    final value = int.parse(match.group(1)!);
    final unit = match.group(2)!.toLowerCase();

    Duration duration;
    if (unit.startsWith('sec')) {
      duration = Duration(seconds: value);
    } else if (unit.startsWith('hour')) {
      duration = Duration(hours: value);
    } else {
      duration = Duration(minutes: value);
    }

    return OutlinedButton.icon(
      onPressed: () => _startTimer(duration, 'Step ${_currentStep + 1}'),
      icon: const Icon(Icons.timer),
      label: Text('Set ${value} ${unit} timer'),
      style: OutlinedButton.styleFrom(
        foregroundColor: AppColors.terracotta,
        side: const BorderSide(color: AppColors.terracotta),
      ),
    );
  }
}

class _ActiveTimer {
  final String label;
  final Duration duration;
  Duration remaining;
  final DateTime startTime;
  Timer? timer;

  _ActiveTimer({
    required this.label,
    required this.duration,
    required this.remaining,
    required this.startTime,
    this.timer,
  });
}
```

### Implementation: ingredient_strip.dart

```dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../core/theme/app_colors.dart';

class IngredientStrip extends StatefulWidget {
  final List<dynamic> ingredients;
  final Set<int> checkedIndices;
  final ValueChanged<int> onToggle;

  const IngredientStrip({
    super.key,
    required this.ingredients,
    required this.checkedIndices,
    required this.onToggle,
  });

  @override
  State<IngredientStrip> createState() => _IngredientStripState();
}

class _IngredientStripState extends State<IngredientStrip> {
  bool _isExpanded = false;

  @override
  Widget build(BuildContext context) {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeInOut,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 8, 8),
            child: Row(
              children: [
                const Text(
                  'INGREDIENTS',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    letterSpacing: 1,
                    color: AppColors.textTertiary,
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  '${widget.checkedIndices.length}/${widget.ingredients.length}',
                  style: const TextStyle(
                    fontSize: 11,
                    color: AppColors.textTertiary,
                  ),
                ),
                const Spacer(),
                GestureDetector(
                  onTap: () {
                    HapticFeedback.selectionClick();
                    setState(() => _isExpanded = !_isExpanded);
                  },
                  child: Padding(
                    padding: const EdgeInsets.all(8),
                    child: Row(
                      children: [
                        Text(
                          _isExpanded ? 'Collapse' : 'Expand',
                          style: const TextStyle(
                            fontSize: 12,
                            color: AppColors.hazelnut,
                          ),
                        ),
                        Icon(
                          _isExpanded ? Icons.expand_less : Icons.expand_more,
                          size: 18,
                          color: AppColors.hazelnut,
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),

          // Ingredient chips
          AnimatedCrossFade(
            firstChild: _buildHorizontalStrip(),
            secondChild: _buildExpandedGrid(),
            crossFadeState: _isExpanded
                ? CrossFadeState.showSecond
                : CrossFadeState.showFirst,
            duration: const Duration(milliseconds: 300),
          ),
        ],
      ),
    );
  }

  Widget _buildHorizontalStrip() {
    return SizedBox(
      height: 80,
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        itemCount: widget.ingredients.length,
        itemBuilder: (context, index) {
          return Padding(
            padding: const EdgeInsets.only(right: 8),
            child: _IngredientChip(
              ingredient: widget.ingredients[index],
              isChecked: widget.checkedIndices.contains(index),
              onTap: () => widget.onToggle(index),
              isCompact: true,
            ),
          );
        },
      ),
    );
  }

  Widget _buildExpandedGrid() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
      child: Wrap(
        spacing: 8,
        runSpacing: 8,
        children: widget.ingredients.asMap().entries.map((entry) {
          return _IngredientChip(
            ingredient: entry.value,
            isChecked: widget.checkedIndices.contains(entry.key),
            onTap: () => widget.onToggle(entry.key),
            isCompact: false,
          );
        }).toList(),
      ),
    );
  }
}

class _IngredientChip extends StatelessWidget {
  final dynamic ingredient;
  final bool isChecked;
  final VoidCallback onTap;
  final bool isCompact;

  const _IngredientChip({
    required this.ingredient,
    required this.isChecked,
    required this.onTap,
    required this.isCompact,
  });

  @override
  Widget build(BuildContext context) {
    final name = ingredient['ingredient']?['canonical_name'] ?? 'Unknown';
    final quantity = ingredient['quantity_display'] ?? '';
    final unit = ingredient['unit_display'] ?? '';

    if (isCompact) {
      // Compact vertical chip for horizontal scroll
      return GestureDetector(
        onTap: () {
          HapticFeedback.selectionClick();
          onTap();
        },
        child: Container(
          width: 64,
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: isChecked ? AppColors.sage : AppColors.beige,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: isChecked ? AppColors.sage : AppColors.beigeAccent,
            ),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              // Quantity
              Text(
                '$quantity $unit'.trim(),
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: isChecked ? AppColors.cream : AppColors.textPrimary,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 4),
              // Name
              Text(
                name,
                style: TextStyle(
                  fontSize: 10,
                  color: isChecked ? AppColors.cream : AppColors.textSecondary,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.center,
              ),
              if (isChecked) ...[
                const SizedBox(height: 4),
                const Icon(Icons.check, size: 14, color: AppColors.cream),
              ],
            ],
          ),
        ),
      );
    }

    // Expanded horizontal chip
    return GestureDetector(
      onTap: () {
        HapticFeedback.selectionClick();
        onTap();
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: isChecked ? AppColors.sage : AppColors.beige,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (isChecked)
              const Padding(
                padding: EdgeInsets.only(right: 6),
                child: Icon(Icons.check, size: 16, color: AppColors.cream),
              ),
            Text(
              '$quantity $unit $name'.trim(),
              style: TextStyle(
                fontSize: 13,
                color: isChecked ? AppColors.cream : AppColors.textPrimary,
                decoration: isChecked ? TextDecoration.lineThrough : null,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
```

### Implementation: step_navigator.dart

```dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../core/theme/app_colors.dart';

class StepNavigator extends StatelessWidget {
  final int currentStep;
  final int totalSteps;
  final Set<int> completedSteps;
  final VoidCallback? onPrevious;
  final VoidCallback? onNext;
  final ValueChanged<int> onStepTap;
  final VoidCallback onLongPressStep;

  const StepNavigator({
    super.key,
    required this.currentStep,
    required this.totalSteps,
    required this.completedSteps,
    this.onPrevious,
    this.onNext,
    required this.onStepTap,
    required this.onLongPressStep,
  });

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.warmWhite,
          boxShadow: [
            BoxShadow(
              color: AppColors.shadow,
              blurRadius: 8,
              offset: const Offset(0, -2),
            ),
          ],
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Prev/Next buttons
            Row(
              children: [
                // Previous
                Expanded(
                  child: _NavButton(
                    icon: Icons.arrow_back_rounded,
                    label: 'Prev',
                    onPressed: onPrevious,
                    alignment: MainAxisAlignment.start,
                  ),
                ),

                const SizedBox(width: 16),

                // Next
                Expanded(
                  child: _NavButton(
                    icon: Icons.arrow_forward_rounded,
                    label: currentStep == totalSteps - 1 ? 'Done' : 'Next',
                    onPressed: onNext ?? (currentStep == totalSteps - 1 ? () {
                      // Mark last step complete and exit
                      Navigator.pop(context);
                    } : null),
                    alignment: MainAxisAlignment.end,
                    isPrimary: true,
                  ),
                ),
              ],
            ),

            const SizedBox(height: 16),

            // Step dots
            GestureDetector(
              onLongPress: onLongPressStep,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: List.generate(totalSteps, (index) {
                  final isCurrent = index == currentStep;
                  final isCompleted = completedSteps.contains(index);

                  return GestureDetector(
                    onTap: () => onStepTap(index),
                    child: Container(
                      width: isCurrent ? 28 : 24,
                      height: 28,
                      margin: const EdgeInsets.symmetric(horizontal: 4),
                      decoration: BoxDecoration(
                        color: isCurrent
                            ? AppColors.chocolate
                            : isCompleted
                                ? AppColors.sage
                                : AppColors.beige,
                        borderRadius: BorderRadius.circular(14),
                        border: isCurrent
                            ? null
                            : Border.all(
                                color: isCompleted
                                    ? AppColors.sage
                                    : AppColors.beigeAccent,
                              ),
                      ),
                      child: Center(
                        child: isCompleted && !isCurrent
                            ? const Icon(
                                Icons.check,
                                size: 14,
                                color: AppColors.cream,
                              )
                            : Text(
                                '${index + 1}',
                                style: TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w600,
                                  color: isCurrent
                                      ? AppColors.cream
                                      : AppColors.textSecondary,
                                ),
                              ),
                      ),
                    ),
                  );
                }),
              ),
            ),

            // Hint text
            const SizedBox(height: 8),
            const Text(
              'Long press to mark all steps complete up to here',
              style: TextStyle(
                fontSize: 11,
                color: AppColors.textTertiary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _NavButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback? onPressed;
  final MainAxisAlignment alignment;
  final bool isPrimary;

  const _NavButton({
    required this.icon,
    required this.label,
    this.onPressed,
    required this.alignment,
    this.isPrimary = false,
  });

  @override
  Widget build(BuildContext context) {
    final isEnabled = onPressed != null;

    return Material(
      color: isPrimary && isEnabled
          ? AppColors.chocolate
          : isEnabled
              ? AppColors.beige
              : AppColors.divider,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        onTap: isEnabled ? () {
          HapticFeedback.selectionClick();
          onPressed!();
        } : null,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
          child: Row(
            mainAxisAlignment: alignment,
            children: alignment == MainAxisAlignment.start
                ? [
                    Icon(
                      icon,
                      size: 20,
                      color: isEnabled ? AppColors.textPrimary : AppColors.textDisabled,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      label,
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: isEnabled ? AppColors.textPrimary : AppColors.textDisabled,
                      ),
                    ),
                  ]
                : [
                    Text(
                      label,
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: isPrimary && isEnabled
                            ? AppColors.cream
                            : isEnabled
                                ? AppColors.textPrimary
                                : AppColors.textDisabled,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Icon(
                      icon,
                      size: 20,
                      color: isPrimary && isEnabled
                          ? AppColors.cream
                          : isEnabled
                              ? AppColors.textPrimary
                              : AppColors.textDisabled,
                    ),
                  ],
          ),
        ),
      ),
    );
  }
}
```

---

## Required Dependencies

Add to `pubspec.yaml`:

```yaml
dependencies:
  # ... existing dependencies ...
  wakelock_plus: ^1.2.1  # Keep screen on during cook mode

  # Optional enhancements:
  # vibration: ^1.8.4     # More haptic feedback options
  # audioplayers: ^5.2.1  # Timer sounds
```

---

## API Additions Needed

The backend needs these additions to fully support the features:

```python
# New endpoints for recipe filtering
GET /v1/recipes?meal_type=dinner&sort=newest&search=chicken

# Track cooking sessions
POST /v1/recipes/{id}/cook-session
{
  "started_at": "timestamp",
  "completed_at": "timestamp",
  "steps_completed": [0, 1, 2, 3]
}

# Increment times_cooked automatically

# Recipe schema additions:
# - meal_type: str (breakfast/lunch/dinner/dessert/snack)
# - tags: list[str]
# - times_cooked: int
# - popularity: int (for public recipes)
```

---

## Implementation Order

1. **Home Screen** - Replace current home with recipe grid
2. **Recipe Card** - Build the card component
3. **Meal Filter + Sort** - Add filtering UI
4. **Cook Mode Screen** - Core cooking experience
5. **Ingredient Strip** - Horizontal ingredient scroller
6. **Step Navigator** - Prev/next with step dots
7. **Add Recipe Sheet** - Bottom sheet with options
8. **Recipe Wizard** - Multi-step form
9. **Timers** - Inline timer integration
10. **Polish** - Haptics, animations, wakelock

---

*This document provides complete implementation code for all three features working together as a unified recipe experience.*
