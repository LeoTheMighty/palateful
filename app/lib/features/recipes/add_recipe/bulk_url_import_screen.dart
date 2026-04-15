import 'dart:async';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';
import '../../../core/services/auth_service.dart';
import '../../../core/services/error_reporter.dart';
import '../../../shared/widgets/error_banner.dart';

class BulkUrlImportScreen extends StatefulWidget {
  final String? recipeBookId;

  const BulkUrlImportScreen({super.key, this.recipeBookId});

  @override
  State<BulkUrlImportScreen> createState() => _BulkUrlImportScreenState();
}

class _BulkUrlImportScreenState extends State<BulkUrlImportScreen> {
  final _apiClient = getIt<ApiClient>();
  final _urlsController = TextEditingController();

  // Book selection
  String? _selectedBookId;
  List<dynamic> _recipeBooks = [];
  bool _isLoadingBooks = true;

  // URL validation
  List<String> _validUrls = [];
  int _invalidCount = 0;

  // Import state
  bool _isImporting = false;
  String? _importJobId;
  String _importStatus = '';
  int _totalItems = 0;
  int _completedItems = 0;
  int _failedItems = 0;
  Timer? _pollTimer;
  int _pollCount = 0;
  static const _maxPolls = 300; // 10 minutes at 2s intervals

  // Results state
  List<dynamic> _importItems = [];
  bool _isLoadingItems = false;
  String? _error;
  String? _errorDetail;

  // Item action state
  final Set<String> _processingItemIds = {};

  @override
  void initState() {
    super.initState();
    _selectedBookId = widget.recipeBookId;
    _loadRecipeBooks();
    _urlsController.addListener(_parseUrls);
  }

  @override
  void dispose() {
    _urlsController.removeListener(_parseUrls);
    _urlsController.dispose();
    _pollTimer?.cancel();
    super.dispose();
  }

  void _parseUrls() {
    final lines = _urlsController.text
        .split('\n')
        .map((l) => l.trim())
        .where((l) => l.isNotEmpty)
        .toList();

    final valid = <String>[];
    final seen = <String>{};
    var invalid = 0;

    for (final line in lines) {
      if (_isValidUrl(line)) {
        if (seen.add(line)) {
          valid.add(line);
        }
        // Silently skip duplicates — they're just counted once
      } else {
        invalid++;
      }
    }

    setState(() {
      _validUrls = valid;
      _invalidCount = invalid;
    });
  }

  bool _isValidUrl(String url) {
    try {
      final uri = Uri.parse(url);
      return uri.hasScheme && (uri.scheme == 'http' || uri.scheme == 'https');
    } catch (_) {
      return false;
    }
  }

