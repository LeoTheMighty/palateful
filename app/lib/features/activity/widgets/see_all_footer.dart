import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';
import '../../../core/theme/app_colors.dart';
import '../providers/activity_archive_provider.dart';
import '../providers/imports_see_all_provider.dart';
import '../providers/see_all_count_provider.dart';
import 'import_row.dart';

/// Imports-tab See-all footer. afh-4 swapped the ahr-5-era one-shot
/// `onLoad` callback for cursor-paginated fetches via
/// [importsSeeAllProvider] + [importsSeeAllCountProvider], with retry-
/// on-failure parity with `NotificationsSeeAllFooter` (afh-3).
///
/// Consumes [AppColors.mutedOnSurface] exclusively — no raw
/// `withOpacity(0.65)` in this file (afh-4 AC7).
///
/// Rows render inline as Column children; the ancestor ListView in
/// `ImportsTab` handles virtualization. Scroll position persistence
/// (afh-4 AC6) lives on that ancestor's PageStorageKey.
class SeeAllFooter extends ConsumerStatefulWidget {
  const SeeAllFooter({super.key});

  @override
  ConsumerState<SeeAllFooter> createState() => _SeeAllFooterState();
}

class _SeeAllFooterState extends ConsumerState<SeeAllFooter> {
  /// See afh-3 footer for the design rationale — we bind to the
  /// nearest ancestor Scrollable and react to its scroll notifications
  /// rather than owning our own ScrollController, so we don't nest
  /// scrollables inside ImportsTab's outer ListView.
  ScrollPosition? _ancestorScrollPosition;

  /// Per-id nonce for the `Dismissible` key so a re-inserted row after
  /// an undo gets a fresh `_dismissed = false` state.
  final Map<String, int> _restoreNonce = {};

  late final ApiClient _apiClient = getIt<ApiClient>();

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final pos = Scrollable.maybeOf(context)?.position;
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
    if (!ref.read(importsSeeAllExpandedProvider)) return;
    final s = ref.read(importsSeeAllProvider);
    if (s.isLoading || s.hasError || s.nextJobCursor == null) return;
    ref.read(importsSeeAllProvider.notifier).loadNextPage();
  }

  Future<void> _toggleExpand() async {
    final expanded = ref.read(importsSeeAllExpandedProvider);
    ref.read(importsSeeAllExpandedProvider.notifier).setExpanded(!expanded);
    if (!expanded) {
      final s = ref.read(importsSeeAllProvider);
      if (!s.hasLoadedFirstPage && !s.isLoading) {
        await ref.read(importsSeeAllProvider.notifier).loadNextPage();
      }
    }
  }

  Future<void> _unarchive(SeeAllImportItemView row) async {
    if (!mounted) return;
    final id = row.id;
    ref.read(importItemArchiveProvider.notifier).remove(id);
    ref.read(importsSeeAllProvider.notifier).removeRow(id);

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
      await _apiClient.unarchiveImportItem(id);
      if (mounted) {
        await ref.read(importsSeeAllCountProvider.notifier).refresh();
      }
    } catch (_) {
      if (!mounted) return;
      ref.read(importItemArchiveProvider.notifier).add(id);
      setState(() {
        _restoreNonce[id] = (_restoreNonce[id] ?? 0) + 1;
      });
      ref.read(importsSeeAllProvider.notifier).restoreRow(row);
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

  Future<void> _undoUnarchive(SeeAllImportItemView row) async {
    if (!mounted) return;
    final id = row.id;
    setState(() {
      _restoreNonce[id] = (_restoreNonce[id] ?? 0) + 1;
    });
    ref.read(importsSeeAllProvider.notifier).restoreRow(row);
    try {
      await _apiClient.archiveImportItem(id);
      if (mounted) {
        await ref.read(importsSeeAllCountProvider.notifier).refresh();
      }
    } catch (_) {
      // Silent — the next count poll reconciles.
    }
  }

  void _retryFailedPage() {
    ref.read(importsSeeAllProvider.notifier).loadNextPage();
  }

  @override
  Widget build(BuildContext context) {
    final countAsync = ref.watch(importsSeeAllCountProvider);
    final count = countAsync.maybeWhen(
      data: (triple) => triple.total,
      orElse: () => 0,
    );
    if (count == 0) return const SizedBox.shrink();

    final expanded = ref.watch(importsSeeAllExpandedProvider);
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
              Icon(Icons.inbox_outlined, size: 18, color: mutedColor),
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
          if (expanded)
            _buildExpandedBody(mutedColor, colorScheme, textTheme),
        ],
      ),
    );
  }

  Widget _buildExpandedBody(
    Color mutedColor,
    ColorScheme colorScheme,
    TextTheme textTheme,
  ) {
    final state = ref.watch(importsSeeAllProvider);
    final locallyArchived = ref.watch(importItemArchiveProvider);

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

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final row in visible)
          _buildMutedSwipeRow(row, mutedColor, colorScheme),
        ...trailing,
      ],
    );
  }

  Widget _buildMutedSwipeRow(
    SeeAllImportItemView row,
    Color mutedColor,
    ColorScheme colorScheme,
  ) {
    final nonce = _restoreNonce[row.id] ?? 0;
    return Dismissible(
      key: ValueKey('see-all-${row.id}-$nonce'),
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
          child: ImportRow(
            id: row.id,
            sourceIcon: _iconForSourceType(row.sourceType),
            title: row.title,
            statusLabel: row.statusLabel,
            stateColor: mutedColor,
            stateChipLabel: null,
            timeLabel: _formatTime(row.archivedAt ?? row.createdAt),
            trailing:
                Icon(Icons.chevron_right, size: 20, color: mutedColor),
          ),
        ),
      ),
    );
  }

  static IconData _iconForSourceType(String? sourceType) {
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

  static String _formatTime(DateTime? date) {
    if (date == null) return '';
    final local = date.toLocal();
    final now = DateTime.now();
    final diff = now.difference(local);
    if (diff.inMinutes < 1) return 'just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    if (diff.inDays < 7) return '${diff.inDays}d ago';
    return '${local.month}/${local.day}/${local.year}';
  }
}

/// Tap-to-retry row rendered when a page fetch fails. Re-fires the
/// same cursor so the user doesn't lose their spot.
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
