import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../core/theme/theme.dart';
import '../../core/services/error_reporter.dart';
import '../../shared/widgets/error_banner.dart';
import 'providers/activity_read_provider.dart';

/// Activity feed screen — shows notifications like invites, partner actions, reminders.
/// Also surfaces high-priority "Needs Review" import items in a collapsed section.
/// Import details live in the dedicated Import Activity screen.
class ActivityScreen extends StatefulWidget {
  const ActivityScreen({super.key});

  @override
  State<ActivityScreen> createState() => _ActivityScreenState();
}

class _ActivityScreenState extends State<ActivityScreen> {
  final _apiClient = getIt<ApiClient>();
  final _readProvider = getIt<ActivityReadProvider>();

  List<dynamic> _activities = [];
  bool _isLoading = true;
  String? _error;
  String? _errorDetail;
  Timer? _pollTimer;

  // Import review data for the "Needs Review" section + badge
  List<dynamic> _reviewJobSummaries = [];
  List<_ReviewJobWithItems> _reviewItems = [];
  int _importActionCount = 0;
  bool _reviewExpanded = false;
  bool _isLoadingReviewItems = false;

  /// Activity types that belong in Import Activity, not here.
  static const _importActivityTypes = {
    'import_started',
    'import_complete',
    'import_needs_review',
    'import_extracting',
    'import_item_complete',
    'import_failed',
  };

  @override
  void initState() {
    super.initState();
    _loadAll();
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
    await Future.wait([
      _loadActivities(silent: silent),
      _loadImportSummary(),
    ]);
  }

