import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';

/// import-dup-3 — "you already have this" banner shown above the Approve-
/// Import form when the backend's `duplicate.matches` block on
/// `GET /v1/import-items/{id}` returned at least one match.
///
/// Three variants by `match.archived_at`:
///  - **Active** (archived_at = null) → blue. Buttons: Skip / Add anyway.
///  - **Archived** (archived_at != null) → amber. Buttons: Restore / Skip /
///    Add anyway.
///  - **Multi-match** (otherMatchCount > 0) → primary match shown plus a
///    "Show all matches" button that the parent expands into a sheet.
///
/// The widget is purely presentational: no async state, no DB calls, no
/// router knowledge. Action buttons fire the callbacks the parent passes
/// in. Keeps the widget testable in isolation and lets the parent layer
/// in loading-spinner / disabled-state semantics for whichever button is
/// currently in flight.
class DuplicateBanner extends StatefulWidget {
  const DuplicateBanner({
    super.key,
    required this.match,
    required this.onSkip,
    required this.onAddAnyway,
    required this.onTapMatch,
    this.onRestore,
    this.onShowAll,
    this.otherMatchCount = 0,
    this.isProcessing = false,
  });

  /// The primary match (first entry from `duplicate.matches`).
  /// Required keys: `recipe_id`, `title`, `current_book_name`,
  /// `archived_at` (nullable), `last_cooked` (nullable, ISO8601 string).
  final Map<String, dynamic> match;

  /// User taps "Skip". Parent calls the skip endpoint and bounces the
  /// user back to the import-activity list.
  final VoidCallback onSkip;

  /// User taps "Restore". Only invoked when the match is archived;
  /// parent calls `restoreRecipe` then skips the import item.
  /// REQUIRED when `match.archived_at != null` (asserted in build).
  final VoidCallback? onRestore;

  /// User taps "Add anyway". Parent dismisses the banner and lets the
  /// existing Approve flow proceed (creates a new Recipe row).
  final VoidCallback onAddAnyway;

  /// User taps the matched recipe's name. Parent deep-links to
  /// `/recipes/{recipe_id}` and closes the import flow.
  final VoidCallback onTapMatch;

  /// Multi-match: how many ADDITIONAL matches exist beyond the primary.
  /// 0 = single match, no "Show all" button. >0 = show count and button.
  final int otherMatchCount;

  /// Optional callback for "Show all matches". Required when
  /// `otherMatchCount > 0`; ignored otherwise.
  final VoidCallback? onShowAll;

  /// True while a parent-side network call is in flight. Disables all
  /// action buttons so the user can't double-fire (e.g. tap Skip twice
  /// while the first request is still pending). Tap-on-match-name still
  /// works — that's a navigation, not a mutation.
  final bool isProcessing;

  @override
  State<DuplicateBanner> createState() => _DuplicateBannerState();
}

class _DuplicateBannerState extends State<DuplicateBanner> {
  late final TapGestureRecognizer _tapRecognizer;

  @override
  void initState() {
    super.initState();
    _tapRecognizer = TapGestureRecognizer()..onTap = widget.onTapMatch;
  }

  @override
  void didUpdateWidget(covariant DuplicateBanner oldWidget) {
    super.didUpdateWidget(oldWidget);
    // Re-bind onTap if the parent rebuilt with a new callback identity
    // (rare, but cheap to be correct here).
    _tapRecognizer.onTap = widget.onTapMatch;
  }

  @override
  void dispose() {
    _tapRecognizer.dispose();
    super.dispose();
  }

  bool get _isArchived => widget.match['archived_at'] != null;

