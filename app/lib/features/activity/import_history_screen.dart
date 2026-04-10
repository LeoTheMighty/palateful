import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';

class ImportHistoryScreen extends StatefulWidget {
  const ImportHistoryScreen({super.key});

  @override
  State<ImportHistoryScreen> createState() => _ImportHistoryScreenState();
}

class _ImportHistoryScreenState extends State<ImportHistoryScreen> {
  final _apiClient = getIt<ApiClient>();

  List<dynamic> _jobs = [];
  bool _isLoading = true;
  bool _isLoadingMore = false;
  String? _error;
  bool _hasMore = false;
  int _offset = 0;
  String? _statusFilter;

  static const _pageSize = 20;

  static const _filterOptions = <String, String?>{
    'All': null,
    'Processing': 'processing',
    'Needs Review': 'awaiting_review',
    'Completed': 'completed',
    'Failed': 'failed',
  };

  @override
  void initState() {
    super.initState();
    _loadJobs();
  }

  Future<void> _loadJobs({bool loadMore = false}) async {
    if (loadMore) {
      setState(() => _isLoadingMore = true);
    } else {
      setState(() {
        _isLoading = true;
        _error = null;
        _offset = 0;
        _jobs = [];
      });
    }

    try {
      final response = await _apiClient.listImportJobs(
        status: _statusFilter,
        limit: _pageSize,
        offset: loadMore ? _offset : 0,
      );
      if (!mounted) return;

      final newJobs = List<dynamic>.from(response.data['jobs'] ?? []);
      final hasMore = response.data['has_more'] == true;

      setState(() {
        if (loadMore) {
          _jobs.addAll(newJobs);
        } else {
          _jobs = newJobs;
        }
        _offset = _jobs.length;
        _hasMore = hasMore;
        _isLoading = false;
        _isLoadingMore = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = 'Failed to load import history';
        _isLoading = false;
        _isLoadingMore = false;
      });
    }
  }

  void _onFilterChanged(String? status) {
    setState(() => _statusFilter = status);
    _loadJobs();
  }

  IconData _iconForSourceType(String? sourceType) {
    switch (sourceType) {
      case 'url':
        return Icons.link;
      case 'url_list':
        return Icons.list;
      case 'photo':
        return Icons.camera_alt;
      case 'text':
        return Icons.description;
      case 'spreadsheet':
        return Icons.table_chart;
      case 'pdf':
        return Icons.picture_as_pdf;
      case 'audio':
        return Icons.mic;
      default:
        return Icons.import_export;
    }
  }

  Color _colorForStatus(String? status, ColorScheme colorScheme) {
    switch (status) {
      case 'processing':
      case 'awaiting_review':
        return colorScheme.tertiary;
      case 'completed':
        return colorScheme.primary;
      case 'failed':
        return colorScheme.error;
      case 'cancelled':
        return colorScheme.outline;
      default:
        return colorScheme.onSurfaceVariant;
    }
  }

  String _labelForStatus(String? status) {
    switch (status) {
      case 'processing':
        return 'Processing';
      case 'awaiting_review':
        return 'Needs Review';
      case 'completed':
        return 'Completed';
      case 'failed':
        return 'Failed';
      case 'cancelled':
        return 'Cancelled';
      case 'pending':
        return 'Pending';
      default:
        return status ?? 'Unknown';
    }
  }

  String _formatTime(String? dateStr) {
    if (dateStr == null) return '';
    final date = DateTime.tryParse(dateStr);
    if (date == null) return '';

    final now = DateTime.now();
    final diff = now.difference(date);

    if (diff.inMinutes < 1) return 'Just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    if (diff.inDays < 7) return '${diff.inDays}d ago';
    return '${date.month}/${date.day}/${date.year}';
  }

  String _buildCountSummary(dynamic job) {
    final parts = <String>[];
    final succeeded = job['succeeded_items'] as int? ?? 0;
    final failed = job['failed_items'] as int? ?? 0;
    final pendingReview = job['pending_review_items'] as int? ?? 0;

    if (succeeded > 0) parts.add('$succeeded imported');
    if (pendingReview > 0) parts.add('$pendingReview to review');
    if (failed > 0) parts.add('$failed failed');

    if (parts.isEmpty) {
      final total = job['total_items'] as int? ?? 0;
      return '$total item${total == 1 ? '' : 's'}';
    }
    return parts.join(' \u00b7 ');
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Import History'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
      ),
      body: Column(
        children: [
          // Filter chips
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Row(
              children: _filterOptions.entries.map((entry) {
                final isSelected = _statusFilter == entry.value;
                return Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: FilterChip(
                    label: Text(entry.key),
                    selected: isSelected,
                    onSelected: (_) => _onFilterChanged(entry.value),
                  ),
                );
              }).toList(),
            ),
          ),

          // Content
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                    ? _buildError(colorScheme)
                    : _jobs.isEmpty
                        ? _buildEmptyState(colorScheme, textTheme)
                        : RefreshIndicator(
                            onRefresh: _loadJobs,
                            child: _buildJobList(colorScheme, textTheme),
                          ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState(ColorScheme colorScheme, TextTheme textTheme) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.cloud_off,
            size: 64,
            color: colorScheme.onSurfaceVariant.withValues(alpha: 0.5),
          ),
          const SizedBox(height: 16),
          Text(
            'No imports yet',
            style: textTheme.titleMedium?.copyWith(
              color: colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'Your import history will appear here',
            style: textTheme.bodyMedium?.copyWith(
              color: colorScheme.onSurfaceVariant.withValues(alpha: 0.7),
            ),
          ),
        ],
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
            ElevatedButton(onPressed: _loadJobs, child: const Text('Retry')),
          ],
        ),
      ),
    );
  }

  Widget _buildJobList(ColorScheme colorScheme, TextTheme textTheme) {
    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      itemCount: _jobs.length + (_hasMore ? 1 : 0),
      itemBuilder: (context, index) {
        if (index == _jobs.length) {
          return Padding(
            padding: const EdgeInsets.symmetric(vertical: 16),
            child: Center(
              child: _isLoadingMore
                  ? const CircularProgressIndicator()
                  : TextButton(
                      onPressed: () => _loadJobs(loadMore: true),
                      child: const Text('Load more'),
                    ),
            ),
          );
        }

        final job = _jobs[index];
        return _buildJobCard(job, colorScheme, textTheme);
      },
    );
  }

  Widget _buildJobCard(
    dynamic job,
    ColorScheme colorScheme,
    TextTheme textTheme,
  ) {
    final status = job['status'] as String?;
    final sourceType = job['source_type'] as String?;
    final jobId = job['id']?.toString() ?? '';
    final statusColor = _colorForStatus(status, colorScheme);

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: colorScheme.surfaceContainerHighest,
          child: Icon(
            _iconForSourceType(sourceType),
            size: 20,
            color: colorScheme.onSurfaceVariant,
          ),
        ),
        title: Row(
          children: [
            Expanded(
              child: Text(
                _buildCountSummary(job),
                style: textTheme.bodyMedium,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(
                color: statusColor.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(
                _labelForStatus(status),
                style: textTheme.labelSmall?.copyWith(
                  color: statusColor,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
        subtitle: Text(
          _formatTime(job['created_at']?.toString()),
          style: textTheme.bodySmall?.copyWith(
            color: colorScheme.onSurfaceVariant,
          ),
        ),
        trailing: const Icon(Icons.chevron_right),
        onTap: () async {
          await context.push('/recipes/import/review-list/$jobId');
          if (mounted) _loadJobs();
        },
      ),
    );
  }
}
