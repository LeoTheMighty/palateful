import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import 'import_history_screen.dart';
import 'providers/activity_read_provider.dart';
import 'providers/activity_tab_provider.dart';

/// Activity Hub shell — two top-of-screen tabs (Notifications | Imports)
/// on a single `/activity` route.
///
/// Story ahr-2: this file owns the tab strip + tab controller sync with
/// [activityTabProvider] + mark-all-read action + the bottom-nav badge
/// formula. The individual tab bodies are:
///  - Notifications → [_NotificationsTabBody] below (to be replaced by
///    the richer body in ahr-3).
///  - Imports → the legacy `ImportHistoryScreen` body rendered in-place
///    for now (ahr-4 replaces this with the color-sectioned layout).
///
/// Deep-link schema:
///  - `/activity?tab=<notifications|imports>` — canonical.
///  - `/activity?filter=imports` — legacy; router redirects to
///    `?tab=imports` for one release (ahr-7 retires).
class ActivityScreen extends ConsumerStatefulWidget {
  final String? initialTab;

  const ActivityScreen({super.key, this.initialTab});

  @override
  ConsumerState<ActivityScreen> createState() => _ActivityScreenState();
}

class _ActivityScreenState extends ConsumerState<ActivityScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController;
  bool _syncingFromController = false;

  @override
  void initState() {
    super.initState();
    // Seed the provider from the route's `?tab=` on mount — the router
    // is the source of truth for the first frame; subsequent tab
    // switches flow provider → controller (and vice versa).
    final initial = ActivityTab.fromWire(widget.initialTab);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      if (ref.read(activityTabProvider) != initial) {
        ref.read(activityTabProvider.notifier).setTab(initial);
      }
    });

    _tabController = TabController(
      length: ActivityTab.values.length,
      vsync: this,
      initialIndex: initial.index,
    );
    _tabController.addListener(_onControllerChange);
  }

  @override
  void dispose() {
    _tabController.removeListener(_onControllerChange);
    _tabController.dispose();
    super.dispose();
  }

  void _onControllerChange() {
    // Tab transitions fire twice — during the drag and when the new
    // index settles. Only write on the settle to avoid thrashing the
    // provider mid-swipe.
    if (_tabController.indexIsChanging) return;
    if (_syncingFromController) return;
    final next = ActivityTab.values[_tabController.index];
    if (ref.read(activityTabProvider) != next) {
      _syncingFromController = true;
      ref.read(activityTabProvider.notifier).setTab(next);
      _syncingFromController = false;
    }
  }

  void _syncControllerFromProvider(ActivityTab tab) {
    if (_tabController.index != tab.index) {
      _tabController.animateTo(tab.index);
    }
  }

  @override
  Widget build(BuildContext context) {
    // Keep the TabController following the provider so external sources
    // (deep-link, push notification) can drive the selection.
    ref.listen<ActivityTab>(activityTabProvider, (prev, next) {
      _syncControllerFromProvider(next);
    });

    return Scaffold(
      appBar: AppBar(
        title: const Text('Activity'),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: 'Notifications'),
            Tab(text: 'Imports'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: const [
          _NotificationsTabBody(),
          _ImportsTabBody(),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Notifications tab body — preserves the existing chronological feed.
// ahr-3 replaces this with a Dismissible-wrapped version with per-row
// swipe-to-archive + 3s undo snackbar.
// ---------------------------------------------------------------------------

class _NotificationsTabBody extends StatefulWidget {
  const _NotificationsTabBody();

  @override
  State<_NotificationsTabBody> createState() => _NotificationsTabBodyState();
}

class _NotificationsTabBodyState extends State<_NotificationsTabBody>
    with AutomaticKeepAliveClientMixin {
  final _apiClient = getIt<ApiClient>();
  final _readProvider = getIt<ActivityReadProvider>();

  List<dynamic> _activities = [];
  bool _isLoading = true;
  String? _error;
  Timer? _pollTimer;

  /// Activity types that belong on the Imports tab, not here.
  static const _importActivityTypes = {
    'import_started',
    'import_complete',
    'import_needs_review',
    'import_extracting',
    'import_item_complete',
    'import_failed',
  };

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _load();
    _pollTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      _load(silent: true);
    });
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  Future<void> _load({bool silent = false}) async {
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
      final filtered = all
          .where((a) => !_importActivityTypes.contains(a['type']?.toString()))
          .toList();

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
    } catch (_) {
      if (!mounted) return;
      if (!silent) {
        setState(() {
          _error = 'Failed to load activities';
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _onActivityTap(dynamic activity) async {
    final id = activity['id']?.toString();
    final actionUrl = activity['action_url'] as String?;
    if (id != null && activity['read'] != true) {
      setState(() => activity['read'] = true);
      _readProvider.markIdsRead([id]).then((_) {
        if (mounted) _readProvider.refreshUnreadCount();
      });
    }
    if (actionUrl != null && actionUrl.isNotEmpty && mounted) {
      context.push(actionUrl);
    }
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
    super.build(context);
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    if (_isLoading) return const Center(child: CircularProgressIndicator());
    if (_error != null) return Center(child: Text(_error!));

    if (_activities.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.only(top: 120),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.check_circle_outline,
                  size: 64,
                  color: colorScheme.onSurfaceVariant.withValues(alpha: 0.5)),
              const SizedBox(height: 16),
              Text("You're all caught up",
                  style: textTheme.titleMedium
                      ?.copyWith(color: colorScheme.onSurfaceVariant)),
            ],
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.builder(
        padding: const EdgeInsets.only(bottom: 16),
        itemCount: _activities.length,
        itemBuilder: (context, i) {
          final a = _activities[i];
          final isUnread = a['read'] != true;
          final type = a['type']?.toString();
          return ListTile(
            leading: CircleAvatar(
              backgroundColor: isUnread
                  ? colorScheme.primaryContainer
                  : colorScheme.surfaceContainerHighest,
              child: Icon(
                _iconForType(type),
                size: 20,
                color: isUnread
                    ? colorScheme.primary
                    : colorScheme.onSurfaceVariant,
              ),
            ),
            title: Text(
              a['title'] ?? '',
              style: textTheme.bodyMedium?.copyWith(
                fontWeight: isUnread ? FontWeight.w600 : FontWeight.normal,
              ),
            ),
            subtitle: a['subtitle'] != null
                ? Text(a['subtitle'],
                    style: textTheme.bodySmall
                        ?.copyWith(color: colorScheme.onSurfaceVariant))
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
            onTap: () => _onActivityTap(a),
          );
        },
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Imports tab body — ahr-2 delegates to the legacy [ImportHistoryScreen]
// body so Leo still sees his imports. ahr-4 replaces this with the
// color-sectioned layout (In Progress / Needs Review / Failed /
// Auto-Imported) + swipe-to-archive + see-all footer.
// ---------------------------------------------------------------------------

class _ImportsTabBody extends StatelessWidget {
  const _ImportsTabBody();

  @override
  Widget build(BuildContext context) {
    // Render the existing screen content without its own Scaffold/AppBar.
    return const ImportHistoryScreen(embedded: true);
  }
}
