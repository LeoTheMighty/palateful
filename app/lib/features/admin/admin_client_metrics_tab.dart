import 'dart:async';

import 'package:flutter/material.dart';

import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../core/services/error_reporter.dart';
import 'widgets/latency_sparkline.dart';
import 'widgets/metrics_table.dart';

/// Client tab on `/admin/metrics` (cla-10b).
///
/// Mirrors the server-side tab's shape: a header with filters, four stat
/// cards with sparklines, and three drilldown tables (routes, endpoints,
/// jank). Data comes from four `/v1/admin/metrics/client/...` endpoints
/// shipped in cla-10a; the sparkline endpoint is called once per metric
/// (cold-start, route-paint, network, jank) to drive the stat cards.
///
/// Kept as a StatefulWidget (not Riverpod) to match the rest of the admin
/// surface. `AutomaticKeepAliveClientMixin` prevents re-fetch when the
/// parent TabBarView rebuilds.
class AdminClientMetricsTab extends StatefulWidget {
  const AdminClientMetricsTab({super.key});

  @override
  State<AdminClientMetricsTab> createState() => _AdminClientMetricsTabState();
}

enum _ClientWindow { oneHour, twentyFourHours, sevenDays, thirtyDays }

extension on _ClientWindow {
  String get wire => switch (this) {
        _ClientWindow.oneHour => '1h',
        _ClientWindow.twentyFourHours => '24h',
        _ClientWindow.sevenDays => '7d',
        _ClientWindow.thirtyDays => '30d',
      };
  String get label => switch (this) {
        _ClientWindow.oneHour => '1h',
        _ClientWindow.twentyFourHours => '24h',
        _ClientWindow.sevenDays => '7d',
        _ClientWindow.thirtyDays => '30d',
      };
}

enum _ClientPlatform { all, ios, android, web }

extension on _ClientPlatform {
  String? get wire => switch (this) {
        _ClientPlatform.all => null,
        _ClientPlatform.ios => 'ios',
        _ClientPlatform.android => 'android',
        _ClientPlatform.web => 'web',
      };
  String get label => switch (this) {
        _ClientPlatform.all => 'All',
        _ClientPlatform.ios => 'iOS',
        _ClientPlatform.android => 'Android',
        _ClientPlatform.web => 'Web',
      };
}

class _RouteRow {
  final String route;
  final int p50Ms;
  final int p95Ms;
  final int p99Ms;
  final int count;

  const _RouteRow({
    required this.route,
    required this.p50Ms,
    required this.p95Ms,
    required this.p99Ms,
    required this.count,
  });

  factory _RouteRow.fromJson(Map<String, dynamic> json) {
    return _RouteRow(
      route: json['route'] as String,
      p50Ms: (json['p50_ms'] as num? ?? 0).toInt(),
      p95Ms: (json['p95_ms'] as num? ?? 0).toInt(),
      p99Ms: (json['p99_ms'] as num? ?? 0).toInt(),
      count: (json['count'] as num? ?? 0).toInt(),
    );
  }
}

class _EndpointRow {
  final String method;
  final String endpoint;
  final int p50Ms;
  final int p95Ms;
  final int p99Ms;
  final int count;

  const _EndpointRow({
    required this.method,
    required this.endpoint,
    required this.p50Ms,
    required this.p95Ms,
    required this.p99Ms,
    required this.count,
  });

  factory _EndpointRow.fromJson(Map<String, dynamic> json) {
    return _EndpointRow(
      method: json['method'] as String? ?? '',
      endpoint: json['endpoint'] as String,
      p50Ms: (json['p50_ms'] as num? ?? 0).toInt(),
      p95Ms: (json['p95_ms'] as num? ?? 0).toInt(),
      p99Ms: (json['p99_ms'] as num? ?? 0).toInt(),
      count: (json['count'] as num? ?? 0).toInt(),
    );
  }
}

class _JankRow {
  final String route;
  final int buildP95Ms;
  final int rasterP95Ms;
  final int count;

  const _JankRow({
    required this.route,
    required this.buildP95Ms,
    required this.rasterP95Ms,
    required this.count,
  });

  factory _JankRow.fromJson(Map<String, dynamic> json) {
    return _JankRow(
      route: json['route'] as String,
      buildP95Ms: (json['build_p95_ms'] as num? ?? 0).toInt(),
      rasterP95Ms: (json['raster_p95_ms'] as num? ?? 0).toInt(),
      count: (json['count'] as num? ?? 0).toInt(),
    );
  }
}

