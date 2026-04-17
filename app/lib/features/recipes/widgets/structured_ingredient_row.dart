import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'package:palateful/core/utils/fraction_parser.dart';
import 'package:palateful/features/recipes/widgets/unit_input.dart';

/// Value object for one row of the structured ingredient editor.
///
/// `quantity` is the parsed numeric value. `ingredientId` is optional and
/// is only populated when editing an existing recipe_ingredient (so the
/// backend update path can preserve the canonical-ingredient FK instead of
/// running find-or-create by name again).
class IngredientRowData {
  const IngredientRowData({
    this.name,
    this.quantity,
    this.unit,
    this.notes,
    this.isOptional = false,
    this.ingredientId,
  });

  final String? name;
  final double? quantity;
  final String? unit;
  final String? notes;
  final bool isOptional;
  final String? ingredientId;

  IngredientRowData copyWith({
    Object? name = _sentinel,
    Object? quantity = _sentinel,
    Object? unit = _sentinel,
    Object? notes = _sentinel,
    bool? isOptional,
    Object? ingredientId = _sentinel,
  }) {
    return IngredientRowData(
      name: identical(name, _sentinel) ? this.name : name as String?,
      quantity:
          identical(quantity, _sentinel) ? this.quantity : quantity as double?,
      unit: identical(unit, _sentinel) ? this.unit : unit as String?,
      notes: identical(notes, _sentinel) ? this.notes : notes as String?,
      isOptional: isOptional ?? this.isOptional,
      ingredientId: identical(ingredientId, _sentinel)
          ? this.ingredientId
          : ingredientId as String?,
    );
  }

  static const Object _sentinel = Object();
}

/// Structured ingredient row used across Review Import, the recipe wizard,
/// and the recipe edit screen.
///
/// Value-in / callback-out: the widget owns text controllers internally,
/// and the parent only sees the [IngredientRowData] value and callbacks.
/// For insert/delete/reorder operations, the parent should assign a
/// stable [Key] per row so controllers don't leak across list mutations.
class StructuredIngredientRow extends StatefulWidget {
  const StructuredIngredientRow({
    super.key,
    required this.value,
    required this.onChanged,
    this.onDeleteRequested,
    this.enabled = true,
  });

  final IngredientRowData value;
  final ValueChanged<IngredientRowData> onChanged;

  /// Fires when the user taps the trash icon. The parent owns the list and
  /// decides whether to remove the row, surface a snackbar-undo, etc.
  final VoidCallback? onDeleteRequested;

  final bool enabled;

  @override
  State<StructuredIngredientRow> createState() =>
      _StructuredIngredientRowState();
}

class _StructuredIngredientRowState extends State<StructuredIngredientRow> {
  late final TextEditingController _qtyController;
  late final TextEditingController _nameController;
  late final TextEditingController _notesController;
  late final FocusNode _qtyFocus;

  @override
  void initState() {
    super.initState();
    _qtyController = TextEditingController(
      text: widget.value.quantity == null
          ? ''
          : formatFraction(widget.value.quantity!),
    );
    _nameController = TextEditingController(text: widget.value.name ?? '');
    _notesController = TextEditingController(text: widget.value.notes ?? '');
    _qtyFocus = FocusNode(debugLabel: 'qty');
    _qtyFocus.addListener(_onQtyFocusChange);
  }

  @override
  void didUpdateWidget(covariant StructuredIngredientRow oldWidget) {
    super.didUpdateWidget(oldWidget);
    // Parent-side value sync. Only overwrite controllers when the widget
    // isn't being edited, so typing-in-progress isn't clobbered.
    if (widget.value.quantity != oldWidget.value.quantity &&
        !_qtyFocus.hasFocus) {
      final next = widget.value.quantity == null
          ? ''
          : formatFraction(widget.value.quantity!);
      if (_qtyController.text != next) {
        _qtyController.value = TextEditingValue(text: next);
      }
    }
    if (widget.value.name != oldWidget.value.name) {
      final next = widget.value.name ?? '';
      if (_nameController.text != next) {
        _nameController.value = TextEditingValue(text: next);
      }
    }
    if (widget.value.notes != oldWidget.value.notes) {
      final next = widget.value.notes ?? '';
      if (_notesController.text != next) {
        _notesController.value = TextEditingValue(text: next);
      }
    }
  }

