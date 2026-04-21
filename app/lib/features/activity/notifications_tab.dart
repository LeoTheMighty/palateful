import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import 'providers/activity_archive_provider.dart';
import 'providers/activity_read_provider.dart';
import 'providers/notifications_see_all_provider.dart';
import 'providers/see_all_count_provider.dart';
import 'widgets/empty_state_gateway_link.dart';
import 'widgets/notifications_see_all_footer.dart';

/// Chronological feed of non-import `user_activity` rows with swipe-to-
/// archive + 3s undo. Replaces the inline Notifications body that
/// ahr-2 shipped in `activity_screen.dart`.
///
/// Surfaces the ahr-1 `POST /v1/activities/{id}/archive` endpoint.
/// Optimistic removal is revert-on-error — the row reappears and an
/// error snackbar fires if the API call fails.
class NotificationsTab extends ConsumerStatefulWidget {
  const NotificationsTab({super.key});

  @override
  ConsumerState<NotificationsTab> createState() => _NotificationsTabState();
}

class _NotificationsTabState extends ConsumerState<NotificationsTab>
    with AutomaticKeepAliveClientMixin {
  final _apiClient = getIt<ApiClient>();
  final _readProvider = getIt<ActivityReadProvider>();

  List<dynamic> _activities = [];
  bool _isLoading = true;
  String? _error;
  VoidCallback? _disposeTickListener;

  /// Per-id monotonic nonce — bumped every time we restore an archived
  /// row. Flutter's [Dismissible] persists its `_dismissed = true` state
  /// via the widget key, so re-inserting the same row would leave it
  /// invisible. Including the nonce in the key forces a fresh State
  /// object on restore.
  final Map<String, int> _restoreNonce = {};

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _load();
    // pfc-1: subscribe to the shared 30s tick. `contributesUnreadCount:
    // true` tells the provider to skip its own `/unread-count` fetch
    // while this tab is mounted — our `_load` path calls
    // `refreshUnreadCount` downstream so the badge stays fresh without
    // the redundant top-level request.
    _disposeTickListener = _readProvider.registerTickListener(
      () => _load(silent: true),
      contributesUnreadCount: true,
    );
  }

  @override
  void dispose() {
    _disposeTickListener?.call();
    _disposeTickListener = null;
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
          .where((a) => !ActivityReadProvider.importActivityTypes
              .contains(a['type']?.toString()))
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

  /// Handle a confirmed swipe — optimistically mark [id] archived in the
  /// session-scoped archive set (which the build() filter honors), fire
  /// the archive API, and show a 3s undo snackbar. On failure, drop the
  /// id from the set (row reappears) and show an error snackbar.
  ///
  /// `_activities` itself is left untouched — it stays the pristine
  /// server mirror and `build()` derives visibility by filtering against
  /// the archive set. This keeps Dismissible key semantics clean: the
  /// widget is removed + re-added through natural list rebuilds rather
  /// than through index splicing, which matters because re-inserting a
  /// Dismissible with a recycled key causes Flutter to reuse the
  /// `_dismissed = true` state.
  Future<void> _archive(dynamic activity) async {
    final id = activity['id']?.toString();
    if (id == null || !mounted) return;

    ref.read(activityArchiveProvider.notifier).add(id);

    final messenger = ScaffoldMessenger.of(context);
    messenger.hideCurrentSnackBar();
    messenger.showSnackBar(
      SnackBar(
        content: const Text('Archived'),
        duration: const Duration(seconds: 3),
        action: SnackBarAction(
          label: 'Undo',
          onPressed: () => _undoArchive(id),
        ),
      ),
    );

    try {
      await _apiClient.archiveActivity(id);
      // See-all count bumps by 1 — refresh the footer label.
      if (mounted) {
        await ref
            .read(notificationsSeeAllCountProvider.notifier)
            .refresh();
      }
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _restoreNonce[id] = (_restoreNonce[id] ?? 0) + 1;
      });
      ref.read(activityArchiveProvider.notifier).remove(id);
      messenger.hideCurrentSnackBar();
      messenger.showSnackBar(
        SnackBar(
          content: const Text("Couldn't archive, try again"),
          backgroundColor: Theme.of(context).colorScheme.error,
          duration: const Duration(seconds: 3),
        ),
      );
    }
  }

  /// Pull-to-refresh: re-fetch active list + see-all count; if See-all
  /// is expanded, reset its cursor and re-fetch page 1 so the footer
  /// shows up-to-date rows.
  Future<void> _refreshAll() async {
    await _load();
    if (!mounted) return;
    await ref.read(notificationsSeeAllCountProvider.notifier).refresh();
    if (!mounted) return;
    if (ref.read(notificationsSeeAllExpandedProvider)) {
      await ref.read(notificationsSeeAllProvider.notifier).refreshFromTop();
    }
  }

  /// afh-5 — tap-handler for the empty-state gateway link. Expands
  /// the See-all footer (which triggers its first-page fetch) AND
  /// scrolls the outer ListView so the footer is visible — the user
  /// shouldn't have to scroll down manually after tapping a link that
  /// promises to open something.
  Future<void> _expandAndScrollToSeeAll() async {
    ref
        .read(notificationsSeeAllExpandedProvider.notifier)
        .setExpanded(true);
    final state = ref.read(notificationsSeeAllProvider);
    if (!state.hasLoadedFirstPage && !state.isLoading) {
      unawaited(
        ref.read(notificationsSeeAllProvider.notifier).loadNextPage(),
      );
    }
    if (!mounted) return;
    // Wait a frame so the expanded rows have a chance to lay out,
    // then animate the outer scroll view to the bottom.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final pos = Scrollable.maybeOf(context)?.position;
      if (pos == null || !pos.hasContentDimensions) return;
      pos.animateTo(
        pos.maxScrollExtent,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOut,
      );
    });
  }

  Future<void> _undoArchive(String id) async {
    if (!mounted) return;
    setState(() {
      _restoreNonce[id] = (_restoreNonce[id] ?? 0) + 1;
    });
    ref.read(activityArchiveProvider.notifier).remove(id);
    // Fire-and-forget — the row is already restored visually. A transient
    // failure just means the next poll will re-hide it, and the user can
    // archive again.
    try {
      await _apiClient.unarchiveActivity(id);
      if (mounted) {
        await ref
            .read(notificationsSeeAllCountProvider.notifier)
            .refresh();
      }
    } catch (_) {
      // Silent — matches the shopping-list undo pattern.
    }
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final locallyArchived = ref.watch(activityArchiveProvider);

    if (_isLoading) return const Center(child: CircularProgressIndicator());
    if (_error != null) return Center(child: Text(_error!));

    // Hide any rows that the local session has already archived — guards
    // against a slow poll returning a just-swiped row.
    final visible = _activities
        .where((a) => !locallyArchived.contains(a['id']?.toString()))
        .toList();

    if (visible.isEmpty) {
      final countAsync = ref.watch(notificationsSeeAllCountProvider);
      final historyCount = countAsync.maybeWhen(
        data: (t) => t.total,
        orElse: () => 0,
      );
      return RefreshIndicator(
        onRefresh: _refreshAll,
        child: ListView(
          key: const PageStorageKey<String>('notifications-tab-empty-list'),
          children: [
            Padding(
              padding: const EdgeInsets.only(top: 120),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.check_circle_outline,
                      size: 64,
                      color: colorScheme.onSurfaceVariant
                          .withValues(alpha: 0.5)),
                  const SizedBox(height: 16),
                  Text("You're all caught up",
                      style: textTheme.titleMedium
                          ?.copyWith(color: colorScheme.onSurfaceVariant)),
                  // afh-5 — inline "See past notifications (N)" gateway
                  // whenever lifetime history exists. Tapping expands
                  // the See-all footer below AND auto-scrolls it into
                  // view.
                  EmptyStateGatewayLink(
                    count: historyCount,
                    label: 'See past notifications',
                    onTap: _expandAndScrollToSeeAll,
                  ),
                ],
              ),
            ),
            // See-all is still reachable even when the active list is
            // empty — archived + >30d-read history lives here.
            const NotificationsSeeAllFooter(),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _refreshAll,
      child: ListView.builder(
        // afh-3 AC10.b — scroll offset persists across tab switches
        // (PageStorageBucket lookup key). `AutomaticKeepAliveClientMixin`
        // holds the widget tree alive; the PageStorageKey keeps the
        // scroll offset even if the widget tree briefly rebuilds.
        key: const PageStorageKey<String>('notifications-tab-list'),
        padding: const EdgeInsets.only(bottom: 16),
        // `+ 1` for the trailing See-all footer. The footer renders as
        // `SizedBox.shrink()` when total == 0 so zero-history users
        // still see a clean list bottom.
        itemCount: visible.length + 1,
        itemBuilder: (context, i) {
          if (i == visible.length) {
            return const NotificationsSeeAllFooter();
          }
          final a = visible[i];
          final id = a['id']?.toString() ?? 'idx-$i';
          final isUnread = a['read'] != true;
          final type = a['type']?.toString();
          final nonce = _restoreNonce[id] ?? 0;
          return Dismissible(
            key: ValueKey('activity-$id-$nonce'),
            direction: DismissDirection.endToStart,
            background: Container(
              color: colorScheme.error,
              alignment: Alignment.centerRight,
              padding: const EdgeInsets.symmetric(horizontal: 24),
              child: const Icon(
                Icons.archive_outlined,
                color: Colors.white,
              ),
            ),
            onDismissed: (_) => _archive(a),
            child: ListTile(
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
            ),
          );
        },
      ),
    );
  }
}
