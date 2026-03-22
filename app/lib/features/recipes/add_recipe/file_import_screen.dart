import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';


class FileImportScreen extends StatelessWidget {
  const FileImportScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Scaffold(
      backgroundColor: colorScheme.surface,
      appBar: AppBar(
        backgroundColor: colorScheme.surface,
        title: const Text('Import from File'),
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                padding: const EdgeInsets.all(32),
                decoration: BoxDecoration(
                  color: colorScheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(24),
                ),
                child: Icon(
                  Icons.folder_outlined,
                  size: 64,
                  color: colorScheme.secondary,
                ),
              ),
              const SizedBox(height: 32),
              Text(
                'File Import',
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.w600,
                  color: colorScheme.onSurface,
                ),
              ),
              const SizedBox(height: 12),
              Text(
                'Import recipes from CSV, Google Sheets, Notion, or other file formats.',
                style: TextStyle(color: colorScheme.onSurfaceVariant),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 32),
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: colorScheme.tertiary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: colorScheme.tertiary),
                ),
                child: Row(
                  children: [
                    Icon(Icons.construction, color: colorScheme.tertiary),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        'Coming soon! File import uses the same AI as photo OCR.',
                        style: TextStyle(color: colorScheme.tertiary),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),
              OutlinedButton(
                onPressed: () => context.pop(),
                child: const Text('Go Back'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
