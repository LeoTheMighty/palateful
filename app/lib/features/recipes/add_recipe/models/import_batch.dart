// Client-side model mirroring the response of `GET /v1/parser/batches/{id}`
// from story 13.12.

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

  /// ImportJob statuses that mean the job has stopped moving.
  ///
  /// Mirrors the server's vocabulary at
  /// `libraries/utils/utils/models/import_job.py:37-38`. `awaiting_review`
  /// counts as terminal *for the batch*: the import is done and the ball is
  /// in the user's court, and the Imports tab already shows it in Needs
  /// Review — so the batch has nothing left to contribute.
  static const terminalImportJobStatuses = {
    'completed',
    'failed',
    'cancelled',
    'awaiting_review',
  };

  /// True once this batch has fanned out into ImportJobs.
  ///
  /// Before this, the batch is the ONLY record of the import: the Imports
  /// tab's jobs/items queries cannot see it, which is the gap that let a
  /// photo import count on the Add Recipe strip while the tab rendered
  /// nothing (impvis1).
  bool get hasFannedOut => importJobs.isNotEmpty;

  /// True when at least one of this batch's ImportJobs is still moving.
  bool get hasLiveImportJob => importJobs
      .any((j) => !terminalImportJobStatuses.contains(j.status));

  /// Whether this batch should be counted and shown as in-flight.
  ///
  /// Not the same as [isActive]. `partial` is in [isActive] and absent from
  /// [isTerminal], so a batch parked there counted as in-progress forever —
  /// a badge that can never reach zero. Once a batch has fanned out, its
  /// ImportJobs are the truth: if they have all stopped, the batch has
  /// nothing left to report regardless of its own status.
  bool get isInFlight => isActive && (!hasFannedOut || hasLiveImportJob);
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
