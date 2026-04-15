import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// A banner that shows a user-friendly error message with an expandable
/// technical detail section for debugging.
class ErrorBanner extends StatefulWidget {
  final String message;
  final String? detail;

  const ErrorBanner({
    super.key,
    required this.message,
    this.detail,
  });

  @override
  State<ErrorBanner> createState() => _ErrorBannerState();
}

class _ErrorBannerState extends State<ErrorBanner> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: colorScheme.errorContainer,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          GestureDetector(
            onTap: widget.detail != null
                ? () => setState(() => _expanded = !_expanded)
                : null,
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    widget.message,
                    style: TextStyle(color: colorScheme.onErrorContainer),
                    textAlign: TextAlign.center,
                  ),
                ),
                if (widget.detail != null)
                  Icon(
                    _expanded ? Icons.expand_less : Icons.expand_more,
                    size: 18,
                    color: colorScheme.onErrorContainer.withValues(alpha: 0.7),
                  ),
              ],
            ),
          ),
          if (_expanded && widget.detail != null) ...[
            const SizedBox(height: 8),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: colorScheme.error.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Stack(
                children: [
                  SelectableText(
                    widget.detail!,
                    style: textTheme.bodySmall?.copyWith(
                      fontFamily: 'monospace',
                      fontSize: 11,
                      color: colorScheme.onErrorContainer.withValues(alpha: 0.8),
                      height: 1.4,
                    ),
                  ),
                  Positioned(
                    top: 0,
                    right: 0,
                    child: GestureDetector(
                      onTap: () {
                        Clipboard.setData(
                            ClipboardData(text: widget.detail!));
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                              content: Text('Error detail copied')),
                        );
                      },
                      child: Icon(
                        Icons.copy,
                        size: 14,
                        color: colorScheme.onErrorContainer
                            .withValues(alpha: 0.5),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}
