import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';

import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../core/services/error_reporter.dart';
import '../../shared/widgets/error_banner.dart';

class AdminDashboardScreen extends StatefulWidget {
  const AdminDashboardScreen({super.key});

  @override
  State<AdminDashboardScreen> createState() => _AdminDashboardScreenState();
}

class _AdminDashboardScreenState extends State<AdminDashboardScreen> {
  final _apiClient = getIt<ApiClient>();

  bool _isLoading = true;
  String? _error;
  String? _errorDetail;

  int _totalUsers = 0;
  int _totalRecipes = 0;
  int _totalRecipeBooks = 0;
  int _errors24h = 0;
  int _activeUsers7d = 0;
  int _unreadFeedback = 0;
  int? _overallP95Ms;
  Map<String, dynamic>? _slowestEndpoint;

  bool _testPushSending = false;
  String? _testPushResult;
  bool _testPushIsError = false;

  final _healthLookupController = TextEditingController();
  bool _healthLookupLoading = false;
  Map<String, dynamic>? _healthResult;
  String? _healthError;
  bool _healthTargetTestPushSending = false;
  String? _healthTargetTestPushResult;
  bool _healthTargetTestPushIsError = false;

  @override
  void initState() {
    super.initState();
    _fetchStats();
  }

  @override
  void dispose() {
    _healthLookupController.dispose();
    super.dispose();
  }

  Future<void> _fetchStats() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final response = await _apiClient.getAdminStats();
      if (!mounted) return;

