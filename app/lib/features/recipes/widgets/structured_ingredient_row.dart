import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'package:palateful/core/utils/fraction_parser.dart';
import 'package:palateful/features/recipes/services/session_alias_map.dart';
import 'package:palateful/features/recipes/widgets/unit_input.dart';

/// Value object for one row of the structured ingredient editor.
///
/// `quantity` is the parsed numeric value. `ingredientId` is optional and
/// is only populated when editing an existing recipe_ingredient (so the
/// backend update path can preserve the canonical-ingredient FK instead of
/// running find-or-create by name again).
///
/// `expanded` is the persisted UI state for the caret-expansion row
/// (riip-6) — kept on the value-object so manual collapse survives the
/// auto-save rebuilds that wash through the recipe editor / Review Import
/// screen. The parent owns this and round-trips it on every change.
///
/// `pendingReviewIngredient` is the riip-7 badge flag — true when the
/// ingredient's canonical entry was auto-created via find-or-create and
/// hasn't been reviewed yet. Wired in riip-7.
class IngredientRowData {
  const IngredientRowData({
    this.name,
    this.quantity,
    this.unit,
    this.notes,
    this.isOptional = false,
    this.ingredientId,
    bool? expanded,
    this.pendingReviewIngredient = false,
  }) : _explicitExpanded = expanded;

  final String? name;
  final double? quantity;
  final String? unit;
  final String? notes;
  final bool isOptional;
  final String? ingredientId;
  final bool pendingReviewIngredient;

  /// Internal expansion state. Use [expanded] to read; auto-expand
  /// when caller didn't set it and notes/optional are non-empty.
  final bool? _explicitExpanded;

  /// True if the caret-expansion row should be visible. Defaults to
  /// auto-expand when notes is non-empty OR is_optional is true.
  bool get expanded =>
      _explicitExpanded ?? ((notes != null && notes!.isNotEmpty) || isOptional);

  /// True if the caret has hidden content behind it (collapsed dot
  /// indicator should render).
  bool get hasHiddenContent =>
      !expanded && ((notes != null && notes!.isNotEmpty) || isOptional);

  IngredientRowData copyWith({
    Object? name = _sentinel,
    Object? quantity = _sentinel,
    Object? unit = _sentinel,
    Object? notes = _sentinel,
    bool? isOptional,
    Object? ingredientId = _sentinel,
    Object? expanded = _sentinel,
    bool? pendingReviewIngredient,
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
      expanded: identical(expanded, _sentinel)
          ? _explicitExpanded
          : expanded as bool?,
      pendingReviewIngredient:
          pendingReviewIngredient ?? this.pendingReviewIngredient,
    );
  }

  static const Object _sentinel = Object();
}

/// Locked layout widths (riip-6 design principle 2).
///
/// Math is calibrated for iPhone SE 1st-gen (320 × 568): qty 48 + unit
/// 72 + caret 40 + delete 40 + paddings (≈24) = 224, leaving ≥96 for
/// the name field. Asserted in widget tests.
class _RowLayout {
  static const double qty = 48;
  static const double unit = 72;
  static const double caret = 40;
  static const double delete = 40;
  static const double minRowHeight = 48;
}

/// Structured ingredient row used across Review Import, the recipe wizard,
/// and the recipe edit screen.
///
/// One-line layout (riip-6): `[qty] [unit] [name] [caret] [delete]`,
/// with `notes` + `optional` revealed below the row when the caret is
/// expanded. The expansion state is owned by the [IngredientRowData]
/// value object so manual collapse survives auto-save rebuilds.
///
/// Value-in / callback-out: the widget owns text controllers internally
/// for typing-in-progress smoothness. Parent should assign a stable
/// [Key] per row so controllers don't leak across list mutations.
class StructuredIngredientRow extends StatefulWidget {
  const StructuredIngredientRow({
    super.key,
    required this.value,
    required this.onChanged,
    this.onDeleteRequested,
    this.enabled = true,
    this.aliasMap,
  });

