import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../core/services/error_reporter.dart';
import 'widgets/metrics_table.dart';

/// Admin view at `/admin/metrics` — endpoint + task latency at a glance.
///
/// Mirrors `AdminErrorsScreen`'s layout conventions: pull-to-refresh,
/// inline error card with retry, and a simple stateful widget (no
/// Riverpod here — consistent with the rest of the admin surface).
class AdminMetricsScreen extends StatefulWidget {
  const AdminMetricsScreen({super.key});

  @override
  State<AdminMetricsScreen> createState() => _AdminMetricsScreenState();
}

enum _Window { oneHour, twentyFourHours, sevenDays }

extension on _Window {
  String get wire => switch (this) {
        _Window.oneHour => '1h',
        _Window.twentyFourHours => '24h',
        _Window.sevenDays => '7d',
      };
}

class _EndpointRow {
  final String method;
  final String normalizedPath;
  final int p50Ms;
  final int p95Ms;
  final int p99Ms;
  final int count;
  final double errorRate;
  final List<double> sparkline;

  const _EndpointRow({
    required this.method,
    required this.normalizedPath,
    required this.p50Ms,
    required this.p95Ms,
    required this.p99Ms,
    required this.count,
    required this.errorRate,
    required this.sparkline,
  });

  factory _EndpointRow.fromJson(Map<String, dynamic> json) {
    return _EndpointRow(
      method: json['method'] as String,
      normalizedPath: json['normalized_path'] as String,
      p50Ms: json['p50_ms'] as int? ?? 0,
      p95Ms: json['p95_ms'] as int? ?? 0,
      p99Ms: json['p99_ms'] as int? ?? 0,
      count: json['count'] as int? ?? 0,
      errorRate: (json['error_rate'] as num? ?? 0).toDouble(),
      sparkline: (json['sparkline'] as List<dynamic>? ?? const [])
          .map((e) => (e as num).toDouble())
          .toList(),
    );
  }
}

class _TaskRow {
  final String taskName;
  final int p50Ms;
  final int p95Ms;
  final int p99Ms;
  final int count;
  final double failureRate;
  final List<double> sparkline;

  const _TaskRow({
    required this.taskName,
    required this.p50Ms,
    required this.p95Ms,
    required this.p99Ms,
    required this.count,
    required this.failureRate,
    required this.sparkline,
  });

  factory _TaskRow.fromJson(Map<String, dynamic> json) {
    return _TaskRow(
      taskName: json['task_name'] as String,
      p50Ms: json['p50_ms'] as int? ?? 0,
      p95Ms: json['p95_ms'] as int? ?? 0,
      p99Ms: json['p99_ms'] as int? ?? 0,
      count: json['count'] as int? ?? 0,
      failureRate: (json['failure_rate'] as num? ?? 0).toDouble(),
      sparkline: (json['sparkline'] as List<dynamic>? ?? const [])
          .map((e) => (e as num).toDouble())
          .toList(),
    );
  }
}

class _AdminMetricsScreenState extends State<AdminMetricsScreen> {
  final _apiClient = getIt<ApiClient>();

  _Window _window = _Window.twentyFourHours;
  bool _isLoading = true;
  String? _error;
  String? _errorDetail;

  List<_EndpointRow> _endpointRows = const [];
  List<_TaskRow> _taskRows = const [];

  int _endpointSortIdx = 3; // p95
  bool _endpointSortAsc = false;
  int _taskSortIdx = 2; // p95
  bool _taskSortAsc = false;

  DateTime? _lastUpdatedAt;
  Timer? _updatedAgoTicker;

  @override
  void initState() {
    super.initState();
    _fetch();
    // "Last updated Xs ago" refreshes each second.
    _updatedAgoTicker = Timer.periodic(
      const Duration(seconds: 1),
      (_) {
        if (mounted) setState(() {});
      },
    );
  }

  @override
  void dispose() {
    _updatedAgoTicker?.cancel();
    super.dispose();
  }

