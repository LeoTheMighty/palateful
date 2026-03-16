import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../shared/widgets/empty_state.dart';

class RecipeBookDetailScreen extends StatefulWidget {
  final String recipeBookId;

  const RecipeBookDetailScreen({super.key, required this.recipeBookId});

  @override
  State<RecipeBookDetailScreen> createState() => _RecipeBookDetailScreenState();
}

class _RecipeBookDetailScreenState extends State<RecipeBookDetailScreen> {
  final _apiClient = getIt<ApiClient>();
  Map<String, dynamic>? _recipeBook;
  List<dynamic> _recipes = [];
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadRecipeBook();
  }

  Future<void> _loadRecipeBook() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final response = await _apiClient.getRecipeBook(widget.recipeBookId);
      if (mounted) {
        setState(() {
          _recipeBook = response.data;
          _recipes = response.data['recipes'] ?? [];
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Could not load recipe book. Please try again.';
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _deleteRecipeBook() async {
    final colorScheme = Theme.of(context).colorScheme;

    final confirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Recipe Book?'),
        content: const Text(
          'This will permanently delete this recipe book and all its recipes.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: colorScheme.error,
              foregroundColor: colorScheme.onError,
            ),
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );

    if (confirm == true) {
      try {
        await _apiClient.deleteRecipeBook(widget.recipeBookId);
        if (mounted) {
          context.pop();
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Could not delete recipe book. Please try again.')),
          );
        }
      }
    }
  }

  Future<void> _renameRecipeBook() async {
    final nameController = TextEditingController(text: _recipeBook?['name'] ?? '');
    final descriptionController = TextEditingController(text: _recipeBook?['description'] ?? '');

    try {
      final result = await showDialog<bool>(
        context: context,
        builder: (context) {
          return StatefulBuilder(
            builder: (context, setDialogState) {
              final nameIsEmpty = nameController.text.trim().isEmpty;
              return AlertDialog(
                title: const Text('Edit Recipe Book'),
                content: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    TextField(
                      controller: nameController,
                      decoration: const InputDecoration(
                        labelText: 'Name',
                      ),
                      autofocus: true,
                      onChanged: (_) => setDialogState(() {}),
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: descriptionController,
                      decoration: const InputDecoration(
                        labelText: 'Description (optional)',
                      ),
                      maxLines: 2,
                    ),
                  ],
                ),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.pop(context, false),
                    child: const Text('Cancel'),
                  ),
                  ElevatedButton(
                    onPressed: nameIsEmpty
                        ? null
                        : () => Navigator.pop(context, true),
                    child: const Text('Save'),
                  ),
                ],
              );
            },
          );
        },
      );

      if (result == true) {
        try {
          await _apiClient.updateRecipeBook(widget.recipeBookId, {
            'name': nameController.text,
            'description': descriptionController.text.isEmpty
                ? null
                : descriptionController.text,
          });
          _loadRecipeBook();
        } catch (e) {
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Could not update recipe book. Please try again.')),
            );
          }
        }
      }
    } finally {
      nameController.dispose();
      descriptionController.dispose();
    }
  }

  Future<void> _addRecipe() async {
    await context.push('/recipes/add/wizard', extra: {
      'recipeBookId': widget.recipeBookId,
    });
    if (mounted) _loadRecipeBook();
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(
        title: Text(_recipeBook?['name'] ?? 'Recipe Book'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
        actions: [
          PopupMenuButton<String>(
            onSelected: (value) {
              if (value == 'edit') {
                _renameRecipeBook();
              } else if (value == 'delete') {
                _deleteRecipeBook();
              }
            },
            itemBuilder: (context) => [
              const PopupMenuItem(
                value: 'edit',
                child: Row(
                  children: [
                    Icon(Icons.edit_outlined),
                    SizedBox(width: 8),
                    Text('Edit'),
                  ],
                ),
              ),
              PopupMenuItem(
                value: 'delete',
                child: Row(
                  children: [
                    Icon(Icons.delete, color: colorScheme.error),
                    const SizedBox(width: 8),
                    Text('Delete', style: TextStyle(color: colorScheme.error)),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _addRecipe,
        child: const Icon(Icons.add),
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
                          onPressed: _loadRecipeBook,
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _loadRecipeBook,
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      // Description
                      if (_recipeBook?['description'] != null) ...[
                        Text(
                          _recipeBook!['description'],
                          style: textTheme.bodyLarge?.copyWith(
                            color: colorScheme.onSurfaceVariant,
                          ),
                        ),
                        const SizedBox(height: 16),
                      ],

                      // Recipes header
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            'Recipes (${_recipes.length})',
                            style: textTheme.titleMedium,
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),

                      // Recipes list or empty state
                      if (_recipes.isEmpty)
                        SizedBox(
                          height: MediaQuery.of(context).size.height * 0.4,
                          child: EmptyStateWidget(
                            icon: Icons.restaurant_menu,
                            title: 'Add your first recipe',
                            subtitle: 'Tap + to add a recipe to this book',
                            actionLabel: 'Add Recipe',
                            actionIcon: Icons.add,
                            onAction: _addRecipe,
                          ),
                        )
                      else
                        ...(_recipes.map((recipe) => _RecipeCard(
                              recipe: recipe,
                              onTap: () async {
                                await context.push('/recipes/${recipe['id']}');
                                _loadRecipeBook();
                              },
                            ))),
                    ],
                  ),
                ),
    );
  }
}

class _RecipeCard extends StatelessWidget {
  final dynamic recipe;
  final VoidCallback onTap;

  const _RecipeCard({required this.recipe, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final imageUrl = recipe['image_url'] as String?;
    final tags = (recipe['tags'] as List?)?.cast<String>() ?? [];

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Hero image area (~60% of card)
            SizedBox(
              height: 180,
              width: double.infinity,
              child: imageUrl != null
                  ? CachedNetworkImage(
                      imageUrl: imageUrl,
                      fit: BoxFit.cover,
                      placeholder: (context, url) => Container(
                        color: colorScheme.surfaceContainerHighest,
                        child: const Center(
                          child: CircularProgressIndicator(strokeWidth: 2),
                        ),
                      ),
                      errorWidget: (context, url, error) => Container(
                        color: colorScheme.surfaceContainerHighest,
                        child: Icon(
                          Icons.restaurant,
                          size: 48,
                          color: colorScheme.onSurfaceVariant,
                        ),
                      ),
                    )
                  : Container(
                      color: colorScheme.surfaceContainerHighest,
                      child: Icon(
                        Icons.restaurant,
                        size: 48,
                        color: colorScheme.onSurfaceVariant,
                      ),
                    ),
            ),

            // Recipe info
            Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    recipe['name'] ?? 'Untitled',
                    style: textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 6),

                  // Metadata chips
                  Wrap(
                    spacing: 8,
                    runSpacing: 4,
                    children: [
                      if (recipe['prep_time'] != null)
                        _MetadataChip(
                          icon: Icons.timer_outlined,
                          label: 'Prep ${recipe['prep_time']}m',
                        ),
                      if (recipe['cook_time'] != null)
                        _MetadataChip(
                          icon: Icons.local_fire_department_outlined,
                          label: 'Cook ${recipe['cook_time']}m',
                        ),
                      if (recipe['servings'] != null)
                        _MetadataChip(
                          icon: Icons.people_outline,
                          label: 'Serves ${recipe['servings']}',
                        ),
                    ],
                  ),

                  // Tags
                  if (tags.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 6,
                      runSpacing: 4,
                      children: tags
                          .map((tag) => Chip(
                                label: Text(tag),
                                labelStyle: textTheme.labelSmall,
                                materialTapTargetSize:
                                    MaterialTapTargetSize.shrinkWrap,
                                visualDensity: VisualDensity.compact,
                                backgroundColor:
                                    colorScheme.surfaceContainerHighest,
                                padding: EdgeInsets.zero,
                              ))
                          .toList(),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MetadataChip extends StatelessWidget {
  final IconData icon;
  final String label;

  const _MetadataChip({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 14, color: colorScheme.outline),
        const SizedBox(width: 4),
        Text(
          label,
          style: textTheme.bodySmall?.copyWith(
            color: colorScheme.outline,
          ),
        ),
      ],
    );
  }
}
