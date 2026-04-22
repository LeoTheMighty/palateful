import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../core/services/auth_service.dart';
import '../../core/state/mutation_failure_copy.dart';
import '../../core/state/mutation_snackbar.dart';
import '../../shared/widgets/empty_state.dart';
import '../../core/services/error_reporter.dart';
import '../../shared/widgets/error_banner.dart';
import 'services/recipe_book_service.dart';

class RecipeBooksScreen extends StatefulWidget {
  const RecipeBooksScreen({super.key});

  @override
  State<RecipeBooksScreen> createState() => _RecipeBooksScreenState();
}

class _RecipeBooksScreenState extends State<RecipeBooksScreen> {
  final _apiClient = getIt<ApiClient>();
  final _bookService = getIt<RecipeBookService>();
  List<dynamic> _recipeBooks = [];
  bool _isLoading = true;
  String? _error;
  String? _errorDetail;

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
          _errorDetail = ErrorReporter.detail(e);
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
          final book = await _bookService.createRecipeBook({
            'name': nameController.text,
            'description': descriptionController.text.isEmpty
                ? null
                : descriptionController.text,
          });
          // If this is the user's first book, auto-set as default
          final authService = getIt<AuthService>();
          if (authService.defaultRecipeBookId == null && book.isNotEmpty) {
            final newBookId = book['id']?.toString();
            if (newBookId != null) {
              await _apiClient.setDefaultRecipeBook(newBookId);
              authService.updateDefaultRecipeBook(
                defaultRecipeBookId: newBookId,
              );
              if (mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('This is now your default recipe book')),
                );
              }
            }
          }
          _loadRecipeBooks();
        } catch (e) {
          if (mounted) {
            showMutationFailureSnackbar(
              context,
              MutationType.createRecipeBook,
              _createRecipeBook,
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
        actions: [
          IconButton(
            icon: const Icon(Icons.archive_outlined),
            tooltip: 'Archived Books',
            onPressed: () async {
              await context.push('/recipe-books/archived');
              _loadRecipeBooks();
            },
          ),
        ],
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
                        ErrorBanner(message: _error!, detail: _errorDetail),
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
                            final isShared = book['is_shared'] as bool? ?? false;
                            final userRole = book['user_role'] as String? ?? 'owner';
                            final bookId = book['id']?.toString() ?? '';
                            final isDefault = getIt<AuthService>().defaultRecipeBookId == bookId;

                            Color roleChipColor(String role) {
                              switch (role) {
                                case 'owner':
                                  return colorScheme.primaryContainer;
                                case 'editor':
                                  return colorScheme.tertiaryContainer;
                                default:
                                  return colorScheme.surfaceContainerHighest;
                              }
                            }

                            Color roleChipTextColor(String role) {
                              switch (role) {
                                case 'owner':
                                  return colorScheme.onPrimaryContainer;
                                case 'editor':
                                  return colorScheme.onTertiaryContainer;
                                default:
                                  return colorScheme.onSurfaceVariant;
                              }
                            }

                            return Card(
                              margin: const EdgeInsets.only(bottom: 12),
                              child: InkWell(
                                borderRadius: BorderRadius.circular(12),
                                onTap: () async {
                                  await context.push('/recipe-books/${book['id']}');
                                  _loadRecipeBooks();
                                },
                                onLongPress: () {
                                  showModalBottomSheet(
                                    context: context,
                                    builder: (ctx) => SafeArea(
                                      child: Column(
                                        mainAxisSize: MainAxisSize.min,
                                        children: [
                                          ListTile(
                                            leading: Icon(
                                              isDefault ? Icons.star : Icons.star_outline,
                                              color: isDefault ? Colors.amber : null,
                                            ),
                                            title: Text(isDefault
                                                ? 'This is your default book'
                                                : 'Set as default'),
                                            enabled: !isDefault,
                                            onTap: () async {
                                              Navigator.pop(ctx);
                                              try {
                                                final resp = await _apiClient.setDefaultRecipeBook(bookId);
                                                final authService = getIt<AuthService>();
                                                authService.updateDefaultRecipeBook(
                                                  defaultRecipeBookId: resp.data['default_recipe_book_id']?.toString(),
                                                  previousRecipeBookId: resp.data['previous_recipe_book_id']?.toString(),
                                                );
                                                if (mounted) {
                                                  ScaffoldMessenger.of(context).showSnackBar(
                                                    SnackBar(
                                                      content: Text(
                                                          '${book['name'] ?? 'Recipe Book'} is now your default book'),
                                                    ),
                                                  );
                                                  setState(() {}); // Refresh badge
                                                }
                                              } catch (_) {}
                                            },
                                          ),
                                        ],
                                      ),
                                    ),
                                  );
                                },
                                child: Padding(
                                  padding: const EdgeInsets.all(16),
                                  child: Row(
                                    children: [
                                      Container(
                                        width: 48,
                                        height: 48,
                                        decoration: BoxDecoration(
                                          color: isShared
                                              ? colorScheme.secondaryContainer
                                              : colorScheme.primaryContainer,
                                          borderRadius: BorderRadius.circular(12),
                                        ),
                                        child: Icon(
                                          isShared ? Icons.book_outlined : Icons.book,
                                          color: isShared
                                              ? colorScheme.onSecondaryContainer
                                              : colorScheme.onPrimaryContainer,
                                        ),
                                      ),
                                      const SizedBox(width: 16),
                                      Expanded(
                                        child: Column(
                                          crossAxisAlignment: CrossAxisAlignment.start,
                                          children: [
                                            Row(
                                              children: [
                                                Flexible(
                                                  child: Text(
                                                    book['name'] ?? 'Untitled',
                                                    style: textTheme.titleMedium?.copyWith(
                                                      fontWeight: FontWeight.w600,
                                                    ),
                                                    overflow: TextOverflow.ellipsis,
                                                  ),
                                                ),
                                                if (isDefault) ...[
                                                  const SizedBox(width: 6),
                                                  Icon(
                                                    Icons.star,
                                                    size: 14,
                                                    color: Colors.amber.shade700,
                                                  ),
                                                ],
                                              ],
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
                                            if (isShared) ...[
                                              const SizedBox(height: 6),
                                              Container(
                                                padding: const EdgeInsets.symmetric(
                                                    horizontal: 8, vertical: 2),
                                                decoration: BoxDecoration(
                                                  color: roleChipColor(userRole),
                                                  borderRadius: BorderRadius.circular(8),
                                                ),
                                                child: Text(
                                                  userRole,
                                                  style: textTheme.labelSmall?.copyWith(
                                                    color: roleChipTextColor(userRole),
                                                    fontWeight: FontWeight.w600,
                                                  ),
                                                ),
                                              ),
                                            ],
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
