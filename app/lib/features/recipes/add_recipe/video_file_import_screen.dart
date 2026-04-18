import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/di/injection.dart';
import '../../../core/router/activity_routes.dart';
import '../../../core/services/auth_service.dart';
import '../../../core/services/error_reporter.dart';

/// Stand-alone screen for importing a local video clip. Mirrors the
/// shape of `PdfImportScreen` — file picker + size cap + submit button.
/// The actual presigned-upload sequence is owned by sru-4; this screen
/// ships the wrapper (Add Recipe sheet can already reach it via
/// `/recipes/add/video`), and sru-4 wires `_submit` to the upload path.
class VideoFileImportScreen extends StatefulWidget {
  const VideoFileImportScreen({super.key, this.recipeBookId, this.initialPath});

  final String? recipeBookId;
  final String? initialPath;

  @override
  State<VideoFileImportScreen> createState() => _VideoFileImportScreenState();
}

class _VideoFileImportScreenState extends State<VideoFileImportScreen> {
  PlatformFile? _selectedFile;
  bool _isImporting = false;
  String? _error;

  String get _bookId =>
      widget.recipeBookId ?? getIt<AuthService>().defaultRecipeBookId ?? '';

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
    if (_selectedFile == null || _bookId.isEmpty) return;
    setState(() {
      _isImporting = true;
      _error = null;
    });

    try {
      // sru-4 wires the presigned-upload sequence here. Until it lands,
      // video imports from Add Recipe sheet surface an informative
      // error so users aren't left holding a spinner.
      throw UnimplementedError(
        'Video upload is coming in the next release.',
      );
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isImporting = false;
        _error = (e is UnimplementedError)
            ? e.message ?? 'Video upload is not available yet.'
            : 'Import failed. Please try again.';
      });
      ErrorReporter.log('video_import_submit_failed: $e');
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
              const Center(child: CircularProgressIndicator())
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