  Future<void> _fetch() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final [endpoints, tasks] = await Future.wait([
        _apiClient.getEndpointMetrics(window: _window.wire),
        _apiClient.getTaskMetrics(window: _window.wire),
      ]);
      if (!mounted) return;
      final endpointRows = (endpoints.data['rows'] as List<dynamic>)
          .map((e) => _EndpointRow.fromJson(e as Map<String, dynamic>))
          .toList();
      final taskRows = (tasks.data['rows'] as List<dynamic>)
          .map((e) => _TaskRow.fromJson(e as Map<String, dynamic>))
          .toList();
      setState(() {
        _endpointRows = endpointRows;
        _taskRows = taskRows;
        _isLoading = false;
        _lastUpdatedAt = DateTime.now();
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = 'Failed to load metrics: $e';
        _errorDetail = ErrorReporter.detail(e);
        _isLoading = false;
      });
    }
  }

  void _setWindow(_Window w) {
    setState(() => _window = w);
    _fetch();
  }

  List<_EndpointRow> get _sortedEndpointRows {
    final rows = List<_EndpointRow>.from(_endpointRows);
    int cmp<T extends Comparable<T>>(T a, T b) =>
        _endpointSortAsc ? a.compareTo(b) : b.compareTo(a);
    rows.sort((a, b) {
      switch (_endpointSortIdx) {
        case 0:
          return cmp(a.normalizedPath, b.normalizedPath);
        case 1:
          return cmp(a.p50Ms, b.p50Ms);
        case 2:
          return cmp(a.p95Ms, b.p95Ms);
        case 3:
          return cmp(a.p99Ms, b.p99Ms);
        case 4:
          return cmp(a.count, b.count);
        case 5:
          return cmp(a.errorRate, b.errorRate);
        default:
          return cmp(a.p95Ms, b.p95Ms);
      }
    });
    return rows;
  }

  List<_TaskRow> get _sortedTaskRows {
    final rows = List<_TaskRow>.from(_taskRows);
    int cmp<T extends Comparable<T>>(T a, T b) =>
        _taskSortAsc ? a.compareTo(b) : b.compareTo(a);
    rows.sort((a, b) {
      switch (_taskSortIdx) {
        case 0:
          return cmp(a.taskName, b.taskName);
        case 1:
          return cmp(a.p50Ms, b.p50Ms);
        case 2:
          return cmp(a.p95Ms, b.p95Ms);
        case 3:
          return cmp(a.p99Ms, b.p99Ms);
        case 4:
          return cmp(a.count, b.count);
        case 5:
          return cmp(a.failureRate, b.failureRate);
        default:
          return cmp(a.p95Ms, b.p95Ms);
      }
    });
    return rows;
  }

  String _lastUpdatedLabel() {
    final ts = _lastUpdatedAt;
    if (ts == null) return '';
    final secs = DateTime.now().difference(ts).inSeconds;
    if (secs < 2) return 'Last updated just now';
    if (secs < 60) return 'Last updated ${secs}s ago';
    final mins = secs ~/ 60;
    return 'Last updated ${mins}m ago';
  }

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final colorScheme = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: Text('Metrics', style: textTheme.titleLarge),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _buildError(colorScheme, textTheme)
              : RefreshIndicator(
                  onRefresh: _fetch,
                  child: ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.all(16),
                    children: [
                      _buildHeader(textTheme, colorScheme),
                      const SizedBox(height: 24),
                      Text(
                        'Endpoints',
                        style: textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 8),
                      _buildEndpointsTable(),
                      const SizedBox(height: 24),
                      Text(
                        'Tasks',
                        style: textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 8),
                      _buildTasksTable(),
                    ],
                  ),
                ),
    );
  }

  Widget _buildHeader(TextTheme textTheme, ColorScheme colorScheme) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SegmentedButton<_Window>(
          segments: const [
            ButtonSegment(value: _Window.oneHour, label: Text('1h')),
            ButtonSegment(value: _Window.twentyFourHours, label: Text('24h')),
            ButtonSegment(value: _Window.sevenDays, label: Text('7d')),
          ],
          selected: {_window},
          onSelectionChanged: (s) => _setWindow(s.first),
        ),
        const SizedBox(height: 8),
        Text(
          _lastUpdatedLabel(),
          style: textTheme.bodySmall?.copyWith(
            color: colorScheme.onSurfaceVariant,
          ),
        ),
      ],
    );
  }

  Widget _buildEndpointsTable() {
    return MetricsTable(
      columns: const [
        MetricsTableColumn(label: 'Path'),
        MetricsTableColumn(label: 'p50', numeric: true),
        MetricsTableColumn(label: 'p95', numeric: true),
        MetricsTableColumn(label: 'p99', numeric: true),
        MetricsTableColumn(label: 'count', numeric: true),
        MetricsTableColumn(label: 'err%', numeric: true),
        MetricsTableColumn(label: 'trend', sortable: false),
      ],
      sortColumnIndex: _endpointSortIdx,
      sortAscending: _endpointSortAsc,
      onSortChanged: (e) {
        setState(() {
          _endpointSortIdx = e.columnIndex;
          _endpointSortAsc = e.ascending;
        });
      },
      rows: [
        for (final r in _sortedEndpointRows)
          MetricsTableRow(
            cells: [
              '${r.method} ${r.normalizedPath}',
              r.p50Ms,
              r.p95Ms,
              r.p99Ms,
              r.count,
              (r.errorRate * 100).toStringAsFixed(1),
              SparklineCell(r.sparkline),
            ],
          ),
      ],
    );
  }

  Widget _buildTasksTable() {
    return MetricsTable(
      columns: const [
        MetricsTableColumn(label: 'Task'),
        MetricsTableColumn(label: 'p50', numeric: true),
        MetricsTableColumn(label: 'p95', numeric: true),
        MetricsTableColumn(label: 'p99', numeric: true),
        MetricsTableColumn(label: 'count', numeric: true),
        MetricsTableColumn(label: 'fail%', numeric: true),
        MetricsTableColumn(label: 'trend', sortable: false),
      ],
      sortColumnIndex: _taskSortIdx,
      sortAscending: _taskSortAsc,
      onSortChanged: (e) {
        setState(() {
          _taskSortIdx = e.columnIndex;
          _taskSortAsc = e.ascending;
        });
      },
      rows: [
        for (final r in _sortedTaskRows)
          MetricsTableRow(
            cells: [
              r.taskName,
              r.p50Ms,
              r.p95Ms,
              r.p99Ms,
              r.count,
              (r.failureRate * 100).toStringAsFixed(1),
              SparklineCell(r.sparkline),
            ],
          ),
      ],
    );
  }

  Widget _buildError(ColorScheme colorScheme, TextTheme textTheme) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.error_outline, size: 64, color: colorScheme.error),
            const SizedBox(height: 16),
            Text(_error!, style: textTheme.bodyMedium, textAlign: TextAlign.center),
            if (_errorDetail != null) ...[
              const SizedBox(height: 8),
              Text(
                _errorDetail!,
                style: textTheme.bodySmall?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                ),
                textAlign: TextAlign.center,
              ),
            ],
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: _fetch,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }
}
