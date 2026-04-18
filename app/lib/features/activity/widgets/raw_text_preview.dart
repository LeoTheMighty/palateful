import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Collapsible "Show extracted text" row used inside
/// [ImportRowExpansion] to surface either OCR output or extracted-recipe
/// JSON (one per stage).
///
/// Collapsed view is a single `TextButton.icon` row. Tapping expands
/// a monospaced `SelectableText` inside a 300px-max-height scrollable
/// container. When the server-side preview was truncated to 4096 chars,
/// a "Truncated" pill renders in the header alongside a Copy button.
class RawTextPreview extends StatefulWidget {
  /// Short label — e.g. "Parsed text (OCR)" or "Extracted recipe JSON".
  final String label;

  /// Raw preview text. Empty / null is rendered as a muted "no preview"
  /// line (the component caller should usually only mount the widget
  /// when the preview is non-empty; this guards against races).
  final String? text;

  /// Server-side truncation flag. Surfaces the "Truncated" pill when
  /// true.
  final bool truncated;

  const RawTextPreview({
    super.key,
    required this.label,
    required this.text,
    this.truncated = false,
  });

  @override
  State<RawTextPreview> createState() => _RawTextPreviewState();
}

class _RawTextPreviewState extends State<RawTextPreview> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final text = widget.text ?? '';
    final hasText = text.trim().isNotEmpty;
    final charCount = text.length;

    if (!hasText) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Text(
          '${widget.label}: no preview yet',
          style: theme.textTheme.bodySmall?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
            fontStyle: FontStyle.italic,
          ),
        ),
      );
    }

    return Semantics(
      container: true,
      label: _expanded
          ? '${widget.label} · $charCount characters'
          : 'Show ${widget.label.toLowerCase()}',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          InkWell(
            onTap: () => setState(() => _expanded = !_expanded),
            borderRadius: BorderRadius.circular(6),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(
                children: [
                  Icon(
                    _expanded ? Icons.expand_less : Icons.expand_more,
                    size: 18,
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                  const SizedBox(width: 4),
                  Text(
                    _expanded
                        ? 'Hide ${widget.label.toLowerCase()}'
                        : 'Show ${widget.label.toLowerCase()}',
                    style: theme.textTheme.labelMedium?.copyWith(
                      color: theme.colorScheme.primary,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  if (widget.truncated) ...[
                    const SizedBox(width: 8),
                    _TruncatedPill(),
                  ],
                ],
              ),
            ),
          ),
          if (_expanded) _Body(text: text, theme: theme),
        ],
      ),
    );
  }
}

class _Body extends StatelessWidget {
  final String text;
  final ThemeData theme;

  const _Body({required this.text, required this.theme});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(top: 6, bottom: 8),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: theme.colorScheme.outlineVariant,
          width: 0.5,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.end,
        mainAxisSize: MainAxisSize.min,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(4, 4, 4, 0),
            child: _CopyButton(text: text),
          ),
          ConstrainedBox(
            constraints: const BoxConstraints(maxHeight: 300),
            child: Scrollbar(
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
                child: SelectableText(
                  text,
                  style: theme.textTheme.bodySmall?.copyWith(
                    fontFamily: 'Menlo',
                    fontFamilyFallback: const [
                      'Courier',
                      'monospace',
                    ],
                    fontSize: 12,
                    height: 1.4,
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _TruncatedPill extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
      decoration: BoxDecoration(
        color: theme.colorScheme.secondaryContainer,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        'Truncated',
        style: theme.textTheme.labelSmall?.copyWith(
          color: theme.colorScheme.onSecondaryContainer,
          fontWeight: FontWeight.w600,
          fontSize: 10,
        ),
      ),
    );
  }
}

class _CopyButton extends StatelessWidget {
  final String text;

  const _CopyButton({required this.text});

  @override
  Widget build(BuildContext context) {
    return IconButton(
      tooltip: 'Copy',
      visualDensity: VisualDensity.compact,
      padding: EdgeInsets.zero,
      constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
      icon: const Icon(Icons.copy, size: 16),
      onPressed: () async {
        await Clipboard.setData(ClipboardData(text: text));
        if (!context.mounted) return;
        ScaffoldMessenger.of(context).hideCurrentSnackBar();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Copied'),
            duration: Duration(seconds: 2),
          ),
        );
      },
    );
  }
}
