import 'dart:async';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';

class EditRecipeScreen extends StatefulWidget {
  final String recipeId;

  const EditRecipeScreen({super.key, required this.recipeId});

  @override
  State<EditRecipeScreen> createState() => _EditRecipeScreenState();
}

class _EditRecipeScreenState extends State<EditRecipeScreen> {
  final _apiClient = getIt<ApiClient>();
  bool _isLoading = true;
  String? _error;

  // Save state
  Timer? _debounceTimer;
  bool _isSaving = false;
  bool _hasSaved = false;
  bool _hasUnsavedChanges = false;

  // Form controllers
  final _nameController = TextEditingController();
  final _descriptionController = TextEditingController();
  final _prepTimeController = TextEditingController();
  final _cookTimeController = TextEditingController();
  final _servingsController = TextEditingController();
  final _sourceUrlController = TextEditingController();
  final _tagController = TextEditingController();

  // Form data
  List<Map<String, dynamic>> _steps = [];
  final List<TextEditingController> _stepControllers = [];
  List<String> _tags = [];

  @override
  void initState() {
    super.initState();
    _loadRecipe();
  }

  @override
  void dispose() {
    _debounceTimer?.cancel();
    // Fire-and-forget final save if there are pending changes.
    // Context is gone so errors are silently dropped — acceptable tradeoff.
    if (_hasUnsavedChanges) {
      unawaited(_saveNow());
    }
    _nameController.dispose();
    _descriptionController.dispose();
    _prepTimeController.dispose();
    _cookTimeController.dispose();
    _servingsController.dispose();
    _sourceUrlController.dispose();
    _tagController.dispose();
    for (final c in _stepControllers) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _loadRecipe() async {
    try {
      final response = await _apiClient.getRecipe(widget.recipeId);
      if (!mounted) return;

      final data = response.data;
      _nameController.text = data['name'] ?? '';
      _descriptionController.text = data['description'] ?? '';
      _prepTimeController.text = data['prep_time']?.toString() ?? '';
      _cookTimeController.text = data['cook_time']?.toString() ?? '';
      _servingsController.text = data['servings']?.toString() ?? '';
      _sourceUrlController.text = data['source_url'] ?? '';
      _tags = List<String>.from(data['tags'] ?? []);

      final stepsData = data['steps'] as List? ?? [];
      _steps = stepsData.map((s) => Map<String, dynamic>.from(s)).toList();
      // Sort by step_number
      _steps.sort((a, b) =>
          (a['step_number'] as int? ?? 0).compareTo(b['step_number'] as int? ?? 0));

      for (final step in _steps) {
        _stepControllers.add(
          TextEditingController(text: step['instruction'] ?? ''),
        );
      }

      setState(() => _isLoading = false);
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Failed to load recipe: $e';
          _isLoading = false;
        });
      }
    }
  }

  void _scheduleSave() {
    _hasUnsavedChanges = true;
    _debounceTimer?.cancel();
    _debounceTimer = Timer(const Duration(seconds: 2), _saveNow);
    if (mounted) {
      setState(() {
        _hasSaved = false;
      });
    }
  }

  Future<void> _saveNow() async {
    if (_isSaving) return;
    _isSaving = true;
    _hasUnsavedChanges = false;

    if (mounted) setState(() {});

    try {
      final structuredSteps = _steps.asMap().entries.map((e) => {
            'step_number': e.key + 1,
            'instruction': e.value['instruction'] ?? '',
          }).toList();

      final data = {
        'name': _nameController.text,
        'description': _descriptionController.text.isEmpty
            ? null
            : _descriptionController.text,
        'prep_time': int.tryParse(_prepTimeController.text),
        'cook_time': int.tryParse(_cookTimeController.text),
        'servings': int.tryParse(_servingsController.text),
        'source_url': _sourceUrlController.text.isEmpty
            ? null
            : _sourceUrlController.text,
        'tags': _tags,
        'steps': structuredSteps,
      };

      await _apiClient.updateRecipe(widget.recipeId, data);

      if (mounted) {
        setState(() {
          _isSaving = false;
          _hasSaved = true;
        });
      }
    } catch (e) {
      _isSaving = false;
      if (mounted) {
        setState(() {});
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to save: $e')),
        );
      }
    }
  }

  void _addStep() {
    setState(() {
      _steps.add({'instruction': ''});
      _stepControllers.add(TextEditingController());
    });
    _scheduleSave();
  }

  void _removeStep(int index) {
    _stepControllers[index].dispose();
    _stepControllers.removeAt(index);
    setState(() {
      _steps.removeAt(index);
    });
    _scheduleSave();
  }

  void _onStepChanged(int index, String text) {
    _steps[index] = {..._steps[index], 'instruction': text};
    _scheduleSave();
  }

  void _onReorderSteps(int oldIndex, int newIndex) {
    if (newIndex > oldIndex) newIndex--;
    setState(() {
      final step = _steps.removeAt(oldIndex);
      _steps.insert(newIndex, step);
      final ctrl = _stepControllers.removeAt(oldIndex);
      _stepControllers.insert(newIndex, ctrl);
    });
    _scheduleSave();
  }

  void _addTag() {
    final text = _tagController.text.trim();
    if (text.isEmpty || _tags.contains(text)) return;
    setState(() {
      _tags.add(text);
    });
    _tagController.clear();
    _scheduleSave();
  }

  void _removeTag(String tag) {
    setState(() {
      _tags.remove(tag);
    });
    _scheduleSave();
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
        title: const Text('Edit Recipe'),
        actions: [
          // Save status indicator
          Padding(
            padding: const EdgeInsets.only(right: 16),
            child: Center(
              child: _isSaving
                  ? Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        ),
                        const SizedBox(width: 6),
                        Text('Saving...',
                            style: textTheme.bodySmall?.copyWith(
                                color: colorScheme.onSurfaceVariant)),
                      ],
                    )
                  : _hasSaved
                      ? Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.check,
                                size: 16, color: colorScheme.tertiary),
                            const SizedBox(width: 4),
                            Text('Saved',
                                style: textTheme.bodySmall
                                    ?.copyWith(color: colorScheme.tertiary)),
                          ],
                        )
                      : const SizedBox.shrink(),
            ),
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text(_error!))
              : SingleChildScrollView(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Name
                      TextField(
                        controller: _nameController,
                        decoration: const InputDecoration(
                          labelText: 'Recipe Name',
                        ),
                        textCapitalization: TextCapitalization.words,
                        onChanged: (_) => _scheduleSave(),
                      ),
                      const SizedBox(height: 16),

                      // Description
                      TextField(
                        controller: _descriptionController,
                        decoration: const InputDecoration(
                          labelText: 'Description (optional)',
                        ),
                        maxLines: 3,
                        textCapitalization: TextCapitalization.sentences,
                        onChanged: (_) => _scheduleSave(),
                      ),
                      const SizedBox(height: 16),

                      // Time inputs
                      Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: _prepTimeController,
                              decoration: const InputDecoration(
                                labelText: 'Prep time',
                                suffixText: 'min',
                              ),
                              keyboardType: TextInputType.number,
                              onChanged: (_) => _scheduleSave(),
                            ),
                          ),
                          const SizedBox(width: 16),
                          Expanded(
                            child: TextField(
                              controller: _cookTimeController,
                              decoration: const InputDecoration(
                                labelText: 'Cook time',
                                suffixText: 'min',
                              ),
                              keyboardType: TextInputType.number,
                              onChanged: (_) => _scheduleSave(),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),

                      // Servings
                      TextField(
                        controller: _servingsController,
                        decoration: const InputDecoration(
                          labelText: 'Servings',
                        ),
                        keyboardType: TextInputType.number,
                        onChanged: (_) => _scheduleSave(),
                      ),
                      const SizedBox(height: 16),

                      // Source URL
                      TextField(
                        controller: _sourceUrlController,
                        decoration: const InputDecoration(
                          labelText: 'Source URL (optional)',
                          prefixIcon: Icon(Icons.link),
                        ),
                        keyboardType: TextInputType.url,
                        onChanged: (_) => _scheduleSave(),
                      ),
                      const SizedBox(height: 24),

                      // Steps section
                      Text('Steps', style: textTheme.titleMedium),
                      const SizedBox(height: 8),
                      ..._steps.asMap().entries.map((entry) {
                        final index = entry.key;
                        return Padding(
                          padding: const EdgeInsets.only(bottom: 12),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Container(
                                width: 32,
                                height: 32,
                                margin: const EdgeInsets.only(top: 8),
                                decoration: BoxDecoration(
                                  color: colorScheme.surfaceContainerHighest,
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: Center(
                                  child: Text(
                                    '${index + 1}',
                                    style: textTheme.bodyMedium?.copyWith(
                                      fontWeight: FontWeight.w600,
                                      color: colorScheme.secondary,
                                    ),
                                  ),
                                ),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: TextField(
                                  controller: _stepControllers[index],
                                  onChanged: (v) => _onStepChanged(index, v),
                                  decoration: InputDecoration(
                                    hintText: 'Step ${index + 1}...',
                                  ),
                                  maxLines: null,
                                  textCapitalization:
                                      TextCapitalization.sentences,
                                ),
                              ),
                              IconButton(
                                icon: const Icon(Icons.close, size: 20),
                                onPressed: () => _removeStep(index),
                                color: colorScheme.onSurfaceVariant,
                              ),
                            ],
                          ),
                        );
                      }),
                      Center(
                        child: TextButton.icon(
                          onPressed: _addStep,
                          icon: const Icon(Icons.add),
                          label: const Text('Add Step'),
                        ),
                      ),
                      const SizedBox(height: 24),

                      // Tags section
                      Text('Tags', style: textTheme.titleMedium),
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: _tagController,
                              decoration: const InputDecoration(
                                hintText: 'Add a tag...',
                                isDense: true,
                              ),
                              onSubmitted: (_) => _addTag(),
                            ),
                          ),
                          const SizedBox(width: 8),
                          IconButton(
                            onPressed: _addTag,
                            icon: const Icon(Icons.add),
                            style: IconButton.styleFrom(
                              backgroundColor: colorScheme.primary,
                              foregroundColor: colorScheme.onPrimary,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      if (_tags.isNotEmpty)
                        Wrap(
                          spacing: 8,
                          runSpacing: 4,
                          children: _tags
                              .map((tag) => InputChip(
                                    label: Text(tag),
                                    onDeleted: () => _removeTag(tag),
                                    backgroundColor:
                                        colorScheme.surfaceContainerHighest,
                                  ))
                              .toList(),
                        ),
                      const SizedBox(height: 48),
                    ],
                  ),
                ),
    );
  }
}
