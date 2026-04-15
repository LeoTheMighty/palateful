import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';
import '../../../core/services/error_reporter.dart';
import '../../../shared/widgets/error_banner.dart';

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
  final _ingredientControllers = <TextEditingController>[];
  final _stepControllers = <TextEditingController>[];

  // Action state
  bool _isApproving = false;
  bool _isSaving = false;
  bool _hasEdits = false;
  Timer? _saveTimer;

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
    for (final c in _ingredientControllers) {
      c.dispose();
    }
    _saveTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadItem() async {
    try {
      final response = await _apiClient.getImportItem(widget.itemId);
      if (!mounted) return;

      final item = response.data as Map<String, dynamic>;
      final parsed = item['parsed_recipe'] as Map<String, dynamic>?;
      final edits = item['user_edits'] as Map<String, dynamic>?;

      // Merge: user_edits override parsed_recipe
      final recipe = <String, dynamic>{};
      if (parsed != null) recipe.addAll(parsed);
      if (edits != null) recipe.addAll(edits);

      _populateControllers(recipe);

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

    // Build ingredient controllers
    for (final c in _ingredientControllers) {
      c.dispose();
    }
    _ingredientControllers.clear();

    final ingredients = recipe['ingredients'] as List? ?? [];
    for (final ing in ingredients) {
      final text = ing is Map ? (ing['text'] ?? '') : ing.toString();
      _ingredientControllers.add(TextEditingController(text: text));
    }
  }

  void _onFieldChanged() {
    if (!_hasEdits) {
      setState(() => _hasEdits = true);
    }
    _debounceSave();
  }

  void _debounceSave() {
    _saveTimer?.cancel();
    _saveTimer = Timer(const Duration(seconds: 2), _saveEdits);
  }

  Map<String, dynamic> _buildUserEdits() {
    final ingredients = _ingredientControllers
        .map((c) => c.text.trim())
        .where((t) => t.isNotEmpty)
        .map((t) => {'text': t})
        .toList();

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
      _ingredientControllers.add(TextEditingController());
    });
    _onFieldChanged();
  }

  void _removeIngredient(int index) {
    setState(() {
      _ingredientControllers[index].dispose();
      _ingredientControllers.removeAt(index);
    });
    _onFieldChanged();
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
    final textTheme = Theme.of(context).textTheme;
    final errorMessage = _item?['error_message'] as String? ?? 'Unknown error';
    final sourceUrl = _item?['source_url'] as String? ?? '';

    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.error_outline, size: 64, color: colorScheme.error),
          const SizedBox(height: 16),
          Text(
            'Import Failed',
            style: textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          if (sourceUrl.isNotEmpty) ...[
            Text(
              sourceUrl,
              style: textTheme.bodySmall?.copyWith(color: colorScheme.outline),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),
          ],
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: colorScheme.errorContainer,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              errorMessage,
              style: TextStyle(color: colorScheme.onErrorContainer),
              textAlign: TextAlign.center,
            ),
          ),
          const SizedBox(height: 24),
          FilledButton(
            onPressed: _dismiss,
            child: const Text('Dismiss'),
          ),
        ],
      ),
    );
  }

  Widget _buildEditForm(ColorScheme colorScheme) {
    final textTheme = Theme.of(context).textTheme;
    final sourceUrl = _item?['source_url'] as String? ?? '';

    return Column(
      children: [
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              // Source info
              if (sourceUrl.isNotEmpty) ...[
                Text(
                  'Source: $sourceUrl',
                  style: textTheme.bodySmall?.copyWith(color: colorScheme.outline),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 16),
              ],

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
                decoration: const InputDecoration(
                  labelText: 'Description',
                  border: OutlineInputBorder(),
                ),
                maxLines: 3,
                onChanged: (_) => _onFieldChanged(),
              ),
              const SizedBox(height: 16),

              // Metadata row
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _prepTimeController,
                      decoration: const InputDecoration(
                        labelText: 'Prep (min)',
                        border: OutlineInputBorder(),
                      ),
                      keyboardType: TextInputType.number,
                      onChanged: (_) => _onFieldChanged(),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextField(
                      controller: _cookTimeController,
                      decoration: const InputDecoration(
                        labelText: 'Cook (min)',
                        border: OutlineInputBorder(),
                      ),
                      keyboardType: TextInputType.number,
                      onChanged: (_) => _onFieldChanged(),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextField(
                      controller: _servingsController,
                      decoration: const InputDecoration(
                        labelText: 'Servings',
                        border: OutlineInputBorder(),
                      ),
                      keyboardType: TextInputType.number,
                      onChanged: (_) => _onFieldChanged(),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 24),

              // Ingredients
              Text(
                'Ingredients (${_ingredientControllers.length})',
                style: textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 8),
              ...List.generate(_ingredientControllers.length, (i) {
                return Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _ingredientControllers[i],
                          decoration: InputDecoration(
                            hintText: 'e.g. 2 cups flour',
                            border: const OutlineInputBorder(),
                            isDense: true,
                            contentPadding: const EdgeInsets.symmetric(
                              horizontal: 12,
                              vertical: 10,
                            ),
                            suffixIcon: IconButton(
                              icon: Icon(Icons.remove_circle_outline,
                                  size: 20, color: colorScheme.error),
                              onPressed: () => _removeIngredient(i),
                            ),
                          ),
                          onChanged: (_) => _onFieldChanged(),
                        ),
                      ),
                    ],
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
