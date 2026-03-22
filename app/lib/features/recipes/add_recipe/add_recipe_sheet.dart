import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';

class AddRecipeSheet extends StatelessWidget {
  final String? recipeBookId;

  const AddRecipeSheet({super.key, this.recipeBookId});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Container(
      decoration: BoxDecoration(
        color: colorScheme.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 24, 24, 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Drag handle
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: colorScheme.outlineVariant,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 24),

              // Title
              Center(
                child: Text(
                  'Add Recipe',
                  style: textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w600,
                    color: colorScheme.onSurface,
                  ),
                ),
              ),
              const SizedBox(height: 24),

              // Quick Import section
              Padding(
                padding: const EdgeInsets.only(left: 4, bottom: 8),
                child: Text(
                  'Quick Import',
                  style: textTheme.labelLarge?.copyWith(
                    color: colorScheme.onSurfaceVariant,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              _SheetOption(
                icon: Icons.link,
                title: 'From URL',
                subtitle: 'Paste a recipe link',
                onTap: () {
                  Navigator.pop(context);
                  context.push('/recipes/add/url', extra: {
                    if (recipeBookId != null) 'recipeBookId': recipeBookId,
                  });
                },
              ),
              _SheetOption(
                icon: Icons.camera_alt,
                title: 'From Photo',
                subtitle: 'Snap or upload a photo',
                onTap: () {
                  Navigator.pop(context);
                  context.push('/recipes/add/photo', extra: {
                    if (recipeBookId != null) 'recipeBookId': recipeBookId,
                  });
                },
              ),
              _SheetOption(
                icon: Icons.content_paste,
                title: 'Paste Text',
                subtitle: 'Paste recipe from anywhere',
                onTap: () {
                  Navigator.pop(context);
                  context.push('/recipes/add/text', extra: {
                    if (recipeBookId != null) 'recipeBookId': recipeBookId,
                  });
                },
              ),

              const SizedBox(height: 16),

              // More Options section
              Padding(
                padding: const EdgeInsets.only(left: 4, bottom: 8),
                child: Text(
                  'More Options',
                  style: textTheme.labelLarge?.copyWith(
                    color: colorScheme.onSurfaceVariant,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              _SheetOption(
                icon: Icons.picture_as_pdf,
                title: 'From PDF',
                subtitle: 'Cookbook pages or recipe PDFs',
                onTap: () {
                  Navigator.pop(context);
                  context.push('/recipes/add/pdf', extra: {
                    if (recipeBookId != null) 'recipeBookId': recipeBookId,
                  });
                },
              ),
              _SheetOption(
                icon: Icons.table_chart,
                title: 'From Spreadsheet',
                subtitle: 'Import CSV or Excel file',
                onTap: () {
                  Navigator.pop(context);
                  context.push('/recipes/add/spreadsheet', extra: {
                    if (recipeBookId != null) 'recipeBookId': recipeBookId,
                  });
                },
              ),
              _SheetOption(
                icon: Icons.edit,
                title: 'Create Manually',
                subtitle: 'Build from scratch',
                onTap: () {
                  Navigator.pop(context);
                  context.push('/recipes/add/wizard', extra: {
                    if (recipeBookId != null) 'recipeBookId': recipeBookId,
                  });
                },
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SheetOption extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  const _SheetOption({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return InkWell(
      borderRadius: BorderRadius.circular(12),
      onTap: () {
        HapticFeedback.mediumImpact();
        onTap();
      },
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 10),
        child: Row(
          children: [
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, size: 22, color: colorScheme.primary),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: textTheme.bodyLarge?.copyWith(
                      fontWeight: FontWeight.w500,
                      color: colorScheme.onSurface,
                    ),
                  ),
                  Text(
                    subtitle,
                    style: textTheme.bodySmall?.copyWith(
                      color: colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
            Icon(Icons.chevron_right, color: colorScheme.outline, size: 20),
          ],
        ),
      ),
    );
  }
}