      final data = response.data as Map<String, dynamic>;
      setState(() {
        _totalUsers = data['total_users'] as int? ?? 0;
        _totalRecipes = data['total_recipes'] as int? ?? 0;
        _totalRecipeBooks = data['total_recipe_books'] as int? ?? 0;
        _errors24h = data['errors_24h'] as int? ?? 0;
        _activeUsers7d = data['active_users_7d'] as int? ?? 0;
        _unreadFeedback = data['unread_feedback'] as int? ?? 0;
        _overallP95Ms = data['overall_p95_ms'] as int?;
        _slowestEndpoint = data['slowest_endpoint'] as Map<String, dynamic>?;
        _isLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = 'Failed to load stats: $e';
        _errorDetail = ErrorReporter.detail(e);
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(
        title: Text('Admin Dashboard', style: textTheme.titleLarge),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _buildError(colorScheme, textTheme)
              : _buildContent(colorScheme, textTheme),
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
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: _fetchStats,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildContent(ColorScheme colorScheme, TextTheme textTheme) {
    return RefreshIndicator(
      onRefresh: _fetchStats,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Overview', style: textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600)),
            const SizedBox(height: 12),

            // Stats cards grid
            Wrap(
              spacing: 12,
              runSpacing: 12,
              children: [
                _buildStatCard('Total Users', '$_totalUsers', Icons.people, colorScheme.primary, colorScheme, textTheme),
                _buildStatCard('Total Recipes', '$_totalRecipes', Icons.restaurant_menu, colorScheme.secondary, colorScheme, textTheme),
                _buildStatCard('Recipe Books', '$_totalRecipeBooks', Icons.menu_book, colorScheme.tertiary, colorScheme, textTheme),
                _buildStatCard('Errors (24h)', '$_errors24h', Icons.error_outline, _errors24h > 0 ? colorScheme.error : colorScheme.primary, colorScheme, textTheme),
                _buildStatCard('Active (7d)', '$_activeUsers7d', Icons.trending_up, colorScheme.primary, colorScheme, textTheme),
                _buildStatCard(
                  'p95 (24h)',
                  _overallP95Ms == null ? '—' : '${_overallP95Ms}ms',
                  Icons.speed,
                  colorScheme.primary,
                  colorScheme,
                  textTheme,
                ),
              ],
            ),
            if (_slowestEndpoint != null) ...[
              const SizedBox(height: 12),
              _buildSlowestEndpointStrip(colorScheme, textTheme),
            ],

            const SizedBox(height: 32),
            Text('Quick Actions', style: textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600)),
            const SizedBox(height: 12),

            _buildNavTile(
              icon: Icons.article_outlined,
              label: 'View Logs',
              subtitle: 'Browse service logs in real-time',
              onTap: () => context.push('/admin/logs'),
              colorScheme: colorScheme,
              textTheme: textTheme,
            ),
            const SizedBox(height: 8),
            _buildNavTile(
              icon: Icons.bug_report_outlined,
              label: 'View Errors',
              subtitle: 'Inspect API errors and stack traces',
              onTap: () => context.push('/admin/errors'),
              colorScheme: colorScheme,
              textTheme: textTheme,
            ),
            const SizedBox(height: 8),
            _buildNavTile(
              icon: Icons.admin_panel_settings_outlined,
              label: 'Manage Users',
              subtitle: 'View users and manage admin access',
              onTap: () => context.push('/admin/users'),
              colorScheme: colorScheme,
              textTheme: textTheme,
            ),
            const SizedBox(height: 8),
            _buildNavTile(
              icon: Icons.query_stats_outlined,
              label: 'Metrics',
              subtitle: 'Endpoint + Celery latency at p50/p95/p99',
              onTap: () => context.push('/admin/metrics'),
              colorScheme: colorScheme,
              textTheme: textTheme,
            ),
            const SizedBox(height: 8),
            _buildFeedbackTile(colorScheme, textTheme),

            const SizedBox(height: 32),
            Text(
              'Notifications',
              style: textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 12),
            _buildTestPushCard(colorScheme, textTheme),
            const SizedBox(height: 12),
            _buildHealthLookupCard(colorScheme, textTheme),
          ],
        ),
      ),
    );
  }

  Widget _buildHealthLookupCard(ColorScheme colorScheme, TextTheme textTheme) {
    return Material(
      color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.health_and_safety_outlined,
                    color: colorScheme.onSurfaceVariant),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Check user\'s push health',
                    style: textTheme.bodyLarge,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              'Diagnose "I\'m not getting pushes" reports. Paste a user UUID '
              'or email. Read-only; writes a single audit row.',
              style: textTheme.bodySmall
                  ?.copyWith(color: colorScheme.onSurfaceVariant),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _healthLookupController,
                    decoration: const InputDecoration(
                      labelText: 'User UUID or email',
                      border: OutlineInputBorder(),
                      isDense: true,
                    ),
                    onSubmitted: (_) => _lookupHealth(),
                  ),
                ),
                const SizedBox(width: 8),
                FilledButton.icon(
                  onPressed: _healthLookupLoading ? null : _lookupHealth,
                  icon: _healthLookupLoading
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.search, size: 18),
                  label: Text(_healthLookupLoading ? 'Checking…' : 'Check'),
                ),
              ],
            ),
            if (_healthError != null) ...[
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: colorScheme.errorContainer.withValues(alpha: 0.4),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  _healthError!,
                  style: textTheme.bodySmall
                      ?.copyWith(color: colorScheme.onErrorContainer),
                ),
              ),
            ],
            if (_healthResult != null) ...[
              const SizedBox(height: 12),
              _buildHealthResult(colorScheme, textTheme),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildHealthResult(ColorScheme colorScheme, TextTheme textTheme) {
    final data = _healthResult!;
    final status = data['notification_permission_status'] as String?;
    final tokenCount = data['push_tokens_count'] as int? ?? 0;
    final errorCount = data['recent_errors_count'] as int? ?? 0;
    final errors = (data['recent_errors'] as List?) ?? const [];
    final crashlyticsUrl = data['crashlytics_query_url'] as String?;
    final targetUserId = data['user_id'] as String?;

    Color permissionColor() {
      switch (status) {
        case 'granted':
        case 'provisional':
          return Colors.green;
        case 'declined':
          return colorScheme.error;
        default:
          return colorScheme.onSurfaceVariant;
      }
    }

    Color tokenColor() =>
        tokenCount > 0 ? Colors.green : colorScheme.error;

    Color errorColor() =>
        errorCount > 0 ? colorScheme.error : colorScheme.onSurfaceVariant;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _healthRow('User', data['user_id']?.toString() ?? '—', textTheme,
            colorScheme.onSurface),
        _healthRow('Email', data['email']?.toString() ?? '—', textTheme,
            colorScheme.onSurface),
        _healthRow(
          'Permission',
          status ?? 'null (never asked)',
          textTheme,
          permissionColor(),
        ),
        _healthRow('Tokens', '$tokenCount', textTheme, tokenColor()),
        _healthRow('Recent errors', '$errorCount', textTheme, errorColor()),
        _healthRow(
          'Last send',
          data['last_successful_send_at']?.toString() ?? 'not tracked',
          textTheme,
          colorScheme.onSurfaceVariant,
        ),
        if (errors.isNotEmpty) ...[
          const SizedBox(height: 8),
          Text('Recent push errors:',
              style: textTheme.bodySmall
                  ?.copyWith(fontWeight: FontWeight.w600)),
          const SizedBox(height: 4),
          ...errors.take(5).map((e) {
            final row = e as Map<String, dynamic>;
            return Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Text(
                '· ${row['timestamp']} — ${row['error_type']}: ${row['message']}',
                style: textTheme.bodySmall
                    ?.copyWith(color: colorScheme.onSurfaceVariant),
              ),
            );
          }),
        ],
        const SizedBox(height: 12),
        Row(
          children: [
            if (targetUserId != null)
              FilledButton.tonalIcon(
                onPressed: _healthTargetTestPushSending
                    ? null
                    : () => _sendTestPushTo(targetUserId),
                icon: _healthTargetTestPushSending
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.send_outlined, size: 18),
                label: Text(_healthTargetTestPushSending
                    ? 'Sending…'
                    : 'Send test push to this user'),
              ),
            if (crashlyticsUrl != null) ...[
              const SizedBox(width: 8),
              TextButton.icon(
                onPressed: () {
                  Clipboard.setData(ClipboardData(text: crashlyticsUrl));
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content:
                          Text('Crashlytics link copied to clipboard'),
                    ),
                  );
                },
                icon: const Icon(Icons.open_in_new, size: 18),
                label: const Text('Crashlytics link'),
              ),
            ],
          ],
        ),
        if (_healthTargetTestPushResult != null) ...[
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: (_healthTargetTestPushIsError
                      ? colorScheme.errorContainer
                      : colorScheme.primaryContainer)
                  .withValues(alpha: 0.4),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Text(
              _healthTargetTestPushResult!,
              style: textTheme.bodySmall?.copyWith(
                color: _healthTargetTestPushIsError
                    ? colorScheme.onErrorContainer
                    : colorScheme.onPrimaryContainer,
              ),
            ),
          ),
        ],
      ],
    );
  }

  Widget _healthRow(
      String label, String value, TextTheme textTheme, Color valueColor) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 110,
            child: Text(
              label,
              style: textTheme.bodySmall?.copyWith(fontWeight: FontWeight.w600),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: textTheme.bodySmall?.copyWith(color: valueColor),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _lookupHealth() async {
    final query = _healthLookupController.text.trim();
    if (query.isEmpty) return;

    setState(() {
      _healthLookupLoading = true;
      _healthError = null;
      _healthResult = null;
      _healthTargetTestPushResult = null;
    });

    try {
      final response = await _apiClient.getAdminPushHealth(query);
      if (!mounted) return;
      setState(() {
        _healthLookupLoading = false;
        _healthResult = (response.data as Map).cast<String, dynamic>();
      });
    } on DioException catch (e) {
      if (!mounted) return;
      final status = e.response?.statusCode ?? 0;
      final body = e.response?.data;
      String message;
      if (status == 404) {
        message = 'No user found with that UUID or email.';
      } else if (body is Map && body['error_message'] is String) {
        message = 'Error ($status): ${body['error_message']}';
      } else {
        message = 'Error: ${ErrorReporter.detail(e)}';
      }
      setState(() {
        _healthLookupLoading = false;
        _healthError = message;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _healthLookupLoading = false;
        _healthError = 'Unexpected error: $e';
      });
    }
  }

  Future<void> _sendTestPushTo(String targetUserId) async {
    setState(() {
      _healthTargetTestPushSending = true;
      _healthTargetTestPushResult = null;
      _healthTargetTestPushIsError = false;
    });

    try {
      final response =
          await _apiClient.sendAdminTestPush(targetUserId: targetUserId);
      if (!mounted) return;
      final data = response.data as Map<String, dynamic>;
      final outcome = data['outcome'] as String? ?? 'ok';
      final messageId = data['message_id'] as String?;
      String message;
      switch (outcome) {
        case 'ok':
          message = '✓ Sent (msg-id: ${messageId ?? "—"}).';
          break;
        case 'no_tokens':
          message =
              'No push tokens registered for target user.';
          break;
        case 'log_only':
          message = 'Sent in log-only mode.';
          break;
        default:
          message = 'Sent (outcome=$outcome).';
      }
      setState(() {
        _healthTargetTestPushSending = false;
        _healthTargetTestPushResult = message;
      });
    } on DioException catch (e) {
      if (!mounted) return;
      setState(() {
        _healthTargetTestPushSending = false;
        _healthTargetTestPushResult = 'Error: ${ErrorReporter.detail(e)}';
        _healthTargetTestPushIsError = true;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _healthTargetTestPushSending = false;
        _healthTargetTestPushResult = 'Unexpected error: $e';
        _healthTargetTestPushIsError = true;
      });
    }
  }

  Widget _buildTestPushCard(ColorScheme colorScheme, TextTheme textTheme) {
    return Material(
      color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.notifications_active_outlined, color: colorScheme.onSurfaceVariant),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Send test push to myself',
                    style: textTheme.bodyLarge,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              'Fires a FCM push with title "Palateful test push" to every device you have registered.',
              style: textTheme.bodySmall?.copyWith(color: colorScheme.onSurfaceVariant),
            ),
            const SizedBox(height: 12),
            FilledButton.icon(
              onPressed: _testPushSending ? null : _sendTestPush,
              icon: _testPushSending
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.send_outlined, size: 18),
              label: Text(_testPushSending ? 'Sending…' : 'Send test push'),
            ),
            if (_testPushResult != null) ...[
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: (_testPushIsError ? colorScheme.errorContainer : colorScheme.primaryContainer)
                      .withValues(alpha: 0.4),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  _testPushResult!,
                  style: textTheme.bodySmall?.copyWith(
                    color: _testPushIsError ? colorScheme.onErrorContainer : colorScheme.onPrimaryContainer,
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Future<void> _sendTestPush() async {
    setState(() {
      _testPushSending = true;
      _testPushResult = null;
      _testPushIsError = false;
    });

    try {
      final response = await _apiClient.sendAdminTestPush();
      if (!mounted) return;

      final data = response.data as Map<String, dynamic>;
      final outcome = data['outcome'] as String? ?? 'ok';
      final messageId = data['message_id'] as String?;
      final logOnly = data['log_only'] as bool? ?? false;
      final suppressed = data['suppressed_by_quiet_hours'] as bool? ?? false;
      final tokens = data['tokens_registered'] as int? ?? 0;

      String message;
      switch (outcome) {
        case 'ok':
          message = '✓ Sent (msg-id: ${messageId ?? "—"}). Check your phone.';
          break;
        case 'log_only':
          message = 'Sent in log-only mode — check the API logs. Real FCM delivery '
              'requires FIREBASE_CREDENTIALS_JSON in prod (see docs/PUSH_NOTIFICATIONS.md).';
          break;
        case 'suppressed_quiet_hours':
          message = 'Suppressed by quiet hours. Use force=true (default) to bypass.';
          break;
        case 'no_tokens':
          message = 'No push tokens registered for your user. '
              'Grant notification permission on your device first.';
          break;
        default:
          if (logOnly) {
            message = 'Log-only mode (outcome: $outcome).';
          } else if (suppressed) {
            message = 'Suppressed by quiet hours.';
          } else {
            message = 'Sent but outcome=$outcome (tokens=$tokens).';
          }
      }

      setState(() {
        _testPushSending = false;
        _testPushResult = message;
        _testPushIsError = false;
      });
    } on DioException catch (e) {
      if (!mounted) return;

      String message;
      final status = e.response?.statusCode ?? 0;
      final body = e.response?.data;

      if (status == 429 && body is Map) {
        final retryAfter = (body['data'] as Map?)?['retry_after_s'] as int?;
        message = 'Rate-limited. Retry in ${retryAfter ?? "a few"} seconds.';
      } else if (body is Map && body['error_message'] is String) {
        message = 'Error (${status == 0 ? "?" : status}): ${body['error_message']}';
      } else {
        message = 'Error: ${ErrorReporter.detail(e)}';
      }

      setState(() {
        _testPushSending = false;
        _testPushResult = message;
        _testPushIsError = true;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _testPushSending = false;
        _testPushResult = 'Unexpected error: $e';
        _testPushIsError = true;
      });
    }
  }

  Widget _buildSlowestEndpointStrip(
    ColorScheme colorScheme,
    TextTheme textTheme,
  ) {
    final data = _slowestEndpoint!;
    final method = data['method'] as String? ?? '—';
    final path = data['normalized_path'] as String? ?? '—';
    final p95 = data['p95_ms'] as int? ?? 0;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: colorScheme.errorContainer.withValues(alpha: 0.3),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          Icon(Icons.warning_amber_outlined,
              size: 18, color: colorScheme.error),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              'Slowest (24h): $method $path — ${p95}ms p95',
              style: textTheme.bodySmall?.copyWith(
                color: colorScheme.onErrorContainer,
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatCard(
    String label,
    String value,
    IconData icon,
    Color accentColor,
    ColorScheme colorScheme,
    TextTheme textTheme,
  ) {
    return SizedBox(
      width: 160,
      child: Card(
        elevation: 0,
        color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, color: accentColor, size: 24),
              const SizedBox(height: 8),
              Text(
                value,
                style: textTheme.headlineMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: colorScheme.onSurface,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                label,
                style: textTheme.bodySmall?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildFeedbackTile(
    ColorScheme colorScheme,
    TextTheme textTheme,
  ) {
    return Material(
      color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        key: const Key('admin_feedback_card'),
        onTap: () => context.push(
          '/admin/feedback${_unreadFeedback > 0 ? "?status=unread" : ""}',
        ),
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          child: Row(
            children: [
              Icon(Icons.feedback_outlined,
                  color: colorScheme.onSurfaceVariant),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Feedback', style: textTheme.bodyLarge),
                    Text(
                      _unreadFeedback == 0
                          ? 'No unread feedback'
                          : '$_unreadFeedback unread',
                      style: textTheme.bodySmall?.copyWith(
                        color: colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
              if (_unreadFeedback > 0)
                Container(
                  key: const Key('admin_feedback_badge'),
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 4,
                  ),
                  decoration: BoxDecoration(
                    color: colorScheme.error,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    '$_unreadFeedback',
                    style: textTheme.labelSmall?.copyWith(
                      color: colorScheme.onError,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              const SizedBox(width: 8),
              Icon(Icons.chevron_right, color: colorScheme.onSurfaceVariant),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildNavTile({
    required IconData icon,
    required String label,
    required String subtitle,
    required VoidCallback onTap,
    required ColorScheme colorScheme,
    required TextTheme textTheme,
  }) {
    return Material(
      color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          child: Row(
            children: [
              Icon(icon, color: colorScheme.onSurfaceVariant),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(label, style: textTheme.bodyLarge),
                    Text(
                      subtitle,
                      style: textTheme.bodySmall?.copyWith(
                        color: colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
              Icon(Icons.chevron_right, color: colorScheme.onSurfaceVariant),
            ],
          ),
        ),
      ),
    );
  }
}
