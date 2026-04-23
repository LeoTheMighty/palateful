import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import '../../../core/constants/inferable_fields.dart';
import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';
import '../../../core/services/error_reporter.dart';
import '../../../core/state/mutation_bus.dart';
import '../../../shared/widgets/error_banner.dart';
import '../../activity/widgets/import_activity_detail.dart';
import '../widgets/structured_ingredient_row.dart';
import 'ingredient_edits_mapping.dart';
import 'widgets/inferred_field_badge.dart';

class ImportItemReviewScreen extends StatefulWidget {
  final String itemId;

  const ImportItemReviewScreen({super.key, required this.itemId});

  @override
  State<ImportItemReviewScreen> createState() => _ImportItemReviewScreenState();
}

class _ImportItemReviewScreenState extends State<ImportItemReviewScreen> {
  final _apiClient = getIt<ApiClient>();

  // Loading state
  bool _isLoading = true;
  String? _error;
  String? _errorDetail;
  Map<String, dynamic>? _item;
  // Edit controllers
  final _nameController = TextEditingController();
  final _descriptionController = TextEditingController();
  final _prepTimeController = TextEditingController();
  final _cookTimeController = TextEditingController();
  final _servingsController = TextEditingController();
  final _instructionsController = TextEditingController();
  // Ingredients — structured shape. Parent owns the list; each entry
  // carries a stable localKey so StructuredIngredientRow's internal
  // controllers survive list-order mutations (add, delete+undo).
  final _ingredientRows = <_IngredientEntry>[];
  int _nextRowKey = 0;
  final _stepControllers = <TextEditingController>[];

  // Action state
  bool _isApproving = false;
  bool _isSaving = false;
  bool _hasEdits = false;
  Timer? _saveTimer;

  // efi-6 — local mutable set of field names the extractor best-guessed.
  // Rendered sparkles next to the 4 inferable field labels Review Import
  // actually edits (description, prep, cook, servings). A field leaves
  // the set on first value change; a 1500ms-debounced correction
  // dispatches to the audit endpoint on focus-loss. Network errors are
  // silent per design principle 14.
  Set<String> _inferredFields = <String>{};
  // Original extracted values, captured at load time, so `_onFieldEdited`
  // can tell a real edit ("value != original") from no-op setState cycles.
  final Map<String, Object?> _originalValues = {};
  // Per-field debounce timers for correction dispatch. Keyed by the
  // backend field name so the dispatch always sends the LATEST edit for
  // that field.
  final Map<String, Timer> _correctionTimers = {};

  @override
  void initState() {
    super.initState();
    _loadItem();
  }

  @override
  void dispose() {
    _nameController.dispose();
    _descriptionController.dispose();
    _prepTimeController.dispose();
    _cookTimeController.dispose();
    _servingsController.dispose();
    _instructionsController.dispose();
    for (final c in _stepControllers) {
      c.dispose();
    }
    _saveTimer?.cancel();
    for (final t in _correctionTimers.values) {
      t.cancel();
    }
    super.dispose();
  }

  Future<void> _loadItem() async {
    try {
      // ffm-10: review screen needs the heavy `parsed_recipe` blob
      // to render the editor. Opt in via the include param.
      final response = await _apiClient.getImportItem(
        widget.itemId,
        includeParsedRecipe: true,
      );
      if (!mounted) return;

      final item = response.data as Map<String, dynamic>;
      final parsed = item['parsed_recipe'] as Map<String, dynamic>?;
      final edits = item['user_edits'] as Map<String, dynamic>?;

      // Merge: user_edits override parsed_recipe
      final recipe = <String, dynamic>{};
      if (parsed != null) recipe.addAll(parsed);
      if (edits != null) recipe.addAll(edits);

      _populateControllers(recipe);

      // efi-6 — decode extractor-flagged inferred fields. The set is
      // mutable so edits can shrink it. The original values map lets
      // `_onFieldEdited` distinguish real edits from identity re-sets.
      _inferredFields = decodeInferredFields(item['inferred_fields']);
      _originalValues
        ..clear()
        ..['description'] = recipe['description']
        ..['prep_time_minutes'] = recipe['prep_time_minutes']
        ..['cook_time_minutes'] = recipe['cook_time_minutes']
        ..['servings'] = recipe['servings'];

      setState(() {
        _item = item;
        _isLoading = false;
      });
    } catch (e) {
      if (mounted) {
        setState(() {
          _isLoading = false;
          _error = 'Could not load import item.';
          _errorDetail = ErrorReporter.detail(e);
        });
      }
    }
  }

