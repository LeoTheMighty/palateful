import 'package:flutter/material.dart';
import '../../../../../core/services/api_client.dart';
import '../../../../../core/services/recipe_cache_service.dart';
import '../../../../../core/theme/theme.dart';
import '../../../providers/recipe_provider.dart';
import '../cook_plan.dart';

/// Bottom sheet shown after the user finishes cooking.
///
/// cmm-1 — refactored to accept a `List<ComponentRatable>`. The recipe
/// cook path passes a single-entry list; meal cook (cmm-6) passes one
/// per started component. Single-component rendering is pixel-identical
/// to the pre-refactor layout (same keys, same widget tree).
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

  PostCookFeedbackSheet({
    super.key,
    required this.components,
    this.apiClient,
    required this.recipeCache,
    required this.isOffline,
    required this.onComplete,
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
  // Multi-component meal path (cmm-6) layers per-row state on top.
  int _selectedRating = 0;
  final _notesController = TextEditingController();
  bool _isSaving = false;

  @override
  void dispose() {
    _notesController.dispose();
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

  @override
  Widget build(BuildContext context) {
    if (!_isSingle) {
      // Multi-component layout is wired in cmm-6. Hard-fail rather than
      // silently render only the first component (which would drop the
      // user's per-component ratings on submit).
      throw UnimplementedError(
        'PostCookFeedbackSheet with components.length > 1 ships in cmm-6. '
        'Got ${widget.components.length} components.',
      );
    }
    return _buildSingle(context);
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
          // Drag handle (visual only — sheet is not draggable)
          Container(
            width: 40,
            height: 4,
            decoration: BoxDecoration(
              color: cook.cookOnSurface.withValues(alpha: 0.3),
              borderRadius: BorderRadius.circular(2),
            ),
          ),
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
}
