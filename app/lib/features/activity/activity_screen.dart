import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';

/// Activity feed screen — shows import status, partner actions, reminders.
class ActivityScreen extends StatefulWidget {
  const ActivityScreen({super.key});

  @override
  State<ActivityScreen> createState() => _ActivityScreenState();
}

class _ActivityScreenState extends State<ActivityScreen> {
  final _apiClient = getIt<ApiClient>();

  List<dynamic> _activities = [];
  List<dynamic> _activeJobs = [];
  bool _isLoading = true;
  String? _error;
  Timer? _pollTimer;

  @override
  void initState() {
    super.initState();
    _loadAll();
    // Poll for new activities every 30s
    _pollTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      _loadAll(silent: true);
    });
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadAll({bool silent = false}) async {
    if (!silent) {
      setState(() {
        _isLoading = true;
        _error = null;
      });
    }

    try {
      final activitiesResponse = await _apiClient.getActivities();
      if (!mounted) return;

      setState(() {
        _activities = List<dynamic>.from(activitiesResponse.data['items'] ?? []);
        _isLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      if (!silent) {
        setState(() {
          _error = 'Failed to load activities';
          _isLoading = false;
        });
      }
      return;
    }

    // Load active jobs separately — don't break the feed if this fails
    try {
      final jobResults = await Future.wait([
        _apiClient.listImportJobs(status: 'processing', limit: 10),
        _apiClient.listImportJobs(status: 'awaiting_review', limit: 10),
      ]);
      if (!mounted) return;

      final processingJobs = List<dynamic>.from(jobResults[0].data['jobs'] ?? []);
      final reviewJobs = List<dynamic>.from(jobResults[1].data['jobs'] ?? []);

      setState(() {
        _activeJobs = [...processingJobs, ...reviewJobs];
      });
    } catch (_) {
      // Active jobs section is non-critical — silently degrade
      if (mounted) {
        setState(() => _activeJobs = []);
      }
    }
  }

  Future<void> _markAllRead() async {
    try {
      await _apiClient.markAllActivitiesRead();
      if (!mounted) return;
      setState(() {
        for (final a in _activities) {
          a['read'] = true;
        }
      });
    } catch (_) {}
  }

  Future<void> _onActivityTap(dynamic activity) async {
    final id = activity['id']?.toString();
    final actionUrl = activity['action_url'] as String?;

    // Mark as read
    if (id != null && activity['read'] != true) {
      try {
        await _apiClient.markActivityRead(id);
        if (mounted) {
          setState(() => activity['read'] = true);
        }
      } catch (_) {}
    }

    // Navigate if action_url present
    if (actionUrl != null && actionUrl.isNotEmpty && mounted) {
      context.push(actionUrl);
    }
  }

  /// Group activities by day: Today, Yesterday, or date string.
  Map<String, List<dynamic>> _groupByDay() {
    final groups = <String, List<dynamic>>{};
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final yesterday = today.subtract(const Duration(days: 1));

    for (final a in _activities) {
      final createdAt = DateTime.tryParse(a['created_at']?.toString() ?? '');
      String label;
      if (createdAt == null) {
        label = 'Earlier';
      } else {
        final day = DateTime(createdAt.year, createdAt.month, createdAt.day);
        if (day == today) {
          label = 'Today';
        } else if (day == yesterday) {
          label = 'Yesterday';
        } else {
          label = '${createdAt.month}/${createdAt.day}/${createdAt.year}';
        }
      }
      groups.putIfAbsent(label, () => []).add(a);
    }
    return groups;
  }

  IconData _iconForType(String? type) {
    switch (type) {
      case 'import_started':
        return Icons.cloud_upload;
      case 'import_complete':
        return Icons.cloud_done;
      case 'import_needs_review':
        return Icons.rate_review;
      case 'partner_action':
        return Icons.people;
      case 'meal_reminder':
        return Icons.restaurant;
      default:
        return Icons.notifications;
    }
  }

  String _labelForJobStatus(String? status) {
    switch (status) {
      case 'processing':
        return 'Processing';
      case 'awaiting_review':
        return 'Needs Review';
      default:
        return status ?? '';
    }
  }

  Color _colorForJobStatus(String? status, ColorScheme colorScheme) {
    switch (status) {
      case 'processing':
        return colorScheme.tertiary;
      case 'awaiting_review':
        return colorScheme.tertiary;
      default:
        return colorScheme.onSurfaceVariant;
    }
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

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final hasUnread = _activities.any((a) => a['read'] != true);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Activity'),
        actions: [
          IconButton(
            icon: const Icon(Icons.import_export),
            tooltip: 'Import Activity',
            onPressed: () => context.push('/activity/import-history'),
          ),
          if (hasUnread)
            IconButton(
              icon: const Icon(Icons.done_all),
              tooltip: 'Mark all as read',
              onPressed: _markAllRead,
            ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text(_error!))
              : (_activities.isEmpty && _activeJobs.isEmpty)
                  ? _buildEmptyState(colorScheme)
                  : RefreshIndicator(
                      onRefresh: _loadAll,
                      child: _buildBody(colorScheme),
                    ),
    );
  }

  Widget _buildEmptyState(ColorScheme colorScheme) {
    final textTheme = Theme.of(context).textTheme;
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.check_circle_outline,
            size: 64,
            color: colorScheme.onSurfaceVariant.withValues(alpha: 0.5),
          ),
          const SizedBox(height: 16),
          Text(
            'All caught up!',
            style: textTheme.titleMedium?.copyWith(
              color: colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'No new activity',
            style: textTheme.bodyMedium?.copyWith(
              color: colorScheme.onSurfaceVariant.withValues(alpha: 0.7),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBody(ColorScheme colorScheme) {
    final textTheme = Theme.of(context).textTheme;
    final groups = _groupByDay();

    return ListView(
      padding: const EdgeInsets.only(bottom: 16),
      children: [
        // Active imports section
        if (_activeJobs.isNotEmpty) ...[
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
            child: Text(
              'Active Imports',
              style: textTheme.labelLarge?.copyWith(
                color: colorScheme.tertiary,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          ..._activeJobs.map((job) => _buildActiveJobTile(job, colorScheme, textTheme)),
          const Divider(height: 24),
        ],

        // Day-grouped activities
        ...groups.entries.map((entry) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
                child: Text(
                  entry.key,
                  style: textTheme.labelLarge?.copyWith(
                    color: colorScheme.onSurfaceVariant,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              ...entry.value.map((a) => _buildActivityTile(a, colorScheme, textTheme)),
            ],
          );
        }),
      ],
    );
  }

  Widget _buildActiveJobTile(
    dynamic job,
    ColorScheme colorScheme,
    TextTheme textTheme,
  ) {
    final status = job['status'] as String?;
    final sourceType = job['source_type'] as String?;
    final jobId = job['id']?.toString() ?? '';
    final statusColor = _colorForJobStatus(status, colorScheme);
    final total = job['total_items'] as int? ?? 0;
    final succeeded = job['succeeded_items'] as int? ?? 0;
    final pendingReview = job['pending_review_items'] as int? ?? 0;

    String subtitle;
    if (status == 'awaiting_review') {
      subtitle = '$pendingReview item${pendingReview == 1 ? '' : 's'} to review';
    } else {
      subtitle = '$succeeded / $total processed';
    }

    return ListTile(
      leading: CircleAvatar(
        backgroundColor: statusColor.withValues(alpha: 0.12),
        child: Icon(
          _iconForSourceType(sourceType),
          size: 20,
          color: statusColor,
        ),
      ),
      title: Text(
        _labelForJobStatus(status),
        style: textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600),
      ),
      subtitle: Text(
        subtitle,
        style: textTheme.bodySmall?.copyWith(
          color: colorScheme.onSurfaceVariant,
        ),
      ),
      trailing: const Icon(Icons.chevron_right),
      onTap: () => context.push('/recipes/import/review-list/$jobId'),
    );
  }

  Widget _buildActivityTile(
    dynamic activity,
    ColorScheme colorScheme,
    TextTheme textTheme,
  ) {
    final isUnread = activity['read'] != true;
    final type = activity['type']?.toString();

    return ListTile(
      leading: CircleAvatar(
        backgroundColor: isUnread
            ? colorScheme.primaryContainer
            : colorScheme.surfaceContainerHighest,
        child: Icon(
          _iconForType(type),
          size: 20,
          color: isUnread ? colorScheme.primary : colorScheme.onSurfaceVariant,
        ),
      ),
      title: Text(
        activity['title'] ?? '',
        style: textTheme.bodyMedium?.copyWith(
          fontWeight: isUnread ? FontWeight.w600 : FontWeight.normal,
        ),
      ),
      subtitle: activity['subtitle'] != null
          ? Text(
              activity['subtitle'],
              style: textTheme.bodySmall?.copyWith(
                color: colorScheme.onSurfaceVariant,
              ),
            )
          : null,
      trailing: isUnread
          ? Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(
                color: colorScheme.primary,
                shape: BoxShape.circle,
              ),
            )
          : null,
      onTap: () => _onActivityTap(activity),
    );
  }
}
