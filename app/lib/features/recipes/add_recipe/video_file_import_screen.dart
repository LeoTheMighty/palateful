import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/di/injection.dart';
import '../../../core/router/activity_routes.dart';
import '../../../core/services/api_client.dart';
import '../../../core/services/auth_service.dart';
import '../../../core/services/error_reporter.dart';
import '../../../core/services/presigned_uploader.dart';
import 'state/receive_import_notifier.dart';
import 'state/receive_upload_coordinator.dart';

/// Stand-alone screen for importing a local video clip. Mirrors the
/// shape of `PdfImportScreen` — file picker + size cap + submit button.
/// Submits through the same presigned-upload sequence as the receiving
/// screen (sru-4): `upload-url` → PUT → `/import {s3_key, etag}` with
/// `source_type=video_file`.
class VideoFileImportScreen extends StatefulWidget {
  const VideoFileImportScreen({
    super.key,
    this.recipeBookId,
    this.initialPath,
    this.uploader,
  });

  final String? recipeBookId;
  final String? initialPath;

  /// Injection seam for the presigned PUT, matching the receiving
  /// screen's. Production leaves it null and the screen owns (and
  /// aborts) a `DioPresignedUploader`.
  @visibleForTesting
  final PresignedUploader? uploader;

  @override
  State<VideoFileImportScreen> createState() => _VideoFileImportScreenState();
}

class _VideoFileImportScreenState extends State<VideoFileImportScreen> {
  PlatformFile? _selectedFile;
  bool _isImporting = false;
  String? _error;

  /// Bytes handed to S3 so far, and the "claiming the object" stage that
  /// follows the PUT. Both drive the submit-button area's copy.
  int _uploadedBytes = 0;
  bool _sending = false;

  /// Owned here so `dispose()` aborts an in-flight PUT — same
  /// half-uploaded-object guard the receiving screen has.
  late final PresignedUploader _uploader =
      widget.uploader ?? DioPresignedUploader();

  String get _bookId =>
      widget.recipeBookId ?? getIt<AuthService>().defaultRecipeBookId ?? '';

  @override
  void dispose() {
    _uploader.abort();
    super.dispose();
  }

  @override
  void initState() {
    super.initState();
    final seed = widget.initialPath;
    if (seed != null && seed.isNotEmpty) {
      _prefillFromPath(seed);
    }
  }

