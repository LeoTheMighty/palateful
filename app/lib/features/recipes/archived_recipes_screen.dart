import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../shared/widgets/empty_state.dart';

class ArchivedRecipesScreen extends StatefulWidget {
  const ArchivedRecipesScreen({super.key});

  @override
  State<ArchivedRecipesScreen> createState() => _ArchivedRecipesScreenState();
}

class _ArchivedRecipesScreenState extends State<ArchivedRecipesScreen> {
  final _apiClient = getIt<ApiClient>();
  List<dynamic> _archivedRecipes = [];
  bool _isLoading = true;
  String? _error;
  final Set<String> _restoringIds = {};

  @override
  void initState() {
    super.initState();
    _loadArchivedRecipes();
  }

  Future<void> _loadArchivedRecipes() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final response = await _apiClient.getArchivedRecipes();
      if (mounted) {
        setState(() {
          _archivedRecipes = response.data['items'] ?? [];
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Could not load archived recipes. Please try again.';
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _restoreRecipe(dynamic recipe) async {
    final recipeId = recipe['id']?.toString();
    if (recipeId == null) return;
    if (_restoringIds.contains(recipeId)) return;
    _restoringIds.add(recipeId);

    try {
      HapticFeedback.selectionClick();
      await _apiClient.restoreRecipe(recipeId);
      if (mounted) {
        setState(() {
          _archivedRecipes.removeWhere((r) => r['id']?.toString() == recipeId);
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Recipe restored')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not restore recipe. Please try again.')),
        );
      }
    } finally {
      _restoringIds.remove(recipeId);
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
        title: const Text('Archived Recipes'),
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
                            style: TextStyle(color: colorScheme.onErrorContainer),
                            textAlign: TextAlign.center,
                          ),
                        ),
                        const SizedBox(height: 16),
                        ElevatedButton(
                          onPressed: _loadArchivedRecipes,
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                )
              : _archivedRecipes.isEmpty
                  ? EmptyStateWidget(
                      icon: Icons.archive_outlined,
                      title: 'No archived recipes',
                      subtitle: 'Recipes you archive will appear here',
                    )
                  : RefreshIndicator(
                      onRefresh: _loadArchivedRecipes,
                      child: ListView.builder(
                        padding: const EdgeInsets.all(16),
                        itemCount: _archivedRecipes.length,
                        itemBuilder: (context, index) {
                          final recipe = _archivedRecipes[index];
                          final imageUrl = recipe['image_url'] as String?;
                          final name = recipe['name'] ?? 'Untitled';
                          final archivedDate = _formatArchivedDate(
                              recipe['archived_at']?.toString());

                          return Card(
                            margin: const EdgeInsets.only(bottom: 12),
                            clipBehavior: Clip.antiAlias,
                            child: Padding(
                              padding: EdgeInsets.zero,
                              child: Row(
                                children: [
                                  // Image
                                  SizedBox(
                                    width: 80,
                                    height: 80,
                                    child: imageUrl != null
                                        ? Image.network(
                                            imageUrl,
                                            fit: BoxFit.cover,
                                            errorBuilder: (_, __, ___) =>
                                                Container(
                                              color: colorScheme
                                                  .surfaceContainerHighest,
                                              child: Icon(Icons.restaurant,
                                                  color: colorScheme
                                                      .onSurfaceVariant),
                                            ),
                                          )
                                        : Container(
                                            color: colorScheme
                                                .surfaceContainerHighest,
                                            child: Icon(Icons.restaurant,
                                                color: colorScheme
                                                    .onSurfaceVariant),
                                          ),
                                  ),
                                  // Info
                                  Expanded(
                                    child: Padding(
                                      padding: const EdgeInsets.symmetric(
                                          horizontal: 12, vertical: 8),
                                      child: Column(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        children: [
                                          Text(
                                            name,
                                            style: textTheme.titleSmall
                                                ?.copyWith(
                                              fontWeight: FontWeight.w600,
                                            ),
                                            maxLines: 1,
                                            overflow: TextOverflow.ellipsis,
                                          ),
                                          if (archivedDate.isNotEmpty) ...[
                                            const SizedBox(height: 4),
                                            Text(
                                              archivedDate,
                                              style: textTheme.bodySmall
                                                  ?.copyWith(
                                                color: colorScheme
                                                    .onSurfaceVariant,
                                              ),
                                            ),
                                          ],
                                        ],
                                      ),
                                    ),
                                  ),
                                  // Restore button
                                  Padding(
                                    padding: const EdgeInsets.only(right: 8),
                                    child: TextButton.icon(
                                      onPressed: () => _restoreRecipe(recipe),
                                      icon: const Icon(Icons.restore, size: 18),
                                      label: const Text('Restore'),
                                    ),
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
