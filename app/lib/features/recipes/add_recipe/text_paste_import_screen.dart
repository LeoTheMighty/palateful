import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';
import '../../../core/services/auth_service.dart';

/// Screen for importing a recipe by pasting text.
class TextPasteImportScreen extends StatefulWidget {
  final String? recipeBookId;

  const TextPasteImportScreen({super.key, this.recipeBookId});

  @override
  State<TextPasteImportScreen> createState() => _TextPasteImportScreenState();
}

class _TextPasteImportScreenState extends State<TextPasteImportScreen> {
  final _apiClient = getIt<ApiClient>();
  final _controller = TextEditingController();
  bool _isExtracting = false;
  static const _maxChars = 16000;

  String get _bookId =>
      widget.recipeBookId ?? getIt<AuthService>().defaultRecipeBookId ?? '';

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _pasteFromClipboard() async {
    final data = await Clipboard.getData(Clipboard.kTextPlain);
    if (data?.text != null && data!.text!.isNotEmpty) {
      _controller.text = data.text!;
      setState(() {});
    }
  }

  Future<void> _extractRecipe() async {
    final text = _controller.text.trim();
    if (text.isEmpty || _bookId.isEmpty) return;

    setState(() => _isExtracting = true);

    try {
      final response = await _apiClient.startImport(
        _bookId,
        sourceType: 'text',
        rawText: text,
      );

      if (!mounted) return;
      final jobId = response.data['id'];
      if (jobId != null) {
        context.pushReplacement('/recipes/import/review-list/$jobId');
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _isExtracting = false);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Failed to extract recipe. Please try again.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final charCount = _controller.text.length;
    final isOverLimit = charCount > _maxChars;
    final canSubmit = charCount > 0 && !isOverLimit && !_isExtracting;

    return Scaffold(
      appBar: AppBar(title: const Text('Paste Recipe')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Expanded(
              child: TextField(
                controller: _controller,
                maxLines: null,
                expands: true,
                textAlignVertical: TextAlignVertical.top,
                decoration: InputDecoration(
                  hintText: 'Paste your recipe text here...',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  contentPadding: const EdgeInsets.all(16),
                ),
                onChanged: (_) => setState(() {}),
              ),
            ),
            const SizedBox(height: 8),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                TextButton.icon(
                  onPressed: _pasteFromClipboard,
                  icon: const Icon(Icons.content_paste, size: 18),
                  label: const Text('Paste from Clipboard'),
                ),
                Text(
                  '$charCount / $_maxChars',
                  style: textTheme.bodySmall?.copyWith(
                    color: isOverLimit ? colorScheme.error : colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: canSubmit ? _extractRecipe : null,
              child: _isExtracting
                  ? const Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        ),
                        SizedBox(width: 12),
                        Text('AI is reading your recipe...'),
                      ],
                    )
                  : const Text('Extract Recipe'),
            ),
          ],
        ),
      ),
    );
  }
}
