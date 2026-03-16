import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../shared/widgets/empty_state.dart';

class ArchivedRecipeBooksScreen extends StatefulWidget {
  const ArchivedRecipeBooksScreen({super.key});

  @override
  State<ArchivedRecipeBooksScreen> createState() =>
      _ArchivedRecipeBooksScreenState();
}

class _ArchivedRecipeBooksScreenState extends State<ArchivedRecipeBooksScreen> {
  final _apiClient = getIt<ApiClient>();
  List<dynamic> _archivedBooks = [];
  bool _isLoading = true;
  String? _error;
  final Set<String> _restoringIds = {};

  @override
  void initState() {
    super.initState();
    _loadArchivedBooks();
  }

  Future<void> _loadArchivedBooks() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final response = await _apiClient.getArchivedRecipeBooks();
      if (mounted) {
        setState(() {
          _archivedBooks = response.data['items'] ?? [];
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Could not load archived books. Please try again.';
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _restoreBook(dynamic book) async {
    final bookId = book['id']?.toString();
    if (bookId == null) return;
    if (_restoringIds.contains(bookId)) return;
    _restoringIds.add(bookId);

    try {
      HapticFeedback.selectionClick();
      await _apiClient.restoreRecipeBook(bookId);
      if (mounted) {
        setState(() {
          _archivedBooks.removeWhere((b) => b['id']?.toString() == bookId);
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Recipe book restored')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
              content:
                  Text('Could not restore recipe book. Please try again.')),
        );
      }
    } finally {
      _restoringIds.remove(bookId);
    }
  }

  String _formatArchivedDate(String? dateStr) {
    if (dateStr == null) return '';
    try {
      final date = DateTime.parse(dateStr);
      return 'Archived ${date.month}/${date.day}/${date.year}';
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
        title: const Text('Archived Books'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
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
                            style:
                                TextStyle(color: colorScheme.onErrorContainer),
                            textAlign: TextAlign.center,
                          ),
                        ),
                        const SizedBox(height: 16),
                        ElevatedButton(
                          onPressed: _loadArchivedBooks,
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                )
              : _archivedBooks.isEmpty
                  ? EmptyStateWidget(
                      icon: Icons.archive_outlined,
                      title: 'No archived books',
                      subtitle: 'Recipe books you archive will appear here',
                    )
                  : RefreshIndicator(
                      onRefresh: _loadArchivedBooks,
                      child: ListView.builder(
                        padding: const EdgeInsets.all(16),
                        itemCount: _archivedBooks.length,
                        itemBuilder: (context, index) {
                          final book = _archivedBooks[index];
                          final name = book['name'] ?? 'Untitled';
                          final recipeCount = book['recipe_count'] ?? 0;
                          final archivedDate = _formatArchivedDate(
                              book['archived_at']?.toString());

                          return Card(
                            margin: const EdgeInsets.only(bottom: 12),
                            child: Padding(
                              padding: const EdgeInsets.all(16),
                              child: Row(
                                children: [
                                  Container(
                                    width: 48,
                                    height: 48,
                                    decoration: BoxDecoration(
                                      color: colorScheme.surfaceContainerHighest,
                                      borderRadius: BorderRadius.circular(12),
                                    ),
                                    child: Icon(
                                      Icons.book,
                                      color: colorScheme.onSurfaceVariant,
                                    ),
                                  ),
                                  const SizedBox(width: 16),
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          name,
                                          style:
                                              textTheme.titleSmall?.copyWith(
                                            fontWeight: FontWeight.w600,
                                          ),
                                          maxLines: 1,
                                          overflow: TextOverflow.ellipsis,
                                        ),
                                        const SizedBox(height: 4),
                                        Text(
                                          '$recipeCount ${recipeCount == 1 ? 'recipe' : 'recipes'}${archivedDate.isNotEmpty ? ' · $archivedDate' : ''}',
                                          style:
                                              textTheme.bodySmall?.copyWith(
                                            color:
                                                colorScheme.onSurfaceVariant,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                  TextButton.icon(
                                    onPressed: () => _restoreBook(book),
                                    icon: const Icon(Icons.restore, size: 18),
                                    label: const Text('Restore'),
                                  ),
                                ],
                              ),
                            ),
                          );
                        },
                      ),
                    ),
    );
  }
}
