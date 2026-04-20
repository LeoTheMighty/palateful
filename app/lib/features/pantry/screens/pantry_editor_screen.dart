import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';
import '../models/pantry_ingredient.dart';
import '../services/pantry_service.dart';

class PantryEditorScreen extends StatefulWidget {
  /// The path parameter — either an `ingredientId` to edit, or the literal
  /// string `"new"` to open in add mode.
  final String ingredientId;

  const PantryEditorScreen({super.key, required this.ingredientId});

  bool get isNew => ingredientId == 'new';

  @override
  State<PantryEditorScreen> createState() => _PantryEditorScreenState();
}

class _PantryEditorScreenState extends State<PantryEditorScreen> {
  PantryService get _service => getIt<PantryService>();
  ApiClient get _api => getIt<ApiClient>();

  PantryIngredient? _existing;
  final _nameController = TextEditingController();
  final _quantityController = TextEditingController();
  final _unitController = TextEditingController();
  String? _storageLocation;
  DateTime? _expiresAt;
  DateTime? _lastEstimatedAt;

  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    if (!widget.isNew) _loadExisting();
  }

  @override
  void dispose() {
    _nameController.dispose();
    _quantityController.dispose();
    _unitController.dispose();
    super.dispose();
  }

  void _loadExisting() {
    try {
      final pantry = _service.current;
      if (pantry == null || pantry.items.isEmpty) return;
      PantryIngredient? match;
      for (final item in pantry.items) {
        if (item.ingredientId == widget.ingredientId) {
          match = item;
          break;
        }
      }
      if (match == null) return;
      _existing = match;
      _quantityController.text =
          match.quantityDisplay == match.quantityDisplay.truncateToDouble()
              ? match.quantityDisplay.toInt().toString()
              : match.quantityDisplay.toString();
      _unitController.text = match.unitDisplay;
      _storageLocation = match.storageLocation;
      _expiresAt = match.expiresAt;
      if (mounted) setState(() {});
    } catch (_) {
      // Service not registered (tests) — leave fields empty.
    }
  }

  bool get _isFormValid {
    final qty = double.tryParse(_quantityController.text.trim());
    if (qty == null || qty <= 0) return false;
    if (widget.isNew && _nameController.text.trim().isEmpty) return false;
    return true;
  }

  Future<void> _onStorageChanged(String? next) async {
    setState(() => _storageLocation = next);
    if (next == null) return;

    // Don't re-estimate if the user has already touched the date.
    final userHasEdited = _expiresAt != _lastEstimatedAt;
    if (userHasEdited && _expiresAt != null) return;
    if (_expiresAt == null && _lastEstimatedAt != null) {
      // User deliberately cleared — respect that.
      return;
    }

    final pantryId = _existing?.pantryId ?? _service.current?.id;
    final ingredientId = _existing?.ingredientId;
    if (pantryId == null || ingredientId == null) return;

    try {
      final response = await _api.estimatePantryExpiry(pantryId, {
        'ingredient_id': ingredientId,
        'storage_location': next,
      });
      final rawExpires = response.data['expires_at'] as String?;
      final estimated =
          rawExpires == null ? null : DateTime.tryParse(rawExpires);
      if (!mounted) return;
      setState(() {
        _expiresAt = estimated;
        _lastEstimatedAt = estimated;
      });
    } catch (_) {
      // Silent — the user can pick a date manually.
    }
  }

  Future<void> _pickDate() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _expiresAt ?? now,
      firstDate: now.subtract(const Duration(days: 365)),
      lastDate: now.add(const Duration(days: 365 * 3)),
    );
    if (picked != null) {
      setState(() => _expiresAt = picked);
    }
  }

  Future<void> _save() async {
    if (!_isFormValid) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    final pantryId = _existing?.pantryId ?? _service.current?.id;
    if (pantryId == null) {
      setState(() {
        _saving = false;
        _error = 'Pantry not loaded yet.';
      });
      return;
    }
    final qty = double.parse(_quantityController.text.trim());
    final unit = _unitController.text.trim().isEmpty
        ? 'each'
        : _unitController.text.trim();

    final payload = {
      'quantity_display': qty,
      'unit_display': unit,
      'quantity_normalized': qty,
      'unit_normalized': unit,
      if (_storageLocation != null) 'storage_location': _storageLocation,
      if (_expiresAt != null) 'expires_at': _expiresAt!.toIso8601String(),
    };

    try {
      if (widget.isNew) {
        payload['name'] = _nameController.text.trim();
        await _service.addPantryIngredient(pantryId, payload);
      } else {
        // PATCH via ApiClient directly (PantryService doesn't own PATCH yet).
        await _api.updatePantryIngredient(pantryId, widget.ingredientId, payload);
        await _service.loadDefaultPantry();
      }
      if (!mounted) return;
      context.pop();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = 'Save failed. Please try again.';
      });
    }
  }

  Future<void> _confirmDelete() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Remove from pantry?'),
        content: const Text('This can be undone from the list screen.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Remove'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    final pantryId = _existing?.pantryId;
    if (pantryId == null) return;
    try {
      await _service.deletePantryIngredient(pantryId, widget.ingredientId);
      if (!mounted) return;
      context.pop();
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Remove failed')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final isNew = widget.isNew;
    return Scaffold(
      appBar: AppBar(
        title: Text(isNew ? 'Add pantry item' : 'Edit pantry item'),
        actions: [
          if (!isNew)
            IconButton(
              icon: const Icon(Icons.delete_outline),
              tooltip: 'Remove',
              onPressed: _confirmDelete,
            ),
        ],
      ),
      body: _buildForm(),
    );
  }

  Widget _buildForm() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (widget.isNew)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Semantics(
              label: 'Ingredient name',
              child: TextField(
                key: const Key('pantry_editor_name'),
                controller: _nameController,
                autofocus: true,
                decoration: const InputDecoration(
                  labelText: 'Ingredient',
                  hintText: 'e.g. olive oil',
                ),
                textInputAction: TextInputAction.next,
                onChanged: (_) => setState(() {}),
              ),
            ),
          )
        else
          ListTile(
            title: Text(_existing?.ingredientName ?? ''),
            subtitle: Text(_existing?.category ?? ''),
            leading: const Icon(Icons.grass),
          ),
        const SizedBox(height: 8),
        TextField(
          controller: _quantityController,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          decoration: const InputDecoration(labelText: 'Quantity'),
          onChanged: (_) => setState(() {}),
        ),
        const SizedBox(height: 8),
        TextField(
          controller: _unitController,
          decoration: const InputDecoration(
            labelText: 'Unit',
            hintText: 'e.g. each, cups, g',
          ),
          onChanged: (_) => setState(() {}),
        ),
        const SizedBox(height: 16),
        Text('Storage', style: Theme.of(context).textTheme.labelLarge),
        const SizedBox(height: 8),
        SegmentedButton<String?>(
          segments: const [
            ButtonSegment(value: 'fridge', label: Text('Fridge')),
            ButtonSegment(value: 'pantry', label: Text('Pantry')),
            ButtonSegment(value: 'freezer', label: Text('Freezer')),
            ButtonSegment(value: null, label: Text('None')),
          ],
          selected: {_storageLocation},
          onSelectionChanged: (set) => _onStorageChanged(set.first),
          multiSelectionEnabled: false,
          emptySelectionAllowed: true,
        ),
        const SizedBox(height: 16),
        ListTile(
          leading: const Icon(Icons.event),
          title: const Text('Expires'),
          subtitle: Text(_expiresAt == null
              ? 'No expiry set'
              : _formatDate(_expiresAt!)),
          trailing: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (_expiresAt != null)
                IconButton(
                  icon: const Icon(Icons.clear),
                  onPressed: () => setState(() => _expiresAt = null),
                ),
              IconButton(
                icon: const Icon(Icons.calendar_today),
                onPressed: _pickDate,
              ),
            ],
          ),
        ),
        const SizedBox(height: 24),
        if (_error != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ),
        FilledButton(
          onPressed: _isFormValid && !_saving ? _save : null,
          child: _saving
              ? const SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('Save'),
        ),
      ],
    );
  }
}

String _formatDate(DateTime d) {
  final y = d.year;
  final m = d.month.toString().padLeft(2, '0');
  final day = d.day.toString().padLeft(2, '0');
  return '$y-$m-$day';
}
