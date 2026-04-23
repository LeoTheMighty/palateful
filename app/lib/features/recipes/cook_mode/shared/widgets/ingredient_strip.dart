import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';
import 'package:flutter/services.dart';
import '../../../../../core/theme/theme.dart';
import '../../../../../core/utils/quantity_formatter.dart';

// Sentinel values for the group tracker. A plain `null` would collide
// with `builder(i) == null` in the comparison; these Object identities
// cannot.
const Object _kInitialSentinel = Object();
const Object _kUntaggedSentinel = Object();

class IngredientStrip extends StatefulWidget {
  final List<dynamic> ingredients;
  final Set<int> checkedIndices;
  final ValueChanged<int> onToggle;
  final double scaleFactor;

  /// Optional: when supplied, chips are emitted grouped by the value
  /// this builder returns. Recipe-cook plans pass `null`; meal-cook
  /// plans pass a builder backed by `CombinedIngredient.sourceComponentName`.
  final String? Function(int index)? sourceTagBuilder;

  const IngredientStrip({
    super.key,
    required this.ingredients,
    required this.checkedIndices,
    required this.onToggle,
    this.scaleFactor = 1.0,
    this.sourceTagBuilder,
  });

  @override
  State<IngredientStrip> createState() => _IngredientStripState();
}

class _IngredientStripState extends State<IngredientStrip> {
  // Layout: all chips live on one horizontally-scrollable row. In
  // grouped (meal) mode, each group is introduced by a tiny inline
  // header (Semantics header: true) carrying the component name, and
  // a dot row below tracks which group is currently in view. The
  // previous Wrap layout stacked into multiple rows vertically and
  // took ~3× the vertical space on a typical 3-component meal.
  final ScrollController _scrollController = ScrollController();
  final GlobalKey _contentKey = GlobalKey();

