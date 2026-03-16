import 'dart:async';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';

class UrlImportScreen extends StatefulWidget {
  final String? recipeBookId;

  const UrlImportScreen({super.key, this.recipeBookId});

  @override
  State<UrlImportScreen> createState() => _UrlImportScreenState();
}

class _UrlImportScreenState extends State<UrlImportScreen> {
  final _apiClient = getIt<ApiClient>();
  final _urlController = TextEditingController();

  // State
  String? _selectedBookId;
  List<dynamic> _recipeBooks = [];
  bool _isLoadingBooks = true;

  // Import state
  bool _isImporting = false;
  String? _importJobId;
  String? _importStatus;
  Timer? _pollTimer;

  // Result state
  Map<String, dynamic>? _importItem;
  Map<String, dynamic>? _parsedRecipe;
  bool _isApproving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _selectedBookId = widget.recipeBookId;
    _loadRecipeBooks();
  }

  @override
  void dispose() {
    _urlController.dispose();
    _pollTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadRecipeBooks() async {
    try {
      final response = await _apiClient.getRecipeBooks();
      if (mounted) {
        setState(() {
          _recipeBooks = response.data['items'] ?? [];
          _isLoadingBooks = false;
          if (_selectedBookId == null && _recipeBooks.isNotEmpty) {
            _selectedBookId = _recipeBooks.first['id']?.toString();
          }
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoadingBooks = false);
      }
    }
  }

  bool _isValidUrl(String url) {
    try {
      final uri = Uri.parse(url);
      return uri.hasScheme && (uri.scheme == 'http' || uri.scheme == 'https');
    } catch (_) {
      return false;
    }
  }

  Future<void> _startImport() async {
    final url = _urlController.text.trim();
    if (!_isValidUrl(url)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter a valid URL')),
      );
      return;
    }
    if (_selectedBookId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select a recipe book')),
      );
      return;
    }

    setState(() {
      _isImporting = true;
      _error = null;
      _importItem = null;
      _parsedRecipe = null;
    });

    try {
      final response = await _apiClient.startImport(
        _selectedBookId!,
        sourceType: 'url',
        url: url,
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
    _pollTimer = Timer.periodic(const Duration(seconds: 2), (_) {
      _pollImportJob();
    });
  }

  Future<void> _pollImportJob() async {
    if (_importJobId == null) return;

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
          _error = 'Could not load extracted recipe. Please try again.';
        });
      }
    }
  }

  Future<void> _approveImport() async {
    if (_isApproving || _importItem == null) return;

    final itemId = _importItem!['id']?.toString();
    if (itemId == null) return;

    setState(() => _isApproving = true);
    try {
      HapticFeedback.selectionClick();
      await _apiClient.approveImportItem(itemId);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Recipe imported successfully!')),
        );
        context.pop(true);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not save recipe. Please try again.')),
        );
      }
    } finally {
      if (mounted) setState(() => _isApproving = false);
    }
  }

  Future<void> _skipImport() async {
    if (_importItem == null) return;
    final itemId = _importItem!['id']?.toString();
    if (itemId == null) return;

    try {
      await _apiClient.skipImportItem(itemId);
    } catch (_) {}
    if (mounted) context.pop();
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Import from URL'),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => context.pop(),
        ),
      ),
      body: _parsedRecipe != null
          ? _buildPreview(colorScheme, textTheme)
          : _buildInputForm(colorScheme, textTheme),
    );
  }

  Widget _buildInputForm(ColorScheme colorScheme, TextTheme textTheme) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'Paste a recipe URL to import it automatically.',
            style: textTheme.bodyLarge?.copyWith(
              color: colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 24),

          // URL input
          TextField(
            controller: _urlController,
            decoration: InputDecoration(
              labelText: 'Recipe URL',
              hintText: 'https://example.com/recipe/...',
              prefixIcon: const Icon(Icons.link),
              border: const OutlineInputBorder(),
              enabled: !_isImporting,
            ),
            keyboardType: TextInputType.url,
            textInputAction: TextInputAction.done,
            onSubmitted: (_) => _isImporting ? null : _startImport(),
          ),
          const SizedBox(height: 16),

          // Book selector
          if (_isLoadingBooks)
            const Center(child: CircularProgressIndicator())
          else if (_recipeBooks.isEmpty)
            Text(
              'No recipe books available. Create one first.',
              style: textTheme.bodyMedium?.copyWith(color: colorScheme.error),
            )
          else
            DropdownButtonFormField<String>(
              value: _selectedBookId,
              decoration: const InputDecoration(
                labelText: 'Destination Book',
                prefixIcon: Icon(Icons.book_outlined),
                border: OutlineInputBorder(),
              ),
              items: _recipeBooks.map((book) {
                return DropdownMenuItem<String>(
                  value: book['id']?.toString(),
                  child: Text(book['name'] ?? 'Untitled'),
                );
              }).toList(),
              onChanged: _isImporting ? null : (value) {
                setState(() => _selectedBookId = value);
              },
            ),
          const SizedBox(height: 24),

          // Import button or status
          if (_isImporting) ...[
            const Center(child: CircularProgressIndicator()),
            const SizedBox(height: 16),
            Text(
              _importStatus == 'processing'
                  ? 'Extracting recipe from URL...'
                  : 'Starting import...',
              style: textTheme.bodyMedium,
              textAlign: TextAlign.center,
            ),
          ] else ...[
            FilledButton.icon(
              onPressed: _recipeBooks.isEmpty ? null : _startImport,
              icon: const Icon(Icons.download),
              label: const Text('Import Recipe'),
            ),
          ],

          // Error message
          if (_error != null) ...[
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: colorScheme.errorContainer,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                _error!,
                style: TextStyle(color: colorScheme.onErrorContainer),
              ),
            ),
          ],
        ],
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
    final sourceUrl = _parsedRecipe!['source_url'] as String?;
    final extractorUsed = _parsedRecipe!['extractor_used'] as String?;

    return Column(
      children: [
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              // Extracted badge
              Row(
                children: [
                  Icon(Icons.auto_awesome, size: 16, color: colorScheme.primary),
                  const SizedBox(width: 4),
                  Text(
                    'Extracted via ${extractorUsed ?? 'auto'}',
                    style: textTheme.labelSmall?.copyWith(
                      color: colorScheme.primary,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),

              // Image
              if (imageUrl != null)
                ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: CachedNetworkImage(
                    imageUrl: imageUrl,
                    height: 200,
                    width: double.infinity,
                    fit: BoxFit.cover,
                    errorWidget: (_, __, ___) => const SizedBox.shrink(),
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

              // Source URL
              if (sourceUrl != null) ...[
                const SizedBox(height: 8),
                Text(
                  'Source: $sourceUrl',
                  style: textTheme.bodySmall?.copyWith(
                    color: colorScheme.outline,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
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
                  onPressed: _isApproving ? null : _skipImport,
                  child: const Text('Skip'),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: FilledButton.icon(
                    onPressed: _isApproving ? null : _approveImport,
                    icon: _isApproving
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.check),
                    label: const Text('Save Recipe'),
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
