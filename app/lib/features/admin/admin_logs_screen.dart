import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';

class AdminLogsScreen extends StatefulWidget {
  const AdminLogsScreen({super.key});

  @override
  State<AdminLogsScreen> createState() => _AdminLogsScreenState();
}

class _AdminLogsScreenState extends State<AdminLogsScreen> {
  final _apiClient = getIt<ApiClient>();
  final _searchController = TextEditingController();
  final _scrollController = ScrollController();

  bool _isLoading = true;
  String? _error;
  List<dynamic> _logs = [];

  // Filters
  String _service = 'api';
  String _level = 'ALL';
  String _timeRange = '1h';
  bool _autoRefresh = false;
  Timer? _refreshTimer;

  @override
  void initState() {
    super.initState();
    _fetchLogs();
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    _searchController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _toggleAutoRefresh(bool value) {
    setState(() {
      _autoRefresh = value;
    });
    _refreshTimer?.cancel();
    if (value) {
      _refreshTimer = Timer.periodic(const Duration(seconds: 5), (_) {
        _fetchLogs(showLoading: false);
      });
    }
  }

  Future<void> _fetchLogs({bool showLoading = true}) async {
    if (showLoading) {
      setState(() {
        _isLoading = true;
        _error = null;
      });
    }

    try {
      final response = await _apiClient.getAdminLogs(
        service: _service,
        level: _level == 'ALL' ? null : _level,
        search: _searchController.text.isNotEmpty ? _searchController.text : null,
        limit: 200,
      );
      if (!mounted) return;

      final data = response.data;
      setState(() {
        _logs = (data is Map && data['logs'] != null)
            ? data['logs'] as List<dynamic>
            : (data is List ? data : []);
        _isLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = 'Failed to load logs: $e';
        _isLoading = false;
      });
    }
  }

  Color _levelColor(String? level) {
    switch (level?.toUpperCase()) {
      case 'ERROR':
        return Colors.red;
      case 'WARNING':
        return Colors.orange;
      case 'DEBUG':
        return Colors.grey;
      default:
        return Colors.transparent;
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(
        title: Text('Logs', style: textTheme.titleLarge),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
        actions: [
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('Auto', style: textTheme.bodySmall),
              Switch(
                value: _autoRefresh,
                onChanged: _toggleAutoRefresh,
              ),
            ],
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _fetchLogs,
          ),
        ],
      ),
      body: Column(
        children: [
          // Filters bar
          _buildFilters(colorScheme, textTheme),
          const Divider(height: 1),
          // Log output
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                    ? Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Text(_error!, style: textTheme.bodyMedium),
                            const SizedBox(height: 8),
                            FilledButton(onPressed: _fetchLogs, child: const Text('Retry')),
                          ],
                        ),
                      )
                    : _logs.isEmpty
                        ? Center(
                            child: Text('No logs found', style: textTheme.bodyMedium?.copyWith(color: colorScheme.onSurfaceVariant)),
                          )
                        : _buildLogList(colorScheme, textTheme),
          ),
        ],
      ),
    );
  }

  Widget _buildFilters(ColorScheme colorScheme, TextTheme textTheme) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Column(
        children: [
          Row(
            children: [
              // Service dropdown
              Expanded(
                child: DropdownButtonFormField<String>(
                  value: _service,
                  decoration: const InputDecoration(
                    labelText: 'Service',
                    isDense: true,
                    contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  ),
                  items: const [
                    DropdownMenuItem(value: 'api', child: Text('API')),
                    DropdownMenuItem(value: 'worker', child: Text('Worker')),
                  ],
                  onChanged: (value) {
                    if (value != null) {
                      setState(() => _service = value);
                      _fetchLogs();
                    }
                  },
                ),
              ),
              const SizedBox(width: 8),
              // Level dropdown
              Expanded(
                child: DropdownButtonFormField<String>(
                  value: _level,
                  decoration: const InputDecoration(
                    labelText: 'Level',
                    isDense: true,
                    contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  ),
                  items: const [
                    DropdownMenuItem(value: 'ALL', child: Text('ALL')),
                    DropdownMenuItem(value: 'INFO', child: Text('INFO')),
                    DropdownMenuItem(value: 'WARNING', child: Text('WARNING')),
                    DropdownMenuItem(value: 'ERROR', child: Text('ERROR')),
                  ],
                  onChanged: (value) {
                    if (value != null) {
                      setState(() => _level = value);
                      _fetchLogs();
                    }
                  },
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          // Search field
          TextField(
            controller: _searchController,
            decoration: InputDecoration(
              hintText: 'Search logs...',
              isDense: true,
              contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              suffixIcon: IconButton(
                icon: const Icon(Icons.search, size: 20),
                onPressed: _fetchLogs,
              ),
            ),
            onSubmitted: (_) => _fetchLogs(),
          ),
          const SizedBox(height: 8),
          // Time range buttons
          Row(
            children: ['15m', '1h', '6h', '24h'].map((range) {
              final isSelected = _timeRange == range;
              return Padding(
                padding: const EdgeInsets.only(right: 8),
                child: ChoiceChip(
                  label: Text(range),
                  selected: isSelected,
                  onSelected: (selected) {
                    if (selected) {
                      setState(() => _timeRange = range);
                      _fetchLogs();
                    }
                  },
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildLogList(ColorScheme colorScheme, TextTheme textTheme) {
    return ListView.builder(
      controller: _scrollController,
      itemCount: _logs.length,
      padding: const EdgeInsets.all(8),
      itemBuilder: (context, index) {
        final log = _logs[index];
        final message = log is Map ? (log['message'] ?? log.toString()) : log.toString();
        final level = log is Map ? (log['level'] as String?) : null;
        final timestamp = log is Map ? (log['timestamp'] as String?) : null;
        final levelColor = _levelColor(level);

        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            border: levelColor != Colors.transparent
                ? Border(left: BorderSide(color: levelColor, width: 3))
                : null,
          ),
          child: Text.rich(
            TextSpan(
              children: [
                if (timestamp != null)
                  TextSpan(
                    text: '${timestamp.length > 19 ? timestamp.substring(11, 19) : timestamp} ',
                    style: TextStyle(
                      color: colorScheme.onSurfaceVariant,
                      fontFamily: 'monospace',
                      fontSize: 12,
                    ),
                  ),
                if (level != null)
                  TextSpan(
                    text: '[$level] ',
                    style: TextStyle(
                      color: levelColor != Colors.transparent ? levelColor : colorScheme.onSurface,
                      fontWeight: FontWeight.bold,
                      fontFamily: 'monospace',
                      fontSize: 12,
                    ),
                  ),
                TextSpan(
                  text: message.toString(),
                  style: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 12,
                    color: level?.toUpperCase() == 'ERROR'
                        ? Colors.red
                        : level?.toUpperCase() == 'WARNING'
                            ? Colors.orange
                            : colorScheme.onSurface,
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}
