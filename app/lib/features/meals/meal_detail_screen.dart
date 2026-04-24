import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:share_plus/share_plus.dart';

import '../../core/di/injection.dart';
import '../../core/services/auth_service.dart';
import '../../core/services/error_reporter.dart';
import '../../core/state/mutation_failure_copy.dart';
import '../../core/state/mutation_snackbar.dart';
import '../../shared/widgets/error_banner.dart';
import '../calendar/widgets/plan_meal_sheet.dart';
import '../shopping_cart/models/shopping_list.dart';
import '../shopping_cart/services/shopping_cart_service.dart';
import 'models/meal.dart';
import 'providers/meals_provider.dart';
import 'services/meal_service.dart';
import 'widgets/component_collage_hero.dart';
import 'widgets/component_row.dart';

class MealDetailScreen extends ConsumerStatefulWidget {
  final String mealId;
  const MealDetailScreen({super.key, required this.mealId});

  @override
  ConsumerState<MealDetailScreen> createState() => _MealDetailScreenState();
}

class _MealDetailScreenState extends ConsumerState<MealDetailScreen> {
  final _service = getIt<MealService>();

  // Optimistic favorite state — updated immediately on tap, rolled back
  // on failure. Null means "use whatever the provider says."
  bool? _optimisticFavorite;
  bool _busyFavorite = false;
  bool _busyArchive = false;
  bool _busyShare = false;
  bool _busyShop = false;

  Future<void> _toggleFavorite(Meal meal) async {
    if (_busyFavorite) return;
    final currentlyFav = _optimisticFavorite ?? meal.isFavorite;
    setState(() {
      _optimisticFavorite = !currentlyFav;
      _busyFavorite = true;
    });
    try {
      if (currentlyFav) {
        await _service.unfavoriteMeal(meal.id, bookId: meal.recipeBookId);
      } else {
        await _service.favoriteMeal(meal.id, bookId: meal.recipeBookId);
      }
      if (mounted) {
        setState(() {
          _optimisticFavorite = null;
          _busyFavorite = false;
        });
      }
    } catch (e) {
      ErrorReporter.report(
        e,
        StackTrace.current,
        area: 'meals.detail',
        operation: 'toggleFavorite',
      );
      if (mounted) {
        setState(() {
          _optimisticFavorite = currentlyFav;
          _busyFavorite = false;
        });
        showMutationFailureSnackbar(
          context,
          currentlyFav
              ? MutationType.unfavoriteMeal
              : MutationType.favoriteMeal,
          () => _toggleFavorite(meal),
        );
      }
    }
  }

  Future<void> _shareMeal(Meal meal) async {
    if (_busyShare) return;
    setState(() => _busyShare = true);
    try {
      final result = await _service.share(meal.id);
      final shareUrl = 'https://palateful.app/meal-public/${result.token}';
      if (!mounted) return;
      final box = context.findRenderObject() as RenderBox?;
      await Share.share(
        'Check out this meal on Palateful: $shareUrl',
        subject: meal.name,
        sharePositionOrigin: box == null
            ? null
            : box.localToGlobal(Offset.zero) & box.size,
      );
    } catch (e) {
      ErrorReporter.report(
        e,
        StackTrace.current,
        area: 'meals.detail',
        operation: 'shareMeal',
      );
      if (mounted) {
        showMutationFailureSnackbar(
          context,
          MutationType.shareMeal,
          () => _shareMeal(meal),
        );
      }
    } finally {
      if (mounted) setState(() => _busyShare = false);
    }
  }

