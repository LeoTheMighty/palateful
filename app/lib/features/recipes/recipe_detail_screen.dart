import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';

class RecipeDetailScreen extends StatefulWidget {
  final String recipeId;

  const RecipeDetailScreen({super.key, required this.recipeId});

  @override
  State<RecipeDetailScreen> createState() => _RecipeDetailScreenState();
}

class _RecipeDetailScreenState extends State<RecipeDetailScreen> {
  final _apiClient = getIt<ApiClient>();
  Map<String, dynamic>? _recipe;
  List<dynamic> _ingredients = [];
  bool _isLoading = true;
  String? _error;
  final Set<int> _checkedIngredients = {};
  bool _isFavorite = false;
  bool _isTogglingFavorite = false;

  @override
  void initState() {
    super.initState();
    _loadRecipe();
  }

  Future<void> _loadRecipe() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final response = await _apiClient.getRecipe(widget.recipeId);
      if (mounted) {
        setState(() {
          _recipe = response.data;
          _ingredients = response.data['ingredients'] ?? [];
          _isFavorite = response.data['is_favorite'] == true;
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

  Future<void> _toggleFavorite() async {
    if (_isTogglingFavorite) return;
    setState(() => _isTogglingFavorite = true);

    // Optimistic update
    final wasFavorite = _isFavorite;
    setState(() => _isFavorite = !_isFavorite);

    try {
      await _apiClient.toggleFavorite(widget.recipeId);
    } catch (e) {
      if (mounted) {
        setState(() => _isFavorite = wasFavorite);
      }
    } finally {
      if (mounted) {
        setState(() => _isTogglingFavorite = false);
      }
    }
  }

  void _startCooking() {
    context.push('/recipes/${widget.recipeId}/cook');
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      floatingActionButton: !_isLoading && _error == null
          ? FloatingActionButton.extended(
              onPressed: _startCooking,
              icon: const Icon(Icons.restaurant),
              label: const Text('Start Cooking'),
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
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: colorScheme.errorContainer,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            _error!,
                            style: TextStyle(
                                color: colorScheme.onErrorContainer),
                            textAlign: TextAlign.center,
                          ),
                        ),
                        const SizedBox(height: 16),
                        ElevatedButton(
                          onPressed: _loadRecipe,
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                )
              : CustomScrollView(
                  slivers: [
                    // App Bar
                    SliverAppBar(
                      expandedHeight: _recipe?['image_url'] != null ? 200 : 0,
                      pinned: true,
                      leading: IconButton(
                        icon: const Icon(Icons.arrow_back),
                        onPressed: () => context.pop(),
                      ),
                      flexibleSpace: _recipe?['image_url'] != null
                          ? FlexibleSpaceBar(
                              background: Image.network(
                                _recipe!['image_url'],
                                fit: BoxFit.cover,
                              ),
                            )
                          : null,
                      title: Text(_recipe?['name'] ?? 'Recipe'),
                      actions: [
                        IconButton(
                          icon: Icon(
                            _isFavorite ? Icons.favorite : Icons.favorite_border,
                            color: _isFavorite ? Colors.red : null,
                          ),
                          onPressed: _toggleFavorite,
                        ),
                        if (_recipe?['can_edit'] == true)
                          IconButton(
                            icon: const Icon(Icons.edit_outlined),
                            onPressed: () async {
                              await context.push('/recipes/${widget.recipeId}/edit');
                              _loadRecipe();
                            },
                          ),
                      ],
                    ),

                    // Content
                    SliverPadding(
                      padding: const EdgeInsets.all(16),
                      sliver: SliverList(
                        delegate: SliverChildListDelegate([
                          // Recipe info
                          if (_recipe?['description'] != null) ...[
                            Text(
                              _recipe!['description'],
                              style: textTheme.bodyLarge?.copyWith(
                                  color: colorScheme.onSurfaceVariant),
                            ),
                            const SizedBox(height: 16),
                          ],

                          // Time and servings
                          Wrap(
                            spacing: 16,
                            runSpacing: 8,
                            children: [
                              if (_recipe?['prep_time'] != null)
                                _InfoChip(
                                  icon: Icons.timer_outlined,
                                  label: 'Prep: ${_recipe!['prep_time']} min',
                                ),
                              if (_recipe?['cook_time'] != null)
                                _InfoChip(
                                  icon: Icons.local_fire_department_outlined,
                                  label: 'Cook: ${_recipe!['cook_time']} min',
                                ),
                              if (_recipe?['servings'] != null)
                                _InfoChip(
                                  icon: Icons.people_outline,
                                  label: 'Serves ${_recipe!['servings']}',
                                ),
                            ],
                          ),
                          const SizedBox(height: 24),

                          // Ingredients section
                          Text(
                            'Ingredients',
                            style: textTheme.titleLarge,
                          ),
                          const SizedBox(height: 8),
                          ...(_ingredients.asMap().entries.map((entry) {
                            final index = entry.key;
                            final ing = entry.value;
                            final ingredientInfo = ing['ingredient'];
                            return CheckboxListTile(
                              value: _checkedIngredients.contains(index),
                              onChanged: (checked) {
                                setState(() {
                                  if (checked == true) {
                                    _checkedIngredients.add(index);
                                  } else {
                                    _checkedIngredients.remove(index);
                                  }
                                });
                              },
                              title: Text(
                                '${ing['quantity_display']} ${ing['unit_display']} ${ingredientInfo?['canonical_name'] ?? 'Unknown'}',
                                style: _checkedIngredients.contains(index)
                                    ? TextStyle(
                                        decoration: TextDecoration.lineThrough,
                                        color: colorScheme.outline,
                                      )
                                    : null,
                              ),
                              subtitle: ing['notes'] != null
                                  ? Text(ing['notes'])
                                  : null,
                              controlAffinity: ListTileControlAffinity.leading,
                              contentPadding: EdgeInsets.zero,
                            );
                          })),
                          const SizedBox(height: 24),

                          // Steps section (structured) or legacy instructions fallback
                          if ((_recipe?['steps'] as List?)?.isNotEmpty == true) ...[
                            Text(
                              'Steps',
                              style: textTheme.titleLarge,
                            ),
                            const SizedBox(height: 8),
                            ...(_recipe!['steps'] as List).asMap().entries.map((entry) {
                              final index = entry.key;
                              final step = entry.value;
                              return Padding(
                                padding: const EdgeInsets.only(bottom: 12),
                                child: Row(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Container(
                                      width: 32,
                                      height: 32,
                                      decoration: BoxDecoration(
                                        color: colorScheme.surfaceContainerHighest,
                                        borderRadius: BorderRadius.circular(8),
                                      ),
                                      child: Center(
                                        child: Text(
                                          '${index + 1}',
                                          style: textTheme.bodyMedium?.copyWith(
                                            fontWeight: FontWeight.w600,
                                            color: colorScheme.secondary,
                                          ),
                                        ),
                                      ),
                                    ),
                                    const SizedBox(width: 12),
                                    Expanded(
                                      child: Padding(
                                        padding: const EdgeInsets.only(top: 6),
                                        child: Text(
                                          step['instruction'] ?? '',
                                          style: textTheme.bodyLarge
                                              ?.copyWith(height: 1.5),
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              );
                            }),
                          ] else if (_recipe?['instructions'] != null) ...[
                            Text(
                              'Instructions',
                              style: textTheme.titleLarge,
                            ),
                            const SizedBox(height: 8),
                            Container(
                              padding: const EdgeInsets.all(16),
                              decoration: BoxDecoration(
                                color: colorScheme.surfaceContainerHighest,
                                borderRadius: BorderRadius.circular(12),
                                border: Border.all(
                                    color: colorScheme.outlineVariant),
                              ),
                              child: Text(
                                _recipe!['instructions'],
                                style: textTheme.bodyLarge
                                    ?.copyWith(height: 1.6),
                              ),
                            ),
                          ],
                          const SizedBox(height: 24),

                          // Tags section
                          if ((_recipe?['tags'] as List?)?.isNotEmpty == true) ...[
                            Text(
                              'Tags',
                              style: textTheme.titleLarge,
                            ),
                            const SizedBox(height: 8),
                            Wrap(
                              spacing: 8,
                              runSpacing: 4,
                              children: (_recipe!['tags'] as List)
                                  .map((tag) => Chip(
                                        label: Text(tag.toString()),
                                        backgroundColor: colorScheme
                                            .surfaceContainerHighest,
                                      ))
                                  .toList(),
                            ),
                            const SizedBox(height: 24),
                          ],

                          // Source URL
                          if (_recipe?['source_url'] != null &&
                              (_recipe!['source_url'] as String).isNotEmpty) ...[
                            InkWell(
                              onTap: () => launchUrl(
                                Uri.parse(_recipe!['source_url']),
                                mode: LaunchMode.externalApplication,
                              ),
                              child: Row(
                                children: [
                                  Icon(Icons.link,
                                      size: 18, color: colorScheme.secondary),
                                  const SizedBox(width: 8),
                                  Expanded(
                                    child: Text(
                                      _recipe!['source_url'],
                                      style: TextStyle(
                                        color: colorScheme.secondary,
                                        decoration: TextDecoration.underline,
                                      ),
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            const SizedBox(height: 24),
                          ],

                          const SizedBox(height: 32),
                        ]),
                      ),
                    ),
                  ],
                ),
    );
  }
}

class _InfoChip extends StatelessWidget {
  final IconData icon;
  final String label;

  const _InfoChip({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: colorScheme.secondaryContainer.withValues(alpha: 0.4),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: colorScheme.secondary),
          const SizedBox(width: 6),
          Text(
            label,
            style: TextStyle(
              color: colorScheme.secondary,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }
}
