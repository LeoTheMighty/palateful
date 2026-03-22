import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';
import '../../../core/services/auth_service.dart';

class AudioImportScreen extends StatefulWidget {
  final String? recipeBookId;

  const AudioImportScreen({super.key, this.recipeBookId});

  @override
  State<AudioImportScreen> createState() => _AudioImportScreenState();
}

class _AudioImportScreenState extends State<AudioImportScreen> {
  final _apiClient = getIt<ApiClient>();
  PlatformFile? _selectedFile;
  bool _isImporting = false;
  String? _importJobId;
  String? _importStatus;
  Timer? _pollTimer;
  int _pollCount = 0;
  String? _error;

  String get _bookId =>
      widget.recipeBookId ?? getIt<AuthService>().defaultRecipeBookId ?? '';

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  Future<void> _pickFile() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['m4a', 'mp3', 'wav', 'aac', 'ogg'],
        withData: true,
      );
      if (result != null && result.files.isNotEmpty) {
        final file = result.files.first;
        // 50MB limit for audio
        if (file.size > 50 * 1024 * 1024) {
          setState(() {
            _error = 'File too large — max 50MB';
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

  Future<void> _startImport() async {
    if (_selectedFile == null || _bookId.isEmpty) return;

    setState(() {
      _isImporting = true;
      _error = null;
      _pollCount = 0;
    });

    try {
      final bytes = _selectedFile!.bytes ??
          await File(_selectedFile!.path!).readAsBytes();
      final base64Data = base64Encode(bytes);

      final response = await _apiClient.startImport(
        _bookId,
        sourceType: 'audio',
        fileBase64: base64Data,
        fileName: _selectedFile!.name,
      );

      if (!mounted) return;
      _importJobId = response.data['id']?.toString();
      _importStatus = response.data['status']?.toString();
      _startPolling();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isImporting = false;
        _error = 'Import failed. Please try again.';
      });
    }
  }

  void _startPolling() {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(seconds: 2), (_) {
      _pollImportJob();
    });
  }

  Future<void> _pollImportJob() async {
    if (_importJobId == null) return;

    try {
      final response = await _apiClient.getImportJob(_importJobId!);
      if (!mounted) return;

      final status = response.data['status']?.toString();
      setState(() {
        _importStatus = status;
        _pollCount++;
      });

      if (status == 'completed') {
        _pollTimer?.cancel();
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Recipe saved!')),
          );
          context.pop();
        }
      } else if (status == 'awaiting_review') {
        _pollTimer?.cancel();
        if (mounted) {
          context.pushReplacement('/recipes/import/review-list/$_importJobId');
        }
      } else if (status == 'failed') {
        _pollTimer?.cancel();
        setState(() {
          _isImporting = false;
          _error = "Couldn't find a recipe in this recording. Try pasting the text instead.";
        });
      }
    } catch (_) {}
  }

  String get _progressMessage {
    if (_pollCount < 2) return 'Uploading audio...';
    if (_pollCount < 6) return 'Transcribing...';
    if (_pollCount < 10) return 'Extracting recipe...';
    return 'Almost done...';
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(title: const Text('Import Voice Memo')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Import a recipe from a voice recording — dictated recipes, voice memos, or audio messages.',
              style: textTheme.bodyLarge?.copyWith(
                color: colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 24),

            // File picker
            OutlinedButton.icon(
              onPressed: _isImporting ? null : _pickFile,
              icon: const Icon(Icons.mic),
              label: Text(_selectedFile?.name ?? 'Choose audio file'),
            ),

            if (_selectedFile != null) ...[
              const SizedBox(height: 8),
              Text(
                '${(_selectedFile!.size / 1024).toStringAsFixed(0)} KB',
                style: textTheme.bodySmall?.copyWith(color: colorScheme.outline),
                textAlign: TextAlign.center,
              ),
            ],

            const SizedBox(height: 24),

            if (_isImporting) ...[
              const Center(child: CircularProgressIndicator()),
              const SizedBox(height: 16),
              Text(
                _progressMessage,
                style: textTheme.bodyMedium,
                textAlign: TextAlign.center,
              ),
            ] else
              FilledButton.icon(
                onPressed: _selectedFile != null ? _startImport : null,
                icon: const Icon(Icons.download),
                label: const Text('Import Recipe'),
              ),

            if (_error != null) ...[
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: colorScheme.errorContainer,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _error!,
                      style: TextStyle(color: colorScheme.onErrorContainer),
                    ),
                    const SizedBox(height: 12),
                    OutlinedButton.icon(
                      onPressed: () => context.pushReplacement('/recipes/add/text'),
                      icon: const Icon(Icons.edit_note, size: 18),
                      label: const Text('Paste recipe text instead'),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