  /// Launch the plan-meal sheet in Meal mode with this meal pre-filled.
  /// Epic principle 3: "Plan for Date" is the one context where the
  /// toggle flips to Meal by default.
  Future<void> _planForDate(Meal meal) async {
    final result = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (_) => PlanMealSheet(
        initialPlanMealType: PlanMealType.meal,
        initialMealId: meal.id,
        initialMealName: meal.name,
      ),
    );
    if (result == true && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${meal.name} added to calendar')),
      );
    }
  }

  /// Append this Meal's aggregated ingredients to a shopping list without
  /// scheduling an event. Reuses the default-list resolution pattern from
  /// the calendar tile so the user picks a list on first use and sees a
  /// list picker only when multiple lists are active.
  Future<void> _addToShoppingList(Meal meal) async {
    if (_busyShop) return;
    setState(() => _busyShop = true);
    try {
      final cartService = getIt<ShoppingCartService>();
      final authService = getIt<AuthService>();
      List<ShoppingList> lists;
      try {
        lists = await cartService.getShoppingLists();
      } catch (_) {
        if (!mounted) return;
        showMutationFailureSnackbar(
          context,
          MutationType.loadShoppingLists,
          () => _addToShoppingList(meal),
        );
        return;
      }
      if (!mounted) return;
      if (lists.isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('No shopping lists — tap + to create one'),
          ),
        );
        return;
      }

      ShoppingList? target;
      final defaultId = authService.defaultShoppingListId;
      if (defaultId != null) {
        final match = lists.where((l) => l.id == defaultId);
        if (match.isNotEmpty) target = match.first;
      }
      if (target == null && lists.length == 1) {
        target = lists.first;
      } else if (target == null) {
        if (!mounted) return;
        target = await showModalBottomSheet<ShoppingList>(
          context: context,
          builder: (ctx) => SafeArea(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Padding(
                  padding: EdgeInsets.all(16),
                  child: Text(
                    'Choose a shopping list',
                    style: TextStyle(
                        fontWeight: FontWeight.w600, fontSize: 16),
                  ),
                ),
                ...lists.map((list) => ListTile(
                      title: Text(list.name),
                      subtitle: Text('${list.items.length} item(s)'),
                      onTap: () => Navigator.pop(ctx, list),
                    )),
              ],
            ),
          ),
        );
        if (target == null || !mounted) return;
        cartService.setDefaultShoppingList(target.id);
      }

      final result =
          await _service.addToShoppingList(meal.id, target.id);
      if (!mounted) return;
      final n = result.itemsAdded;
      final noun = n == 1 ? '1 item' : '$n items';
      final String message;
      if (n == 0 && result.itemsSkipped == 0) {
        if (result.componentCount == 0) {
          message =
              'Nothing to add — ${meal.name} has no components yet.';
        } else {
          message =
              'Nothing to add — all ${result.componentCount} component(s) were empty or unavailable.';
        }
      } else if (result.itemsSkipped > 0 && n == 0) {
        message = 'Already on your list (skipped ${result.itemsSkipped}).';
      } else if (result.itemsSkipped > 0) {
        message =
            'Added $noun (${result.itemsSkipped} already on list).';
      } else {
        message = 'Added $noun from ${meal.name}';
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(message)),
      );
    } catch (e) {
      ErrorReporter.report(
        e,
        StackTrace.current,
        area: 'meals.detail',
        operation: 'addToShoppingList',
      );
      if (mounted) {
        showMutationFailureSnackbar(
          context,
          MutationType.addEventIngredients,
          () => _addToShoppingList(meal),
        );
      }
    } finally {
      if (mounted) setState(() => _busyShop = false);
    }
  }

  Future<void> _archiveMeal(Meal meal) async {
    if (_busyArchive) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogCtx) => AlertDialog(
        title: const Text('Archive meal?'),
        content: Text(
          'This will move "${meal.name}" to your archive. You can restore it anytime.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogCtx).pop(false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(dialogCtx).pop(true),
            child: const Text('Archive'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    setState(() => _busyArchive = true);
    try {
      await _service.archiveMeal(meal.id, bookId: meal.recipeBookId);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Meal archived')),
        );
        context.pop();
      }
    } catch (e) {
      ErrorReporter.report(
        e,
        StackTrace.current,
        area: 'meals.detail',
        operation: 'archiveMeal',
      );
      if (mounted) {
        setState(() => _busyArchive = false);
        showMutationFailureSnackbar(
          context,
          MutationType.archiveMeal,
          () => _archiveMeal(meal),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final mealAsync = ref.watch(mealByIdProvider(widget.mealId));
    return Scaffold(
      floatingActionButton: mealAsync.maybeWhen(
        data: _buildStartCookingFab,
        orElse: () => null,
      ),
      body: mealAsync.when(
        data: (meal) => _buildBody(meal),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, _) => Scaffold(
          appBar: AppBar(title: const Text('Meal')),
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
      ),
    );
  }

  /// cmm-2 AC4 — bottom-right "Start Cooking" FAB on meal detail.
  /// Hidden when zero components; disabled with a tooltip when all
  /// components are unavailable; enabled when ≥1 is available.
  Widget? _buildStartCookingFab(Meal meal) {
    if (meal.components.isEmpty) return null;
    final anyAvailable = meal.components.any((c) => c.available);
    if (!anyAvailable) {
      return Tooltip(
        message: 'Add a recipe to start cooking',
        child: FloatingActionButton.extended(
          key: const Key('meal_start_cooking_fab_disabled'),
          onPressed: null,
          icon: const Icon(Icons.restaurant_menu),
          label: const Text('Start Cooking'),
        ),
      );
    }
    return FloatingActionButton.extended(
      key: const Key('meal_start_cooking_fab'),
      onPressed: () => context.push('/meals/${meal.id}/cook'),
      icon: const Icon(Icons.restaurant_menu),
      label: const Text('Start Cooking'),
    );
  }

  Widget _buildBody(Meal meal) {
    final textTheme = Theme.of(context).textTheme;
    final colorScheme = Theme.of(context).colorScheme;
    final components = [...meal.components]
      ..sort((a, b) => a.orderIndex.compareTo(b.orderIndex));
    final unavailable = components.where((c) => !c.available).length;
    final total = components.length;
    final favorite = _optimisticFavorite ?? meal.isFavorite;

    return CustomScrollView(
      slivers: [
        SliverAppBar(
          pinned: true,
          expandedHeight: 260,
          flexibleSpace: FlexibleSpaceBar(
            background: ComponentCollageHero(
              components: components,
            ),
          ),
        ),
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(meal.name, style: textTheme.headlineSmall),
                if ((meal.description ?? '').isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Text(
                    meal.description!,
                    style: textTheme.bodyMedium?.copyWith(
                      color: colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
                const SizedBox(height: 16),
                _ActionBar(
                  favorite: favorite,
                  busyFavorite: _busyFavorite,
                  busyArchive: _busyArchive,
                  busyShare: _busyShare,
                  busyShop: _busyShop,
                  onFavorite: () => _toggleFavorite(meal),
                  onPlan: () => _planForDate(meal),
                  onShop: () => _addToShoppingList(meal),
                  onArchive: () => _archiveMeal(meal),
                  onShare: () => _shareMeal(meal),
                  onEdit: () async {
                    await context.push('/meals/${meal.id}/edit');
                    if (mounted) {
                      invalidateMeal(ref, meal.id,
                          bookId: meal.recipeBookId);
                    }
                  },
                ),
                const SizedBox(height: 16),
                if (total > 0 && unavailable == total)
                  const _UnavailableBanner(
                    text: 'All components are unavailable. '
                        'Archive or edit to fix.',
                  )
                else if (unavailable > 0)
                  const _UnavailableBanner(
                    text: 'Some components are unavailable.',
                  ),
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  child: Text(
                    'Recipes (${components.length})',
                    style: textTheme.titleSmall,
                  ),
                ),
              ],
            ),
          ),
        ),
        SliverList.separated(
          itemCount: components.length,
          separatorBuilder: (_, _) => const Divider(height: 1),
          itemBuilder: (_, i) {
            final c = components[i];
            return ComponentRow(
              component: c,
              onTap: () => context.push('/recipes/${c.recipeId}'),
            );
          },
        ),
        const SliverToBoxAdapter(child: SizedBox(height: 24)),
      ],
    );
  }
}

