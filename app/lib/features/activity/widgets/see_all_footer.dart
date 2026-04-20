import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';
import '../../../core/theme/app_colors.dart';
import '../providers/activity_archive_provider.dart';
import 'import_row.dart';

/// Immutable view-model for a See-all row. Built once per fetch from
/// the raw `{jobs, items}` payload so the row widget doesn't reach
/// back into loosely-typed maps.
class SeeAllItemView {
  final String id;
  final String title;
  final String? sourceType;
  final String? statusLabel;
  final DateTime? archivedAt;
  final DateTime? createdAt;

  const SeeAllItemView({
    required this.id,
    required this.title,
    required this.sourceType,
    required this.statusLabel,
    required this.archivedAt,
    required this.createdAt,
  });
}

/// Collapsible footer for the bottom of the Imports tab. Surfaces
/// archived imports + items older than 30 days in muted typography.
/// Swipe-right on any row unarchives it (symmetric with the main
/// sections' swipe-left to archive).
class SeeAllFooter extends ConsumerStatefulWidget {
  /// Explicit count passed by the parent — computed from the parent's
  /// own poll results so we don't duplicate network work. When 0, the
  /// footer renders as `SizedBox.shrink()`.
  final int count;

  /// Resolver invoked on first expand. Returns the rows the footer
  /// should render. The parent owns the fetch; we just ask for them
  /// lazily.
  final Future<List<SeeAllItemView>> Function() onLoad;

  const SeeAllFooter({
    super.key,
    required this.count,
    required this.onLoad,
  });

  @override
  ConsumerState<SeeAllFooter> createState() => _SeeAllFooterState();
}

class _SeeAllFooterState extends ConsumerState<SeeAllFooter> {
  bool _expanded = false;
  bool _loading = false;
  List<SeeAllItemView>? _rows;

  /// Per-id nonce — bumped each time an unarchive is undone so a
  /// re-inserted Dismissible gets a fresh `_dismissed = false`.
  final Map<String, int> _restoreNonce = {};

  late final ApiClient _apiClient = getIt<ApiClient>();

  Future<void> _toggle() async {
    if (_expanded) {
      setState(() => _expanded = false);
      return;
    }

    setState(() => _expanded = true);
    if (_rows != null) return;

    setState(() => _loading = true);
    try {
      final rows = await widget.onLoad();
      if (!mounted) return;
      setState(() {
        _rows = rows;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _rows = const [];
        _loading = false;
      });
    }
  }

  Future<void> _unarchive(SeeAllItemView row) async {
    if (!mounted) return;
    final id = row.id;
    // Optimistic: drop from the local archive set so the main
    // sections can re-claim it on the next poll, and hide from
    // See-all immediately.
    ref.read(importItemArchiveProvider.notifier).remove(id);
    setState(() {
      _rows = (_rows ?? const [])
          .where((r) => r.id != id)
          .toList(growable: false);
    });

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
    } catch (_) {
      if (!mounted) return;
      // Re-add to the archive set and restore the row in See-all.
      ref.read(importItemArchiveProvider.notifier).add(id);
      setState(() {
        _restoreNonce[id] = (_restoreNonce[id] ?? 0) + 1;
        _rows = [...(_rows ?? const []), row];
      });
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

  Future<void> _undoUnarchive(SeeAllItemView row) async {
    if (!mounted) return;
    final id = row.id;
    // Put it back in the session archive set + restore the row here.
    ref.read(importItemArchiveProvider.notifier).add(id);
    setState(() {
      _restoreNonce[id] = (_restoreNonce[id] ?? 0) + 1;
      _rows = [...(_rows ?? const []), row];
    });
    try {
      await _apiClient.archiveImportItem(id);
    } catch (_) {
      // Silent — the next poll will reconcile.
    }
  }

  @override
  Widget build(BuildContext context) {
    if (widget.count == 0) return const SizedBox.shrink();

    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final mutedColor = AppColors.mutedOnSurface(colorScheme);

    final toggle = InkWell(
      onTap: _toggle,
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
                  'See all (${widget.count})',
                  style: textTheme.bodyMedium?.copyWith(
                    color: mutedColor,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
              Icon(
                _expanded ? Icons.expand_less : Icons.expand_more,
                size: 20,
                color: mutedColor,
              ),
            ],
          ),
        ),
      ),
    );

    final children = <Widget>[toggle];
    if (_expanded) {
      if (_loading) {
        children.add(const Padding(
          padding: EdgeInsets.all(16),
          child: Center(
            child: SizedBox(
              width: 18,
              height: 18,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
          ),
        ));
      } else if (_rows != null && _rows!.isNotEmpty) {
        for (final row in _rows!) {
          children.add(_buildMutedSwipeRow(row, mutedColor));
        }
      }
    }

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
          ...children,
        ],
      ),
    );
  }

  Widget _buildMutedSwipeRow(SeeAllItemView row, Color mutedColor) {
    final colorScheme = Theme.of(context).colorScheme;
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
