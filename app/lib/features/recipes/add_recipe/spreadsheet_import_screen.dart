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

/// Screen for importing recipes from a CSV or XLSX spreadsheet.
class SpreadsheetImportScreen extends StatefulWidget {
  final String? recipeBookId;

  const SpreadsheetImportScreen({super.key, this.recipeBookId});

  @override
  State<SpreadsheetImportScreen> createState() => _SpreadsheetImportScreenState();
}

class _SpreadsheetImportScreenState extends State<SpreadsheetImportScreen> {
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
        allowedExtensions: ['csv', 'xlsx', 'xls'],
        withData: true,
      );
      if (result != null && result.files.isNotEmpty) {
        final file = result.files.first;
        // Size checks
        final ext = file.extension?.toLowerCase() ?? '';
        final maxSize = ext == 'csv' ? 5 * 1024 * 1024 : 10 * 1024 * 1024;
        if (file.size > maxSize) {
          setState(() {
            _error = 'File too large — max ${ext == "csv" ? "5MB" : "10MB"}';
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
      final bytes = _selectedFile!.bytes ?? await File(_selectedFile!.path!).readAsBytes();
      final base64Data = base64Encode(bytes);

      final response = await _apiClient.startImport(
        _bookId,
        sourceType: 'spreadsheet',
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
      appBar: AppBar(title: const Text('Import Spreadsheet')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Select a CSV or Excel file with your recipes. AI will parse each row automatically — no column mapping needed.',
              style: textTheme.bodyMedium?.copyWith(
                color: colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 24),

            // File selection area
            GestureDetector(
              onTap: _isImporting ? null : _pickFile,
              child: Container(
                height: 140,
                decoration: BoxDecoration(
                  color: colorScheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(
                    color: _selectedFile != null
                        ? colorScheme.primary
                        : colorScheme.outlineVariant,
                  ),
                ),
                child: Center(
                  child: _selectedFile != null
                      ? Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.description, size: 36, color: colorScheme.primary),
                            const SizedBox(height: 8),
                            Text(
                              _selectedFile!.name,
                              style: textTheme.bodyLarge?.copyWith(
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                            Text(
                              '${(_selectedFile!.size / 1024).toStringAsFixed(1)} KB',
                              style: textTheme.bodySmall?.copyWith(
                                color: colorScheme.onSurfaceVariant,
                              ),
                            ),
                          ],
                        )
                      : Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.upload_file, size: 36, color: colorScheme.onSurfaceVariant),
                            const SizedBox(height: 8),
                            Text(
                              'Tap to select file',
                              style: textTheme.bodyMedium?.copyWith(
                                color: colorScheme.onSurfaceVariant,
                              ),
                            ),
                            Text(
                              'CSV (5MB) or Excel (10MB) • Max 200 recipes',
                              style: textTheme.bodySmall?.copyWith(
                                color: colorScheme.onSurfaceVariant.withValues(alpha: 0.7),
                              ),
                            ),
                          ],
                        ),
                ),
              ),
            ),

            if (_error != null) ...[
              const SizedBox(height: 12),
              Text(
                _error!,
                style: textTheme.bodySmall?.copyWith(color: colorScheme.error),
              ),
            ],

            const Spacer(),

            FilledButton(
              onPressed: _selectedFile != null && !_isImporting ? _startImport : null,
              child: _isImporting
                  ? const Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                        ),
                        SizedBox(width: 12),
                        Text('Processing spreadsheet...'),
                      ],
                    )
                  : const Text('Import Recipes'),
            ),
          ],
        ),
      ),
    );
  }
}
