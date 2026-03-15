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
          _error = 'Failed to load recipe books: $e';
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
        builder: (context) => AlertDialog(
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
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Create'),
            ),
          ],
        ),
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
              SnackBar(content: Text('Failed to create recipe book: $e')),
            );
          }
        }
      }
    } finally {
      nameController.dispose();
      descriptionController.dispose();
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

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
                            return Card(
                              margin: const EdgeInsets.only(bottom: 12),
                              child: ListTile(
                                leading: Container(
                                  width: 44,
                                  height: 44,
                                  decoration: BoxDecoration(
                                    color: colorScheme.primaryContainer,
                                    borderRadius: BorderRadius.circular(10),
                                  ),
                                  child: Icon(
                                    Icons.book,
                                    color: colorScheme.onSurfaceVariant,
                                  ),
                                ),
                                title: Text(book['name'] ?? 'Untitled'),
                                subtitle: Text(
                                  book['description'] ??
                                      '${book['recipe_count'] ?? 0} recipes',
                                ),
                                trailing: Icon(
                                  Icons.chevron_right,
                                  color: colorScheme.outline,
                                ),
                                onTap: () =>
                                    context.go('/recipe-books/${book['id']}'),
                              ),
                            );
                          },
                        ),
                ),
    );
  }
}