  // Measured left-edge offset (in scroll pixels) of each group in the
  // current build. Populated post-layout; empty during the first
  // frame before measurement completes.
  List<double> _groupOffsets = const [];
  int _activeGroup = 0;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _scrollController.removeListener(_onScroll);
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (!mounted || _groupOffsets.isEmpty) return;
    final offset = _scrollController.offset;
    // Treat a group as "active" once its left edge has scrolled past
    // ~20px into the viewport. The 20dp tolerance avoids dot-flicker
    // when the active group is barely clipped at the leading edge.
    int active = 0;
    for (var i = 0; i < _groupOffsets.length; i++) {
      if (_groupOffsets[i] - 20 <= offset) {
        active = i;
      } else {
        break;
      }
    }
    if (active != _activeGroup) {
      setState(() => _activeGroup = active);
    }
  }

  void _scheduleMeasure(List<_Group> groups) {
    SchedulerBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final contentCtx = _contentKey.currentContext;
      if (contentCtx == null) return;
      final contentBox = contentCtx.findRenderObject() as RenderBox?;
      if (contentBox == null) return;
      final offsets = <double>[];
      for (final g in groups) {
        final ctx = g.measureKey.currentContext;
        if (ctx == null) {
          offsets.add(offsets.isEmpty ? 0 : offsets.last);
          continue;
        }
        final box = ctx.findRenderObject() as RenderBox?;
        if (box == null) {
          offsets.add(offsets.isEmpty ? 0 : offsets.last);
          continue;
        }
        final local = box.localToGlobal(Offset.zero, ancestor: contentBox);
        offsets.add(local.dx);
      }
      if (!_listEquals(offsets, _groupOffsets)) {
        setState(() => _groupOffsets = offsets);
      }
    });
  }

  static bool _listEquals(List<double> a, List<double> b) {
    if (a.length != b.length) return false;
    for (var i = 0; i < a.length; i++) {
      if ((a[i] - b[i]).abs() > 0.5) return false;
    }
    return true;
  }

  void _jumpToGroup(int index, List<_Group> groups) {
    if (!_scrollController.hasClients) return;
    if (index < 0 || index >= groups.length) return;
    final ctx = groups[index].measureKey.currentContext;
    if (ctx == null) return;
    Scrollable.ensureVisible(
      ctx,
      duration: const Duration(milliseconds: 250),
      alignment: 0.0,
      curve: Curves.easeOutCubic,
    );
    // Optimistically set the active dot — scroll listener will
    // reconcile once the animation settles.
    if (index != _activeGroup) {
      setState(() => _activeGroup = index);
    }
  }

  @override
  Widget build(BuildContext context) {
    // cmlp-2 empty-ingredient edge case: render nothing — no padding,
    // no empty header, no "0 ingredients" label.
    if (widget.ingredients.isEmpty) return const SizedBox.shrink();

    final builder = widget.sourceTagBuilder;
    if (builder == null) {
      return _buildUngrouped();
    }
    return _buildGrouped(builder);
  }

  Widget _buildUngrouped() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
      child: SingleChildScrollView(
        controller: _scrollController,
        scrollDirection: Axis.horizontal,
        child: Row(
          key: _contentKey,
          mainAxisSize: MainAxisSize.min,
          children: [
            for (var i = 0; i < widget.ingredients.length; i++) ...[
              if (i > 0) const SizedBox(width: 8),
              _IngredientChip(
                ingredient: widget.ingredients[i],
                isChecked: widget.checkedIndices.contains(i),
                onTap: () => widget.onToggle(i),
                scaleFactor: widget.scaleFactor,
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildGrouped(String? Function(int) builder) {
    final cook = context.cookModeTheme;

    // Partition ingredients into consecutive same-tag buckets. Null
    // tag is bucketed under "Other" and guarded by `_kUntaggedSentinel`
    // so a real component literally named "Other" stays distinct.
    final groups = <_Group>[];
    Object? lastTag = _kInitialSentinel;
    for (var i = 0; i < widget.ingredients.length; i++) {
      final rawTag = builder(i);
      final slot = rawTag ?? _kUntaggedSentinel;
      if (!identical(slot, lastTag) && slot != lastTag) {
        groups.add(_Group(
          rawTag: rawTag,
          displayName: rawTag ?? 'Other',
          widgetKey: rawTag == null
              ? const Key('ingredient_group_untagged')
              : Key('ingredient_group_$rawTag'),
          measureKey: GlobalKey(
            debugLabel: 'ingredient_group_measure_${rawTag ?? "untagged"}',
          ),
          indices: [i],
        ));
        lastTag = slot;
      } else {
        groups.last.indices.add(i);
      }
    }

    // Re-measure group offsets after layout every build — chip counts
    // and widths can change when the user checks items or the plan
    // rebuilds.
    _scheduleMeasure(groups);

    final activeIndex =
        _activeGroup >= groups.length ? groups.length - 1 : _activeGroup;

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          SingleChildScrollView(
            controller: _scrollController,
            scrollDirection: Axis.horizontal,
            child: Row(
              key: _contentKey,
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                for (var g = 0; g < groups.length; g++) ...[
                  if (g > 0) const SizedBox(width: 16),
                  _buildGroup(groups[g], cook),
                ],
              ],
            ),
          ),
          if (groups.length > 1) ...[
            const SizedBox(height: 8),
            _DotRow(
              count: groups.length,
              active: activeIndex,
              accent: cook.cookAccent,
              inactive: cook.cookOnSurface.withValues(alpha: 0.25),
              onTap: (i) => _jumpToGroup(i, groups),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildGroup(_Group group, CookModeTheme cook) {
    // Each group is a keyed Container so tests can scope into a
    // single group (`ingredient_group_$tag`), plus an inner
    // GlobalKey-bearing Row for post-layout offset measurement.
    return Container(
      key: group.widgetKey,
      child: Row(
        key: group.measureKey,
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Semantics(
            header: true,
            child: Padding(
              padding: const EdgeInsets.only(right: 8),
              child: Text(
                group.displayName,
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  letterSpacing: 0.4,
                  color: cook.cookOnSurface.withValues(alpha: 0.7),
                ),
              ),
            ),
          ),
          for (var j = 0; j < group.indices.length; j++) ...[
            if (j > 0) const SizedBox(width: 8),
            _IngredientChip(
              ingredient: widget.ingredients[group.indices[j]],
              isChecked: widget.checkedIndices.contains(group.indices[j]),
              onTap: () => widget.onToggle(group.indices[j]),
              scaleFactor: widget.scaleFactor,
            ),
          ],
        ],
      ),
    );
  }
}

class _Group {
  final String? rawTag;
  final String displayName;
  final Key widgetKey;
  final GlobalKey measureKey;
  final List<int> indices;
  _Group({
    required this.rawTag,
    required this.displayName,
    required this.widgetKey,
    required this.measureKey,
    required this.indices,
  });
}

class _DotRow extends StatelessWidget {
  final int count;
  final int active;
  final Color accent;
  final Color inactive;
  final ValueChanged<int> onTap;

  const _DotRow({
    required this.count,
    required this.active,
    required this.accent,
    required this.inactive,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        for (var i = 0; i < count; i++) ...[
          if (i > 0) const SizedBox(width: 6),
          GestureDetector(
            onTap: () => onTap(i),
            behavior: HitTestBehavior.opaque,
            child: Container(
              key: Key('ingredient_group_dot_$i'),
              width: 6,
              height: 6,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: i == active ? accent : inactive,
              ),
            ),
          ),
        ],
      ],
    );
  }
}

class _IngredientChip extends StatelessWidget {
  final dynamic ingredient;
  final bool isChecked;
  final VoidCallback onTap;
  final double scaleFactor;

  const _IngredientChip({
    required this.ingredient,
    required this.isChecked,
    required this.onTap,
    this.scaleFactor = 1.0,
  });

  @override
  Widget build(BuildContext context) {
    final cook = context.cookModeTheme;
    final name = ingredient['ingredient']?['canonical_name'] ?? 'Unknown';
    final quantity = scaleQuantityDisplay(
        ingredient['quantity_display'] as String?, scaleFactor);
    final unit = ingredient['unit_display'] ?? '';
    final quantityText = '$quantity $unit'.trim();

    // cmlp-3 width strategy: ConstrainedBox (not IntrinsicWidth) — the
    // chip hugs short content up to 160dp, then wraps the name to 2
    // lines. IntrinsicWidth inside a Wrap forces a layout pass per
    // child and bloats cost at 30+ ingredient meals.
    final nameColor =
        isChecked ? cook.cookOnCompleted : cook.cookOnSurface;
    final quantityColor =
        isChecked ? cook.cookOnCompleted : cook.cookAccent;

    final body = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        if (quantityText.isNotEmpty)
          Text(
            quantityText,
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: quantityColor,
              decoration: isChecked ? TextDecoration.lineThrough : null,
            ),
          ),
        Text(
          name,
          style: TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w500,
            color: nameColor,
            decoration: isChecked ? TextDecoration.lineThrough : null,
          ),
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          softWrap: true,
        ),
      ],
    );

    return GestureDetector(
      onTap: () {
        HapticFeedback.selectionClick();
        onTap();
      },
      child: Container(
        constraints: const BoxConstraints(minWidth: 72, maxWidth: 160),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: isChecked ? cook.cookCompleted : cook.cookSurfaceDim,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (isChecked)
              Padding(
                padding: const EdgeInsets.only(right: 6),
                child: Icon(
                  Icons.check,
                  size: 16,
                  color: cook.cookOnCompleted,
                ),
              ),
            Flexible(child: body),
          ],
        ),
      ),
    );
  }
}
