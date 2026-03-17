import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';

class ImportReviewListScreen extends StatefulWidget {
  final String jobId;

  const ImportReviewListScreen({super.key, required this.jobId});

  @override
  State<ImportReviewListScreen> createState() => _ImportReviewListScreenState();
}

class _ImportReviewListScreenState extends State<ImportReviewListScreen> {
  final _apiClient = getIt<ApiClient>();

  bool _isLoading = true;
  String? _error;
  List<dynamic> _items = [];

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final itemsResponse = await _apiClient.listImportItems(widget.jobId);
      if (!mounted) return;

      setState(() {
        _items = itemsResponse.data['items'] as List? ?? [];
        _isLoading = false;
      });
    } catch (e) {
      if (mounted) {
        setState(() {
          _isLoading = false;
          _error = 'Could not load import items.';
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    final reviewItems = _items.where((i) => i['status'] == 'awaiting_review').toList();
    final completedItems = _items.where((i) => i['status'] == 'completed').toList();
    final failedItems = _items.where((i) => i['status'] == 'failed').toList();
    final skippedItems = _items.where((i) => i['status'] == 'skipped').toList();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Review Imports'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _buildError(colorScheme)
              : RefreshIndicator(
                  onRefresh: _loadData,
                  child: Column(
                    children: [
                      // Summary bar
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                        color: colorScheme.surfaceContainerHighest,
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                          children: [
                            _CountChip(
                              count: reviewItems.length,
                              label: 'To Review',
                              color: colorScheme.tertiary,
                            ),
                            _CountChip(
                              count: completedItems.length,
                              label: 'Imported',
                              color: colorScheme.primary,
                            ),
                            _CountChip(
                              count: failedItems.length,
                              label: 'Failed',
                              color: colorScheme.error,
                            ),
                            if (skippedItems.isNotEmpty)
                              _CountChip(
                                count: skippedItems.length,
                                label: 'Skipped',
                                color: colorScheme.outline,
                              ),
                          ],
                        ),
                      ),

                      // Items needing review first
                      if (reviewItems.isEmpty && failedItems.isEmpty)
                        Expanded(
                          child: Center(
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(Icons.check_circle, size: 64, color: colorScheme.primary),
                                const SizedBox(height: 16),
                                Text(
                                  'All items reviewed!',
                                  style: textTheme.titleMedium,
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  '${completedItems.length} imported, ${skippedItems.length} skipped',
                                  style: textTheme.bodyMedium?.copyWith(
                                    color: colorScheme.onSurfaceVariant,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        )
                      else
                        Expanded(
                          child: ListView(
                            padding: const EdgeInsets.all(16),
                            children: [
                              // Review needed section
                              if (reviewItems.isNotEmpty) ...[
                                Text(
                                  'Needs Review',
                                  style: textTheme.titleSmall?.copyWith(
                                    color: colorScheme.tertiary,
                                  ),
                                ),
                                const SizedBox(height: 8),
                                ...reviewItems.map((item) => _buildItemTile(
                                  item,
                                  colorScheme,
                                  textTheme,
                                  statusColor: colorScheme.tertiary,
                                  statusIcon: Icons.rate_review,
                                )),
                                const SizedBox(height: 16),
                              ],

                              // Failed section
                              if (failedItems.isNotEmpty) ...[
                                Text(
                                  'Failed',
                                  style: textTheme.titleSmall?.copyWith(
                                    color: colorScheme.error,
                                  ),
                                ),
                                const SizedBox(height: 8),
                                ...failedItems.map((item) => _buildItemTile(
                                  item,
                                  colorScheme,
                                  textTheme,
                                  statusColor: colorScheme.error,
                                  statusIcon: Icons.error,
                                )),
                                const SizedBox(height: 16),
                              ],

                              // Completed section
                              if (completedItems.isNotEmpty) ...[
                                Text(
                                  'Imported',
                                  style: textTheme.titleSmall?.copyWith(
                                    color: colorScheme.primary,
                                  ),
                                ),
                                const SizedBox(height: 8),
                                ...completedItems.map((item) => _buildItemTile(
                                  item,
                                  colorScheme,
                                  textTheme,
                                  statusColor: colorScheme.primary,
                                  statusIcon: Icons.check_circle,
                                  tappable: false,
                                )),
                              ],

                              // Skipped section
                              if (skippedItems.isNotEmpty) ...[
                                const SizedBox(height: 16),
                                Text(
                                  'Skipped',
                                  style: textTheme.titleSmall?.copyWith(
                                    color: colorScheme.outline,
                                  ),
                                ),
                                const SizedBox(height: 8),
                                ...skippedItems.map((item) => _buildItemTile(
                                  item,
                                  colorScheme,
                                  textTheme,
                                  statusColor: colorScheme.outline,
                                  statusIcon: Icons.skip_next,
                                  tappable: false,
                                )),
                              ],
                            ],
                          ),
                        ),
                    ],
                  ),
                ),
    );
  }

  Widget _buildError(ColorScheme colorScheme) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
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
            const SizedBox(height: 16),
            ElevatedButton(onPressed: _loadData, child: const Text('Retry')),
          ],
        ),
      ),
    );
  }

  Widget _buildItemTile(
    dynamic item,
    ColorScheme colorScheme,
    TextTheme textTheme, {
    required Color statusColor,
    required IconData statusIcon,
    bool tappable = true,
  }) {
    final recipeName = item['recipe_name'] as String? ?? 'Untitled';
    final sourceUrl = item['source_url'] as String? ?? '';
    final itemId = item['id']?.toString() ?? '';
    final errorMessage = item['error_message'] as String?;

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: Icon(statusIcon, color: statusColor),
        title: Text(
          recipeName,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        subtitle: errorMessage != null
            ? Text(
                errorMessage,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(color: colorScheme.error),
              )
            : sourceUrl.isNotEmpty
                ? Text(
                    sourceUrl,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  )
                : null,
        trailing: tappable
            ? const Icon(Icons.chevron_right)
            : null,
        onTap: tappable
            ? () async {
                final result = await context.push(
                  '/recipes/import/review/$itemId',
                );
                if (mounted && result != null) {
                  _loadData();
                }
              }
            : null,
      ),
    );
  }
}

class _CountChip extends StatelessWidget {
  final int count;
  final String label;
  final Color color;

  const _CountChip({
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
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.bold,
            color: color,
          ),
        ),
        Text(
          label,
          style: Theme.of(context).textTheme.bodySmall?.copyWith(color: color),
        ),
      ],
    );
  }
}