class _ActionBar extends StatelessWidget {
  final bool favorite;
  final bool busyFavorite;
  final bool busyArchive;
  final bool busyShare;
  final bool busyShop;
  final VoidCallback onFavorite;
  final VoidCallback onPlan;
  final VoidCallback onShop;
  final VoidCallback onArchive;
  final VoidCallback onShare;
  final VoidCallback onEdit;

  const _ActionBar({
    required this.favorite,
    required this.busyFavorite,
    required this.busyArchive,
    required this.busyShare,
    required this.busyShop,
    required this.onFavorite,
    required this.onPlan,
    required this.onShop,
    required this.onArchive,
    required this.onShare,
    required this.onEdit,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        _ActionIcon(
          icon: favorite ? Icons.favorite : Icons.favorite_border,
          label: 'Favorite',
          color: favorite ? Colors.pink : null,
          onTap: busyFavorite ? null : onFavorite,
        ),
        _ActionIcon(
          icon: Icons.calendar_today_outlined,
          label: 'Plan',
          onTap: onPlan,
        ),
        _ActionIcon(
          icon: Icons.shopping_cart_outlined,
          label: 'Shop',
          onTap: busyShop ? null : onShop,
          busy: busyShop,
        ),
        _ActionIcon(
          icon: Icons.ios_share,
          label: 'Share',
          onTap: busyShare ? null : onShare,
          busy: busyShare,
        ),
        _ActionIcon(
          icon: Icons.archive_outlined,
          label: 'Archive',
          color: colorScheme.error,
          onTap: busyArchive ? null : onArchive,
        ),
        _ActionIcon(
          icon: Icons.edit_outlined,
          label: 'Edit',
          onTap: onEdit,
        ),
      ],
    );
  }
}

class _ActionIcon extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback? onTap;
  final Color? color;
  final bool busy;

  const _ActionIcon({
    required this.icon,
    required this.label,
    this.onTap,
    this.color,
    this.busy = false,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final effective = color ?? colorScheme.primary;
    final disabled = onTap == null;
    final iconColor = disabled
        ? effective.withValues(alpha: 0.4)
        : effective;
    final glyph = busy
        ? SizedBox(
            width: 18,
            height: 18,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              valueColor: AlwaysStoppedAnimation<Color>(iconColor),
            ),
          )
        : Icon(icon, color: iconColor);
    final body = InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(height: 24, child: Center(child: glyph)),
            const SizedBox(height: 4),
            Text(
              label,
              style: TextStyle(fontSize: 11, color: iconColor),
            ),
          ],
        ),
      ),
    );
    return body;
  }
}

class _UnavailableBanner extends StatelessWidget {
  final String text;
  const _UnavailableBanner({required this.text});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: colorScheme.errorContainer.withValues(alpha: 0.4),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Icon(Icons.info_outline,
              size: 18, color: colorScheme.error),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              text,
              style: textTheme.bodySmall?.copyWith(
                color: colorScheme.onErrorContainer,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