  Future<void> _loadRecipeBooks() async {
    try {
      final response = await _apiClient.getRecipeBooks();
      if (mounted) {
        setState(() {
          _recipeBooks = response.data['items'] ?? [];
          _isLoadingBooks = false;
          if (_selectedBookId == null && _recipeBooks.isNotEmpty) {
            final defaultId = getIt<AuthService>().defaultRecipeBookId;
            if (defaultId != null && _recipeBooks.any((b) => b['id']?.toString() == defaultId)) {
              _selectedBookId = defaultId;
            } else {
              _selectedBookId = _recipeBooks.first['id']?.toString();
            }
          }
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoadingBooks = false);
      }
    }
  }

  static const _maxUrls = 50;

  Future<void> _startImport() async {
    if (_validUrls.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter at least one valid URL')),
      );
      return;
    }
    if (_validUrls.length > _maxUrls) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Maximum $_maxUrls URLs per import. You have ${_validUrls.length}.')),
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
      _importItems = [];
      _completedItems = 0;
      _failedItems = 0;
      _pollCount = 0;
    });

    try {
      final response = await _apiClient.startImport(
        _selectedBookId!,
        sourceType: 'url_list',
        urls: _validUrls,
      );
      if (!mounted) return;

      _importJobId = response.data['id']?.toString();
      _totalItems = response.data['total_items'] ?? _validUrls.length;
      _importStatus = response.data['status']?.toString() ?? 'pending';
      setState(() {});
      _startPolling();
    } catch (e) {
      if (mounted) {
        setState(() {
          _isImporting = false;
          _error = 'Could not start import. Please try again.';
          _errorDetail = ErrorReporter.detail(e);
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

    _pollCount++;
    if (_pollCount > _maxPolls) {
      _pollTimer?.cancel();
      if (mounted) {
        setState(() {
          _isImporting = false;
          _error = 'Import is taking too long. Check back later.';
        });
      }
      return;
    }

    try {
      final response = await _apiClient.getImportJob(_importJobId!);
      if (!mounted) return;

      final status = response.data['status']?.toString() ?? '';
      final completed = response.data['succeeded_items'] ?? 0;
      final failed = response.data['failed_items'] ?? 0;
      final total = response.data['total_items'] ?? _totalItems;

      setState(() {
        _importStatus = status;
        _completedItems = completed;
        _failedItems = failed;
        _totalItems = total;
      });

      if (status == 'awaiting_review' || status == 'completed') {
        _pollTimer?.cancel();
        await _loadImportItems();
      } else if (status == 'failed') {
        _pollTimer?.cancel();
        setState(() {
          _isImporting = false;
          _error = 'Import failed. Some URLs may not contain recipes.';
        });
        await _loadImportItems();
      }
    } catch (e) {
      // Keep polling on transient errors
    }
  }

  Future<void> _loadImportItems() async {
    if (_importJobId == null) return;

    setState(() => _isLoadingItems = true);
    try {
      final response = await _apiClient.listImportItems(_importJobId!);
      if (!mounted) return;

      setState(() {
        _importItems = response.data['items'] as List? ?? [];
        _isImporting = false;
        _isLoadingItems = false;
      });
    } catch (e) {
      if (mounted) {
        setState(() {
          _isImporting = false;
          _isLoadingItems = false;
          _error = 'Could not load import results.';
          _errorDetail = ErrorReporter.detail(e);
        });
      }
    }
  }

  Future<void> _approveItem(String itemId) async {
    if (_processingItemIds.contains(itemId)) return;

    setState(() => _processingItemIds.add(itemId));
    try {
      HapticFeedback.selectionClick();
      await _apiClient.approveImportItem(itemId);
      if (mounted) {
        setState(() {
          _processingItemIds.remove(itemId);
          // Update item status locally
          final idx = _importItems.indexWhere((i) => i['id']?.toString() == itemId);
          if (idx >= 0) {
            _importItems[idx] = {..._importItems[idx], 'status': 'completed'};
          }
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => _processingItemIds.remove(itemId));
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not approve recipe.')),
        );
      }
    }
  }

  Future<void> _skipItem(String itemId) async {
    if (_processingItemIds.contains(itemId)) return;

    setState(() => _processingItemIds.add(itemId));
    try {
      await _apiClient.skipImportItem(itemId);
      if (mounted) {
        setState(() {
          _processingItemIds.remove(itemId);
          final idx = _importItems.indexWhere((i) => i['id']?.toString() == itemId);
          if (idx >= 0) {
            _importItems[idx] = {..._importItems[idx], 'status': 'skipped'};
          }
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => _processingItemIds.remove(itemId));
      }
    }
  }

  Future<void> _approveAll() async {
    final reviewItems = _importItems.where((i) =>
      i['status'] == 'awaiting_review' && i['parsed_recipe'] != null
    ).toList();

    var approved = 0;
    for (final item in reviewItems) {
      final id = item['id']?.toString();
      if (id == null) continue;
      final idx = _importItems.indexWhere((i) => i['id']?.toString() == id);
      await _approveItem(id);
      if (!mounted) return;
      // Check if the item was actually approved
      if (idx >= 0 && _importItems[idx]['status'] == 'completed') {
        approved++;
      }
    }

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('$approved recipe${approved == 1 ? '' : 's'} imported')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Bulk URL Import'),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => context.pop(),
        ),
      ),
      body: _importItems.isNotEmpty
          ? _buildResults()
          : _isImporting
              ? _buildProgress()
              : _buildInputForm(),
    );
  }

  Widget _buildInputForm() {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'Paste recipe URLs below, one per line.',
            style: textTheme.bodyLarge?.copyWith(
              color: colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 16),

          // Multi-line URL input
          Expanded(
            child: TextField(
              controller: _urlsController,
              maxLines: null,
              expands: true,
              textAlignVertical: TextAlignVertical.top,
              decoration: const InputDecoration(
                hintText: 'https://example.com/recipe1\nhttps://example.com/recipe2\nhttps://example.com/recipe3',
                border: OutlineInputBorder(),
                alignLabelWithHint: true,
                labelText: 'Recipe URLs',
              ),
              keyboardType: TextInputType.multiline,
            ),
          ),
          const SizedBox(height: 12),

          // URL count display
          if (_validUrls.isNotEmpty || _invalidCount > 0)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Row(
                children: [
                  if (_validUrls.isNotEmpty) ...[
                    Icon(Icons.check_circle, size: 16, color: colorScheme.primary),
                    const SizedBox(width: 4),
                    Text(
                      '${_validUrls.length} valid URL${_validUrls.length == 1 ? '' : 's'}',
                      style: textTheme.bodySmall?.copyWith(color: colorScheme.primary),
                    ),
                  ],
                  if (_validUrls.isNotEmpty && _invalidCount > 0)
                    const SizedBox(width: 16),
                  if (_invalidCount > 0) ...[
                    Icon(Icons.warning_amber, size: 16, color: colorScheme.error),
                    const SizedBox(width: 4),
                    Text(
                      '$_invalidCount invalid',
                      style: textTheme.bodySmall?.copyWith(color: colorScheme.error),
                    ),
                  ],
                ],
              ),
            ),

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
              initialValue: _selectedBookId,
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
              onChanged: (value) => setState(() => _selectedBookId = value),
            ),
          const SizedBox(height: 16),

          // Error message
          if (_error != null) ...[
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
            const SizedBox(height: 12),
          ],

          // Import button
          FilledButton.icon(
            onPressed: _validUrls.isEmpty || _recipeBooks.isEmpty
                ? null
                : _startImport,
            icon: const Icon(Icons.download),
            label: Text(
              _validUrls.isEmpty
                  ? 'Import Recipes'
                  : 'Import ${_validUrls.length} Recipe${_validUrls.length == 1 ? '' : 's'}',
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildProgress() {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final processed = _completedItems + _failedItems;
    final progress = _totalItems > 0 ? processed / _totalItems : 0.0;

    return Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          SizedBox(
            width: 120,
            height: 120,
            child: Stack(
              alignment: Alignment.center,
              children: [
                SizedBox(
                  width: 120,
                  height: 120,
                  child: CircularProgressIndicator(
                    value: _totalItems > 0 ? progress : null,
                    strokeWidth: 8,
                    backgroundColor: colorScheme.surfaceContainerHighest,
                  ),
                ),
                Text(
                  _totalItems > 0 ? '$processed/$_totalItems' : '...',
                  style: textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 32),
          Text(
            'Importing recipes...',
            style: textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          Text(
            _importStatus == 'processing'
                ? 'Extracting recipes from URLs'
                : 'Starting import pipeline',
            style: textTheme.bodyMedium?.copyWith(
              color: colorScheme.onSurfaceVariant,
            ),
          ),
          if (_completedItems > 0 || _failedItems > 0) ...[
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                if (_completedItems > 0) ...[
                  Icon(Icons.check_circle, size: 16, color: colorScheme.primary),
                  const SizedBox(width: 4),
                  Text('$_completedItems done', style: textTheme.bodySmall),
                ],
                if (_completedItems > 0 && _failedItems > 0)
                  const SizedBox(width: 16),
                if (_failedItems > 0) ...[
                  Icon(Icons.error, size: 16, color: colorScheme.error),
                  const SizedBox(width: 4),
                  Text('$_failedItems failed', style: textTheme.bodySmall),
                ],
              ],
            ),
          ],
          const SizedBox(height: 32),
          Text(
            'Processing continues even if you close the app.',
            style: textTheme.bodySmall?.copyWith(
              color: colorScheme.outline,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildResults() {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    final reviewItems = _importItems.where((i) => i['status'] == 'awaiting_review').toList();
    final completedItems = _importItems.where((i) => i['status'] == 'completed').toList();
    final failedItems = _importItems.where((i) => i['status'] == 'failed').toList();
    final skippedItems = _importItems.where((i) => i['status'] == 'skipped').toList();

    return Column(
      children: [
        // Summary bar
        Container(
          padding: const EdgeInsets.all(16),
          color: colorScheme.surfaceContainerHighest,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              _SummaryChip(
                count: completedItems.length,
                label: 'Imported',
                color: colorScheme.primary,
              ),
              _SummaryChip(
                count: reviewItems.length,
                label: 'To Review',
                color: colorScheme.tertiary,
              ),
              _SummaryChip(
                count: failedItems.length,
                label: 'Failed',
                color: colorScheme.error,
              ),
              if (skippedItems.isNotEmpty)
                _SummaryChip(
                  count: skippedItems.length,
                  label: 'Skipped',
                  color: colorScheme.outline,
                ),
            ],
          ),
        ),

        // Action buttons for items needing review
        if (reviewItems.isNotEmpty)
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
            child: Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () async {
                      if (_importJobId == null) return;
                      await context.push('/recipes/import/review-list/$_importJobId');
                      if (mounted) _loadImportItems();
                    },
                    icon: const Icon(Icons.edit_note),
                    label: const Text('Review & Edit'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: FilledButton.icon(
                    onPressed: _approveAll,
                    icon: const Icon(Icons.done_all),
                    label: Text('Approve All (${reviewItems.length})'),
                  ),
                ),
              ],
            ),
          ),

        // Items list
        Expanded(
          child: _isLoadingItems
              ? const Center(child: CircularProgressIndicator())
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: _importItems.length,
                  itemBuilder: (context, index) {
                    final item = _importItems[index];
                    return _buildItemCard(item, colorScheme, textTheme);
                  },
                ),
        ),

        // Done button
        SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: () => context.pop(true),
                child: const Text('Done'),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildItemCard(dynamic item, ColorScheme colorScheme, TextTheme textTheme) {
    final status = item['status'] as String? ?? 'pending';
    final sourceUrl = item['source_url'] as String? ?? '';
    final parsedRecipe = item['parsed_recipe'] as Map<String, dynamic>?;
    final itemId = item['id']?.toString() ?? '';
    final isProcessing = _processingItemIds.contains(itemId);

    final recipeName = parsedRecipe?['name'] as String? ?? 'Untitled Recipe';
    final imageUrl = parsedRecipe?['image_url'] as String?;

    Color statusColor;
    IconData statusIcon;
    String statusText;

    switch (status) {
      case 'completed':
        statusColor = colorScheme.primary;
        statusIcon = Icons.check_circle;
        statusText = 'Imported';
      case 'awaiting_review':
        statusColor = colorScheme.tertiary;
        statusIcon = Icons.rate_review;
        statusText = 'Ready to review';
      case 'failed':
        statusColor = colorScheme.error;
        statusIcon = Icons.error;
        statusText = 'Failed';
      case 'skipped':
        statusColor = colorScheme.outline;
        statusIcon = Icons.skip_next;
        statusText = 'Skipped';
      default:
        statusColor = colorScheme.outline;
        statusIcon = Icons.hourglass_empty;
        statusText = 'Processing';
    }

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                // Thumbnail
                if (imageUrl != null)
                  ClipRRect(
                    borderRadius: BorderRadius.circular(6),
                    child: CachedNetworkImage(
                      imageUrl: imageUrl,
                      width: 48,
                      height: 48,
                      fit: BoxFit.cover,
                      errorWidget: (_, _, _) => Container(
                        width: 48,
                        height: 48,
                        color: colorScheme.surfaceContainerHighest,
                        child: Icon(Icons.restaurant, size: 24, color: colorScheme.outline),
                      ),
                    ),
                  )
                else
                  Container(
                    width: 48,
                    height: 48,
                    decoration: BoxDecoration(
                      color: colorScheme.surfaceContainerHighest,
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Icon(Icons.restaurant, size: 24, color: colorScheme.outline),
                  ),
                const SizedBox(width: 12),

                // Name and status
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        parsedRecipe != null ? recipeName : _displayUrl(sourceUrl),
                        style: textTheme.titleSmall,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          Icon(statusIcon, size: 14, color: statusColor),
                          const SizedBox(width: 4),
                          Text(
                            statusText,
                            style: textTheme.bodySmall?.copyWith(color: statusColor),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),

                // Actions
                if (status == 'awaiting_review' && parsedRecipe != null) ...[
                  if (isProcessing)
                    const SizedBox(
                      width: 24,
                      height: 24,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  else ...[
                    IconButton(
                      icon: const Icon(Icons.close),
                      iconSize: 20,
                      onPressed: () => _skipItem(itemId),
                      tooltip: 'Dismiss',
                    ),
                    IconButton(
                      icon: Icon(Icons.check, color: colorScheme.primary),
                      iconSize: 20,
                      onPressed: () => _approveItem(itemId),
                      tooltip: 'Approve',
                    ),
                  ],
                ],
              ],
            ),

            // Source URL
            if (sourceUrl.isNotEmpty && parsedRecipe != null) ...[
              const SizedBox(height: 4),
              Text(
                sourceUrl,
                style: textTheme.bodySmall?.copyWith(color: colorScheme.outline),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ],
        ),
      ),
    );
  }

  String _displayUrl(String url) {
    try {
      final uri = Uri.parse(url);
      return uri.host + uri.path;
    } catch (_) {
      return url;
    }
  }
}

class _SummaryChip extends StatelessWidget {
  final int count;
  final String label;
  final Color color;

  const _SummaryChip({
    required this.count,
    required this.label,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          '$count',
          style: Theme.of(context).textTheme.titleLarge?.copyWith(
            fontWeight: FontWeight.bold,
            color: color,
          ),
        ),
        Text(
          label,
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
            color: color,
          ),
        ),
      ],
    );
  }
}
