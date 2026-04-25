import 'package:flutter/material.dart';
import '../../../../../core/services/api_client.dart';
import '../../../../../core/services/recipe_cache_service.dart';
import '../../../../../core/state/mutation_bus.dart';
import '../../../../../core/theme/theme.dart';
import '../../../providers/recipe_provider.dart';
import '../cook_plan.dart';

/// Bottom sheet shown after the user finishes cooking.
///
/// cmm-1 — refactored to accept a `List<ComponentRatable>`. Recipe
/// cook passes a single-entry list; meal cook (cmm-6) passes one per
/// started component.
///
/// Single-component rendering is pixel-identical to the pre-refactor
/// layout (same keys, same widget tree). Multi-component renders N
/// rating rows in a `ListView` (scrolls when rows overflow viewport)
/// and submits sequential `POST /v1/cooking-logs` writes per
/// `rating > 0` component, emitting a `CookingLogCreated` MutationBus
/// event after each successful POST.
class PostCookFeedbackSheet extends StatefulWidget {
  final List<ComponentRatable> components;
  final ApiClient? apiClient;
  final RecipeCacheService recipeCache;
  final bool isOffline;
  final String? title;

  /// Called when the user completes or skips the feedback flow.
  /// The caller is responsible for dismissing the sheet after this fires.
  ///
  /// [saved] is true only when the user tapped Save AND the log/note
  /// calls returned without throwing. Skip and any caught exception
  /// fire `saved: false` so callers can preserve retry-relevant state
  /// (e.g. persisted cook session, see epic-cook-mode-resume cmr-4).
  final void Function({bool saved}) onComplete;

  /// Optional — when non-null, a back arrow renders in the top-left.
  /// Tapping it should dismiss the sheet AND keep the caller in cook
  /// mode (recovery for an accidental "Done" tap).
  final VoidCallback? onBack;

  PostCookFeedbackSheet({
    super.key,
    required this.components,
    this.apiClient,
    required this.recipeCache,
    required this.isOffline,
    required this.onComplete,
    this.onBack,
    this.title,
  }) {
    if (components.isEmpty) {
      throw ArgumentError.value(
        components,
        'components',
        'PostCookFeedbackSheet requires at least one component',
      );
    }
  }

  @override
  State<PostCookFeedbackSheet> createState() => _PostCookFeedbackSheetState();
}

class _PostCookFeedbackSheetState extends State<PostCookFeedbackSheet> {
  // Single-component path uses these (preserves existing test keys).
  int _selectedRating = 0;
  final _notesController = TextEditingController();
  bool _isSaving = false;

  // Multi-component path: one rating + one notes controller per row.
  // Lists are sized to `widget.components.length` in `initState`.
  late final List<int> _multiRatings;
  late final List<TextEditingController> _multiNotes;

  @override
  void initState() {
    super.initState();
    _multiRatings = List<int>.filled(widget.components.length, 0);
    _multiNotes = List<TextEditingController>.generate(
      widget.components.length,
      (_) => TextEditingController(),
    );
  }

  @override
  void dispose() {
    _notesController.dispose();
    for (final c in _multiNotes) {
      c.dispose();
    }
    super.dispose();
  }

  bool get _isSingle => widget.components.length == 1;

  Future<void> _saveSingle() async {
    setState(() => _isSaving = true);
    var saved = true;
    final c = widget.components.first;
    try {
      if (_selectedRating > 0) {
        await widget.recipeCache.logCook(
          c.recipeId,
          _selectedRating,
          DateTime.now(),
        );
      }
      final notes = _notesController.text.trim();
      if (notes.isNotEmpty) {
        // Online path: only call API when both online AND apiClient available.
        // Falls through to queue if apiClient is null (prevents silent data loss).
        if (!widget.isOffline && widget.apiClient != null) {
          await widget.apiClient!.addRecipeNote(c.recipeId, notes);
          // pfc-3: drop cached recipe payload so reopening detail
          // reflects the freshly-appended note.
          if (mounted) invalidateRecipe(context, c.recipeId);
        } else {
          await widget.recipeCache.queueNoteAdd(c.recipeId, notes);
        }
      }
    } catch (_) {
      // Feedback capture is best-effort — always complete, but flag as
      // unsaved so callers preserve retry-relevant state (cmr-4 AC7).
      saved = false;
    }
    // Reset saving state before invoking onComplete so tests can use pumpAndSettle.
    setState(() => _isSaving = false);
    widget.onComplete(saved: saved);
  }

