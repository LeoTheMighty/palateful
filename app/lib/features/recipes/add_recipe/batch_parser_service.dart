import 'dart:async';
import 'dart:math';
import 'dart:typed_data';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';

import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';

enum BatchJobStatus { uploading, submitting, polling, succeeded, failed }

class BatchParserJob {
  final String localId;
  final String filename;
  Uint8List? imageBytes;
  String? s3Key;
  String? parserJobId;
  BatchJobStatus status;
  String? extractedText;
  String? error;
  bool isNew;

  BatchParserJob({
    required this.localId,
    required this.filename,
    required this.imageBytes,
    this.s3Key,
    this.parserJobId,
    this.status = BatchJobStatus.uploading,
    this.extractedText,
    this.error,
    this.isNew = false,
  });
}

class BatchParserService {
  final _apiClient = getIt<ApiClient>();
  final _random = Random();

  String _generateId() {
    final timestamp = DateTime.now().microsecondsSinceEpoch;
    final rand = _random.nextInt(0xFFFF).toRadixString(16).padLeft(4, '0');
    return '$timestamp-$rand';
  }

  final List<BatchParserJob> _jobs = [];
  final _controller = StreamController<List<BatchParserJob>>.broadcast();
  final Map<String, Timer> _pollTimers = {};

  Stream<List<BatchParserJob>> get jobStream => _controller.stream;
  List<BatchParserJob> get jobs => List.unmodifiable(_jobs);

  void _notify() {
    _controller.add(List.unmodifiable(_jobs));
  }

  Future<void> submitBatch(List<XFile> files) async {
    final newJobs = <BatchParserJob>[];
    for (final file in files) {
      final bytes = await file.readAsBytes();
      final job = BatchParserJob(
        localId: _generateId(),
        filename: file.name,
        imageBytes: bytes,
      );
      newJobs.add(job);
      _jobs.add(job);
    }
    _notify();

    for (final job in newJobs) {
      _processJob(job);
    }
  }

  Future<void> _processJob(BatchParserJob job) async {
    try {
      // Step 1: Get presigned upload URL
      job.status = BatchJobStatus.uploading;
      _notify();

      final uploadUrlResponse =
          await _apiClient.getParserUploadUrl(job.filename);
      final uploadUrl = uploadUrlResponse.data['upload_url'] as String;
      final s3Key = uploadUrlResponse.data['s3_key'] as String;
      final contentType = uploadUrlResponse.data['content_type'] as String;

      // Step 2: Upload image to S3
      final uploadResponse = await http.put(
        Uri.parse(uploadUrl),
        headers: {'Content-Type': contentType},
        body: job.imageBytes,
      );

      if (uploadResponse.statusCode != 200) {
        throw Exception(
            'Failed to upload image: ${uploadResponse.statusCode}');
      }

      job.s3Key = s3Key;
      // Free memory after successful upload
      job.imageBytes = null;

      // Step 3: Submit parser job
      job.status = BatchJobStatus.submitting;
      _notify();

      final submitResponse = await _apiClient.submitParserJob(s3Key);
      final jobId = submitResponse.data['id'] as String;
      job.parserJobId = jobId;

      // Step 4: Start polling
      job.status = BatchJobStatus.polling;
      _notify();

      _startPolling(job);
    } catch (e) {
      job.status = BatchJobStatus.failed;
      job.error = 'Processing failed: $e';
      _notify();
    }
  }

  void _startPolling(BatchParserJob job) {
    _pollTimers[job.localId]?.cancel();
    _pollTimers[job.localId] =
        Timer.periodic(const Duration(seconds: 5), (timer) async {
      try {
        final response = await _apiClient.getParserJob(job.parserJobId!);
        final status = response.data['status'] as String;

        if (status == 'succeeded') {
          timer.cancel();
          _pollTimers.remove(job.localId);
          job.status = BatchJobStatus.succeeded;
          job.extractedText = response.data['extracted_text'] as String?;
          job.isNew = true;
          _notify();
        } else if (status == 'failed') {
          timer.cancel();
          _pollTimers.remove(job.localId);
          job.status = BatchJobStatus.failed;
          job.error =
              response.data['error_message'] as String? ?? 'Job failed';
          _notify();
        }
      } catch (e) {
        debugPrint('Polling error for ${job.localId}: $e');
      }
    });
  }

  void retryJob(String localId) {
    final job = _jobs.firstWhere((j) => j.localId == localId);
    _pollTimers[localId]?.cancel();
    _pollTimers.remove(localId);
    job.status = BatchJobStatus.uploading;
    job.error = null;
    job.extractedText = null;
    job.parserJobId = null;
    job.s3Key = null;
    _notify();
    _processJob(job);
  }

  void dismissJob(String localId) {
    _pollTimers[localId]?.cancel();
    _pollTimers.remove(localId);
    _jobs.removeWhere((j) => j.localId == localId);
    _notify();
  }

  void markSeen(String localId) {
    final job = _jobs.firstWhere((j) => j.localId == localId);
    job.isNew = false;
    _notify();
  }

  void dispose() {
    for (final timer in _pollTimers.values) {
      timer.cancel();
    }
    _pollTimers.clear();
    _controller.close();
  }
}
