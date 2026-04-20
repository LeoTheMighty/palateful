import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';
import '../../../core/theme/app_colors.dart';
import '../providers/activity_archive_provider.dart';
import '../providers/notifications_see_all_provider.dart';
import '../providers/see_all_count_provider.dart';

/// Collapsible footer that surfaces archived + read-and-older-than-30d
/// user activities in muted type. Mirrors the visual shape of
/// `SeeAllFooter` (Imports) — same tap-to-expand caret, same muted token,
/// same swipe-right-to-unarchive — but talks to a different data source
/// (the paginated `/v1/activities` See-all mode) and is driven by
/// `notificationsSeeAllProvider` + `notificationsSeeAllExpandedProvider`.
class NotificationsSeeAllFooter extends ConsumerStatefulWidget {
  const NotificationsSeeAllFooter({super.key});

  @override
  ConsumerState<NotificationsSeeAllFooter> createState() =>
      _NotificationsSeeAllFooterState();
}

class _NotificationsSeeAllFooterState
    extends ConsumerState<NotificationsSeeAllFooter> {
  /// Per-id nonce for the `Dismissible` key so a re-inserted row
  /// after an undo gets a fresh `_dismissed = false` state. Same
  /// rationale as `NotificationsTab` / existing `SeeAllFooter`.
  final Map<String, int> _restoreNonce = {};

  /// Ancestor scrollable position — the footer doesn't own a
  /// ScrollController (it's laid out inline in the Notifications tab's
  /// outer `ListView`) so we listen to whatever Scrollable is our
  /// parent. Grabs the pointer in `didChangeDependencies` and releases
  /// in `dispose`. `null` is a no-op (test harnesses may render the
  /// footer without an ancestor Scrollable).
  ScrollPosition? _ancestorScrollPosition;

  late final ApiClient _apiClient = getIt<ApiClient>();

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final scrollable = Scrollable.maybeOf(context);
    final pos = scrollable?.position;
    if (pos != _ancestorScrollPosition) {
      _ancestorScrollPosition?.removeListener(_onAncestorScroll);
      _ancestorScrollPosition = pos;
      _ancestorScrollPosition?.addListener(_onAncestorScroll);
    }
  }

  @override
  void dispose() {
    _ancestorScrollPosition?.removeListener(_onAncestorScroll);
    super.dispose();
  }

  void _onAncestorScroll() {
    final pos = _ancestorScrollPosition;
    if (pos == null || !pos.hasContentDimensions) return;
    if (pos.pixels < pos.maxScrollExtent - 200) return;
    final expanded = ref.read(notificationsSeeAllExpandedProvider);
    if (!expanded) return;
    final s = ref.read(notificationsSeeAllProvider);
    if (s.isLoading || s.hasError || s.nextCursor == null) return;
    ref.read(notificationsSeeAllProvider.notifier).loadNextPage();
  }

  Future<void> _toggleExpand() async {
    final expanded = ref.read(notificationsSeeAllExpandedProvider);
    ref
        .read(notificationsSeeAllExpandedProvider.notifier)
        .setExpanded(!expanded);
    if (!expanded) {
      // Just expanded — kick off the first fetch if the list is empty.
      final s = ref.read(notificationsSeeAllProvider);
      if (!s.hasLoadedFirstPage && !s.isLoading) {
        await ref.read(notificationsSeeAllProvider.notifier).loadNextPage();
      }
    }
  }

  Future<void> _unarchive(SeeAllActivityView row) async {
    if (!mounted) return;
    final id = row.id;
    ref.read(activityArchiveProvider.notifier).remove(id);
    ref.read(notificationsSeeAllProvider.notifier).removeRow(id);

    final messenger = ScaffoldMessenger.of(context);
    messenger.hideCurrentSnackBar();
    messenger.showSnackBar(
      SnackBar(
        content: const Text('Unarchived'),
        duration: const Duration(seconds: 3),
        action: SnackBarAction(
          label: 'Undo',
          onPressed: () => _undoUnarchive(row),
        ),
      ),
    );

    try {
      await _apiClient.unarchiveActivity(id);
      // See-all count drops by 1 — refresh the footer label.
      await ref
          .read(notificationsSeeAllCountProvider.notifier)
          .refresh();
    } catch (_) {
      if (!mounted) return;
      ref.read(activityArchiveProvider.notifier).add(id);
      setState(() {
        _restoreNonce[id] = (_restoreNonce[id] ?? 0) + 1;
      });
      ref.read(notificationsSeeAllProvider.notifier).restoreRow(row);
      messenger.hideCurrentSnackBar();
      messenger.showSnackBar(
        SnackBar(
          content: const Text("Couldn't unarchive, try again"),
          backgroundColor: Theme.of(context).colorScheme.error,
          duration: const Duration(seconds: 3),
        ),
      );
    }
  }

  Future<void> _undoUnarchive(SeeAllActivityView row) async {
    if (!mounted) return;
    final id = row.id;
    setState(() {
      _restoreNonce[id] = (_restoreNonce[id] ?? 0) + 1;
    });
    ref.read(notificationsSeeAllProvider.notifier).restoreRow(row);
    try {
      await _apiClient.archiveActivity(id);
      await ref
          .read(notificationsSeeAllCountProvider.notifier)
          .refresh();
    } catch (_) {
      // Silent — the next count poll reconciles.
    }
  }

  void _retryFailedPage() {
    ref.read(notificationsSeeAllProvider.notifier).loadNextPage();
  }

  void _onRowTap(SeeAllActivityView row) {
    final url = row.actionUrl;
    if (url != null && url.isNotEmpty && mounted) {
      context.push(url);
    }
  }

  @override
  Widget build(BuildContext context) {
    final countAsync = ref.watch(notificationsSeeAllCountProvider);
    final count = countAsync.maybeWhen(
      data: (triple) => triple.total,
      orElse: () => 0,
    );
    if (count == 0) return const SizedBox.shrink();

    final expanded = ref.watch(notificationsSeeAllExpandedProvider);
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final mutedColor = AppColors.mutedOnSurface(colorScheme);

    final toggle = InkWell(
      onTap: _toggleExpand,
      child: ConstrainedBox(
        constraints: const BoxConstraints(minHeight: 48),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
          child: Row(
            children: [
              Icon(Icons.history, size: 18, color: mutedColor),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'See all ($count)',
                  style: textTheme.bodyMedium?.copyWith(
                    color: mutedColor,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
              Icon(
                expanded ? Icons.expand_less : Icons.expand_more,
                size: 20,
                color: mutedColor,
              ),
            ],
          ),
        ),
      ),
    );

    return Padding(
      padding: const EdgeInsets.only(top: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Divider(
            color: colorScheme.outlineVariant,
            indent: 48,
            endIndent: 48,
            height: 1,
          ),
          toggle,
          if (expanded) _buildExpandedBody(mutedColor, colorScheme, textTheme),
        ],
      ),
    );
  }

  Widget _buildExpandedBody(
    Color mutedColor,
    ColorScheme colorScheme,
    TextTheme textTheme,
  ) {
    final state = ref.watch(notificationsSeeAllProvider);
    final locallyArchived = ref.watch(activityArchiveProvider);

    // Initial loading — never rendered a page yet.
    if (!state.hasLoadedFirstPage && state.isLoading) {
      return const Padding(
        padding: EdgeInsets.all(16),
        child: Center(
          child: SizedBox(
            width: 18,
            height: 18,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
        ),
      );
    }

    // Filter rows that the user optimistically archived this session —
    // they should stay hidden until the next pull-to-refresh.
    final visible = state.items
        .where((r) => !locallyArchived.contains(r.id))
        .toList(growable: false);

    final trailing = <Widget>[];
    if (state.hasError) {
      trailing.add(_RetryRow(mutedColor: mutedColor, onRetry: _retryFailedPage));
    } else if (state.isLoading && state.hasLoadedFirstPage) {
      trailing.add(const Padding(
        padding: EdgeInsets.symmetric(vertical: 16),
        child: Center(
          child: SizedBox(
            width: 18,
            height: 18,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
        ),
      ));
    } else if (state.isEnded) {
      trailing.add(
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 16),
          child: Text(
            "That's everything. (${visible.length} total)",
            textAlign: TextAlign.center,
            style: textTheme.bodySmall?.copyWith(color: mutedColor),
          ),
        ),
      );
    }

    // Rows render as Column children rather than an inner `ListView` so
    // we don't nest scrollables inside the Notifications tab's own
    // outer ListView. Scroll position persistence (afh-3 AC10.b) is
    // owned by the ancestor `ListView` in `NotificationsTab`, which
    // mounts a `PageStorageKey('notifications-tab-list')` — that key
    // survives tab switches via `AutomaticKeepAliveClientMixin`.
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final row in visible)
          _buildSwipeRow(row, mutedColor, colorScheme),
        ...trailing,
      ],
    );
  }

  Widget _buildSwipeRow(
    SeeAllActivityView row,
    Color mutedColor,
    ColorScheme colorScheme,
  ) {
    final nonce = _restoreNonce[row.id] ?? 0;
    final subtitle = row.subtitle?.trim();
    return Dismissible(
      key: ValueKey('notif-see-all-${row.id}-$nonce'),
      direction: DismissDirection.startToEnd,
      background: Container(
        color: colorScheme.primary,
        alignment: Alignment.centerLeft,
        padding: const EdgeInsets.symmetric(horizontal: 24),
        child: const Icon(Icons.unarchive_outlined, color: Colors.white),
      ),
      onDismissed: (_) => _unarchive(row),
      child: DefaultTextStyle.merge(
        style: TextStyle(color: mutedColor),
        child: IconTheme.merge(
          data: IconThemeData(color: mutedColor),
          child: ListTile(
            leading: Icon(_iconForType(row.type), size: 20, color: mutedColor),
            title: Text(
              row.title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(color: mutedColor),
            ),
            subtitle: subtitle != null && subtitle.isNotEmpty
                ? Text(
                    subtitle,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(color: mutedColor),
                  )
                : null,
            trailing: Text(
              _formatTime(row.archivedAt ?? row.createdAt),
              style: TextStyle(color: mutedColor, fontSize: 12),
            ),
            onTap: () => _onRowTap(row),
          ),
        ),
      ),
    );
  }

  static IconData _iconForType(String type) {
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

  static String _formatTime(DateTime? date) {
    if (date == null) return '';
    final local = date.toLocal();
    final now = DateTime.now();
    final diff = now.difference(local);
    if (diff.inMinutes < 1) return 'just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    if (diff.inDays < 7) return '${diff.inDays}d ago';
    if (diff.inDays < 30) return '${diff.inDays}d ago';
    final months = (diff.inDays / 30).floor();
    if (months < 12) return '${months}mo ago';
    return '${local.month}/${local.day}/${local.year}';
  }
}

/// Tap-to-retry row rendered in place of the spinner when a page fetch
/// has failed. Re-fires the same cursor so the user doesn't lose their
/// spot in the list.
class _RetryRow extends StatelessWidget {
  final Color mutedColor;
  final VoidCallback onRetry;

  const _RetryRow({required this.mutedColor, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return InkWell(
      onTap: onRetry,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 16),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.refresh, size: 16, color: mutedColor),
            const SizedBox(width: 8),
            Text(
              "Couldn't load more. Tap to retry.",
              style: textTheme.bodySmall?.copyWith(color: mutedColor),
            ),
          ],
        ),
      ),
    );
  }
}