  /// cmm-6 — sequential per-component POST /v1/cooking-logs writes.
  /// Components with rating == 0 are skipped (no log row, no event).
  /// Each successful POST emits a `CookingLogCreated` so the cooking
  /// history provider invalidates. Partial failure → snackbar
  /// "Cooked X of Y components logged" but onComplete still fires
  /// `saved: true` so the persister clears (user already submitted).
  Future<void> _saveMulti() async {
    setState(() => _isSaving = true);
    final api = widget.apiClient;
    final cookedAt = DateTime.now().toUtc().toIso8601String();
    var attempted = 0;
    var succeeded = 0;
    final failures = <String>[]; // displayName entries
    for (var i = 0; i < widget.components.length; i++) {
      final rating = _multiRatings[i];
      if (rating <= 0) continue;
      attempted++;
      final comp = widget.components[i];
      final note = _multiNotes[i].text.trim();
      try {
        if (api == null || widget.isOffline) {
          // Mirror single-recipe behavior: cache locally even when
          // offline. The CookingLogCreated event is intentionally NOT
          // emitted for offline writes — the providers expect a wire
          // payload (`logId`/`log`) that only the API has.
          await widget.recipeCache.logCook(
            comp.recipeId,
            rating,
            DateTime.now(),
          );
          succeeded++;
        } else {
          final response = await api.createCookingLog({
            'recipe_id': comp.recipeId,
            'rating': rating,
            'cooked_at': cookedAt,
            if (note.isNotEmpty) 'notes': note,
          });
          final data = response.data as Map<String, dynamic>?;
          if (data != null) {
            emitMutation(CookingLogCreated(
              logId: data['id'] as String? ?? '',
              log: data,
              recipeId: comp.recipeId,
            ));
          }
          succeeded++;
        }
      } catch (_) {
        failures.add(comp.displayName);
      }
    }
    if (!mounted) return;
    setState(() => _isSaving = false);
    if (failures.isNotEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Cooked $succeeded of $attempted components logged',
          ),
          duration: const Duration(seconds: 4),
        ),
      );
    } else if (attempted == 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Meal finished'),
          duration: Duration(seconds: 2),
        ),
      );
    }
    // Always fire saved=true: the user has submitted (even all-zeroes
    // is a valid signal). Persister clear is the caller's job.
    widget.onComplete(saved: true);
  }

  @override
  Widget build(BuildContext context) {
    if (_isSingle) return _buildSingle(context);
    return _buildMulti(context);
  }

  Widget _buildSingle(BuildContext context) {
    final cook = context.cookModeTheme;
    final headerName = widget.title ?? widget.components.first.displayName;

    return Padding(
      padding: EdgeInsets.fromLTRB(
        24,
        20,
        24,
        MediaQuery.of(context).viewInsets.bottom + 36,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          _buildHeader(cook),
          const SizedBox(height: 20),

          Text(
            'How did it go?',
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w700,
              color: cook.cookOnSurface,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            headerName,
            style: TextStyle(
              fontSize: 14,
              color: cook.cookOnSurface.withValues(alpha: 0.7),
            ),
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 20),

          // 5-star rating row
          Row(
            key: const Key('star_rating_row'),
            mainAxisAlignment: MainAxisAlignment.center,
            children: List.generate(5, (i) {
              final star = i + 1;
              return IconButton(
                key: Key('star_$star'),
                icon: Icon(
                  _selectedRating >= star ? Icons.star : Icons.star_border,
                  color: cook.cookAccent,
                  size: 36,
                ),
                onPressed: () => setState(() => _selectedRating = star),
              );
            }),
          ),
          const SizedBox(height: 16),

          // Optional notes field
          TextField(
            key: const Key('notes_field'),
            controller: _notesController,
            maxLines: 3,
            style: TextStyle(color: cook.cookOnSurface),
            decoration: InputDecoration(
              hintText: 'Add a note... (optional)',
              hintStyle: TextStyle(
                color: cook.cookOnSurface.withValues(alpha: 0.5),
              ),
              enabledBorder: OutlineInputBorder(
                borderSide: BorderSide(color: cook.cookDivider),
                borderRadius: BorderRadius.circular(8),
              ),
              focusedBorder: OutlineInputBorder(
                borderSide: BorderSide(color: cook.cookAccent),
                borderRadius: BorderRadius.circular(8),
              ),
              filled: true,
              fillColor: cook.cookSurfaceDim,
            ),
          ),
          const SizedBox(height: 20),

          // Save button
          FilledButton(
            key: const Key('save_button'),
            onPressed: _isSaving ? null : _saveSingle,
            style: FilledButton.styleFrom(
              backgroundColor: cook.cookAccent,
              foregroundColor: cook.cookOnAccent,
              minimumSize: const Size.fromHeight(48),
            ),
            child: _isSaving
                ? SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(
                      color: cook.cookOnAccent,
                      strokeWidth: 2,
                    ),
                  )
                : const Text('Save'),
          ),
          const SizedBox(height: 8),

          // Skip button — user declined to submit feedback; treat as
          // unsaved so the caller doesn't clear retry-relevant state.
          TextButton(
            key: const Key('skip_button'),
            onPressed:
                _isSaving ? null : () => widget.onComplete(saved: false),
            style: TextButton.styleFrom(
              foregroundColor: cook.cookOnSurface.withValues(alpha: 0.6),
              minimumSize: const Size.fromHeight(48),
            ),
            child: const Text('Skip'),
          ),
        ],
      ),
    );
  }

  Widget _buildMulti(BuildContext context) {
    final cook = context.cookModeTheme;
    final maxHeight = MediaQuery.of(context).size.height * 0.75;
    return ConstrainedBox(
      constraints: BoxConstraints(maxHeight: maxHeight),
      child: Padding(
        padding: EdgeInsets.fromLTRB(
          24,
          20,
          24,
          MediaQuery.of(context).viewInsets.bottom + 24,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            _buildHeader(cook),
            const SizedBox(height: 16),
            Text(
              'How did it go?',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w700,
                color: cook.cookOnSurface,
              ),
            ),
            if (widget.title != null) ...[
              const SizedBox(height: 4),
              Text(
                widget.title!,
                style: TextStyle(
                  fontSize: 14,
                  color: cook.cookOnSurface.withValues(alpha: 0.7),
                ),
                overflow: TextOverflow.ellipsis,
              ),
            ],
            const SizedBox(height: 16),
            Flexible(
              child: ListView.separated(
                key: const Key('multi_rating_list'),
                shrinkWrap: true,
                itemCount: widget.components.length,
                separatorBuilder: (_, _) => Divider(
                  color: cook.cookDivider,
                  height: 24,
                ),
                itemBuilder: (context, i) => _buildMultiRow(context, cook, i),
              ),
            ),
            const SizedBox(height: 12),
            FilledButton(
              key: const Key('multi_done_button'),
              onPressed: _isSaving ? null : _saveMulti,
              style: FilledButton.styleFrom(
                backgroundColor: cook.cookAccent,
                foregroundColor: cook.cookOnAccent,
                minimumSize: const Size.fromHeight(48),
              ),
              child: _isSaving
                  ? SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                        color: cook.cookOnAccent,
                        strokeWidth: 2,
                      ),
                    )
                  : const Text('Done'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader(CookModeTheme cook) {
    final dragHandle = Container(
      width: 40,
      height: 4,
      decoration: BoxDecoration(
        color: cook.cookOnSurface.withValues(alpha: 0.3),
        borderRadius: BorderRadius.circular(2),
      ),
    );
    if (widget.onBack == null) return dragHandle;
    return SizedBox(
      height: 40,
      child: Stack(
        alignment: Alignment.center,
        children: [
          dragHandle,
          Align(
            alignment: Alignment.centerLeft,
            child: IconButton(
              key: const Key('post_cook_back_button'),
              tooltip: 'Back to cooking',
              icon: Icon(
                Icons.arrow_back,
                color: cook.cookOnSurface,
              ),
              onPressed: _isSaving ? null : widget.onBack,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMultiRow(BuildContext context, CookModeTheme cook, int i) {
    final c = widget.components[i];
    final rating = _multiRatings[i];
    return Column(
      key: Key('multi_row_$i'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          c.displayName,
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: cook.cookOnSurface,
          ),
        ),
        const SizedBox(height: 4),
        Semantics(
          label: '${c.displayName}, rate $rating of 5 stars',
          container: true,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.start,
            children: List.generate(5, (s) {
              final star = s + 1;
              return IconButton(
                key: Key('multi_star_${i}_$star'),
                icon: Icon(
                  rating >= star ? Icons.star : Icons.star_border,
                  color: cook.cookAccent,
                  size: 28,
                ),
                onPressed: () => setState(() => _multiRatings[i] = star),
              );
            }),
          ),
        ),
        Semantics(
          label: 'Notes for ${c.displayName}',
          container: true,
          child: TextField(
            key: Key('multi_notes_$i'),
            controller: _multiNotes[i],
            maxLines: 2,
            style: TextStyle(color: cook.cookOnSurface),
            decoration: InputDecoration(
              hintText: 'Add a note... (optional)',
              hintStyle: TextStyle(
                color: cook.cookOnSurface.withValues(alpha: 0.5),
              ),
              enabledBorder: OutlineInputBorder(
                borderSide: BorderSide(color: cook.cookDivider),
                borderRadius: BorderRadius.circular(8),
              ),
              focusedBorder: OutlineInputBorder(
                borderSide: BorderSide(color: cook.cookAccent),
                borderRadius: BorderRadius.circular(8),
              ),
              filled: true,
              fillColor: cook.cookSurfaceDim,
              isDense: true,
            ),
          ),
        ),
      ],
    );
  }
}