  @override
  void dispose() {
    _qtyFocus.removeListener(_onQtyFocusChange);
    _qtyFocus.dispose();
    _qtyController.dispose();
    _nameController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  void _onQtyFocusChange() {
    if (_qtyFocus.hasFocus) return;
    // Re-format on blur so `1 1/2` stays canonical and `0.5` becomes `1/2`.
    final parsed = parseFraction(_qtyController.text);
    final formatted = parsed == null ? '' : formatFraction(parsed);
    if (_qtyController.text != formatted) {
      _qtyController.value = TextEditingValue(text: formatted);
    }
  }

  void _emit(IngredientRowData next) {
    widget.onChanged(next);
  }

  void _onQtyChanged(String raw) {
    final parsed = parseFraction(raw);
    // Emit regardless of whether parse succeeded — if it didn't, the stored
    // numeric value is null (user may still be mid-typing; the blur handler
    // will normalize).
    _emit(widget.value.copyWith(quantity: parsed));
  }

  void _onNameChanged(String raw) {
    final trimmed = raw.trimRight();
    _emit(widget.value.copyWith(name: trimmed.isEmpty ? null : trimmed));
  }

  void _onNotesChanged(String raw) {
    final trimmed = raw.trimRight();
    _emit(widget.value.copyWith(notes: trimmed.isEmpty ? null : trimmed));
  }

  void _onUnitChanged(String? unit) {
    _emit(widget.value.copyWith(unit: unit));
  }

  void _onOptionalToggled(bool? v) {
    _emit(widget.value.copyWith(isOptional: v ?? false));
  }

  @override
  Widget build(BuildContext context) {
    final nameForSemantics =
        (widget.value.name?.trim().isEmpty ?? true) ? 'ingredient' : widget.value.name!.trim();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            SizedBox(
              width: 64,
              child: TextField(
                key: const Key('ingredient_row_qty'),
                controller: _qtyController,
                focusNode: _qtyFocus,
                enabled: widget.enabled,
                keyboardType: TextInputType.text,
                inputFormatters: [
                  FilteringTextInputFormatter.allow(RegExp(r'[0-9./ ]')),
                ],
                decoration: const InputDecoration(
                  hintText: 'Qty',
                  isDense: true,
                  border: OutlineInputBorder(),
                  contentPadding:
                      EdgeInsets.symmetric(horizontal: 6, vertical: 8),
                  helperText: 'e.g. 1/2 or 0.5',
                  helperStyle: TextStyle(fontSize: 10),
                ),
                onChanged: _onQtyChanged,
              ),
            ),
            const SizedBox(width: 8),
            SizedBox(
              width: 96,
              child: UnitInput(
                key: const Key('ingredient_row_unit'),
                value: widget.value.unit,
                onChanged: _onUnitChanged,
                enabled: widget.enabled,
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: TextField(
                key: const Key('ingredient_row_name'),
                controller: _nameController,
                enabled: widget.enabled,
                decoration: const InputDecoration(
                  hintText: 'Name',
                  isDense: true,
                  border: OutlineInputBorder(),
                  contentPadding:
                      EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                ),
                onChanged: _onNameChanged,
              ),
            ),
            if (widget.onDeleteRequested != null) ...[
              const SizedBox(width: 4),
              IconButton(
                key: const Key('ingredient_row_delete'),
                icon: const Icon(Icons.delete_outline, size: 20),
                tooltip: 'Remove ingredient',
                visualDensity: VisualDensity.compact,
                onPressed: widget.enabled ? widget.onDeleteRequested : null,
              ),
            ],
          ],
        ),
        const SizedBox(height: 6),
        Row(
          children: [
            Expanded(
              child: TextField(
                key: const Key('ingredient_row_notes'),
                controller: _notesController,
                enabled: widget.enabled,
                decoration: const InputDecoration(
                  hintText: 'Notes (e.g. melted, chopped)',
                  isDense: true,
                  border: OutlineInputBorder(),
                  contentPadding:
                      EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                ),
                onChanged: _onNotesChanged,
              ),
            ),
            const SizedBox(width: 24),
            Semantics(
              label: 'Mark $nameForSemantics as optional',
              container: true,
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Checkbox(
                    key: const Key('ingredient_row_optional'),
                    value: widget.value.isOptional,
                    onChanged: widget.enabled ? _onOptionalToggled : null,
                    visualDensity: VisualDensity.compact,
                    materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                  const Text('optional', style: TextStyle(fontSize: 12)),
                ],
              ),
            ),
          ],
        ),
      ],
    );
  }
}
