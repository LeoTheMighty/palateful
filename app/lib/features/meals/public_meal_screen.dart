import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/di/injection.dart';
import '../../core/services/error_reporter.dart';
import 'models/meal.dart';
import 'services/meal_service.dart';

/// Unauthenticated read-only view of a Meal fetched by its share token.
/// Route: `/meal-public/:token`.
///
/// Mirrors `PublicRecipeScreen` shape — `StatefulWidget` with `_loadMeal`
/// in `initState`, loading/error/loaded states, shared-via-Palateful
/// footer. Strangers see names + thumbnails + whether each component is
/// itself publicly shared; private component tiles render locked and
/// show a snackbar ("sign in to view") on tap — no login routing from
/// this terminal surface in v1.
class PublicMealScreen extends StatefulWidget {
  final String token;

  const PublicMealScreen({super.key, required this.token});

  @override
  State<PublicMealScreen> createState() => _PublicMealScreenState();
}

class _PublicMealScreenState extends State<PublicMealScreen> {
  final _service = getIt<MealService>();
  PublicMealDto? _meal;
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadMeal();
  }

  Future<void> _loadMeal() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final meal = await _service.getPublicMealByToken(widget.token);
      if (!mounted) return;
      setState(() {
        _meal = meal;
        _isLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = "This meal isn't available.";
        _isLoading = false;
      });
      ErrorReporter.report(
        e,
        StackTrace.current,
        area: 'meals.public',
        operation: 'loadByToken',
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_meal?.name ?? 'Meal'),
        automaticallyImplyLeading: false,
        actions: [
          IconButton(
            icon: const Icon(Icons.close),
            onPressed: () => Navigator.of(context).maybePop(),
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _ErrorView(message: _error!)
              : _LoadedView(meal: _meal!),
    );
  }
}

class _ErrorView extends StatelessWidget {
  final String message;
  const _ErrorView({required this.message});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.link_off_outlined,
              size: 48,
              color: colorScheme.onSurfaceVariant,
            ),
            const SizedBox(height: 16),
            Text(
              message,
              style: textTheme.bodyLarge
                  ?.copyWith(color: colorScheme.onSurfaceVariant),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}

class _LoadedView extends StatelessWidget {
  final PublicMealDto meal;
  const _LoadedView({required this.meal});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return CustomScrollView(
      slivers: [
        SliverToBoxAdapter(
          child: _CollageHero(components: meal.components),
        ),
        SliverPadding(
          padding: const EdgeInsets.all(16),
          sliver: SliverList(
            delegate: SliverChildListDelegate([
              if (meal.recipeBookName.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Text(
                    'From: ${meal.recipeBookName}',
                    style: textTheme.labelMedium
                        ?.copyWith(color: colorScheme.onSurfaceVariant),
                  ),
                ),
              Text(meal.name, style: textTheme.headlineSmall),
              const SizedBox(height: 8),
              if ((meal.description ?? '').isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Text(
                    meal.description!,
                    style: textTheme.bodyLarge
                        ?.copyWith(color: colorScheme.onSurfaceVariant),
                  ),
                ),
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Text(
                  'Recipes (${meal.components.length})',
                  style: textTheme.titleSmall,
                ),
              ),
              ...meal.components
                  .map((c) => _ComponentTile(component: c)),
              const SizedBox(height: 24),
              Center(
                child: Text(
                  'Shared via Palateful',
                  style: textTheme.labelSmall
                      ?.copyWith(color: colorScheme.outline),
                ),
              ),
              const SizedBox(height: 16),
            ]),
          ),
        ),
      ],
    );
  }
}

class _CollageHero extends StatelessWidget {
  final List<PublicMealComponentDto> components;
  const _CollageHero({required this.components});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final images = components
        .map((c) => c.imageUrl)
        .where((u) => u != null && u.isNotEmpty)
        .cast<String>()
        .take(4)
        .toList();

    Widget placeholder() => Container(
          color: colorScheme.surfaceContainerHighest,
          child: Icon(
            Icons.restaurant,
            size: 48,
            color: colorScheme.onSurfaceVariant,
          ),
        );

    Widget cell(String url) => CachedNetworkImage(
          imageUrl: url,
          fit: BoxFit.cover,
          placeholder: (_, _) => placeholder(),
          errorWidget: (_, _, _) => placeholder(),
        );

    Widget body;
    if (images.isEmpty) {
      body = placeholder();
    } else if (images.length == 1) {
      body = cell(images[0]);
    } else if (images.length == 2) {
      body = Row(
        children: [
          Expanded(child: cell(images[0])),
          const SizedBox(width: 2),
          Expanded(child: cell(images[1])),
        ],
      );
    } else if (images.length == 3) {
      body = Row(
        children: [
          Expanded(child: cell(images[0])),
          const SizedBox(width: 2),
          Expanded(
            child: Column(
              children: [
                Expanded(child: cell(images[1])),
                const SizedBox(height: 2),
                Expanded(child: cell(images[2])),
              ],
            ),
          ),
        ],
      );
    } else {
      body = Column(
        children: [
          Expanded(
            child: Row(
              children: [
                Expanded(child: cell(images[0])),
                const SizedBox(width: 2),
                Expanded(child: cell(images[1])),
              ],
            ),
          ),
          const SizedBox(height: 2),
          Expanded(
            child: Row(
              children: [
                Expanded(child: cell(images[2])),
                const SizedBox(width: 2),
                Expanded(child: cell(images[3])),
              ],
            ),
          ),
        ],
      );
    }

    return SizedBox(height: 200, child: body);
  }
}

class _ComponentTile extends StatelessWidget {
  final PublicMealComponentDto component;
  const _ComponentTile({required this.component});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    final thumb = SizedBox(
      width: 48,
      height: 48,
      child: (component.imageUrl == null || component.imageUrl!.isEmpty)
          ? Container(
              color: colorScheme.surfaceContainerHighest,
              child: Icon(
                Icons.restaurant,
                color: colorScheme.onSurfaceVariant,
              ),
            )
          : CachedNetworkImage(
              imageUrl: component.imageUrl!,
              fit: BoxFit.cover,
              errorWidget: (_, _, _) => Container(
                color: colorScheme.surfaceContainerHighest,
                child: Icon(
                  Icons.restaurant,
                  color: colorScheme.onSurfaceVariant,
                ),
              ),
            ),
    );

    final title = Text(
      component.name,
      style: component.hasPublicToken
          ? textTheme.bodyLarge
          : textTheme.bodyLarge
              ?.copyWith(color: colorScheme.onSurfaceVariant),
      maxLines: 2,
      overflow: TextOverflow.ellipsis,
    );

    final subtitle = component.hasPublicToken
        ? null
        : Text(
            'Sign in to view',
            style: textTheme.bodySmall
                ?.copyWith(color: colorScheme.onSurfaceVariant),
          );

    return ListTile(
      leading: ClipRRect(
        borderRadius: BorderRadius.circular(6),
        child: thumb,
      ),
      title: title,
      subtitle: subtitle,
      trailing: Icon(
        component.hasPublicToken
            ? Icons.chevron_right
            : Icons.lock_outline,
        color: component.hasPublicToken
            ? colorScheme.onSurfaceVariant
            : colorScheme.outline,
      ),
      onTap: () {
        if (component.hasPublicToken && component.publicToken != null) {
          context.push('/recipe-public/${component.publicToken}');
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text(
                "This recipe isn't public. Sign in to Palateful to view.",
              ),
            ),
          );
        }
      },
    );
  }
}
