import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/di/injection.dart';
import '../../core/services/error_reporter.dart';
import '../../shared/widgets/error_banner.dart';
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

  Future<void> _toggleFavorite(Meal meal) async {
    if (_busyFavorite) return;
    final currentlyFav = _optimisticFavorite ?? meal.isFavorite;
    setState(() {
      _optimisticFavorite = !currentlyFav;
      _busyFavorite = true;
    });
    try {
      if (currentlyFav) {
        await _service.unfavoriteMeal(meal.id);
      } else {
        await _service.favoriteMeal(meal.id);
      }
      invalidateMeal(ref, meal.id, bookId: meal.recipeBookId);
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
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not update favorite')),
        );
      }
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
      await _service.archiveMeal(meal.id);
      invalidateMeal(ref, meal.id, bookId: meal.recipeBookId);
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
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not archive meal')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final mealAsync = ref.watch(mealByIdProvider(widget.mealId));
    return Scaffold(
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
                  onFavorite: () => _toggleFavorite(meal),
                  onArchive: () => _archiveMeal(meal),
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
  final VoidCallback onFavorite;
  final VoidCallback onArchive;
  final VoidCallback onEdit;

  const _ActionBar({
    required this.favorite,
    required this.busyFavorite,
    required this.busyArchive,
    required this.onFavorite,
    required this.onArchive,
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
          tooltip: 'Available when calendars ship',
          onTap: null,
        ),
        _ActionIcon(
          icon: Icons.shopping_cart_outlined,
          label: 'Shop',
          tooltip: 'Schedule this meal first',
          onTap: null,
        ),
        _ActionIcon(
          icon: Icons.ios_share,
          label: 'Share',
          tooltip: 'Available when sharing ships',
          onTap: null,
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
  final String? tooltip;

  const _ActionIcon({
    required this.icon,
    required this.label,
    this.onTap,
    this.color,
    this.tooltip,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final effective = color ?? colorScheme.primary;
    final disabled = onTap == null;
    final iconColor = disabled
        ? effective.withValues(alpha: 0.4)
        : effective;
    final body = InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: iconColor),
            const SizedBox(height: 4),
            Text(
              label,
              style: TextStyle(fontSize: 11, color: iconColor),
            ),
          ],
        ),
      ),
    );
    if (tooltip != null) {
      return Tooltip(message: tooltip!, child: body);
    }
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
