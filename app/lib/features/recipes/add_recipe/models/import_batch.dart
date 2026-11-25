// Client-side model mirroring the response of `GET /v1/parser/batches/{id}`
// from story 13.12.

import '../../../../core/state/import_job_statuses.dart';

class ImportBatch {
  final String id;
  final String status;
  final int groupCount;
  final String? recipeBookId;
  final DateTime createdAt;
  final DateTime? completedAt;
  final String? errorMessage;
  final List<ImportBatchJob> jobs;
  final List<ImportBatchImportJob> importJobs;

  const ImportBatch({
    required this.id,
    required this.status,
    required this.groupCount,
    required this.recipeBookId,
    required this.createdAt,
    required this.completedAt,
    required this.errorMessage,
    required this.jobs,
    required this.importJobs,
  });

  factory ImportBatch.fromJson(Map<String, dynamic> json) {
    return ImportBatch(
      id: json['id'] as String,
      status: json['status'] as String,
      groupCount: (json['group_count'] as num?)?.toInt() ?? 1,
      recipeBookId: json['recipe_book_id'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String),
      completedAt: json['completed_at'] != null
          ? DateTime.parse(json['completed_at'] as String)
          : null,
      errorMessage: json['error_message'] as String?,
      jobs: ((json['jobs'] as List?) ?? const [])
          .map((j) => ImportBatchJob.fromJson(j as Map<String, dynamic>))
          .toList(),
      importJobs: ((json['import_jobs'] as List?) ?? const [])
          .map((j) =>
              ImportBatchImportJob.fromJson(j as Map<String, dynamic>))
          .toList(),
    );
  }

  bool get isActive => const {
        'pending',
        'submitted',
        'running',
        'partial',
      }.contains(status);

  bool get isTerminal => const {
        'succeeded',
        'failed',
      }.contains(status);

  /// How long a batch that has produced no ImportJobs may keep counting as
  /// in flight.
  ///
  /// `!hasFannedOut` on its own meant "no jobs ⇒ in flight, forever", and
  /// a batch can legitimately end with zero ImportJobs:
  /// `parser_batch_completion.py:133-141` marks a batch `partial` and
  /// returns without creating any when it has no `recipe_book_id` and some
  /// OCR job failed. Nothing sweeps ParserBatch rows, so that batch would
  /// count — and, since impvis1, render — for the life of the account.
  /// Photo OCR finishes in minutes; hours means it is not coming.
  static const preFanOutGrace = Duration(hours: 2);

  /// True once this batch has fanned out into ImportJobs.
  ///
  /// Before this, the batch is the ONLY record of the import: the Imports
  /// tab's jobs/items queries cannot see it, which is the gap that let a
  /// photo import count on the Add Recipe strip while the tab rendered
  /// nothing (impvis1).
  bool get hasFannedOut => importJobs.isNotEmpty;

  /// True when at least one of this batch's ImportJobs is still moving.
  bool get hasLiveImportJob =>
      importJobs.any((j) => !isJobTerminal(j.status));

  /// Whether this batch should be counted and shown as in-flight.
  ///
  /// Not the same as [isActive]. `partial` is in [isActive] and absent from
  /// [isTerminal], so a batch parked there counted as in-progress forever —
  /// a badge that can never reach zero. Two ways that happens, both closed
  /// here: a batch that fanned out into jobs that have all finished (its
  /// jobs are the truth, whatever the batch's own status says), and a batch
  /// that never fanned out at all ([preFanOutGrace]).
  bool isInFlightAt(DateTime now) {
    if (!isActive) return false;
    if (hasFannedOut) return hasLiveImportJob;
    return now.difference(createdAt) < preFanOutGrace;
  }

  bool get isInFlight => isInFlightAt(DateTime.now());
}

class ImportBatchJob {
  final String id;
  final String status;
  final String? inputS3Key;
  final int groupIndex;
  final String? extractedText;
  final String? errorMessage;

  const ImportBatchJob({
    required this.id,
    required this.status,
    required this.inputS3Key,
    required this.groupIndex,
    required this.extractedText,
    required this.errorMessage,
  });

  factory ImportBatchJob.fromJson(Map<String, dynamic> json) {
    return ImportBatchJob(
      id: json['id'] as String,
      status: json['status'] as String,
      inputS3Key: json['input_s3_key'] as String?,
      groupIndex: (json['group_index'] as num?)?.toInt() ?? 0,
      extractedText: json['extracted_text'] as String?,
      errorMessage: json['error_message'] as String?,
    );
  }

  String get displayName {
    final key = inputS3Key;
    if (key == null || key.isEmpty) return 'Photo';
    final segments = key.split('/');
    return segments.isNotEmpty ? segments.last : key;
  }
}

class ImportBatchImportJob {
  final String id;
  final String status;

  const ImportBatchImportJob({
    required this.id,
    required this.status,
  });

  factory ImportBatchImportJob.fromJson(Map<String, dynamic> json) {
    return ImportBatchImportJob(
      id: json['id'] as String,
      status: json['status'] as String,
    );
  }
}

class ImportBatchesState {
  final List<ImportBatch> active;
  final List<ImportBatch> recentlyCompleted;

  const ImportBatchesState({
    this.active = const [],
    this.recentlyCompleted = const [],
  });

  bool get isEmpty => active.isEmpty && recentlyCompleted.isEmpty;

  List<ImportBatch> get all => [...active, ...recentlyCompleted];
}
