import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import 'perf_request_log.dart';

/// Debug-only floating overlay showing recent HTTP requests from
/// [PerfRequestLog]. Install as the `builder` on `MaterialApp.router`
/// so every route sees the hit-zone and toggle state survives
/// navigation.
///
/// Long-press the 64×64 translucent hit-zone in the top-right corner
/// to toggle visibility. `HitTestBehavior.translucent` + no onTap
/// means taps pass through to the underlying UI — the hit-zone only
/// consumes long-press.
///
/// In release (`!kDebugMode`) this widget returns [child] unwrapped
/// and the rest of the file tree-shakes out.
class PerfOverlay extends StatefulWidget {
  const PerfOverlay({super.key, required this.child});

  final Widget child;

  /// Hit-zone side length. Matches the default iOS tappable minimum
  /// of ~44 but larger so the corner is easy to find without looking.
  @visibleForTesting
  static const double hitZoneSize = 64;

  @override
  State<PerfOverlay> createState() => _PerfOverlayState();
}

class _PerfOverlayState extends State<PerfOverlay> {
  bool _visible = false;

  void _toggle() {
    setState(() => _visible = !_visible);
  }

  @override
  Widget build(BuildContext context) {
    if (!kDebugMode) return widget.child;
    return Stack(
      fit: StackFit.expand,
      children: [
        widget.child,
        Positioned(
          top: 0,
          right: 0,
          child: SizedBox(
            width: PerfOverlay.hitZoneSize,
            height: PerfOverlay.hitZoneSize,
            child: GestureDetector(
              key: const ValueKey('perf_overlay_hit_zone'),
              behavior: HitTestBehavior.translucent,
              onLongPress: _toggle,
            ),
          ),
        ),
        if (_visible)
          _PerfOverlayPanel(onClose: _toggle),
      ],
    );
  }
}

class _PerfOverlayPanel extends StatelessWidget {
  const _PerfOverlayPanel({required this.onClose});

  final VoidCallback onClose;

  @override
  Widget build(BuildContext context) {
    final media = MediaQuery.of(context);
    return Positioned(
      top: media.padding.top + 8,
      left: 8,
      right: 8,
      height: media.size.height * 0.5,
      child: Material(
        elevation: 8,
        color: const Color(0xE0000000),
        borderRadius: BorderRadius.circular(8),
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              child: Row(
                children: [
                  const Text(
                    'Perf — recent requests',
                    style: TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const Spacer(),
                  IconButton(
                    key: const ValueKey('perf_overlay_close'),
                    icon: const Icon(Icons.close, color: Colors.white),
                    onPressed: onClose,
                  ),
                ],
              ),
            ),
            const Divider(color: Colors.white24, height: 1),
            Expanded(
              child: ValueListenableBuilder<List<PerfRequestEntry>>(
                valueListenable: PerfRequestLog.instance.entries,
                builder: (context, entries, _) {
                  if (entries.isEmpty) {
                    return const Center(
                      child: Text(
                        'No requests yet',
                        style: TextStyle(color: Colors.white70),
                      ),
                    );
                  }
                  return ListView.builder(
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    itemCount: entries.length,
                    itemBuilder: (context, i) =>
                        _PerfEntryRow(entry: entries[i]),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PerfEntryRow extends StatelessWidget {
  const _PerfEntryRow({required this.entry});

  final PerfRequestEntry entry;

  Color _statusColor() {
    if (entry.errorMessage != null) return Colors.redAccent;
    final code = entry.statusCode;
    if (code == null) return Colors.white60;
    if (code >= 500) return Colors.redAccent;
    if (code >= 400) return Colors.orangeAccent;
    if (code >= 200 && code < 300) return Colors.greenAccent;
    return Colors.white60;
  }

  @override
  Widget build(BuildContext context) {
    final statusLabel = entry.statusCode?.toString() ?? 'ERR';
    final ms = entry.duration.inMilliseconds;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      child: DefaultTextStyle(
        style: const TextStyle(
          color: Colors.white,
          fontFamily: 'monospace',
          fontSize: 11,
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(
              width: 40,
              child: Text(
                statusLabel,
                style: TextStyle(
                  color: _statusColor(),
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            SizedBox(width: 44, child: Text(entry.method)),
            SizedBox(
              width: 56,
              child: Text('${ms}ms', textAlign: TextAlign.right),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                entry.path,
                overflow: TextOverflow.ellipsis,
                maxLines: 2,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