  void _populateControllers(Map<String, dynamic> recipe) {
    _nameController.text = recipe['name'] as String? ?? '';
    _descriptionController.text = recipe['description'] as String? ?? '';
    final prepTime = recipe['prep_time_minutes'];
    _prepTimeController.text = prepTime != null ? prepTime.toString() : '';
    final cookTime = recipe['cook_time_minutes'];
    _cookTimeController.text = cookTime != null ? cookTime.toString() : '';
    final servings = recipe['servings'];
    _servingsController.text = servings != null ? servings.toString() : '';
    _instructionsController.text = recipe['instructions'] as String? ?? '';

    // Build step controllers from steps array
    for (final c in _stepControllers) {
      c.dispose();
    }
    _stepControllers.clear();

    final steps = recipe['steps'] as List? ?? [];
    if (steps.isNotEmpty) {
      for (final step in steps) {
        final text = step is Map ? (step['instruction'] ?? '') : step.toString();
        _stepControllers.add(TextEditingController(text: text));
      }
    } else if (_instructionsController.text.isNotEmpty) {
      // Fallback: split instructions string into steps
      final parts = _instructionsController.text.split(RegExp(r'\d+\.\s+'));
      for (final part in parts) {
        final trimmed = part.trim();
        if (trimmed.isNotEmpty) {
          _stepControllers.add(TextEditingController(text: trimmed));
        }
      }
    }

    // Build ingredient row data from structured shape. When both `name`
    // and `text` are present, `name` wins — matches
    // create_recipe_task._create_recipe_ingredient precedence. Empty-only
    // rows still appear so the user can edit them.
    _ingredientRows.clear();
    final ingredients = recipe['ingredients'] as List? ?? [];
    for (final ing in ingredients) {
      _ingredientRows.add(_IngredientEntry(
        key: ValueKey('ing-${_nextRowKey++}'),
        data: ingredientDataFromJson(ing),
      ));
    }
  }

  void _onFieldChanged() {
    if (!_hasEdits) {
      setState(() => _hasEdits = true);
    }
    _debounceSave();
  }

  /// efi-6 — inferable-field edit handler. If the field was badged,
  /// drop the sparkle immediately (design principle 4: badge is derived
  /// state) and schedule a 1500ms-debounced correction dispatch with
  /// the latest value. `corrected` is the post-edit value (int for
  /// times / servings; string for description / cuisine / category /
  /// vibes). Reverting a field to its original value still counts as
  /// dismissal — the badge stays gone, and the correction dispatch
  /// just sends the original back (harmless side-channel write).
  void _onInferredFieldEdited(String field, Object? corrected) {
    if (_inferredFields.contains(field)) {
      setState(() => _inferredFields.remove(field));
    }
    _correctionTimers[field]?.cancel();
    _correctionTimers[field] = Timer(
      const Duration(milliseconds: 1500),
      () => _dispatchCorrection(field, corrected),
    );
  }

  Future<void> _dispatchCorrection(String field, Object? corrected) async {
    try {
      await _apiClient.submitImportCorrection(
        itemId: widget.itemId,
        field: field,
        corrected: corrected,
      );
    } catch (_) {
      // Silent side-channel write — design principle 14.
    }
  }