class _AdminClientMetricsTabState extends State<AdminClientMetricsTab>
    with AutomaticKeepAliveClientMixin {
  final _apiClient = getIt<ApiClient>();

  _ClientWindow _window = _ClientWindow.twentyFourHours;
  _ClientPlatform _platform = _ClientPlatform.all;
  final _appVersionController = TextEditingController();
  final _routeController = TextEditingController();

  bool _isLoading = true;
  String? _error;
  String? _errorDetail;

  List<_RouteRow> _routeRows = const [];
  List<_EndpointRow> _endpointRows = const [];
  List<_JankRow> _jankRows = const [];

  List<double> _coldStartSparkline = const [];
  List<double> _routePaintSparkline = const [];
  List<double> _networkSparkline = const [];
  List<double> _jankSparkline = const [];

  int _routeSortIdx = 2; // p95
  bool _routeSortAsc = false;
  int _endpointSortIdx = 3; // p95
  bool _endpointSortAsc = false;
  int _jankSortIdx = 1; // build_p95
  bool _jankSortAsc = false;

  DateTime? _lastUpdatedAt;
  Timer? _updatedAgoTicker;

  // Monotonically increasing; the handler drops responses whose token
  // doesn't match so rapid filter changes can't land stale data.
  int _fetchToken = 0;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _fetch();
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
    _appVersionController.dispose();
    _routeController.dispose();
    super.dispose();
  }

  Future<void> _fetch() async {
    final myToken = ++_fetchToken;
    setState(() {
      _isLoading = true;
      _error = null;
    });

    final appVersion = _appVersionController.text.trim().isEmpty
        ? null
        : _appVersionController.text.trim();
    final route = _routeController.text.trim().isEmpty
        ? null
        : _routeController.text.trim();

    try {
      final results = await Future.wait([
        _apiClient.getClientRouteMetrics(
          window: _window.wire,
          platform: _platform.wire,
          appVersion: appVersion,
          route: route,
        ),
        _apiClient.getClientEndpointMetrics(
          window: _window.wire,
          platform: _platform.wire,
          appVersion: appVersion,
          route: route,
        ),
        _apiClient.getClientJankMetrics(
          window: _window.wire,
          platform: _platform.wire,
          appVersion: appVersion,
          route: route,
        ),
        _apiClient.getClientSparkline(
          metric: 'app_start',
          window: _window.wire,
          platform: _platform.wire,
          appVersion: appVersion,
        ),
        _apiClient.getClientSparkline(
          metric: 'route_paint',
          window: _window.wire,
          platform: _platform.wire,
          appVersion: appVersion,
          route: route,
        ),
        _apiClient.getClientSparkline(
          metric: 'network_request',
          window: _window.wire,
          platform: _platform.wire,
          appVersion: appVersion,
          route: route,
        ),
        _apiClient.getClientSparkline(
          metric: 'frame_jank_p95',
          window: _window.wire,
          platform: _platform.wire,
          appVersion: appVersion,
          route: route,
        ),
      ]);
      if (!mounted || myToken != _fetchToken) return;

      final routeRows = (results[0].data['rows'] as List<dynamic>)
          .map((e) => _RouteRow.fromJson(e as Map<String, dynamic>))
          .toList();
      final endpointRows = (results[1].data['rows'] as List<dynamic>)
          .map((e) => _EndpointRow.fromJson(e as Map<String, dynamic>))
          .toList();
      final jankRows = (results[2].data['rows'] as List<dynamic>)
          .map((e) => _JankRow.fromJson(e as Map<String, dynamic>))
          .toList();

      List<double> parseSparkline(dynamic data) {
        return (data['buckets'] as List<dynamic>? ?? const [])
            .map((e) => (e as num).toDouble())
            .toList();
      }

      setState(() {
        _routeRows = routeRows;
        _endpointRows = endpointRows;
        _jankRows = jankRows;
        _coldStartSparkline = parseSparkline(results[3].data);
        _routePaintSparkline = parseSparkline(results[4].data);
        _networkSparkline = parseSparkline(results[5].data);
        _jankSparkline = parseSparkline(results[6].data);
        _isLoading = false;
        _lastUpdatedAt = DateTime.now();
      });
    } catch (e) {
      if (!mounted || myToken != _fetchToken) return;
      setState(() {
        _error = 'Failed to load client metrics: $e';
        _errorDetail = ErrorReporter.detail(e);
        _isLoading = false;
      });
    }
  }

  int _maxRoutePaintP95() {
    if (_routeRows.isEmpty) return 0;
    return _routeRows.map((r) => r.p95Ms).reduce((a, b) => a > b ? a : b);
  }

  int _maxNetworkP95() {
    if (_endpointRows.isEmpty) return 0;
    return _endpointRows.map((r) => r.p95Ms).reduce((a, b) => a > b ? a : b);
  }

  int _maxJankBuildP95() {
    if (_jankRows.isEmpty) return 0;
    return _jankRows.map((r) => r.buildP95Ms).reduce((a, b) => a > b ? a : b);
  }

  int _coldStartPeak() {
    if (_coldStartSparkline.isEmpty) return 0;
    final peak = _coldStartSparkline.reduce((a, b) => a > b ? a : b);
    return peak.round();
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

  List<_RouteRow> get _sortedRouteRows {
    final rows = List<_RouteRow>.from(_routeRows);
    int cmp<T extends Comparable<T>>(T a, T b) =>
        _routeSortAsc ? a.compareTo(b) : b.compareTo(a);
    rows.sort((a, b) {
      switch (_routeSortIdx) {
        case 0:
          return cmp(a.route, b.route);
        case 1:
          return cmp(a.p50Ms, b.p50Ms);
        case 2:
          return cmp(a.p95Ms, b.p95Ms);
        case 3:
          return cmp(a.p99Ms, b.p99Ms);
        case 4:
          return cmp(a.count, b.count);
        default:
          return cmp(a.p95Ms, b.p95Ms);
      }
    });
    return rows;
  }

  List<_EndpointRow> get _sortedEndpointRows {
    final rows = List<_EndpointRow>.from(_endpointRows);
    int cmp<T extends Comparable<T>>(T a, T b) =>
        _endpointSortAsc ? a.compareTo(b) : b.compareTo(a);
    rows.sort((a, b) {
      switch (_endpointSortIdx) {
        case 0:
          return cmp('${a.method} ${a.endpoint}', '${b.method} ${b.endpoint}');
        case 1:
          return cmp(a.p50Ms, b.p50Ms);
        case 2:
          return cmp(a.p95Ms, b.p95Ms);
        case 3:
          return cmp(a.p99Ms, b.p99Ms);
        case 4:
          return cmp(a.count, b.count);
        default:
          return cmp(a.p95Ms, b.p95Ms);
      }
    });
    return rows;
  }

  List<_JankRow> get _sortedJankRows {
    final rows = List<_JankRow>.from(_jankRows);
    int cmp<T extends Comparable<T>>(T a, T b) =>
        _jankSortAsc ? a.compareTo(b) : b.compareTo(a);
    rows.sort((a, b) {
      switch (_jankSortIdx) {
        case 0:
          return cmp(a.route, b.route);
        case 1:
          return cmp(a.buildP95Ms, b.buildP95Ms);
        case 2:
          return cmp(a.rasterP95Ms, b.rasterP95Ms);
        case 3:
          return cmp(a.count, b.count);
        default:
          return cmp(a.buildP95Ms, b.buildP95Ms);
      }
    });
    return rows;
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    final textTheme = Theme.of(context).textTheme;
    final colorScheme = Theme.of(context).colorScheme;

    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return _buildError(colorScheme, textTheme);
    }

    return RefreshIndicator(
      onRefresh: _fetch,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        children: [
          _buildHeader(textTheme, colorScheme),
          const SizedBox(height: 16),
          _buildStatCards(textTheme, colorScheme),
          const SizedBox(height: 24),
          _buildSectionHeader('Routes', textTheme),
          const SizedBox(height: 8),
          _buildRoutesTable(),
          const SizedBox(height: 24),
          _buildSectionHeader('Endpoints', textTheme),
          const SizedBox(height: 8),
          _buildEndpointsTable(),
          const SizedBox(height: 24),
          _buildSectionHeader('Frame jank', textTheme),
          const SizedBox(height: 8),
          _buildJankTable(),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(String title, TextTheme textTheme) {
    return Text(
      title,
      style: textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
    );
  }

  Widget _buildHeader(TextTheme textTheme, ColorScheme colorScheme) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(
          spacing: 12,
          runSpacing: 8,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            SegmentedButton<_ClientWindow>(
              segments: [
                for (final w in _ClientWindow.values)
                  ButtonSegment(value: w, label: Text(w.label)),
              ],
              selected: {_window},
              onSelectionChanged: (s) {
                setState(() => _window = s.first);
                _fetch();
              },
            ),
            SegmentedButton<_ClientPlatform>(
              segments: [
                for (final p in _ClientPlatform.values)
                  ButtonSegment(value: p, label: Text(p.label)),
              ],
              selected: {_platform},
              onSelectionChanged: (s) {
                setState(() => _platform = s.first);
                _fetch();
              },
            ),
          ],
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: TextField(
                controller: _appVersionController,
                decoration: const InputDecoration(
                  labelText: 'app_version',
                  hintText: '1.0.55+68',
                  isDense: true,
                  border: OutlineInputBorder(),
                ),
                onSubmitted: (_) => _fetch(),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: TextField(
                controller: _routeController,
                decoration: const InputDecoration(
                  labelText: 'route',
                  hintText: '/recipes/:id',
                  isDense: true,
                  border: OutlineInputBorder(),
                ),
                onSubmitted: (_) => _fetch(),
              ),
            ),
            const SizedBox(width: 8),
            FilledButton.icon(
              onPressed: _fetch,
              icon: const Icon(Icons.search),
              label: const Text('Apply'),
            ),
          ],
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

  Widget _buildStatCards(TextTheme textTheme, ColorScheme colorScheme) {
    final cards = [
      _StatCard(
        label: 'Cold-start (peak)',
        value: '${_coldStartPeak()} ms',
        sparkline: _coldStartSparkline,
      ),
      _StatCard(
        label: 'Route paint p95 (worst)',
        value: '${_maxRoutePaintP95()} ms',
        sparkline: _routePaintSparkline,
      ),
      _StatCard(
        label: 'Network p95 (worst)',
        value: '${_maxNetworkP95()} ms',
        sparkline: _networkSparkline,
      ),
      _StatCard(
        label: 'Jank build p95 (worst)',
        value: '${_maxJankBuildP95()} ms',
        sparkline: _jankSparkline,
      ),
    ];
    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= 600;
        if (wide) {
          return Row(
            children: [
              for (int i = 0; i < cards.length; i++) ...[
                Expanded(child: cards[i]),
                if (i < cards.length - 1) const SizedBox(width: 12),
              ],
            ],
          );
        }
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            for (int i = 0; i < cards.length; i++) ...[
              cards[i],
              if (i < cards.length - 1) const SizedBox(height: 12),
            ],
          ],
        );
      },
    );
  }

  Widget _buildRoutesTable() {
    return MetricsTable(
      columns: const [
        MetricsTableColumn(label: 'Route'),
        MetricsTableColumn(label: 'p50', numeric: true),
        MetricsTableColumn(label: 'p95', numeric: true),
        MetricsTableColumn(label: 'p99', numeric: true),
        MetricsTableColumn(label: 'count', numeric: true),
      ],
      sortColumnIndex: _routeSortIdx,
      sortAscending: _routeSortAsc,
      onSortChanged: (e) {
        setState(() {
          _routeSortIdx = e.columnIndex;
          _routeSortAsc = e.ascending;
        });
      },
      rows: [
        for (final r in _sortedRouteRows)
          MetricsTableRow(
            cells: [r.route, r.p50Ms, r.p95Ms, r.p99Ms, r.count],
          ),
      ],
    );
  }

  Widget _buildEndpointsTable() {
    return MetricsTable(
      columns: const [
        MetricsTableColumn(label: 'Endpoint'),
        MetricsTableColumn(label: 'p50', numeric: true),
        MetricsTableColumn(label: 'p95', numeric: true),
        MetricsTableColumn(label: 'p99', numeric: true),
        MetricsTableColumn(label: 'count', numeric: true),
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
              '${r.method} ${r.endpoint}',
              r.p50Ms,
              r.p95Ms,
              r.p99Ms,
              r.count,
            ],
          ),
      ],
    );
  }

  Widget _buildJankTable() {
    return MetricsTable(
      columns: const [
        MetricsTableColumn(label: 'Route'),
        MetricsTableColumn(label: 'build p95', numeric: true),
        MetricsTableColumn(label: 'raster p95', numeric: true),
        MetricsTableColumn(label: 'count', numeric: true),
      ],
      sortColumnIndex: _jankSortIdx,
      sortAscending: _jankSortAsc,
      onSortChanged: (e) {
        setState(() {
          _jankSortIdx = e.columnIndex;
          _jankSortAsc = e.ascending;
        });
      },
      rows: [
        for (final r in _sortedJankRows)
          MetricsTableRow(
            cells: [r.route, r.buildP95Ms, r.rasterP95Ms, r.count],
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

class _StatCard extends StatelessWidget {
  final String label;
  final String value;
  final List<double> sparkline;

  const _StatCard({
    required this.label,
    required this.value,
    required this.sparkline,
  });

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final colorScheme = Theme.of(context).colorScheme;
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        side: BorderSide(color: colorScheme.outlineVariant),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              label,
              style: textTheme.labelMedium?.copyWith(
                color: colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              value,
              style: textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 8),
            LayoutBuilder(
              builder: (context, constraints) => LatencySparkline(
                values: sparkline,
                width: constraints.maxWidth,
                height: 24,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
