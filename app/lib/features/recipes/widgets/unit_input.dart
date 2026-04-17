import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'package:palateful/core/constants/ingredient_units.dart';

/// Single-line text input that opens a dropdown of curated ingredient units
/// on focus. Typing filters the list; a synthetic "Add custom" entry appears
/// at the bottom when the typed text doesn't match any curated unit.
///
/// The widget is value-in / callback-out: `value` is the current unit (a
/// curated short form like `"tbsp"`, a custom string, or `null` for empty),
/// and `onChanged` fires when the user selects a suggestion or finishes
/// editing (on blur) with a free-text value.
///
/// Custom units set via this widget apply only to the single ingredient row;
/// they are not persisted back into the curated catalog
/// (`kCuratedUnits`).
class UnitInput extends StatefulWidget {
  const UnitInput({
    super.key,
    required this.value,
    required this.onChanged,
    this.enabled = true,
    this.semanticLabel = 'Unit selector',
  });

  final String? value;
  final ValueChanged<String?> onChanged;
  final bool enabled;
  final String semanticLabel;

  @override
  State<UnitInput> createState() => _UnitInputState();
}

class _UnitInputState extends State<UnitInput> {
  late final TextEditingController _controller;
  late final FocusNode _focusNode;
  final LayerLink _layerLink = LayerLink();
  OverlayEntry? _overlay;
  List<String> _filtered = kCuratedUnits;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: widget.value ?? '');
    _focusNode = FocusNode(debugLabel: 'UnitInput');
    _focusNode.addListener(_onFocusChange);
    _controller.addListener(_onTextChange);
  }

  @override
  void didUpdateWidget(covariant UnitInput oldWidget) {
    super.didUpdateWidget(oldWidget);
    // Parent sync: update field when external value changes and the user
    // isn't actively editing.
    if (widget.value != oldWidget.value && !_focusNode.hasFocus) {
      final v = widget.value ?? '';
      if (_controller.text != v) {
        _controller.value = TextEditingValue(text: v);
      }
    }
  }

  @override
  void dispose() {
    _hideOverlay();
    _focusNode.removeListener(_onFocusChange);
    _focusNode.dispose();
    _controller.removeListener(_onTextChange);
    _controller.dispose();
    super.dispose();
  }

  void _onFocusChange() {
    if (_focusNode.hasFocus) {
      _showOverlay();
    } else {
      _hideOverlay();
      // Commit whatever was typed as the free-text value on blur.
      final typed = _controller.text.trim();
      final committed = typed.isEmpty ? null : typed;
      if (committed != widget.value) widget.onChanged(committed);
    }
  }

  void _onTextChange() {
    final next = filterCuratedUnits(_controller.text);
    if (next.length != _filtered.length ||
        !_listsEqual(next, _filtered)) {
      setState(() => _filtered = next);
      _overlay?.markNeedsBuild();
    }
  }

  bool _listsEqual(List<String> a, List<String> b) {
    if (a.length != b.length) return false;
    for (var i = 0; i < a.length; i++) {
      if (a[i] != b[i]) return false;
    }
    return true;
  }

  void _showOverlay() {
    if (_overlay != null) return;
    _overlay = OverlayEntry(builder: _buildOverlay);
    Overlay.of(context).insert(_overlay!);
  }

  void _hideOverlay() {
    _overlay?.remove();
    _overlay = null;
  }

  void _selectCurated(String unit) {
    _controller.value = TextEditingValue(text: unit);
    _hideOverlay();
    _focusNode.unfocus();
    widget.onChanged(unit);
  }

  void _selectCustom(String typed) {
    _controller.value = TextEditingValue(text: typed);
    _hideOverlay();
    _focusNode.unfocus();
    widget.onChanged(typed);
  }

  bool get _shouldOfferCustom {
    final typed = _controller.text.trim();
    if (typed.isEmpty) return false;
    return !kCuratedUnits.any((u) => u.toLowerCase() == typed.toLowerCase());
  }

  Widget _buildOverlay(BuildContext context) {
    final typed = _controller.text.trim();
    return Positioned(
      width: _fieldWidth(),
      child: CompositedTransformFollower(
        link: _layerLink,
        showWhenUnlinked: false,
        offset: Offset(0, _fieldHeight()),
        child: TapRegion(
          onTapOutside: (_) {
            if (_focusNode.hasFocus) _focusNode.unfocus();
          },
          child: Material(
            elevation: 4,
            borderRadius: BorderRadius.circular(6),
            child: Column(
              key: const Key('unit_input_overlay_column'),
              mainAxisSize: MainAxisSize.min,
              children: [
                Flexible(
                  child: ListView.builder(
                    shrinkWrap: true,
                    padding: EdgeInsets.zero,
                    itemCount: _filtered.length +
                        (_shouldOfferCustom ? 1 : 0),
                    itemBuilder: (ctx, i) {
                      if (i < _filtered.length) {
                        final unit = _filtered[i];
                        return InkWell(
                          key: Key('unit_option_$unit'),
                          onTap: () => _selectCurated(unit),
                          child: Padding(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 12, vertical: 10),
                            child: Text(unit),
                          ),
                        );
                      }
                      return InkWell(
                        key: const Key('unit_add_custom'),
                        onTap: () => _selectCustom(typed),
                        child: Padding(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 12, vertical: 10),
                          child: Text('Add custom: "$typed"'),
                        ),
                      );
                    },
                  ),
                ),
                const Divider(height: 1),
                const Padding(
                  padding: EdgeInsets.symmetric(
                      horizontal: 12, vertical: 8),
                  child: Text(
                    'Custom units apply to this ingredient only',
                    style: TextStyle(fontSize: 11, color: Colors.grey),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  double _fieldWidth() {
    final rb = context.findRenderObject() as RenderBox?;
    return rb?.size.width ?? 96;
  }

  double _fieldHeight() {
    final rb = context.findRenderObject() as RenderBox?;
    return rb?.size.height ?? 48;
  }

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: widget.semanticLabel,
      textField: true,
      child: CompositedTransformTarget(
        link: _layerLink,
        child: Shortcuts(
          shortcuts: const <ShortcutActivator, Intent>{
            SingleActivator(LogicalKeyboardKey.arrowDown):
                _FocusFirstOptionIntent(),
          },
          child: Actions(
            actions: <Type, Action<Intent>>{
              _FocusFirstOptionIntent: CallbackAction<_FocusFirstOptionIntent>(
                onInvoke: (_) {
                  if (_filtered.isNotEmpty) {
                    _selectCurated(_filtered.first);
                  }
                  return null;
                },
              ),
            },
            child: TextField(
              controller: _controller,
              focusNode: _focusNode,
              enabled: widget.enabled,
              textInputAction: TextInputAction.done,
              decoration: const InputDecoration(
                hintText: 'Unit',
                isDense: true,
                border: OutlineInputBorder(),
                contentPadding:
                    EdgeInsets.symmetric(horizontal: 8, vertical: 8),
              ),
              onSubmitted: (submitted) {
                final t = submitted.trim();
                if (t.isEmpty) {
                  widget.onChanged(null);
                  return;
                }
                final match = kCuratedUnits.firstWhere(
                  (u) => u.toLowerCase() == t.toLowerCase(),
                  orElse: () => '',
                );
                if (match.isNotEmpty) {
                  _selectCurated(match);
                } else {
                  _selectCustom(t);
                }
              },
            ),
          ),
        ),
      ),
    );
  }
}

class _FocusFirstOptionIntent extends Intent {
  const _FocusFirstOptionIntent();
}
