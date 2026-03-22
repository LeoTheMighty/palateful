import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';

/// Read-only public view of a recipe accessed via a share token.
/// No authentication required.
class PublicRecipeScreen extends StatefulWidget {
  final String token;

  const PublicRecipeScreen({super.key, required this.token});

  @override
  State<PublicRecipeScreen> createState() => _PublicRecipeScreenState();
}

class _PublicRecipeScreenState extends State<PublicRecipeScreen> {
  final _apiClient = getIt<ApiClient>();
  Map<String, dynamic>? _recipe;
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadRecipe();
  }

  Future<void> _loadRecipe() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final response =
          await _apiClient.getPublicRecipeByToken(widget.token);
      if (mounted) {
        setState(() {
          _recipe = response.data as Map<String, dynamic>;
          _isLoading = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _error = 'Recipe not found or link has been revoked.';
          _isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(
        title: Text(_recipe?['name'] ?? 'Recipe'),
        automaticallyImplyLeading: false,
        actions: [
          IconButton(
            icon: const Icon(Icons.close),
            onPressed: () => Navigator.of(context).maybePop(),
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.link_off_outlined,
                            size: 48,
                            color: colorScheme.onSurfaceVariant),
                        const SizedBox(height: 16),
                        Text(
                          _error!,
                          style: textTheme.bodyLarge?.copyWith(
                              color: colorScheme.onSurfaceVariant),
                          textAlign: TextAlign.center,
                        ),
                      ],
                    ),
                  ),
                )
              : _buildContent(colorScheme, textTheme),
    );
  }

  Widget _buildContent(ColorScheme colorScheme, TextTheme textTheme) {
    final ingredients =
        (_recipe!['ingredients'] as List?) ?? [];
    final steps = (_recipe!['steps'] as List?) ?? [];

    return CustomScrollView(
      slivers: [
        if (_recipe!['image_url'] != null)
          SliverToBoxAdapter(
            child: CachedNetworkImage(
              imageUrl: _recipe!['image_url'] as String,
              height: 200,
              width: double.infinity,
              fit: BoxFit.cover,
              placeholder: (context, url) => const Center(child: CircularProgressIndicator(strokeWidth: 2)),
              errorWidget: (context, url, error) => Icon(Icons.broken_image, color: Theme.of(context).colorScheme.onSurfaceVariant),
            ),
          ),
        SliverPadding(
          padding: const EdgeInsets.all(16),
          sliver: SliverList(
            delegate: SliverChildListDelegate([
              // Recipe book attribution
              if (_recipe!['recipe_book_name'] != null)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Text(
                    'From: ${_recipe!['recipe_book_name']}',
                    style: textTheme.labelMedium?.copyWith(
                        color: colorScheme.onSurfaceVariant),
                  ),
                ),

              // Recipe name
              Text(
                _recipe!['name'] as String,
                style: textTheme.headlineSmall,
              ),
              const SizedBox(height: 8),

              // Description
              if (_recipe!['description'] != null) ...[
                Text(
                  _recipe!['description'] as String,
                  style: textTheme.bodyLarge
                      ?.copyWith(color: colorScheme.onSurfaceVariant),
                ),
                const SizedBox(height: 16),
              ],

              // Ingredients
              if (ingredients.isNotEmpty) ...[
                Text('Ingredients',
                    style: textTheme.titleMedium),
                const SizedBox(height: 8),
                ...ingredients.map((ing) {
                  final name = (ing['ingredient'] as Map?)?['canonical_name']
                          ?.toString() ??
                      '';
                  final qty = ing['quantity_display']?.toString() ?? '';
                  final unit = ing['unit_display']?.toString() ?? '';
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 2),
                    child: Text(
                      [qty, unit, name]
                          .where((s) => s.isNotEmpty)
                          .join(' '),
                      style: textTheme.bodyMedium,
                    ),
                  );
                }),
                const SizedBox(height: 16),
              ],

              // Steps
              if (steps.isNotEmpty) ...[
                Text('Steps', style: textTheme.titleMedium),
                const SizedBox(height: 8),
                ...steps.asMap().entries.map((entry) {
                  final i = entry.key;
                  final step = entry.value as Map;
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        CircleAvatar(
                          radius: 12,
                          backgroundColor:
                              colorScheme.primaryContainer,
                          child: Text(
                            '${i + 1}',
                            style: textTheme.labelSmall?.copyWith(
                                color: colorScheme.onPrimaryContainer),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            step['instruction']?.toString() ?? '',
                            style: textTheme.bodyMedium,
                          ),
                        ),
                      ],
                    ),
                  );
                }),
              ],

              // Palateful attribution
              const SizedBox(height: 24),
              Center(
                child: Text(
                  'Shared via Palateful',
                  style: textTheme.labelSmall
                      ?.copyWith(color: colorScheme.outline),
                ),
              ),
              const SizedBox(height: 16),
            ]),
          ),
        ),
      ],
    );
  }
}
