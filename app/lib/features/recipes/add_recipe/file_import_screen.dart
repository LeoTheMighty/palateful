import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_colors.dart';

class FileImportScreen extends StatelessWidget {
  const FileImportScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.cream,
      appBar: AppBar(
        backgroundColor: AppColors.cream,
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
                  color: AppColors.beige,
                  borderRadius: BorderRadius.circular(24),
                ),
                child: const Icon(
                  Icons.folder_outlined,
                  size: 64,
                  color: AppColors.hazelnut,
                ),
              ),
              const SizedBox(height: 32),
              const Text(
                'File Import',
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 12),
              const Text(
                'Import recipes from CSV, Google Sheets, Notion, or other file formats.',
                style: TextStyle(color: AppColors.textSecondary),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 32),
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppColors.withOpacity(AppColors.terracotta, 0.1),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppColors.terracotta),
                ),
                child: const Row(
                  children: [
                    Icon(Icons.construction, color: AppColors.terracotta),
                    SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        'Coming soon! File import uses the same AI as photo OCR.',
                        style: TextStyle(color: AppColors.terracotta),
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