  Future<void> _prefillFromPath(String path) async {
    try {
      final file = File(path);
      if (!await file.exists()) return;
      final stat = await file.stat();
      if (stat.size > 100 * 1024 * 1024) {
        if (!mounted) return;
        setState(() => _error = 'File too large — max 100 MB');
        return;
      }
      final name = path.split(Platform.pathSeparator).last;
      if (!mounted) return;
      setState(() {
        _selectedFile = PlatformFile(
          name: name,
          path: path,
          size: stat.size,
        );
        _error = null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = 'Could not open shared video.');
    }
  }

  Future<void> _pickFile() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['mp4', 'mov', 'm4v', 'webm'],
        withData: false,
      );
      if (result != null && result.files.isNotEmpty) {
        final file = result.files.first;
        if (file.size > 100 * 1024 * 1024) {
          setState(() {
            _error = 'File too large — max 100 MB';
            _selectedFile = null;
          });
          return;
        }
        setState(() {
          _selectedFile = file;
          _error = null;
        });
      }
    } catch (e) {
      setState(() => _error = 'Could not pick file');
    }
  }

  Future<void> _submit() async {
    final file = _selectedFile;
    final path = file?.path;
    if (file == null || _bookId.isEmpty) return;
    if (path == null || path.isEmpty) {
      // `withData: false` means we never hold the bytes ourselves — the
      // uploader streams from disk, so a path-less pick can't proceed.
      setState(() => _error = 'Could not read that video file.');
      return;
    }

    setState(() {
      _isImporting = true;
      _sending = false;
      _uploadedBytes = 0;
      _error = null;
    });

    try {
      await ReceiveUploadCoordinator(
        api: getIt<ApiClient>(),
        uploader: _uploader,
      ).run(
        bookId: _bookId,
        branch: ReceiveBranch.video,
        filePath: path,
        filename: file.name,
        sizeBytes: file.size,
        onProgress: (sent, _) {
          if (!mounted) return;
          setState(() => _uploadedBytes = sent);
        },
        onUploaded: () {
          if (!mounted) return;
          setState(() => _sending = true);
        },
      );
      if (!mounted) return;
      context.go(ActivityRoutes.hubPath);
    } on UploadAbortedException {
      // Screen is gone — nothing to render, nothing to report.
      return;
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isImporting = false;
        _sending = false;
        _error = e is ReceiveUploadFailure
            ? _copyFor(e.code)
            : 'Import failed. Please try again.';
      });
      ErrorReporter.log('video_import_submit_failed: $e');
    }
  }

  String _copyFor(ReceiveErrorCode code) {
    switch (code) {
      case ReceiveErrorCode.network:
        return "Couldn't upload. Check your connection and try again.";
      case ReceiveErrorCode.unauthorized:
        return 'Your session expired. Sign in again to import.';
      case ReceiveErrorCode.tooLarge:
        return 'That file is too large. Max 100 MB.';
      case ReceiveErrorCode.objectNotReady:
        return 'Upload is still syncing. Try again in a moment.';
      case ReceiveErrorCode.duplicate:
        return 'This video has already been imported.';
      case ReceiveErrorCode.rateLimited:
        return 'Too many imports right now. Try again shortly.';
      case ReceiveErrorCode.unknown:
        return 'Import failed. Please try again.';
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(title: const Text('Import from Video')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Pick a local video clip — Palateful extracts the audio '
              'track, transcribes it, and builds a recipe.',
              style: textTheme.bodyLarge?.copyWith(
                color: colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 24),
            OutlinedButton.icon(
              onPressed: _isImporting ? null : _pickFile,
              icon: const Icon(Icons.videocam),
              label: Text(_selectedFile?.name ?? 'Choose video file'),
            ),
            if (_selectedFile != null) ...[
              const SizedBox(height: 8),
              Text(
                '${(_selectedFile!.size / (1024 * 1024)).toStringAsFixed(1)} MB',
                style: textTheme.bodySmall?.copyWith(color: colorScheme.outline),
                textAlign: TextAlign.center,
              ),
            ],
            const SizedBox(height: 24),
            if (_isImporting)
              _UploadProgress(
                sending: _sending,
                uploadedBytes: _uploadedBytes,
                totalBytes: _selectedFile?.size ?? 0,
              )
            else
              FilledButton.icon(
                onPressed: _selectedFile != null ? _submit : null,
                icon: const Icon(Icons.cloud_upload),
                label: const Text('Upload & Import'),
              ),
            if (_error != null) ...[
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: colorScheme.errorContainer,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  _error!,
                  style: TextStyle(color: colorScheme.onErrorContainer),
                ),
              ),
            ],
            const Spacer(),
            TextButton(
              onPressed: () => context.go(ActivityRoutes.hubPath),
              child: const Text('Done — go to Activity'),
            ),
          ],
        ),
      ),
    );
  }
}

/// Byte-level upload progress for the video submit path. A 100 MB clip
/// on cellular takes long enough that a bare spinner reads as a hang.
class _UploadProgress extends StatelessWidget {
  const _UploadProgress({
    required this.sending,
    required this.uploadedBytes,
    required this.totalBytes,
  });

  final bool sending;
  final int uploadedBytes;
  final int totalBytes;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final determinate = !sending && totalBytes > 0;
    final fraction = determinate
        ? (uploadedBytes / totalBytes).clamp(0.0, 1.0)
        : null;
    return Column(
      children: [
        LinearProgressIndicator(value: fraction),
        const SizedBox(height: 8),
        Text(
          sending
              ? 'Sending to Palateful…'
              : determinate
                  ? 'Uploading… ${(fraction! * 100).round()}%'
                  : 'Uploading…',
          style: theme.textTheme.bodySmall
              ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
        ),
      ],
    );
  }
}
