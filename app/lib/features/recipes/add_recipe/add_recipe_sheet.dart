import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'widgets/live_import_strip.dart';

class AddRecipeSheet extends ConsumerStatefulWidget {
  final String? recipeBookId;

  const AddRecipeSheet({super.key, this.recipeBookId});

  @override
  ConsumerState<AddRecipeSheet> createState() => _AddRecipeSheetState();
}

class _AddRecipeSheetState extends ConsumerState<AddRecipeSheet> {
  bool _moreExpanded = false;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final bookId = widget.recipeBookId;

    return Container(
      decoration: BoxDecoration(
        color: colorScheme.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 24, 24, 16),
          child: SingleChildScrollView(
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

              // Ambient live-progress strip. Taps through to Activity Hub
              // imports filter — full pipeline-state UI lives there now
              // (bugs-act-3). No render when no imports are active.
              const LiveImportStrip(),

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
                title: 'From Link',
                subtitle: 'Any URL — websites, TikTok, Instagram, YouTube',
                onTap: () {
                  Navigator.pop(context);
                  context.push('/recipes/add/url', extra: {
                    if (bookId != null) 'recipeBookId': bookId,
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
                    if (bookId != null) 'recipeBookId': bookId,
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
                    if (bookId != null) 'recipeBookId': bookId,
                  });
                },
              ),

              const SizedBox(height: 8),

              // More Options — collapsible
              GestureDetector(
                onTap: () => setState(() => _moreExpanded = !_moreExpanded),
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 8),
                  child: Row(
                    children: [
                      Text(
                        'More Options',
                        style: textTheme.labelLarge?.copyWith(
                          color: colorScheme.onSurfaceVariant,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(width: 4),
                      Icon(
                        _moreExpanded ? Icons.expand_less : Icons.expand_more,
                        size: 20,
                        color: colorScheme.onSurfaceVariant,
                      ),
                    ],
                  ),
                ),
              ),
              AnimatedCrossFade(
                firstChild: const SizedBox.shrink(),
                secondChild: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    _SheetOption(
                      icon: Icons.picture_as_pdf,
                      title: 'PDF / Document',
                      subtitle: 'Import from a cookbook PDF',
                      onTap: () {
                        Navigator.pop(context);
                        context.push('/recipes/add/pdf', extra: {
                          if (bookId != null) 'recipeBookId': bookId,
                        });
                      },
                    ),
                    _SheetOption(
                      icon: Icons.mic,
                      title: 'Voice Memo',
                      subtitle: 'Record or import a voice recording',
                      onTap: () {
                        Navigator.pop(context);
                        context.push('/recipes/add/audio', extra: {
                          if (bookId != null) 'recipeBookId': bookId,
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
                          if (bookId != null) 'recipeBookId': bookId,
                        });
                      },
                    ),
                    _SheetOption(
                      icon: Icons.videocam,
                      title: 'Video File',
                      subtitle: 'Pull a recipe from a local video clip',
                      onTap: () {
                        Navigator.pop(context);
                        context.push('/recipes/add/video', extra: {
                          if (bookId != null) 'recipeBookId': bookId,
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
                          if (bookId != null) 'recipeBookId': bookId,
                        });
                      },
                    ),
                  ],
                ),
                crossFadeState: _moreExpanded
                    ? CrossFadeState.showSecond
                    : CrossFadeState.showFirst,
                duration: const Duration(milliseconds: 200),
              ),
              ],
            ),
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