  @override
  Widget build(BuildContext context) {
    assert(
      !_isArchived || widget.onRestore != null,
      'DuplicateBanner: archived match requires onRestore callback',
    );
    assert(
      widget.otherMatchCount == 0 || widget.onShowAll != null,
      'DuplicateBanner: multi-match requires onShowAll callback',
    );

    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    // Color-coding by state. Blue = active (informational); amber =
    // archived (the user previously rejected this — flag harder).
    // Both colors are derived from the theme so dark mode + custom
    // palettes work without hard-coded hex values.
    final (bg, fg, accent) = _isArchived
        ? (
            colorScheme.tertiaryContainer,
            colorScheme.onTertiaryContainer,
            colorScheme.tertiary,
          )
        : (
            colorScheme.primaryContainer,
            colorScheme.onPrimaryContainer,
            colorScheme.primary,
          );

    return Container(
      key: const Key('duplicate_banner'),
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: accent.withValues(alpha: 0.4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(
                _isArchived ? Icons.history : Icons.menu_book_outlined,
                size: 20,
                color: fg,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _buildHeadline(context, fg, textTheme),
              ),
            ],
          ),
          if (widget.otherMatchCount > 0) ...[
            const SizedBox(height: 4),
            Padding(
              padding: const EdgeInsets.only(left: 28),
              child: TextButton(
                key: const Key('duplicate_banner_show_all'),
                onPressed: widget.isProcessing ? null : widget.onShowAll,
                style: TextButton.styleFrom(
                  padding: EdgeInsets.zero,
                  minimumSize: const Size(0, 32),
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  foregroundColor: accent,
                ),
                child: Text(
                  '+ ${widget.otherMatchCount} more match'
                  '${widget.otherMatchCount == 1 ? '' : 'es'} — show all',
                ),
              ),
            ),
          ],
          const SizedBox(height: 8),
          _buildActions(context, fg, accent),
        ],
      ),
    );
  }

  Widget _buildHeadline(BuildContext context, Color fg, TextTheme textTheme) {
    final title = (widget.match['title'] as String?) ?? 'Existing recipe';
    final bookName = (widget.match['current_book_name'] as String?) ?? '';
    final archivedAt = widget.match['archived_at'] as String?;
    final lastCooked = widget.match['last_cooked'] as String?;

    final headlineStyle = textTheme.bodyMedium?.copyWith(
      color: fg,
      height: 1.4,
    );
    final boldStyle = headlineStyle?.copyWith(
      fontWeight: FontWeight.w600,
      decoration: TextDecoration.underline,
    );

    if (_isArchived) {
      // "You archived **<title>** on 2024-03-12."
      final dateStr = _formatArchivedDate(archivedAt);
      return Text.rich(
        TextSpan(
          style: headlineStyle,
          children: [
            const TextSpan(text: 'You archived '),
            TextSpan(
              text: title,
              style: boldStyle,
              recognizer: _tapRecognizer,
            ),
            TextSpan(text: ' on $dateStr.'),
          ],
        ),
      );
    }

    // "You already have **<title>** — currently in **<book>**, last cooked X."
    final lastCookedFragment = _formatLastCookedFragment(lastCooked);
    return Text.rich(
      TextSpan(
        style: headlineStyle,
        children: [
          const TextSpan(text: 'You already have '),
          TextSpan(
            text: title,
            style: boldStyle,
            recognizer: _tapRecognizer,
          ),
          if (bookName.isNotEmpty) ...[
            const TextSpan(text: ' — currently in '),
            TextSpan(
              text: bookName,
              style: headlineStyle?.copyWith(fontWeight: FontWeight.w600),
            ),
          ],
          if (lastCookedFragment != null) TextSpan(text: lastCookedFragment),
          const TextSpan(text: '.'),
        ],
      ),
    );
  }

  Widget _buildActions(BuildContext context, Color fg, Color accent) {
    final buttons = <Widget>[];

    if (_isArchived) {
      // Archived → Restore (primary), Skip, Add anyway.
      buttons.addAll([
        FilledButton(
          key: const Key('duplicate_banner_restore'),
          onPressed: widget.isProcessing ? null : widget.onRestore,
          style: FilledButton.styleFrom(
            backgroundColor: accent,
            foregroundColor: Theme.of(context).colorScheme.onPrimary,
          ),
          child: const Text('Restore'),
        ),
        TextButton(
          key: const Key('duplicate_banner_skip'),
          onPressed: widget.isProcessing ? null : widget.onSkip,
          style: TextButton.styleFrom(foregroundColor: fg),
          child: const Text('Skip'),
        ),
      ]);
    } else {
      // Active → Skip (primary), Add anyway.
      buttons.add(FilledButton(
        key: const Key('duplicate_banner_skip'),
        onPressed: widget.isProcessing ? null : widget.onSkip,
        style: FilledButton.styleFrom(
          backgroundColor: accent,
          foregroundColor: Theme.of(context).colorScheme.onPrimary,
        ),
        child: const Text('Skip'),
      ));
    }

    buttons.add(TextButton(
      key: const Key('duplicate_banner_add_anyway'),
      onPressed: widget.isProcessing ? null : widget.onAddAnyway,
      style: TextButton.styleFrom(foregroundColor: fg),
      child: const Text('Add anyway'),
    ));

    return Wrap(
      spacing: 8,
      runSpacing: 4,
      children: buttons,
    );
  }

  static String _formatArchivedDate(String? iso) {
    if (iso == null) return 'an earlier date';
    try {
      final dt = DateTime.parse(iso).toLocal();
      // Match the YYYY-MM-DD form the epic copy uses.
      return '${dt.year.toString().padLeft(4, '0')}-'
          '${dt.month.toString().padLeft(2, '0')}-'
          '${dt.day.toString().padLeft(2, '0')}';
    } catch (_) {
      return 'an earlier date';
    }
  }

  /// Returns ` — last cooked X` or null when last_cooked is missing.
  /// Leading comma+space included so the caller can concatenate
  /// directly without extra punctuation logic.
  static String? _formatLastCookedFragment(String? iso) {
    if (iso == null || iso.isEmpty) return null;
    try {
      final dt = DateTime.parse(iso).toLocal();
      final diff = DateTime.now().difference(dt);
      final relative = _formatRelative(diff);
      return ', last cooked $relative';
    } catch (_) {
      return null;
    }
  }

  static String _formatRelative(Duration diff) {
    if (diff.inMinutes < 1) return 'just now';
    if (diff.inMinutes < 60) {
      final n = diff.inMinutes;
      return '$n minute${n == 1 ? '' : 's'} ago';
    }
    if (diff.inHours < 24) {
      final n = diff.inHours;
      return '$n hour${n == 1 ? '' : 's'} ago';
    }
    if (diff.inDays < 7) {
      final n = diff.inDays;
      return '$n day${n == 1 ? '' : 's'} ago';
    }
    if (diff.inDays < 30) {
      final n = (diff.inDays / 7).floor();
      return '$n week${n == 1 ? '' : 's'} ago';
    }
    if (diff.inDays < 365) {
      final n = (diff.inDays / 30).floor();
      return '$n month${n == 1 ? '' : 's'} ago';
    }
    final n = (diff.inDays / 365).floor();
    return '$n year${n == 1 ? '' : 's'} ago';
  }
}
