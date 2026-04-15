import 'dart:convert';
import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';
import '../../../core/services/auth_service.dart';
import '../../../core/services/error_reporter.dart';
import '../../../shared/widgets/error_banner.dart';

class PdfImportScreen extends StatefulWidget {
  final String? recipeBookId;

  const PdfImportScreen({super.key, this.recipeBookId});

  @override
  State<PdfImportScreen> createState() => _PdfImportScreenState();
}

class _PdfImportScreenState extends State<PdfImportScreen> {
  final _apiClient = getIt<ApiClient>();
  PlatformFile? _selectedFile;
  bool _isImporting = false;
  String? _error;
  String? _errorDetail;

  String get _bookId =>
      widget.recipeBookId ?? getIt<AuthService>().defaultRecipeBookId ?? '';

  Future<void> _pickFile() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['pdf'],
        withData: true,
      );
      if (result != null && result.files.isNotEmpty) {
        final file = result.files.first;
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
    });

    try {
      final bytes = _selectedFile!.bytes ??
          await File(_selectedFile!.path!).readAsBytes();
      final base64Data = base64Encode(bytes);

      final response = await _apiClient.startImport(
        _bookId,
        sourceType: 'pdf',
        fileBase64: base64Data,
        fileName: _selectedFile!.name,
      );

      if (!mounted) return;
      final jobId = response.data['id'];
      if (jobId != null) {
        context.pushReplacement('/recipes/import/review-list/$jobId');
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isImporting = false;
        _error = 'Import failed. Please try again.';
        _errorDetail = ErrorReporter.detail(e);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(title: const Text('Import from PDF')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Import recipes from a PDF — cookbook pages, blog exports, or scanned recipe cards.',
              style: textTheme.bodyLarge?.copyWith(
                color: colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 24),

            // File picker
            OutlinedButton.icon(
              onPressed: _isImporting ? null : _pickFile,
              icon: const Icon(Icons.picture_as_pdf),
              label: Text(_selectedFile?.name ?? 'Choose PDF file'),
            ),

            if (_selectedFile != null) ...[
              const SizedBox(height: 8),
              Text(
                '${(_selectedFile!.size / 1024).toStringAsFixed(0)} KB',
                style: textTheme.bodySmall?.copyWith(
                  color: colorScheme.outline,
                ),
                textAlign: TextAlign.center,
              ),
            ],

            const SizedBox(height: 24),

            if (_isImporting) ...[
              const Center(child: CircularProgressIndicator()),
              const SizedBox(height: 16),
              Text(
                'Reading PDF...',
                style: textTheme.bodyMedium,
                textAlign: TextAlign.center,
              ),
            ] else
              FilledButton.icon(
                onPressed: _selectedFile != null ? _startImport : null,
                icon: const Icon(Icons.download),
                label: const Text('Import Recipes'),
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
          ],
        ),
      ),
    );
  }
}