  final IngredientRowData value;
  final ValueChanged<IngredientRowData> onChanged;

  /// Fires when the user taps the trash icon. The parent owns the list and
  /// decides whether to remove the row, surface a snackbar-undo, etc.
  final VoidCallback? onDeleteRequested;

  final bool enabled;

  /// Test seam — forwarded to the embedded `UnitInput` so widget tests can
  /// inject a fake `SessionAliasMap` without spinning up DI.
  final SessionAliasMap? aliasMap;

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
    // riip-5: paste-handler — strip a multi-token paste like "2 tablespoons"
    // down to the leading numeric/fraction token, surface a snackbar.
    final trimmed = raw.trimLeft();
    if (trimmed.contains(' ') && !_looksLikeMixedFraction(trimmed)) {
      final firstToken = trimmed.split(RegExp(r'\s+')).first;
      if (firstToken != raw) {
        _qtyController.value = TextEditingValue(
          text: firstToken,
          selection: TextSelection.collapsed(offset: firstToken.length),
        );
        ScaffoldMessenger.maybeOf(context)?.showSnackBar(
          const SnackBar(
            content: Text('Trimmed to quantity only — unit dropped'),
            duration: Duration(seconds: 2),
          ),
        );
        _emit(widget.value.copyWith(quantity: parseFraction(firstToken)));
        return;
      }
    }
    final parsed = parseFraction(raw);
    _emit(widget.value.copyWith(quantity: parsed));
  }

  /// True for inputs like `1 1/2` (whole number + fraction) — those
  /// contain a space but are still a single quantity token.
  bool _looksLikeMixedFraction(String s) {
    final m = RegExp(r'^\d+\s+\d+/\d+').firstMatch(s);
    return m != null;
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

  void _toggleExpanded() {
    _emit(widget.value.copyWith(expanded: !widget.value.expanded));
  }

  String _semanticsLabel() {
    final parts = <String>['Ingredient'];
    if (widget.value.quantity != null) {
      parts.add(formatFraction(widget.value.quantity!));
    }
    if (widget.value.unit?.isNotEmpty ?? false) {
      parts.add(widget.value.unit!);
    }
    final n = widget.value.name?.trim();
    parts.add((n == null || n.isEmpty) ? 'unnamed' : n);
    final extras = <String>[];
    if (widget.value.isOptional) extras.add('optional');
    if (widget.value.notes?.isNotEmpty ?? false) {
      extras.add('notes: ${widget.value.notes}');
    }
    final base = parts.join(' ');
    return extras.isEmpty ? '$base.' : '$base, ${extras.join(', ')}.';
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        // riip-6 design principle 1 — debug assertion that we have at
        // least the iPhone-SE width. In release we still render (clipping
        // is acceptable) so we observe the edge case rather than hide it.
        assert(
          constraints.maxWidth >= 320,
          'StructuredIngredientRow requires ≥320pt width '
          '(actual: ${constraints.maxWidth.toStringAsFixed(1)})',
        );
        return Semantics(
          label: _semanticsLabel(),
          container: true,
          child: _buildContents(context),
        );
      },
    );
  }

  Widget _buildContents(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: [
        SizedBox(
          height: _RowLayout.minRowHeight,
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              SizedBox(
                width: _RowLayout.qty,
                child: TextField(
                  key: const Key('ingredient_row_qty'),
                  controller: _qtyController,
                  focusNode: _qtyFocus,
                  enabled: widget.enabled,
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  inputFormatters: [
                    FilteringTextInputFormatter.allow(RegExp(r'[0-9./ ]')),
                  ],
                  decoration: const InputDecoration(
                    hintText: 'Qty',
                    isDense: true,
                    border: OutlineInputBorder(),
                    contentPadding: EdgeInsets.symmetric(
                      horizontal: 4,
                      vertical: 8,
                    ),
                  ),
                  onChanged: _onQtyChanged,
                ),
              ),
              const SizedBox(width: 6),
              SizedBox(
                width: _RowLayout.unit,
                child: UnitInput(
                  key: const Key('ingredient_row_unit'),
                  value: widget.value.unit,
                  onChanged: _onUnitChanged,
                  enabled: widget.enabled,
                  aliasMap: widget.aliasMap,
                ),
              ),
              const SizedBox(width: 6),
              Expanded(
                child: TextField(
                  key: const Key('ingredient_row_name'),
                  controller: _nameController,
                  enabled: widget.enabled,
                  textInputAction: TextInputAction.done,
                  decoration: const InputDecoration(
                    hintText: 'Name',
                    isDense: true,
                    border: OutlineInputBorder(),
                    contentPadding: EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 8,
                    ),
                  ),
                  onChanged: _onNameChanged,
                ),
              ),
              const SizedBox(width: 4),
              SizedBox(
                width: _RowLayout.caret,
                height: _RowLayout.caret,
                child: _CaretButton(
                  expanded: widget.value.expanded,
                  showHiddenDot: widget.value.hasHiddenContent,
                  onPressed: widget.enabled ? _toggleExpanded : null,
                ),
              ),
              if (widget.onDeleteRequested != null)
                SizedBox(
                  width: _RowLayout.delete,
                  height: _RowLayout.delete,
                  child: IconButton(
                    key: const Key('ingredient_row_delete'),
                    icon: const Icon(Icons.delete_outline, size: 20),
                    tooltip: 'Remove ingredient',
                    visualDensity: VisualDensity.compact,
                    onPressed:
                        widget.enabled ? widget.onDeleteRequested : null,
                  ),
                ),
            ],
          ),
        ),
        AnimatedSize(
          duration: const Duration(milliseconds: 150),
          curve: Curves.easeOut,
          child: widget.value.expanded
              ? Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Row(
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
                            contentPadding: EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 8,
                            ),
                          ),
                          onChanged: _onNotesChanged,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Checkbox(
                            key: const Key('ingredient_row_optional'),
                            value: widget.value.isOptional,
                            onChanged:
                                widget.enabled ? _onOptionalToggled : null,
                            visualDensity: VisualDensity.compact,
                            materialTapTargetSize:
                                MaterialTapTargetSize.shrinkWrap,
                          ),
                          const Text(
                            'optional',
                            style: TextStyle(fontSize: 12),
                          ),
                        ],
                      ),
                    ],
                  ),
                )
              : const SizedBox.shrink(),
        ),
      ],
    );
  }
}

/// Caret toggle that overlays a small attention dot when there is hidden
/// content behind the collapsed caret (notes or optional). Dot uses
/// `colorScheme.tertiary` per the epic's design principle 4 (NOT
/// `ImportStateColors`, which is import-state-specific).
class _CaretButton extends StatelessWidget {
  const _CaretButton({
    required this.expanded,
    required this.showHiddenDot,
    required this.onPressed,
  });

  final bool expanded;
  final bool showHiddenDot;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return Stack(
      alignment: Alignment.center,
      children: [
        IconButton(
          key: const Key('ingredient_row_caret'),
          icon: Icon(
            expanded ? Icons.expand_less : Icons.expand_more,
            size: 20,
          ),
          tooltip: expanded
              ? 'Hide notes and options'
              : 'Show notes and options',
          visualDensity: VisualDensity.compact,
          onPressed: onPressed,
        ),
        if (showHiddenDot)
          Positioned(
            top: 8,
            right: 8,
            child: IgnorePointer(
              child: Container(
                key: const Key('ingredient_row_caret_dot'),
                width: 7,
                height: 7,
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.tertiary,
                  shape: BoxShape.circle,
                ),
              ),
            ),
          ),
      ],
    );
  }
}

