/// Client-side model for `GET /v1/import-items/{id}/telemetry` (irrd-2).
///
/// Returns a fixed-length array of four stage entries: parsed, extracted,
/// matched, created. Entries for stages the item has not yet reached
/// have status `pending` with nulls for timestamps + preview.
library;

class StageEntry {
  /// One of `parsed`, `extracted`, `matched`, `created`.
  final String stage;

  /// One of `pending`, `ok`, `failed`, `skipped`.
  final String status;

  final DateTime? startedAt;
  final DateTime? completedAt;
  final int? durationMs;

  /// Human-readable raw text for the `parsed` / `extracted` stages
  /// (OCR output / extracted-recipe JSON pretty-printed). `null` on
  /// `matched` / `created`. Truncated server-side to 4096 chars when
  /// [truncated] is true.
  final String? rawOutputPreview;
  final bool truncated;

  const StageEntry({
    required this.stage,
    required this.status,
    this.startedAt,
    this.completedAt,
    this.durationMs,
    this.rawOutputPreview,
    this.truncated = false,
  });

  factory StageEntry.fromJson(Map<String, dynamic> json) {
    return StageEntry(
      stage: json['stage']?.toString() ?? 'unknown',
      status: json['status']?.toString() ?? 'pending',
      startedAt: json['started_at'] != null
          ? DateTime.tryParse(json['started_at'].toString())
          : null,
      completedAt: json['completed_at'] != null
          ? DateTime.tryParse(json['completed_at'].toString())
          : null,
      durationMs: (json['duration_ms'] as num?)?.toInt(),
      rawOutputPreview: json['raw_output_preview']?.toString(),
      truncated: json['truncated'] == true,
    );
  }

  /// Convenience for tests + stable toggle logic — a stage has landed
  /// when status is ok/failed/skipped (any terminal value).
  bool get isTerminal => status != 'pending';
}

class ImportItemTelemetry {
  final List<StageEntry> stages;

  const ImportItemTelemetry({required this.stages});

  factory ImportItemTelemetry.fromJson(Map<String, dynamic> json) {
    final raw = json['stages'] as List<dynamic>? ?? const [];
    return ImportItemTelemetry(
      stages: raw
          .whereType<Map<String, dynamic>>()
          .map(StageEntry.fromJson)
          .toList(growable: false),
    );
  }

  StageEntry? stage(String name) {
    for (final s in stages) {
      if (s.stage == name) return s;
    }
    return null;
  }
}
