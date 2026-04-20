import 'dart:async';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';
import '../../core/constants/inferable_fields.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../core/services/error_reporter.dart';
import '../../core/utils/fraction_parser.dart';
import '../../shared/widgets/error_banner.dart';
import 'add_recipe/ingredient_edits_mapping.dart';
import 'add_recipe/widgets/inferred_field_badge.dart';
import 'widgets/structured_ingredient_row.dart';

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
  String? _errorDetail;

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
  String? _imageUrl;
  bool _isUploadingPhoto = false;
  List<Map<String, dynamic>> _steps = [];
  final List<TextEditingController> _stepControllers = [];
  List<String> _tags = [];

  // Ingredients — new section added by bugs-imp-ing-4. Rows carry a
  // stable local id so StructuredIngredientRow's internal controllers
  // survive list mutations (add / delete / undo) without leaking.
  final List<_IngredientEntry> _ingredientRows = [];
  int _nextIngredientKey = 0;

  // efi-7 — local mutable inference set. Read from `recipes.inferred_fields`
  // via GetRecipe and shrunken on save via UpdateRecipe. Edits shrink the
  // set locally; save sends the shrunken state. Correction dispatch is
  // deliberately NOT wired here (design principle 9) — the side-channel
  // endpoint is Review-Import-only in v1.
  Set<String> _inferredFields = <String>{};

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
      _imageUrl = data['image_url'] as String?;
      _tags = List<String>.from(data['tags'] ?? []);
      _inferredFields = decodeInferredFields(data['inferred_fields']);

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

      // Hydrate ingredient rows. The GET response exposes
      // `quantity_display` as a formatted string (e.g., "1 1/2") — parse
      // back to a numeric value with fraction_parser so the row editor's
      // format → parse → format round-trip is lossless. Legacy rows that
      // only have `ingredient.canonical_name` populate the Name field and
      // leave qty/unit/notes empty (no data loss).
      _ingredientRows.clear();
      final rawIngredients = data['ingredients'] as List? ?? [];
      for (final raw in rawIngredients) {
        if (raw is! Map) continue;
        final map = Map<String, dynamic>.from(raw);
        _ingredientRows.add(_IngredientEntry(
          key: ValueKey('edit-ing-${_nextIngredientKey++}'),
          data: ingredientRowFromGetRecipe(map, parseQty: parseFraction),
        ));
      }

      setState(() => _isLoading = false);
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Failed to load recipe. Please try again.';
          _errorDetail = ErrorReporter.detail(e);
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

  /// efi-7 — shrink the local inference set when the user edits a
  /// badged field. No dispatch (design principle 9). UpdateRecipe on
  /// save carries the shrunken list to the server, which enforces
  /// new ⊆ stored at the endpoint level.
  void _dismissInferred(String field) {
    if (_inferredFields.contains(field)) {
      setState(() => _inferredFields.remove(field));
    }
  }

  /// efi-7 — wrap a label string in a row with a sparkle badge when the
  /// extractor inferred the field. Preserves the caller-supplied
  /// suffixText (e.g., 'min' on prep/cook fields) so the screen's styling
  /// is unchanged for non-badged fields.
  InputDecoration _decorateInferable(
    String label,
    String field, {
    String? suffixText,
  }) {
    if (!_inferredFields.contains(field)) {
      return InputDecoration(labelText: label, suffixText: suffixText);
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
      suffixText: suffixText,
    );
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

      // Build ingredient payload: existing rows keep their ingredient_id
      // (so the backend doesn't rerun find-or-create on a name typo);
      // net-new rows send just {name, quantity, unit, notes, is_optional}
      // and let resolve_ingredient create the canonical row.
      final ingredientPayloads = <Map<String, dynamic>>[
        for (final entry in _ingredientRows)
          if (ingredientRowHasContent(entry.data))
            ingredientRowToEditSavePayload(entry.data),
      ];

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
        'ingredients': ingredientPayloads,
        // efi-7 — shrink-only. Server enforces new ⊆ stored.
        'inferred_fields': _inferredFields.toList(),
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
          const SnackBar(content: Text('Failed to save. Please try again.')),
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

  void _updateIngredientRow(int index, IngredientRowData next) {
    _ingredientRows[index] = _ingredientRows[index].copyWith(data: next);
    _scheduleSave();
  }

  void _addIngredientRow() {
    setState(() {
      _ingredientRows.add(_IngredientEntry(
        key: ValueKey('edit-ing-${_nextIngredientKey++}'),
        data: const IngredientRowData(),
      ));
    });
    _scheduleSave();
  }

  void _removeIngredientRow(int index) {
    final removed = _ingredientRows[index];
    setState(() => _ingredientRows.removeAt(index));
    _scheduleSave();
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
            _scheduleSave();
          },
        ),
      ),
    );
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

  Future<void> _pickAndUploadPhoto() async {
    final source = await showModalBottomSheet<ImageSource>(
      context: context,
      builder: (context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ListTile(
                leading: const Icon(Icons.camera_alt),
                title: const Text('Take Photo'),
                onTap: () => Navigator.pop(context, ImageSource.camera),
              ),
              ListTile(
                leading: const Icon(Icons.photo_library),
                title: const Text('Choose from Gallery'),
                onTap: () => Navigator.pop(context, ImageSource.gallery),
              ),
            ],
          ),
        ),
      ),
    );

    if (source == null) return;

    try {
      final image = await ImagePicker().pickImage(
        source: source,
        maxWidth: 2048,
        maxHeight: 2048,
        imageQuality: 85,
      );
      if (image == null) return;

      setState(() => _isUploadingPhoto = true);

      final bytes = await image.readAsBytes();
      final uploadUrlResponse = await _apiClient.getRecipePhotoUploadUrl(
        widget.recipeId,
        image.name,
      );
      final uploadUrl = uploadUrlResponse.data['upload_url'] as String;
      final contentType = uploadUrlResponse.data['content_type'] as String;
      final imageUrl = uploadUrlResponse.data['image_url'] as String;

      final uploadResponse = await http.put(
        Uri.parse(uploadUrl),
        headers: {'Content-Type': contentType},
        body: bytes,
      );

      if (uploadResponse.statusCode == 200) {
        await _apiClient.updateRecipe(widget.recipeId, {'image_url': imageUrl});
        if (mounted) {
          setState(() {
            _imageUrl = imageUrl;
            _isUploadingPhoto = false;
          });
        }
      } else {
        throw Exception('Upload failed');
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isUploadingPhoto = false);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not upload photo. Please try again.')),
        );
      }
    }
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
                      // Photo section
                      GestureDetector(
                        onTap: _isUploadingPhoto ? null : _pickAndUploadPhoto,
                        child: Container(
                          height: 180,
                          width: double.infinity,
                          decoration: BoxDecoration(
                            color: colorScheme.surfaceContainerHighest,
                            borderRadius: BorderRadius.circular(16),
                            border: Border.all(color: colorScheme.outlineVariant),
                          ),
                          clipBehavior: Clip.antiAlias,
                          child: _isUploadingPhoto
                              ? Center(
                                  child: Column(
                                    mainAxisAlignment: MainAxisAlignment.center,
                                    children: [
                                      const CircularProgressIndicator(strokeWidth: 2),
                                      const SizedBox(height: 12),
                                      Text(
                                        'Uploading photo...',
                                        style: textTheme.bodySmall?.copyWith(
                                          color: colorScheme.onSurfaceVariant,
                                        ),
                                      ),
                                    ],
                                  ),
                                )
                              : _imageUrl != null
                                  ? Stack(
                                      fit: StackFit.expand,
                                      children: [
                                        CachedNetworkImage(
                                          imageUrl: _imageUrl!,
                                          fit: BoxFit.cover,
                                          placeholder: (context, url) => Center(
                                            child: CircularProgressIndicator(
                                              strokeWidth: 2,
                                              color: colorScheme.onSurfaceVariant,
                                            ),
                                          ),
                                          errorWidget: (context, url, error) => Icon(
                                            Icons.restaurant,
                                            size: 48,
                                            color: colorScheme.onSurfaceVariant,
                                          ),
                                        ),
                                        Positioned(
                                          bottom: 8,
                                          right: 8,
                                          child: Container(
                                            padding: const EdgeInsets.all(8),
                                            decoration: BoxDecoration(
                                              color: colorScheme.surface.withValues(alpha: 0.8),
                                              borderRadius: BorderRadius.circular(8),
                                            ),
                                            child: Icon(
                                              Icons.edit,
                                              size: 20,
                                              color: colorScheme.onSurface,
                                            ),
                                          ),
                                        ),
                                      ],
                                    )
                                  : Center(
                                      child: Column(
                                        mainAxisAlignment: MainAxisAlignment.center,
                                        children: [
                                          Icon(
                                            Icons.add_a_photo_outlined,
                                            size: 48,
                                            color: colorScheme.onSurfaceVariant,
                                          ),
                                          const SizedBox(height: 8),
                                          Text(
                                            'Tap to add photo',
                                            style: textTheme.bodySmall?.copyWith(
                                              color: colorScheme.onSurfaceVariant,
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                        ),
                      ),
                      const SizedBox(height: 16),

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
                        decoration: _decorateInferable(
                          'Description (optional)',
                          'description',
                        ),
                        maxLines: 3,
                        textCapitalization: TextCapitalization.sentences,
                        onChanged: (_) {
                          _dismissInferred('description');
                          _scheduleSave();
                        },
                      ),
                      const SizedBox(height: 16),

                      // Time inputs
                      Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: _prepTimeController,
                              decoration: _decorateInferable(
                                'Prep time',
                                'prep_time_minutes',
                                suffixText: 'min',
                              ),
                              keyboardType: TextInputType.number,
                              onChanged: (_) {
                                _dismissInferred('prep_time_minutes');
                                _scheduleSave();
                              },
                            ),
                          ),
                          const SizedBox(width: 16),
                          Expanded(
                            child: TextField(
                              controller: _cookTimeController,
                              decoration: _decorateInferable(
                                'Cook time',
                                'cook_time_minutes',
                                suffixText: 'min',
                              ),
                              keyboardType: TextInputType.number,
                              onChanged: (_) {
                                _dismissInferred('cook_time_minutes');
                                _scheduleSave();
                              },
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),

                      // Servings
                      TextField(
                        controller: _servingsController,
                        decoration: _decorateInferable('Servings', 'servings'),
                        keyboardType: TextInputType.number,
                        onChanged: (_) {
                          _dismissInferred('servings');
                          _scheduleSave();
                        },
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

                      // Ingredients section (new in bugs-imp-ing-4 —
                      // previously this screen had no ingredient editor
                      // at all).
                      Text('Ingredients', style: textTheme.titleMedium),
                      const SizedBox(height: 8),
                      ..._ingredientRows.asMap().entries.map((entry) {
                        final idx = entry.key;
                        final e = entry.value;
                        return Padding(
                          key: e.key,
                          padding: const EdgeInsets.only(bottom: 12),
                          child: StructuredIngredientRow(
                            value: e.data,
                            onChanged: (v) => _updateIngredientRow(idx, v),
                            onDeleteRequested: () => _removeIngredientRow(idx),
                          ),
                        );
                      }),
                      Center(
                        child: TextButton.icon(
                          onPressed: _addIngredientRow,
                          icon: const Icon(Icons.add),
                          label: const Text('Add Ingredient'),
                        ),
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

class _IngredientEntry {
  _IngredientEntry({required this.key, required this.data});
  final ValueKey<String> key;
  final IngredientRowData data;

  _IngredientEntry copyWith({IngredientRowData? data}) =>
      _IngredientEntry(key: key, data: data ?? this.data);
}

