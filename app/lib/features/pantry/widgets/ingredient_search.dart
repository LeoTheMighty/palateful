import 'dart:async';

import 'package:flutter/material.dart';

import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';

class IngredientMatch {
  final String id;
  final String canonicalName;
  final String? category;

  const IngredientMatch({
    required this.id,
    required this.canonicalName,
    this.category,
  });

  factory IngredientMatch.fromJson(Map<String, dynamic> json) {
    return IngredientMatch(
      id: json['id'] as String,
      canonicalName: json['canonical_name'] as String? ?? '',
      category: json['category'] as String?,
    );
  }
}

/// Debounced (300ms) typeahead against `GET /v1/ingredients/search`.
/// Invokes [onSelected] with the chosen match.
class IngredientSearch extends StatefulWidget {
  final ValueChanged<IngredientMatch> onSelected;

  const IngredientSearch({super.key, required this.onSelected});

  @override
  State<IngredientSearch> createState() => _IngredientSearchState();
}

class _IngredientSearchState extends State<IngredientSearch> {
  final _controller = TextEditingController();
  ApiClient get _api => getIt<ApiClient>();
  Timer? _debounce;
  List<IngredientMatch> _results = const [];
  bool _isLoading = false;

  @override
  void dispose() {
    _debounce?.cancel();
    _controller.dispose();
    super.dispose();
  }

  void _onChanged(String q) {
    _debounce?.cancel();
    if (q.trim().isEmpty) {
      setState(() => _results = const []);
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 300), () => _search(q));
  }

  Future<void> _search(String q) async {
    setState(() => _isLoading = true);
    try {
      final response = await _api.searchIngredients(q);
      final raw = (response.data['items'] as List<dynamic>?) ?? const [];
      final matches = raw
          .map((e) => IngredientMatch.fromJson(e as Map<String, dynamic>))
          .toList();
      if (!mounted) return;
      setState(() => _results = matches);
    } catch (_) {
      if (!mounted) return;
      setState(() => _results = const []);
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        TextField(
          controller: _controller,
          autofocus: true,
          decoration: InputDecoration(
            labelText: 'Search ingredients',
            prefixIcon: const Icon(Icons.search),
            suffixIcon: _isLoading
                ? const Padding(
                    padding: EdgeInsets.all(12),
                    child: SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                  )
                : null,
          ),
          onChanged: _onChanged,
        ),
        const SizedBox(height: 8),
        if (_results.isEmpty && _controller.text.isNotEmpty && !_isLoading)
          const Padding(
            padding: EdgeInsets.all(16),
            child: Text('No matches. Try a different name.'),
          ),
        for (final match in _results)
          ListTile(
            title: Text(match.canonicalName),
            subtitle: match.category != null ? Text(match.category!) : null,
            onTap: () => widget.onSelected(match),
          ),
      ],
    );
  }
}