  Future<void> _loadActivities({bool silent = false}) async {
    if (!silent) {
      setState(() {
        _isLoading = true;
        _error = null;
      });
    }

    try {
      final response = await _apiClient.getActivities();
      if (!mounted) return;

      final all = List<dynamic>.from(response.data['items'] ?? []);
      // Filter out import-related activities — those live in Import Activity
      final filtered = all
          .where((a) => !_importActivityTypes.contains(a['type']?.toString()))
          .toList();

      // Tab-open marks all currently-loaded items read. No viewport
      // tracking — locked design decision: every loaded item is acknowledged
      // when the user opens this surface. Mark-all-as-read remains the
      // safety valve for older unread items that aren't yet paginated in.
      // Flip flags before the first rebuild so the UI goes straight to the
      // read state without a flash-of-unread.
      final idsToMark = <String>[];
      for (final a in filtered) {
        if (a['read'] != true) {
          final id = a['id']?.toString();
          if (id != null) {
            idsToMark.add(id);
            a['read'] = true;
          }
        }
      }

      setState(() {
        _activities = filtered;
        _isLoading = false;
      });

      if (idsToMark.isNotEmpty) {
        _readProvider.setUnreadCount(0);
        _readProvider.markIdsRead(idsToMark).then((_) {
          if (mounted) _readProvider.refreshUnreadCount();
        });
      }
    } catch (e) {
      if (!mounted) return;
      if (!silent) {
        setState(() {
          _error = 'Failed to load activities';
          _errorDetail = ErrorReporter.detail(e);
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _loadImportSummary() async {
    try {
      final results = await Future.wait([
        _apiClient.listImportJobs(status: 'awaiting_review', limit: 50),
        _apiClient.listImportJobs(status: 'failed', limit: 50),
      ]);
      if (!mounted) return;

      // Filter out fully-dismissed jobs — even if the server's cached
      // counters lag, dismissed jobs shouldn't contribute to the badge.
      bool notDismissed(dynamic job) => job['dismissed_at'] == null;
      final reviewJobs = List<dynamic>.from(results[0].data['jobs'] ?? [])
          .where(notDismissed)
          .toList();
      final failedJobs = List<dynamic>.from(results[1].data['jobs'] ?? [])
          .where(notDismissed)
          .toList();

      int reviewCount = 0;
      for (final job in reviewJobs) {
        reviewCount += (job['pending_review_items'] as int? ?? 0);
      }
      int failedCount = 0;
      for (final job in failedJobs) {
        failedCount += (job['failed_items'] as int? ?? 0);
      }

      setState(() {
        _reviewJobSummaries = reviewJobs;
        _importActionCount = reviewCount + failedCount;
        // If review jobs disappeared, reset expanded state
        if (reviewJobs.isEmpty) {
          _reviewExpanded = false;
          _reviewItems = [];
        }
      });
    } catch (_) {}
  }

  Future<void> _loadReviewItems() async {
    if (_reviewJobSummaries.isEmpty) return;
    setState(() => _isLoadingReviewItems = true);

    try {
      final futures = _reviewJobSummaries.map(
        (job) => _apiClient.listImportItems(job['id'].toString()),
      );
      final results = await Future.wait(futures);
      if (!mounted) return;

      final items = <_ReviewJobWithItems>[];
      for (var i = 0; i < _reviewJobSummaries.length; i++) {
        final jobItems = List<dynamic>.from(results[i].data['items'] ?? [])
            .where((item) => item['status'] == 'awaiting_review')
            .toList();
        if (jobItems.isNotEmpty) {
          items.add(_ReviewJobWithItems(
            job: _reviewJobSummaries[i],
            items: jobItems,
          ));
        }
      }

      setState(() {
        _reviewItems = items;
        _isLoadingReviewItems = false;
      });
    } catch (_) {
      if (mounted) setState(() => _isLoadingReviewItems = false);
    }
  }

  Future<void> _onReviewItemTap(String itemId) async {
    final result = await context.push('/recipes/import/review/$itemId');
    if (!mounted) return;
    if (result != null) {
      _loadAll();
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
      _readProvider.setUnreadCount(0);
    } catch (_) {}
  }

  Future<void> _onActivityTap(dynamic activity) async {
    final id = activity['id']?.toString();
    final actionUrl = activity['action_url'] as String?;

    if (id != null && activity['read'] != true) {
      setState(() => activity['read'] = true);
      // Fire-and-forget with retry via provider. The bulk _markLoadedRead
      // will usually have already covered this, but we keep this path so
      // a user who navigates directly to a deep-linked activity still gets
      // the read-flag written without depending on tab-open having run.
      _readProvider.markIdsRead([id]).then((_) {
        if (mounted) _readProvider.refreshUnreadCount();
      });
    }

    if (actionUrl != null && actionUrl.isNotEmpty && mounted) {
      context.push(actionUrl);
    }
  }

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
      case 'partner_action':
        return Icons.people;
      case 'meal_reminder':
        return Icons.restaurant;
      case 'invitation':
        return Icons.mail;
      default:
        return Icons.notifications;
    }
  }

  int get _totalReviewItemCount {
    int count = 0;
    for (final job in _reviewJobSummaries) {
      count += (job['pending_review_items'] as int? ?? 0);
    }
    return count;
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
            icon: Badge(
              label: Text('$_importActionCount'),
              isLabelVisible: _importActionCount > 0,
              child: const Icon(Icons.import_export),
            ),
            tooltip: 'Import Activity',
            onPressed: () async {
              await context.push('/activity/import-history');
              if (mounted) _loadAll();
            },
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
              : RefreshIndicator(
                  onRefresh: _loadAll,
                  child: _buildBody(colorScheme),
                ),
    );
  }

  Widget _buildBody(ColorScheme colorScheme) {
    final textTheme = Theme.of(context).textTheme;
    final groups = _groupByDay();
    final hasReviewItems = _totalReviewItemCount > 0;

    return ListView(
      padding: const EdgeInsets.only(bottom: 16),
      children: [
        // Needs Review collapsed section
        if (hasReviewItems) _buildNeedsReviewSection(colorScheme, textTheme),

        // Regular activity feed
        if (_activities.isEmpty && !hasReviewItems)
          _buildEmptyState(colorScheme)
        else
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
                ...entry.value.map(
                    (a) => _buildActivityTile(a, colorScheme, textTheme)),
              ],
            );
          }),
      ],
    );
  }

  Widget _buildNeedsReviewSection(
      ColorScheme colorScheme, TextTheme textTheme) {
    final appColors = context.appColors;
    final reviewColor = appColors.warning;
    final count = _totalReviewItemCount;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Section header — tappable to expand/collapse
        InkWell(
          onTap: () {
            final willExpand = !_reviewExpanded;
            setState(() => _reviewExpanded = willExpand);
            if (willExpand && _reviewItems.isEmpty) {
              _loadReviewItems();
            }
          },
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
            child: Row(
              children: [
                Icon(Icons.circle, size: 12, color: reviewColor),
                const SizedBox(width: 8),
                Text(
                  'Needs Review',
                  style: textTheme.titleSmall?.copyWith(
                    color: reviewColor,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(width: 8),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: reviewColor.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    '$count',
                    style: textTheme.labelSmall?.copyWith(
                      color: reviewColor,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                const Spacer(),
                Icon(
                  _reviewExpanded ? Icons.expand_less : Icons.expand_more,
                  size: 20,
                  color: colorScheme.onSurfaceVariant,
                ),
              ],
            ),
          ),
        ),

        // Collapsed summary
        if (!_reviewExpanded)
          Padding(
            padding: const EdgeInsets.fromLTRB(36, 0, 16, 8),
            child: Text(
              '$count recipe${count == 1 ? '' : 's'} need${count == 1 ? 's' : ''} your review',
              style: textTheme.bodySmall?.copyWith(
                color: colorScheme.onSurfaceVariant,
              ),
            ),
          ),

        // Expanded items
        if (_reviewExpanded) ...[
          if (_isLoadingReviewItems)
            const Padding(
              padding: EdgeInsets.all(16),
              child: Center(
                child: SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
              ),
            )
          else if (_reviewItems.isEmpty)
            // Counter said "(1)" but the fetch returned nothing — stale
            // server state. Tell the user instead of silently showing an
            // empty expansion so the tap isn't a perceived no-op.
            Padding(
              padding: const EdgeInsets.fromLTRB(36, 0, 16, 12),
              child: Text(
                'All caught up — nothing else to review.',
                style: textTheme.bodySmall?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                ),
              ),
            )
          else
            ..._reviewItems.expand((rj) {
              return rj.items.map((item) {
                final itemId = item['id']?.toString() ?? '';
                final recipeName =
                    item['recipe_name'] as String? ?? 'Untitled';
                return ListTile(
                  dense: true,
                  leading: Icon(Icons.circle, size: 10, color: reviewColor),
                  title: Text(
                    recipeName,
                    style: textTheme.bodyMedium,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  trailing:
                      Icon(Icons.chevron_right, size: 18, color: reviewColor),
                  onTap: () => _onReviewItemTap(itemId),
                );
              });
            }),
        ],

        // Divider after section
        Divider(
          indent: 16,
          endIndent: 16,
          color: colorScheme.outlineVariant,
        ),
      ],
    );
  }

  Widget _buildEmptyState(ColorScheme colorScheme) {
    final textTheme = Theme.of(context).textTheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.only(top: 120),
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
      ),
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

class _ReviewJobWithItems {
  final dynamic job;
  final List<dynamic> items;

  _ReviewJobWithItems({required this.job, required this.items});
}
