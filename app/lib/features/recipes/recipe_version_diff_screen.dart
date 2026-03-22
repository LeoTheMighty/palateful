import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../core/theme/app_colors.dart';


/// Diff change type for an ingredient or step.
enum _DiffType { added, removed, changed, unchanged }

class RecipeVersionDiffScreen extends StatefulWidget {
  final String recipeId;
  final String versionId;
  final int versionNumber;

  const RecipeVersionDiffScreen({
    super.key,
    required this.recipeId,
    required this.versionId,
    this.versionNumber = 0,
  });

  @override
  State<RecipeVersionDiffScreen> createState() =>
      _RecipeVersionDiffScreenState();
}

class _RecipeVersionDiffScreenState extends State<RecipeVersionDiffScreen> {
  final _apiClient = getIt<ApiClient>();
  Map<String, dynamic>? _snapshot;
  Map<String, dynamic>? _currentRecipe;
  List<String> _changedFields = [];
  String? _createdAt;
  bool _isLoading = true;
  String? _error;
  bool _canEdit = false;
  bool _isRestoring = false;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final results = await Future.wait([
        _apiClient.getRecipeVersion(widget.recipeId, widget.versionId),
        _apiClient.getRecipe(widget.recipeId),
      ]);
      if (mounted) {
        final versionData = results[0].data as Map<String, dynamic>;
        setState(() {
          _snapshot = versionData['snapshot'] as Map<String, dynamic>?;
          _changedFields =
              ((versionData['changed_fields'] as List?) ?? [])
                  .map((e) => e.toString())
                  .toList();
          _createdAt = versionData['created_at'] as String?;
          _currentRecipe = results[1].data as Map<String, dynamic>?;
          _canEdit = _currentRecipe?['can_edit'] as bool? ?? false;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Failed to load version diff: $e';
          _isLoading = false;
        });
      }
    }
  }

  static const _fieldLabels = {
    'name': 'Name',
    'instructions': 'Instructions',
    'ingredients': 'Ingredients',
    'steps': 'Steps',
  };

  String _formatDate(String? isoDate) {
    if (isoDate == null) return '';
    try {
      final dt = DateTime.parse(isoDate).toLocal();
      return '${dt.month}/${dt.day}/${dt.year} at ${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
    } catch (_) {
      return isoDate;
    }
  }

  Color _diffColor(BuildContext context, _DiffType type) {
    final colorScheme = Theme.of(context).colorScheme;
    switch (type) {
      case _DiffType.added:
        return AppColors.successLight;
      case _DiffType.removed:
        return colorScheme.errorContainer.withValues(alpha: 0.5);
      case _DiffType.changed:
        return AppColors.warningLight;
      case _DiffType.unchanged:
        return Colors.transparent;
    }
  }

  Color _diffTextColor(BuildContext context, _DiffType type) {
    final colorScheme = Theme.of(context).colorScheme;
    switch (type) {
      case _DiffType.added:
        return AppColors.successDark;
      case _DiffType.removed:
        return colorScheme.onErrorContainer;
      case _DiffType.changed:
        return AppColors.warningDark;
      case _DiffType.unchanged:
        return colorScheme.onSurface;
    }
  }

  // ──────────────────────────────────────────────────────────────────
  // Diff helpers
  // ──────────────────────────────────────────────────────────────────

  List<Widget> _buildNameDiff(BuildContext context) {
    final snapshot = _snapshot!;
    final current = _currentRecipe!;
    final oldName = snapshot['name'] as String? ?? '';
    final newName = current['name'] as String? ?? '';
    if (oldName == newName) return [];
    return [
      _DiffRow(
        label: 'Before',
        text: oldName,
        diffType: _DiffType.removed,
        diffColor: _diffColor(context, _DiffType.removed),
        textColor: _diffTextColor(context, _DiffType.removed),
      ),
      const SizedBox(height: 4),
      _DiffRow(
        label: 'After',
        text: newName,
        diffType: _DiffType.added,
        diffColor: _diffColor(context, _DiffType.added),
        textColor: _diffTextColor(context, _DiffType.added),
      ),
    ];
  }

  List<Widget> _buildInstructionsDiff(BuildContext context) {
    final snapshot = _snapshot!;
    final current = _currentRecipe!;
    final oldText = snapshot['instructions'] as String? ?? '';
    final newText = current['instructions'] as String? ?? '';
    if (oldText == newText) return [];
    return [
      _DiffRow(
        label: 'Before',
        text: oldText.isEmpty ? '(none)' : oldText,
        diffType: _DiffType.removed,
        diffColor: _diffColor(context, _DiffType.removed),
        textColor: _diffTextColor(context, _DiffType.removed),
      ),
      const SizedBox(height: 4),
      _DiffRow(
        label: 'After',
        text: newText.isEmpty ? '(none)' : newText,
        diffType: _DiffType.added,
        diffColor: _diffColor(context, _DiffType.added),
        textColor: _diffTextColor(context, _DiffType.added),
      ),
    ];
  }

  List<Widget> _buildIngredientsDiff(BuildContext context) {
    final snapshot = _snapshot!;
    final current = _currentRecipe!;
    final snapshotIngredients =
        (snapshot['ingredients'] as List?) ?? [];
    final currentIngredients =
        (current['ingredients'] as List?) ?? [];

    // Index by ingredient_id
    final Map<String, dynamic> snapshotMap = {};
    for (final ing in snapshotIngredients) {
      final id = (ing as Map<String, dynamic>)['ingredient_id']?.toString();
      if (id != null) snapshotMap[id] = ing;
    }
    final Map<String, dynamic> currentMap = {};
    for (final ing in currentIngredients) {
      // Current recipe uses nested structure: { ingredient: { id, canonical_name }, ... }
      final ingData = ing as Map<String, dynamic>;
      final ingredientInfo = ingData['ingredient'] as Map<String, dynamic>?;
      final id = ingredientInfo?['id']?.toString() ??
          ingData['ingredient_id']?.toString();
      if (id != null) currentMap[id] = ingData;
    }

    final allIds = {...snapshotMap.keys, ...currentMap.keys};
    final widgets = <Widget>[];

    for (final id in allIds) {
      final inSnapshot = snapshotMap.containsKey(id);
      final inCurrent = currentMap.containsKey(id);

      if (inSnapshot && !inCurrent) {
        // Removed
        final ing = snapshotMap[id] as Map<String, dynamic>;
        widgets.add(_buildIngredientRow(
          context,
          '${ing['quantity_display'] ?? ''} ${ing['unit_display'] ?? ''} (ingredient removed)',
          _DiffType.removed,
        ));
      } else if (!inSnapshot && inCurrent) {
        // Added
        final ing = currentMap[id] as Map<String, dynamic>;
        final ingredientInfo = ing['ingredient'] as Map<String, dynamic>?;
        final name = ingredientInfo?['canonical_name'] ?? 'Unknown';
        widgets.add(_buildIngredientRow(
          context,
          '${ing['quantity_display'] ?? ''} ${ing['unit_display'] ?? ''} $name',
          _DiffType.added,
        ));
      } else if (inSnapshot && inCurrent) {
        // Compare quantity/unit
        final snap = snapshotMap[id] as Map<String, dynamic>;
        final curr = currentMap[id] as Map<String, dynamic>;
        final snapQty = snap['quantity_display']?.toString() ?? '';
        final snapUnit = snap['unit_display']?.toString() ?? '';
        final currQty = curr['quantity_display']?.toString() ?? '';
        final currUnit = curr['unit_display']?.toString() ?? '';
        final ingredientInfo = curr['ingredient'] as Map<String, dynamic>?;
        final name = ingredientInfo?['canonical_name'] ?? 'Unknown';
        if (snapQty != currQty || snapUnit != currUnit) {
          widgets.add(_buildIngredientRow(
            context,
            '$snapQty $snapUnit → $currQty $currUnit $name',
            _DiffType.changed,
          ));
        }
      }
    }

    return widgets;
  }

  Widget _buildIngredientRow(
      BuildContext context, String text, _DiffType type) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: _DiffRow(
        text: text,
        diffType: type,
        diffColor: _diffColor(context, type),
        textColor: _diffTextColor(context, type),
      ),
    );
  }

  List<Widget> _buildStepsDiff(BuildContext context) {
    final snapshot = _snapshot!;
    final current = _currentRecipe!;
    final snapshotSteps = (snapshot['steps'] as List?) ?? [];
    final currentSteps = (current['steps'] as List?) ?? [];

    // Index by step_number
    final Map<int, dynamic> snapshotMap = {};
    for (final step in snapshotSteps) {
      final num = (step as Map<String, dynamic>)['step_number'] as int?;
      if (num != null) snapshotMap[num] = step;
    }
    final Map<int, dynamic> currentMap = {};
    for (final step in currentSteps) {
      final num = (step as Map<String, dynamic>)['step_number'] as int?;
      if (num != null) currentMap[num] = step;
    }

    final allNums = {...snapshotMap.keys, ...currentMap.keys}.toList()..sort();
    final widgets = <Widget>[];

    for (final num in allNums) {
      final inSnapshot = snapshotMap.containsKey(num);
      final inCurrent = currentMap.containsKey(num);

      if (inSnapshot && !inCurrent) {
        final step = snapshotMap[num] as Map<String, dynamic>;
        widgets.add(_buildStepRow(
          context,
          num,
          step['instruction']?.toString() ?? '',
          _DiffType.removed,
        ));
      } else if (!inSnapshot && inCurrent) {
        final step = currentMap[num] as Map<String, dynamic>;
        widgets.add(_buildStepRow(
          context,
          num,
          step['instruction']?.toString() ?? '',
          _DiffType.added,
        ));
      } else if (inSnapshot && inCurrent) {
        final snapInstr =
            (snapshotMap[num] as Map<String, dynamic>)['instruction']
                    ?.toString() ??
                '';
        final currInstr =
            (currentMap[num] as Map<String, dynamic>)['instruction']
                    ?.toString() ??
                '';
        if (snapInstr != currInstr) {
          widgets.add(_buildStepRow(
              context, num, 'Before: $snapInstr', _DiffType.removed));
          widgets.add(_buildStepRow(
              context, num, 'After: $currInstr', _DiffType.added));
        }
      }
    }

    return widgets;
  }

  Widget _buildStepRow(
      BuildContext context, int stepNum, String text, _DiffType type) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: _DiffRow(
        label: 'Step $stepNum',
        text: text,
        diffType: type,
        diffColor: _diffColor(context, type),
        textColor: _diffTextColor(context, type),
      ),
    );
  }

  Future<void> _confirmRestore() async {
    final versionNum = widget.versionNumber;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Restore version?'),
        content: Text(
          'This will restore Version $versionNum as a new version. '
          'Your current recipe will be saved in the history.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Restore'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;

    setState(() => _isRestoring = true);
    try {
      await _apiClient.restoreRecipeVersion(widget.recipeId, widget.versionId);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Restored to Version $versionNum')),
        );
        context.go('/recipes/${widget.recipeId}');
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isRestoring = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Restore failed: $e'),
            backgroundColor: Theme.of(context).colorScheme.error,
          ),
        );
      }
    }
  }

  Widget _buildSection(
    BuildContext context, {
    required String title,
    required List<Widget> children,
  }) {
    if (children.isEmpty) return const SizedBox.shrink();
    final textTheme = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: textTheme.titleMedium),
        const SizedBox(height: 8),
        ...children,
        const SizedBox(height: 20),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final versionNum = widget.versionNumber;

    return Scaffold(
      appBar: AppBar(
        title: Text('Version $versionNum'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          _error!,
                          textAlign: TextAlign.center,
                          style:
                              TextStyle(color: colorScheme.onErrorContainer),
                        ),
                        const SizedBox(height: 16),
                        ElevatedButton(
                          onPressed: _loadData,
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                )
              : SingleChildScrollView(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Header: version info
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: colorScheme.surfaceContainerHighest,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Snapshot from Version $versionNum',
                              style: textTheme.titleSmall?.copyWith(
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              _formatDate(_createdAt),
                              style: textTheme.bodySmall?.copyWith(
                                color: colorScheme.onSurfaceVariant,
                              ),
                            ),
                            if (_changedFields.isNotEmpty) ...[
                              const SizedBox(height: 8),
                              Wrap(
                                spacing: 4,
                                runSpacing: 4,
                                children: _changedFields.map((field) {
                                  final isRestore = field.startsWith('restore:');
                                  if (isRestore) {
                                    final fromVersion = field.substring('restore:'.length);
                                    return Container(
                                      padding: const EdgeInsets.symmetric(
                                          horizontal: 8, vertical: 2),
                                      decoration: BoxDecoration(
                                        color: colorScheme.tertiaryContainer.withValues(alpha: 0.7),
                                        borderRadius: BorderRadius.circular(12),
                                      ),
                                      child: Row(
                                        mainAxisSize: MainAxisSize.min,
                                        children: [
                                          Icon(Icons.restore, size: 12, color: colorScheme.onTertiaryContainer),
                                          const SizedBox(width: 3),
                                          Text(
                                            'Restored from v$fromVersion',
                                            style: textTheme.labelSmall?.copyWith(
                                              color: colorScheme.onTertiaryContainer,
                                            ),
                                          ),
                                        ],
                                      ),
                                    );
                                  }
                                  final label = _fieldLabels[field] ?? field;
                                  return Container(
                                    padding: const EdgeInsets.symmetric(
                                        horizontal: 8, vertical: 2),
                                    decoration: BoxDecoration(
                                      color: colorScheme.primaryContainer
                                          .withValues(alpha: 0.5),
                                      borderRadius:
                                          BorderRadius.circular(12),
                                    ),
                                    child: Text(
                                      label,
                                      style: textTheme.labelSmall?.copyWith(
                                        color: colorScheme.onPrimaryContainer,
                                      ),
                                    ),
                                  );
                                }).toList(),
                              ),
                            ],
                          ],
                        ),
                      ),
                      const SizedBox(height: 20),

                      // Diff sections
                      if (_snapshot != null && _currentRecipe != null) ...[
                        if (_changedFields.contains('name'))
                          _buildSection(
                            context,
                            title: 'Name',
                            children: _buildNameDiff(context),
                          ),
                        if (_changedFields.contains('instructions'))
                          _buildSection(
                            context,
                            title: 'Instructions',
                            children: _buildInstructionsDiff(context),
                          ),
                        if (_changedFields.contains('ingredients'))
                          _buildSection(
                            context,
                            title: 'Ingredients',
                            children: _buildIngredientsDiff(context),
                          ),
                        if (_changedFields.contains('steps'))
                          _buildSection(
                            context,
                            title: 'Steps',
                            children: _buildStepsDiff(context),
                          ),
                        if (_changedFields.isEmpty ||
                            _changedFields.every((f) => f.startsWith('restore:')))
                          Center(
                            child: Padding(
                              padding: const EdgeInsets.all(24),
                              child: Text(
                                _changedFields.any((f) => f.startsWith('restore:'))
                                    ? 'This version was created by a restore operation.'
                                    : 'No changes tracked for this version.',
                                textAlign: TextAlign.center,
                                style: textTheme.bodyMedium?.copyWith(
                                  color: colorScheme.onSurfaceVariant,
                                ),
                              ),
                            ),
                          ),
                      ],

                      // Notes at this version (from snapshot)
                      Builder(builder: (context) {
                        final snapshotNotes = (_snapshot?['notes'] as List?) ?? [];
                        if (snapshotNotes.isEmpty) return const SizedBox.shrink();
                        return _buildSection(
                          context,
                          title: 'Notes at this version',
                          children: snapshotNotes.map<Widget>((note) {
                            final n = note as Map<String, dynamic>;
                            return Padding(
                              padding: const EdgeInsets.only(bottom: 8),
                              child: Container(
                                padding: const EdgeInsets.all(10),
                                decoration: BoxDecoration(
                                  color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(n['body'] as String, style: textTheme.bodyMedium),
                                    const SizedBox(height: 4),
                                    Text(
                                      _formatDate(n['created_at'] as String?),
                                      style: textTheme.labelSmall?.copyWith(
                                        color: colorScheme.onSurfaceVariant,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            );
                          }).toList(),
                        );
                      }),

                      const SizedBox(height: 32),

                      // Restore button — visible only to owners/editors
                      if (_canEdit) ...[
                        SizedBox(
                          width: double.infinity,
                          child: OutlinedButton.icon(
                            icon: _isRestoring
                                ? const SizedBox(
                                    width: 16,
                                    height: 16,
                                    child: CircularProgressIndicator(
                                        strokeWidth: 2),
                                  )
                                : const Icon(Icons.restore),
                            label: Text(
                                _isRestoring ? 'Restoring...' : 'Restore this version'),
                            onPressed: _isRestoring ? null : _confirmRestore,
                          ),
                        ),
                        const SizedBox(height: 16),
                      ],
                    ],
                  ),
                ),
    );
  }
}

class _DiffRow extends StatelessWidget {
  final String? label;
  final String text;
  final _DiffType diffType;
  final Color diffColor;
  final Color textColor;

  const _DiffRow({
    this.label,
    required this.text,
    required this.diffType,
    required this.diffColor,
    required this.textColor,
  });

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: diffColor,
        borderRadius: BorderRadius.circular(6),
      ),
      child: label != null
          ? RichText(
              text: TextSpan(
                style: textTheme.bodyMedium?.copyWith(color: textColor),
                children: [
                  TextSpan(
                    text: '$label: ',
                    style: const TextStyle(fontWeight: FontWeight.w600),
                  ),
                  TextSpan(text: text),
                ],
              ),
            )
          : Text(
              text,
              style: textTheme.bodyMedium?.copyWith(color: textColor),
            ),
    );
  }
}