  /// efi-6 — wrap a label string in a row with a sparkle badge when the
  /// extractor inferred that field. Returns the raw string when the
  /// field isn't badged so `InputDecoration.labelText` stays idiomatic.
  InputDecoration _decorateInferable(String label, String field) {
    if (!_inferredFields.contains(field)) {
      return InputDecoration(
        labelText: label,
        border: const OutlineInputBorder(),
      );
    }
    return InputDecoration(
      label: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(label),
          const SizedBox(width: 4),
          const InferredFieldBadge(),
        ],
      ),
      border: const OutlineInputBorder(),
    );
  }

  void _debounceSave() {
    _saveTimer?.cancel();
    _saveTimer = Timer(const Duration(seconds: 2), _saveEdits);
  }

  Map<String, dynamic> _buildUserEdits() {
    // Serialize each row as {name, quantity, unit, notes, is_optional}.
    // Empty fields go over the wire as null (not ""); create_recipe_task
    // treats null as "no value supplied" and the extractor emits null too.
    // Drop rows that have no meaningful content at all (no name, qty, unit,
    // or notes) — they are empty placeholders the user never filled.
    final ingredients = <Map<String, dynamic>>[];
    for (final entry in _ingredientRows) {
      if (!ingredientRowHasContent(entry.data)) continue;
      ingredients.add(ingredientRowToUserEditJson(entry.data));
    }

    final steps = _stepControllers
        .asMap()
        .entries
        .where((e) => e.value.text.trim().isNotEmpty)
        .map((e) => {'instruction': e.value.text.trim(), 'order': e.key + 1})
        .toList();

    final edits = <String, dynamic>{
      'name': _nameController.text.trim(),
      'description': _descriptionController.text.trim(),
      'instructions': steps.map((s) => "${s['order']}. ${s['instruction']}").join('\n'),
      'steps': steps,
      'ingredients': ingredients,
    };

    final prepText = _prepTimeController.text.trim();
    edits['prep_time_minutes'] = prepText.isNotEmpty ? int.tryParse(prepText) : null;

    final cookText = _cookTimeController.text.trim();
    edits['cook_time_minutes'] = cookText.isNotEmpty ? int.tryParse(cookText) : null;

    final servingsText = _servingsController.text.trim();
    edits['servings'] = servingsText.isNotEmpty ? int.tryParse(servingsText) : null;

    return edits;
  }

  Future<void> _saveEdits() async {
    if (_isSaving) return;
    setState(() => _isSaving = true);

    try {
      await _apiClient.updateImportItem(widget.itemId, _buildUserEdits());
    } catch (_) {
      // Silent save — don't disrupt editing
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }

  Future<void> _approve() async {
    if (_isApproving) return;

    // Cancel any pending debounce timer and save edits
    _saveTimer?.cancel();
    if (_hasEdits) {
      await _saveEdits();
    }

    setState(() => _isApproving = true);
    try {
      HapticFeedback.selectionClick();
      await _apiClient.approveImportItem(widget.itemId);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Recipe imported successfully!')),
        );
        context.pop(true);
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isApproving = false);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not approve recipe.')),
        );
      }
    }
  }

  Future<void> _dismiss() async {
    try {
      await _apiClient.skipImportItem(widget.itemId);
      // Skipping is semantically a dismissal from the user's perspective:
      // the item leaves Needs Review and lands in Skipped. Emit on the
      // MutationBus so the Imports tab (and any see-all / activity-read
      // subscriber) refreshes without waiting for the 30s tick.
      emitMutation(ImportItemDismissed(
        itemId: widget.itemId,
        item: null,
        jobDismissed: false,
      ));
      if (mounted) context.pop(false);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not dismiss item.')),
        );
      }
    }
  }

  void _addIngredient() {
    setState(() {
      _ingredientRows.add(_IngredientEntry(
        key: ValueKey('ing-${_nextRowKey++}'),
        data: const IngredientRowData(),
      ));
    });
    _onFieldChanged();
  }

  void _updateIngredient(int index, IngredientRowData next) {
    // Fast path: avoid setState when nothing structurally changed (only
    // per-row internal controller updates matter). Still emit edit-event.
    _ingredientRows[index] =
        _ingredientRows[index].copyWith(data: next);
    _onFieldChanged();
  }

  void _removeIngredient(int index) {
    final removed = _ingredientRows[index];
    setState(() {
      _ingredientRows.removeAt(index);
    });
    _onFieldChanged();
    final messenger = ScaffoldMessenger.of(context);
    messenger.clearSnackBars();
    messenger.showSnackBar(
      SnackBar(
        duration: const Duration(seconds: 3),
        content: const Text('Ingredient removed.'),
        action: SnackBarAction(
          label: 'UNDO',
          onPressed: () {
            if (!mounted) return;
            setState(() {
              final target = index.clamp(0, _ingredientRows.length);
              _ingredientRows.insert(target, removed);
            });
            _onFieldChanged();
          },
        ),
      ),
    );
  }

  bool _showRawJson = false;

  Widget _buildRawJsonSection(ColorScheme colorScheme, TextTheme textTheme) {
    final parsed = _item?['parsed_recipe'] as Map<String, dynamic>?;
    if (parsed == null) return const SizedBox.shrink();

    final encoder = const JsonEncoder.withIndent('  ');
    final jsonString = encoder.convert(parsed);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        InkWell(
          onTap: () => setState(() => _showRawJson = !_showRawJson),
          child: Row(
            children: [
              Icon(
                Icons.data_object,
                size: 18,
                color: colorScheme.onSurfaceVariant,
              ),
              const SizedBox(width: 8),
              Text(
                'Extracted Recipe Data',
                style: textTheme.titleSmall?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                ),
              ),
              const Spacer(),
              Icon(
                _showRawJson ? Icons.expand_less : Icons.expand_more,
                size: 20,
                color: colorScheme.onSurfaceVariant,
              ),
            ],
          ),
        ),
        if (_showRawJson) ...[
          const SizedBox(height: 8),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: colorScheme.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Stack(
              children: [
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: SelectableText(
                    jsonString,
                    style: TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 11,
                      color: colorScheme.onSurface,
                      height: 1.5,
                    ),
                  ),
                ),
                Positioned(
                  top: 0,
                  right: 0,
                  child: IconButton(
                    icon: Icon(Icons.copy, size: 16, color: colorScheme.onSurfaceVariant),
                    tooltip: 'Copy JSON',
                    onPressed: () {
                      Clipboard.setData(ClipboardData(text: jsonString));
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Copied to clipboard')),
                      );
                    },
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(),
                    visualDensity: VisualDensity.compact,
                  ),
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Review Import'),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => context.pop(),
        ),
        actions: [
          if (_isSaving)
            const Padding(
              padding: EdgeInsets.all(16),
              child: SizedBox(
                width: 16,
                height: 16,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            )
          else if (_hasEdits)
            Padding(
              padding: const EdgeInsets.all(16),
              child: Icon(Icons.check, size: 16, color: colorScheme.primary),
            ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _buildError(colorScheme)
              : _item?['status'] == 'failed'
                  ? _buildFailedView(colorScheme)
                  : _buildEditForm(colorScheme),
    );
  }

  Widget _buildError(ColorScheme colorScheme) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
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
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: () {
                setState(() {
                  _isLoading = true;
                  _error = null;
                });
                _loadItem();
              },
              child: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFailedView(ColorScheme colorScheme) {
    final item = _item ?? const <String, dynamic>{};

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        ImportActivityDetail(item: item),
        const SizedBox(height: 24),
        Center(
          child: FilledButton(
            onPressed: _dismiss,
            child: const Text('Dismiss'),
          ),
        ),
      ],
    );
  }

  Widget _buildEditForm(ColorScheme colorScheme) {
    final textTheme = Theme.of(context).textTheme;
    final item = _item ?? const <String, dynamic>{};

    return Column(
      children: [
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              // Hierarchical detail header (error → stage → source →
              // timestamps → retry). Replaces the old one-liner source row.
              ImportActivityDetail(item: item),
              const SizedBox(height: 16),

              // Recipe name
              TextField(
                controller: _nameController,
                decoration: const InputDecoration(
                  labelText: 'Recipe Name',
                  border: OutlineInputBorder(),
                ),
                onChanged: (_) => _onFieldChanged(),
              ),
              const SizedBox(height: 16),

              // Description
              TextField(
                controller: _descriptionController,
                decoration: _decorateInferable('Description', 'description'),
                maxLines: 3,
                onChanged: (v) {
                  _onFieldChanged();
                  _onInferredFieldEdited('description', v);
                },
              ),
              const SizedBox(height: 16),

              // Metadata row
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _prepTimeController,
                      decoration: _decorateInferable(
                        'Prep (min)',
                        'prep_time_minutes',
                      ),
                      keyboardType: TextInputType.number,
                      onChanged: (v) {
                        _onFieldChanged();
                        _onInferredFieldEdited(
                          'prep_time_minutes',
                          int.tryParse(v),
                        );
                      },
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextField(
                      controller: _cookTimeController,
                      decoration: _decorateInferable(
                        'Cook (min)',
                        'cook_time_minutes',
                      ),
                      keyboardType: TextInputType.number,
                      onChanged: (v) {
                        _onFieldChanged();
                        _onInferredFieldEdited(
                          'cook_time_minutes',
                          int.tryParse(v),
                        );
                      },
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextField(
                      controller: _servingsController,
                      decoration: _decorateInferable('Servings', 'servings'),
                      keyboardType: TextInputType.number,
                      onChanged: (v) {
                        _onFieldChanged();
                        _onInferredFieldEdited('servings', int.tryParse(v));
                      },
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 24),

              // Ingredients — structured rows. See StructuredIngredientRow
              // for layout + fraction-parsing behavior.
              Text(
                'Ingredients (${_ingredientRows.length})',
                style: textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 8),
              ...List.generate(_ingredientRows.length, (i) {
                final entry = _ingredientRows[i];
                return Padding(
                  key: entry.key,
                  padding: const EdgeInsets.only(bottom: 12),
                  child: StructuredIngredientRow(
                    value: entry.data,
                    onChanged: (next) => _updateIngredient(i, next),
                    onDeleteRequested: () => _removeIngredient(i),
                  ),
                );
              }),
              Center(
                child: TextButton.icon(
                  onPressed: _addIngredient,
                  icon: const Icon(Icons.add, size: 18),
                  label: const Text('Add Ingredient'),
                ),
              ),
              const SizedBox(height: 24),

              // Steps
              Text(
                'Steps (${_stepControllers.length})',
                style: textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 8),
              ..._stepControllers.asMap().entries.map((entry) {
                final idx = entry.key;
                final controller = entry.value;
                return Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Padding(
                        padding: const EdgeInsets.only(top: 14),
                        child: Text(
                          '${idx + 1}.',
                          style: textTheme.titleSmall?.copyWith(
                            fontWeight: FontWeight.bold,
                            color: colorScheme.primary,
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: TextField(
                          controller: controller,
                          decoration: InputDecoration(
                            hintText: 'Step ${idx + 1}...',
                            border: const OutlineInputBorder(),
                            suffixIcon: IconButton(
                              icon: const Icon(Icons.remove_circle_outline, size: 20),
                              onPressed: () {
                                setState(() {
                                  _stepControllers[idx].dispose();
                                  _stepControllers.removeAt(idx);
                                  _onFieldChanged();
                                });
                              },
                            ),
                          ),
                          maxLines: 3,
                          onChanged: (_) => _onFieldChanged(),
                        ),
                      ),
                    ],
                  ),
                );
              }),
              Center(
                child: TextButton.icon(
                  onPressed: () {
                    setState(() {
                      _stepControllers.add(TextEditingController());
                    });
                    _onFieldChanged();
                  },
                  icon: const Icon(Icons.add, size: 18),
                  label: const Text('Add Step'),
                ),
              ),
              const SizedBox(height: 24),

              // Raw extracted recipe JSON (debug)
              _buildRawJsonSection(colorScheme, textTheme),
              const SizedBox(height: 32),
            ],
          ),
        ),

        // Bottom action bar
        SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                OutlinedButton(
                  onPressed: _isApproving ? null : _dismiss,
                  child: const Text('Dismiss'),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: FilledButton.icon(
                    onPressed: _isApproving ? null : _approve,
                    icon: _isApproving
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.check),
                    label: const Text('Save Recipe'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _IngredientEntry {
  _IngredientEntry({required this.key, required this.data});
  final ValueKey<String> key;
  final IngredientRowData data;

  _IngredientEntry copyWith({IngredientRowData? data}) =>
      _IngredientEntry(key: key, data: data ?? this.data);
}

