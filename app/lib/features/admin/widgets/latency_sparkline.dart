import 'package:flutter/material.dart';

/// A minimal 60×20 dp polyline sparkline for 24 latency buckets.
///
/// Normalizes each row to its own max value so small-magnitude rows
/// (e.g. 3 ms health checks) still show shape. Renders a flat baseline
/// when every bucket is zero (cold start, no traffic in the window).
class LatencySparkline extends StatelessWidget {
  final List<double> values;
  final double width;
  final double height;

  const LatencySparkline({
    super.key,
    required this.values,
    this.width = 60,
    this.height = 20,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    // WCAG AA-safe — primary on surface stays well above 4.5:1.
    final strokeColor = colorScheme.primary;
    return Semantics(
      label: 'sparkline showing ${values.length} latency buckets',
      excludeSemantics: true,
      child: CustomPaint(
        size: Size(width, height),
        painter: _SparklinePainter(values: values, stroke: strokeColor),
      ),
    );
  }
}

class _SparklinePainter extends CustomPainter {
  final List<double> values;
  final Color stroke;

  _SparklinePainter({required this.values, required this.stroke});

  @override
  void paint(Canvas canvas, Size size) {
    if (values.isEmpty) return;

    final double maxVal = values.reduce((a, b) => a > b ? a : b);

    final paint = Paint()
      ..color = stroke
      ..strokeWidth = 1.4
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;

    final n = values.length;
    // Baseline sits at the vertical bottom of the canvas; shapes grow up.
    final double baseline = size.height;

    // All-zero → flat baseline (still drawn so it reads as "no spikes").
    if (maxVal <= 0) {
      canvas.drawLine(
        Offset(0, baseline - 0.5),
        Offset(size.width, baseline - 0.5),
        paint,
      );
      return;
    }

    final path = Path();
    for (int i = 0; i < n; i++) {
      final x = n == 1 ? size.width / 2 : (i / (n - 1)) * size.width;
      final normalized = values[i] / maxVal;
      final y = baseline - (normalized * (size.height - 2)) - 1;
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant _SparklinePainter old) {
    return old.values != values || old.stroke != stroke;
  }
}
