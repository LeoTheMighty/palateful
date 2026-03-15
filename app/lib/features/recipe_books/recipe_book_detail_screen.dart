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
          _error = 'Failed to load recipe book: $e';
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
          context.go('/recipe-books');
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Failed to delete: $e')),
          );
        }
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: Text(_recipeBook?['name'] ?? 'Recipe Book'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.go('/recipe-books'),
        ),
        actions: [
          PopupMenuButton<String>(
            onSelected: (value) {
              if (value == 'delete') {
                _deleteRecipeBook();
              }
            },
            itemBuilder: (context) => [
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
        onPressed: () {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Create recipe coming soon!')),
          );
        },
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
                          style: Theme.of(context).textTheme.bodyLarge?.copyWith(
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
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),

                      // Recipes list
                      if (_recipes.isEmpty)
                        SizedBox(
                          height: MediaQuery.of(context).size.height * 0.4,
                          child: EmptyStateWidget(
                            icon: Icons.restaurant_menu,
                            title: 'No recipes yet',
                            subtitle: 'Add your first recipe to this book',
                            actionLabel: 'Add Recipe',
                            actionIcon: Icons.add,
                            onAction: () {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(content: Text('Create recipe coming soon!')),
                              );
                            },
                          ),
                        )
                      else
                        ...(_recipes.map((recipe) => Card(
                              margin: const EdgeInsets.only(bottom: 8),
                              child: ListTile(
                                leading: recipe['image_url'] != null
                                    ? ClipRRect(
                                        borderRadius: BorderRadius.circular(10),
                                        child: Image.network(
                                          recipe['image_url'],
                                          width: 56,
                                          height: 56,
                                          fit: BoxFit.cover,
                                          errorBuilder: (_, __, ___) => Container(
                                            width: 56,
                                            height: 56,
                                            decoration: BoxDecoration(
                                              color: colorScheme.primaryContainer,
                                              borderRadius: BorderRadius.circular(10),
                                            ),
                                            child: Icon(
                                              Icons.restaurant,
                                              color: colorScheme.onSurfaceVariant,
                                            ),
                                          ),
                                        ),
                                      )
                                    : Container(
                                        width: 56,
                                        height: 56,
                                        decoration: BoxDecoration(
                                          color: colorScheme.primaryContainer,
                                          borderRadius: BorderRadius.circular(10),
                                        ),
                                        child: Icon(
                                          Icons.restaurant,
                                          color: colorScheme.onSurfaceVariant,
                                        ),
                                      ),
                                title: Text(recipe['name'] ?? 'Untitled'),
                                subtitle: Text(
                                  _formatTime(recipe),
                                  style: TextStyle(
                                    color: colorScheme.outline,
                                  ),
                                ),
                                trailing: Icon(
                                  Icons.chevron_right,
                                  color: colorScheme.outline,
                                ),
                                onTap: () =>
                                    context.go('/recipes/${recipe['id']}'),
                              ),
                            ))),
                    ],
                  ),
                ),
    );
  }

  String _formatTime(Map<String, dynamic> recipe) {
    final parts = <String>[];
    if (recipe['prep_time'] != null) {
      parts.add('Prep: ${recipe['prep_time']}m');
    }
    if (recipe['cook_time'] != null) {
      parts.add('Cook: ${recipe['cook_time']}m');
    }
    if (recipe['servings'] != null) {
      parts.add('Serves ${recipe['servings']}');
    }
    return parts.isEmpty ? 'No time info' : parts.join(' · ');
  }
}
