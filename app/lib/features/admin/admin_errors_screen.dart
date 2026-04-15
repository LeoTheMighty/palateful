import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../core/services/error_reporter.dart';
import '../../shared/widgets/error_banner.dart';

class AdminErrorsScreen extends StatefulWidget {
  const AdminErrorsScreen({super.key});

  @override
  State<AdminErrorsScreen> createState() => _AdminErrorsScreenState();
}

class _AdminErrorsScreenState extends State<AdminErrorsScreen> {
  final _apiClient = getIt<ApiClient>();
  final _scrollController = ScrollController();

  bool _isLoading = true;
  bool _isLoadingMore = false;
  String? _error;
  String? _errorDetail;
  List<dynamic> _errors = [];
  int _offset = 0;
  bool _hasMore = true;
  static const _pageSize = 50;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    _fetchErrors();
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >=
            _scrollController.position.maxScrollExtent - 200 &&
        !_isLoadingMore &&
        _hasMore) {
      _loadMore();
    }
  }

  Future<void> _fetchErrors() async {
    setState(() {
      _isLoading = true;
      _error = null;
      _offset = 0;
      _errors = [];
      _hasMore = true;
    });

    try {
      final response = await _apiClient.getAdminErrors(limit: _pageSize, offset: 0);
      if (!mounted) return;

      final data = response.data;
      final List<dynamic> items = data is Map && data['errors'] != null
          ? data['errors'] as List<dynamic>
          : (data is List ? data : []);

      setState(() {
        _errors = items;
        _offset = items.length;
        _hasMore = items.length >= _pageSize;
        _isLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = 'Failed to load errors: $e';
        _errorDetail = ErrorReporter.detail(e);
        _isLoading = false;
      });
    }
  }

  Future<void> _loadMore() async {
    if (_isLoadingMore || !_hasMore) return;

    setState(() => _isLoadingMore = true);

    try {
      final response = await _apiClient.getAdminErrors(limit: _pageSize, offset: _offset);
      if (!mounted) return;

      final data = response.data;
      final List<dynamic> items = data is Map && data['errors'] != null
          ? data['errors'] as List<dynamic>
          : (data is List ? data : []);

      setState(() {
        _errors.addAll(items);
        _offset += items.length;
        _hasMore = items.length >= _pageSize;
        _isLoadingMore = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _isLoadingMore = false);
    }
  }

  String _formatTimestamp(String? timestamp) {
    if (timestamp == null) return '';
    try {
      final dt = DateTime.parse(timestamp);
      final now = DateTime.now();
      final diff = now.difference(dt);
      if (diff.inMinutes < 1) return 'just now';
      if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
      if (diff.inHours < 24) return '${diff.inHours}h ago';
      if (diff.inDays < 7) return '${diff.inDays}d ago';
      return '${dt.month}/${dt.day}/${dt.year}';
    } catch (_) {
      return timestamp;
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(
        title: Text('Errors', style: textTheme.titleLarge),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.error_outline, size: 64, color: colorScheme.error),
                      const SizedBox(height: 16),
                      Text(_error!, style: textTheme.bodyMedium, textAlign: TextAlign.center),
                      const SizedBox(height: 16),
                      FilledButton.icon(
                        onPressed: _fetchErrors,
                        icon: const Icon(Icons.refresh),
                        label: const Text('Retry'),
                      ),
                    ],
                  ),
                )
              : _errors.isEmpty
                  ? Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.check_circle_outline, size: 64, color: colorScheme.primary),
                          const SizedBox(height: 16),
                          Text('No errors found', style: textTheme.bodyLarge),
                        ],
                      ),
                    )
                  : RefreshIndicator(
                      onRefresh: _fetchErrors,
                      child: ListView.builder(
                        controller: _scrollController,
                        itemCount: _errors.length + (_isLoadingMore ? 1 : 0),
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        itemBuilder: (context, index) {
                          if (index == _errors.length) {
                            return const Center(
                              child: Padding(
                                padding: EdgeInsets.all(16),
                                child: CircularProgressIndicator(),
                              ),
                            );
                          }

                          final err = _errors[index] as Map<String, dynamic>;
                          final errorType = err['error_type'] as String? ?? 'Unknown Error';
                          final path = err['path'] as String? ?? '';
                          final statusCode = err['status_code'];
                          final createdAt = err['created_at'] as String?;
                          final errorId = err['id'] as String? ?? '';

                          return ListTile(
                            leading: Icon(Icons.error, color: colorScheme.error),
                            title: Text(
                              errorType,
                              style: textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                            subtitle: Text(
                              '$path${statusCode != null ? ' ($statusCode)' : ''}',
                              style: textTheme.bodySmall?.copyWith(
                                color: colorScheme.onSurfaceVariant,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                            trailing: Text(
                              _formatTimestamp(createdAt),
                              style: textTheme.bodySmall?.copyWith(
                                color: colorScheme.onSurfaceVariant,
                              ),
                            ),
                            onTap: () => context.push('/admin/errors/$errorId'),
                          );
                        },
                      ),
                    ),
    );
  }
}
