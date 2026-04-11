import 'dart:async';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';
import '../../../core/services/auth_service.dart';

class ShareImportScreen extends StatefulWidget {
  final String initialUrl;

  const ShareImportScreen({super.key, required this.initialUrl});

  @override
  State<ShareImportScreen> createState() => _ShareImportScreenState();
}

class _ShareImportScreenState extends State<ShareImportScreen> {
  final _apiClient = getIt<ApiClient>();
  final _authService = getIt<AuthService>();

  // Import state
  bool _isImporting = true;
  String? _importJobId;
  String? _importStatus;
  Timer? _pollTimer;
  int _pollCount = 0;
  static const _maxPolls = 120; // 10 minutes at 5s intervals (GPU cold start can take 5+ min)

  // Result state
  Map<String, dynamic>? _importItem;
  Map<String, dynamic>? _parsedRecipe;
  bool _isApproving = false;
  String? _error;
  String? _selectedBookId;
  String? _selectedBookName;

  @override
  void initState() {
    super.initState();
    _loadBooksAndStartImport();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadBooksAndStartImport() async {
    try {
      final response = await _apiClient.getRecipeBooks();
      if (!mounted) return;

      final books = response.data['items'] as List? ?? [];
      if (books.isEmpty) {
        setState(() {
          _isImporting = false;
          _error = 'No recipe books available. Create one first.';
        });
        return;
      }

      final defaultId = _authService.defaultRecipeBookId;
      Map<String, dynamic>? targetBook;

      if (defaultId != null) {
        targetBook = books.cast<Map<String, dynamic>>().firstWhere(
          (b) => b['id']?.toString() == defaultId,
          orElse: () => books.first as Map<String, dynamic>,
        );
      } else {
        targetBook = books.first as Map<String, dynamic>;
      }

      _selectedBookId = targetBook['id']?.toString();
      _selectedBookName = targetBook['name'] as String?;

      await _startImport();
    } catch (e) {
      if (mounted) {
        setState(() {
          _isImporting = false;
          _error = 'Could not load recipe books.';
        });
      }
    }
  }

  Future<void> _startImport() async {
    if (_selectedBookId == null) return;

    setState(() {
      _isImporting = true;
      _error = null;
    });

    try {
      final response = await _apiClient.startImport(
        _selectedBookId!,
        sourceType: 'url',
        url: widget.initialUrl,
      );
      if (mounted) {
        _importJobId = response.data['id']?.toString();
        _importStatus = response.data['status']?.toString();
        _startPolling();
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isImporting = false;
          _error = 'Could not start import. Please try again.';
        });
      }
    }
  }

  void _startPolling() {
    _pollTimer?.cancel();
    _pollCount = 0;
    _pollTimer = Timer.periodic(const Duration(seconds: 2), (_) {
      _pollImportJob();
    });
  }

  Future<void> _pollImportJob() async {
    if (_importJobId == null || !mounted) return;

    _pollCount++;
    if (_pollCount > _maxPolls) {
      _pollTimer?.cancel();
      setState(() {
        _isImporting = false;
        _error = 'Import is taking longer than expected. Please try again later.';
      });
      return;
    }

    try {
      final response = await _apiClient.getImportJob(_importJobId!);
      if (!mounted) return;

      final status = response.data['status']?.toString();
      setState(() => _importStatus = status);

      if (status == 'awaiting_review' || status == 'completed') {
        _pollTimer?.cancel();
        await _loadImportItems();
      } else if (status == 'failed') {
        _pollTimer?.cancel();
        setState(() {
          _isImporting = false;
          _error = 'Recipe extraction failed. The URL may not contain a recipe.';
        });
      }
    } catch (e) {
      // Keep polling on transient errors
    }
  }

  Future<void> _loadImportItems() async {
    if (_importJobId == null) return;

    try {
      final response = await _apiClient.listImportItems(_importJobId!);
      if (!mounted) return;

      final items = response.data['items'] as List? ?? [];
      if (items.isNotEmpty) {
        final item = items.first;
        setState(() {
          _importItem = item;
          _parsedRecipe = item['parsed_recipe'] as Map<String, dynamic>?;
          _isImporting = false;
        });
      } else {
        setState(() {
          _isImporting = false;
          _error = 'No recipe data was extracted from this URL.';
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isImporting = false;
          _error = 'Could not load extracted recipe.';
        });
      }
    }
  }

  Future<void> _approve() async {
    if (_isApproving || _importItem == null) return;

    final itemId = _importItem!['id']?.toString();
    if (itemId == null) return;

    setState(() => _isApproving = true);
    try {
      HapticFeedback.selectionClick();
      await _apiClient.approveImportItem(itemId);
      if (mounted) {
        final bookName = _selectedBookName ?? 'your book';
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Recipe saved to $bookName')),
        );
        context.go('/');
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isApproving = false);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not save recipe.')),
        );
      }
    }
  }

  Future<void> _dismiss() async {
    if (_importItem != null) {
      final itemId = _importItem!['id']?.toString();
      if (itemId != null) {
        try {
          await _apiClient.skipImportItem(itemId);
        } catch (_) {}
      }
    }
    if (mounted) context.go('/');
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Save Recipe'),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => context.go('/'),
        ),
      ),
      body: _isImporting
          ? _buildProgress(colorScheme, textTheme)
          : _error != null
              ? _buildError(colorScheme, textTheme)
              : _parsedRecipe != null
                  ? _buildPreview(colorScheme, textTheme)
                  : _buildError(colorScheme, textTheme),
    );
  }

  Widget _buildProgress(ColorScheme colorScheme, TextTheme textTheme) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const CircularProgressIndicator(),
            const SizedBox(height: 24),
            Text(
              _importStatus == 'processing'
                  ? 'Extracting recipe...'
                  : 'Starting import...',
              style: textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Text(
              widget.initialUrl,
              style: textTheme.bodySmall?.copyWith(color: colorScheme.outline),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              textAlign: TextAlign.center,
            ),
            if (_selectedBookName != null) ...[
              const SizedBox(height: 16),
              Text(
                'Saving to $_selectedBookName',
                style: textTheme.bodyMedium?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildError(ColorScheme colorScheme, TextTheme textTheme) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.error_outline, size: 64, color: colorScheme.error),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: colorScheme.errorContainer,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                _error ?? 'Something went wrong.',
                style: TextStyle(color: colorScheme.onErrorContainer),
                textAlign: TextAlign.center,
              ),
            ),
            const SizedBox(height: 24),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                OutlinedButton(
                  onPressed: () => context.go('/'),
                  child: const Text('Close'),
                ),
                const SizedBox(width: 12),
                FilledButton(
                  onPressed: _startImport,
                  child: const Text('Retry'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPreview(ColorScheme colorScheme, TextTheme textTheme) {
    final name = _parsedRecipe!['name'] ?? 'Untitled Recipe';
    final description = _parsedRecipe!['description'] as String?;
    final imageUrl = _parsedRecipe!['image_url'] as String?;
    final ingredients = _parsedRecipe!['ingredients'] as List? ?? [];
    final instructions = _parsedRecipe!['instructions'] as String?;
    final prepTime = _parsedRecipe!['prep_time_minutes'];
    final cookTime = _parsedRecipe!['cook_time_minutes'];
    final servings = _parsedRecipe!['servings'];
    final bookName = _selectedBookName ?? 'Recipe Book';

    return Column(
      children: [
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              // Image
              if (imageUrl != null)
                ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: CachedNetworkImage(
                    imageUrl: imageUrl,
                    height: 200,
                    width: double.infinity,
                    fit: BoxFit.cover,
                    errorWidget: (_, _, _) => const SizedBox.shrink(),
                  ),
                ),
              if (imageUrl != null) const SizedBox(height: 16),

              // Name
              Text(
                name,
                style: textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
              if (description != null) ...[
                const SizedBox(height: 8),
                Text(
                  description,
                  style: textTheme.bodyMedium?.copyWith(
                    color: colorScheme.onSurfaceVariant,
                  ),
                ),
              ],

              // Metadata
              if (prepTime != null || cookTime != null || servings != null) ...[
                const SizedBox(height: 12),
                Wrap(
                  spacing: 12,
                  children: [
                    if (prepTime != null)
                      Chip(
                        avatar: const Icon(Icons.timer_outlined, size: 16),
                        label: Text('Prep ${prepTime}m'),
                        visualDensity: VisualDensity.compact,
                      ),
                    if (cookTime != null)
                      Chip(
                        avatar: const Icon(Icons.local_fire_department_outlined, size: 16),
                        label: Text('Cook ${cookTime}m'),
                        visualDensity: VisualDensity.compact,
                      ),
                    if (servings != null)
                      Chip(
                        avatar: const Icon(Icons.people_outline, size: 16),
                        label: Text('Serves $servings'),
                        visualDensity: VisualDensity.compact,
                      ),
                  ],
                ),
              ],

              // Saving to book
              if (_selectedBookName != null) ...[
                const SizedBox(height: 12),
                Text(
                  'Saving to $_selectedBookName',
                  style: textTheme.bodySmall?.copyWith(
                    color: colorScheme.outline,
                  ),
                ),
              ],

              // Ingredients
              if (ingredients.isNotEmpty) ...[
                const SizedBox(height: 24),
                Text(
                  'Ingredients (${ingredients.length})',
                  style: textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 8),
                ...ingredients.map((ing) {
                  final text = ing is Map ? (ing['text'] ?? '') : ing.toString();
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 2),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('  \u2022  ', style: textTheme.bodyMedium),
                        Expanded(
                          child: Text(text, style: textTheme.bodyMedium),
                        ),
                      ],
                    ),
                  );
                }),
              ],

              // Instructions
              if (instructions != null && instructions.isNotEmpty) ...[
                const SizedBox(height: 24),
                Text(
                  'Instructions',
                  style: textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 8),
                Text(instructions, style: textTheme.bodyMedium),
              ],

              const SizedBox(height: 32),
            ],
          ),
        ),

        // Bottom action bar
        SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                OutlinedButton(
                  onPressed: _isApproving ? null : _dismiss,
                  child: const Text('Dismiss'),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: FilledButton.icon(
                    onPressed: _isApproving ? null : _approve,
                    icon: _isApproving
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.check),
                    label: Text('Save to $bookName'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
