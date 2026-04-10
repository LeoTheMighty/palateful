import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';

/// Activity feed screen — shows notifications like invites, partner actions, reminders.
/// Import status lives in the dedicated Import Activity screen.
class ActivityScreen extends StatefulWidget {
  const ActivityScreen({super.key});

  @override
  State<ActivityScreen> createState() => _ActivityScreenState();
}

class _ActivityScreenState extends State<ActivityScreen> {
  final _apiClient = getIt<ApiClient>();

  List<dynamic> _activities = [];
  bool _isLoading = true;
  String? _error;
  Timer? _pollTimer;

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
    _loadActivities();
    _pollTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      _loadActivities(silent: true);
    });
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
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

      setState(() {
        _activities = filtered;
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

    if (id != null && activity['read'] != true) {
      try {
        await _apiClient.markActivityRead(id);
        if (mounted) {
          setState(() => activity['read'] = true);
        }
      } catch (_) {}
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
              : _activities.isEmpty
                  ? _buildEmptyState(colorScheme)
                  : RefreshIndicator(
                      onRefresh: _loadActivities,
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
      children: groups.entries.map((entry) {
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
      }).toList(),
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
