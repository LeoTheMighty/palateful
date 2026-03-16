import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../shared/widgets/empty_state.dart';

class RecipeBooksScreen extends StatefulWidget {
  const RecipeBooksScreen({super.key});

  @override
  State<RecipeBooksScreen> createState() => _RecipeBooksScreenState();
}

class _RecipeBooksScreenState extends State<RecipeBooksScreen> {
  final _apiClient = getIt<ApiClient>();
  List<dynamic> _recipeBooks = [];
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadRecipeBooks();
  }

  Future<void> _loadRecipeBooks() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final response = await _apiClient.getRecipeBooks();
      if (mounted) {
        setState(() {
          _recipeBooks = response.data['items'] ?? [];
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Could not load recipe books. Please try again.';
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _createRecipeBook() async {
    final nameController = TextEditingController();
    final descriptionController = TextEditingController();

    try {
      final result = await showDialog<bool>(
        context: context,
        builder: (context) {
          return StatefulBuilder(
            builder: (context, setDialogState) {
              final nameIsEmpty = nameController.text.trim().isEmpty;
              return AlertDialog(
                title: const Text('New Recipe Book'),
                content: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    TextField(
                      controller: nameController,
                      decoration: const InputDecoration(
                        labelText: 'Name',
                        hintText: 'My Recipe Book',
                      ),
                      autofocus: true,
                      onChanged: (_) => setDialogState(() {}),
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: descriptionController,
                      decoration: const InputDecoration(
                        labelText: 'Description (optional)',
                        hintText: 'A collection of my favorite recipes',
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
                    child: const Text('Create'),
                  ),
                ],
              );
            },
          );
        },
      );

      if (result == true && nameController.text.isNotEmpty) {
        try {
          await _apiClient.createRecipeBook({
            'name': nameController.text,
            'description': descriptionController.text.isEmpty
                ? null
                : descriptionController.text,
          });
          _loadRecipeBooks();
        } catch (e) {
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Could not create recipe book. Please try again.')),
            );
          }
        }
      }
    } finally {
      nameController.dispose();
      descriptionController.dispose();
    }
  }

  String _formatUpdatedAt(String? updatedAt) {
    if (updatedAt == null) return '';
    try {
      final date = DateTime.parse(updatedAt);
      final now = DateTime.now();
      final diff = now.difference(date);
      if (diff.inDays == 0) return 'Updated today';
      if (diff.inDays == 1) return 'Updated yesterday';
      if (diff.inDays < 7) return 'Updated ${diff.inDays}d ago';
      if (diff.inDays < 30) return 'Updated ${diff.inDays ~/ 7}w ago';
      return 'Updated ${date.month}/${date.day}/${date.year}';
    } catch (_) {
      return '';
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Recipe Books'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.go('/'),
        ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _createRecipeBook,
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
                          onPressed: _loadRecipeBooks,
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _loadRecipeBooks,
                  child: _recipeBooks.isEmpty
                      ? ListView(
                          children: [
                            SizedBox(
                              height: MediaQuery.of(context).size.height * 0.6,
                              child: EmptyStateWidget(
                                icon: Icons.book_outlined,
                                title: 'No recipe books yet',
                                subtitle: 'Create your first book to organize your collection',
                                actionLabel: 'Create Recipe Book',
                                onAction: _createRecipeBook,
                                actionIcon: Icons.add,
                              ),
                            ),
                          ],
                        )
                      : ListView.builder(
                          padding: const EdgeInsets.all(16),
                          itemCount: _recipeBooks.length,
                          itemBuilder: (context, index) {
                            final book = _recipeBooks[index];
                            final recipeCount = book['recipe_count'] ?? 0;
                            final description = book['description'] as String?;
                            final updatedAt = _formatUpdatedAt(book['updated_at']?.toString());

                            return Card(
                              margin: const EdgeInsets.only(bottom: 12),
                              child: InkWell(
                                borderRadius: BorderRadius.circular(12),
                                onTap: () async {
                                  await context.push('/recipe-books/${book['id']}');
                                  _loadRecipeBooks();
                                },
                                child: Padding(
                                  padding: const EdgeInsets.all(16),
                                  child: Row(
                                    children: [
                                      Container(
                                        width: 48,
                                        height: 48,
                                        decoration: BoxDecoration(
                                          color: colorScheme.primaryContainer,
                                          borderRadius: BorderRadius.circular(12),
                                        ),
                                        child: Icon(
                                          Icons.book,
                                          color: colorScheme.onPrimaryContainer,
                                        ),
                                      ),
                                      const SizedBox(width: 16),
                                      Expanded(
                                        child: Column(
                                          crossAxisAlignment: CrossAxisAlignment.start,
                                          children: [
                                            Text(
                                              book['name'] ?? 'Untitled',
                                              style: textTheme.titleMedium?.copyWith(
                                                fontWeight: FontWeight.w600,
                                              ),
                                            ),
                                            const SizedBox(height: 4),
                                            if (description != null && description.isNotEmpty) ...[
                                              Text(
                                                description,
                                                style: textTheme.bodySmall?.copyWith(
                                                  color: colorScheme.onSurfaceVariant,
                                                ),
                                                maxLines: 1,
                                                overflow: TextOverflow.ellipsis,
                                              ),
                                              const SizedBox(height: 4),
                                            ],
                                            Row(
                                              children: [
                                                Text(
                                                  '$recipeCount ${recipeCount == 1 ? 'recipe' : 'recipes'}',
                                                  style: textTheme.bodySmall?.copyWith(
                                                    color: colorScheme.outline,
                                                  ),
                                                ),
                                                if (updatedAt.isNotEmpty) ...[
                                                  Text(
                                                    ' · ',
                                                    style: textTheme.bodySmall?.copyWith(
                                                      color: colorScheme.outline,
                                                    ),
                                                  ),
                                                  Text(
                                                    updatedAt,
                                                    style: textTheme.bodySmall?.copyWith(
                                                      color: colorScheme.outline,
                                                    ),
                                                  ),
                                                ],
                                              ],
                                            ),
                                          ],
                                        ),
                                      ),
                                      Icon(
                                        Icons.chevron_right,
                                        color: colorScheme.outline,
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            );
                          },
                        ),
                ),
    );
  }
}
