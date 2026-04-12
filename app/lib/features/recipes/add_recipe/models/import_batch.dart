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
