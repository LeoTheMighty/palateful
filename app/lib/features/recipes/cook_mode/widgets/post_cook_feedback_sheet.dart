import 'package:flutter/material.dart';
import '../../../../core/services/api_client.dart';
import '../../../../core/services/recipe_cache_service.dart';

/// Bottom sheet shown after the user taps "Done cooking".
///
/// Prompts for a 5-star rating and optional notes. Saves the cook log locally
/// and submits the note to the API (or queues it when offline).
class PostCookFeedbackSheet extends StatefulWidget {
  final String recipeId;
  final String recipeName;
  final ApiClient? apiClient;
  final RecipeCacheService recipeCache;
  final bool isOffline;

  /// Called when the user completes or skips the feedback flow.
  /// The caller is responsible for dismissing the sheet after this fires.
  final VoidCallback onComplete;

  const PostCookFeedbackSheet({
    super.key,
    required this.recipeId,
    required this.recipeName,
    this.apiClient,
    required this.recipeCache,
    required this.isOffline,
    required this.onComplete,
  });

  @override
  State<PostCookFeedbackSheet> createState() => _PostCookFeedbackSheetState();
}

class _PostCookFeedbackSheetState extends State<PostCookFeedbackSheet> {
  int _selectedRating = 0;
  final _notesController = TextEditingController();
  bool _isSaving = false;

  @override
  void dispose() {
    _notesController.dispose();
    super.dispose();
  }

  Future<void> _saveFeedback() async {
    setState(() => _isSaving = true);
    try {
      if (_selectedRating > 0) {
        await widget.recipeCache.logCook(
          widget.recipeId,
          _selectedRating,
          DateTime.now(),
        );
      }
      final notes = _notesController.text.trim();
      if (notes.isNotEmpty) {
        // Online path: only call API when both online AND apiClient available.
        // Falls through to queue if apiClient is null (prevents silent data loss).
        if (!widget.isOffline && widget.apiClient != null) {
          await widget.apiClient!.addRecipeNote(widget.recipeId, notes);
        } else {
          await widget.recipeCache.queueNoteAdd(widget.recipeId, notes);
        }
      }
    } catch (_) {
      // Feedback capture is best-effort — always complete even on error
    }
    // Reset saving state before invoking onComplete so tests can use pumpAndSettle.
    setState(() => _isSaving = false);
    widget.onComplete();
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

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
              color: colorScheme.onSurface.withValues(alpha: 0.3),
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(height: 20),

          Text(
            'How did it go?',
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w700,
              color: colorScheme.onSurface,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            widget.recipeName,
            style: TextStyle(fontSize: 14, color: colorScheme.surface),
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
                  color: colorScheme.tertiary,
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
            style: TextStyle(color: colorScheme.onSurface),
            decoration: InputDecoration(
              hintText: 'Add a note... (optional)',
              hintStyle: TextStyle(
                color: colorScheme.onSurface.withValues(alpha: 0.5),
              ),
              enabledBorder: OutlineInputBorder(
                borderSide:
                    BorderSide(color: colorScheme.primaryContainer),
                borderRadius: BorderRadius.circular(8),
              ),
              focusedBorder: OutlineInputBorder(
                borderSide: BorderSide(color: colorScheme.tertiary),
                borderRadius: BorderRadius.circular(8),
              ),
              filled: true,
              fillColor: colorScheme.onSurface.withValues(alpha: 0.05),
            ),
          ),
          const SizedBox(height: 20),

          // Save button
          FilledButton(
            key: const Key('save_button'),
            onPressed: _isSaving ? null : _saveFeedback,
            style: FilledButton.styleFrom(
              backgroundColor: colorScheme.tertiary,
              foregroundColor: colorScheme.onSurface,
              minimumSize: const Size.fromHeight(48),
            ),
            child: _isSaving
                ? SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(
                      color: colorScheme.onSurface,
                      strokeWidth: 2,
                    ),
                  )
                : const Text('Save'),
          ),
          const SizedBox(height: 8),

          // Skip button
          TextButton(
            key: const Key('skip_button'),
            onPressed: _isSaving ? null : widget.onComplete,
            style: TextButton.styleFrom(
              foregroundColor:
                  colorScheme.onSurface.withValues(alpha: 0.6),
              minimumSize: const Size.fromHeight(48),
            ),
            child: const Text('Skip'),
          ),
        ],
      ),
    );
  }
}
