import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../core/services/error_reporter.dart';
import '../../shared/widgets/error_banner.dart';

class RecipeVersionHistoryScreen extends StatefulWidget {
  final String recipeId;
  final String recipeName;

  const RecipeVersionHistoryScreen({
    super.key,
    required this.recipeId,
    this.recipeName = '',
  });

  @override
  State<RecipeVersionHistoryScreen> createState() =>
      _RecipeVersionHistoryScreenState();
}

class _RecipeVersionHistoryScreenState
    extends State<RecipeVersionHistoryScreen> {
  final _apiClient = getIt<ApiClient>();
  List<dynamic> _versions = [];
  bool _isLoading = true;
  String? _error;
  String? _errorDetail;

  @override
  void initState() {
    super.initState();
    _loadVersions();
  }

  Future<void> _loadVersions() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final response = await _apiClient.getRecipeVersions(widget.recipeId);
      if (mounted) {
        setState(() {
          _versions = (response.data['versions'] as List?) ?? [];
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Failed to load version history: $e';
          _errorDetail = ErrorReporter.detail(e);
          _isLoading = false;
        });
      }
    }
  }

  String _formatDate(String? isoDate) {
    if (isoDate == null) return '';
    try {
      final dt = DateTime.parse(isoDate).toLocal();
      final now = DateTime.now();
      final diff = now.difference(dt);
      if (diff.inDays == 0) {
        if (diff.inHours == 0) return '${diff.inMinutes}m ago';
        return '${diff.inHours}h ago';
      }
      if (diff.inDays < 7) return '${diff.inDays}d ago';
      return '${dt.month}/${dt.day}/${dt.year}';
    } catch (_) {
      return isoDate;
    }
  }

  static const _fieldLabels = {
    'name': 'Name',
    'instructions': 'Instructions',
    'ingredients': 'Ingredients',
    'steps': 'Steps',
  };

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final title = widget.recipeName.isNotEmpty
        ? '${widget.recipeName} — History'
        : 'Version History';

    return Scaffold(
      appBar: AppBar(
        title: Text(title),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
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
                        Text(
                          _error!,
                          textAlign: TextAlign.center,
                          style:
                              TextStyle(color: colorScheme.onErrorContainer),
                        ),
                        const SizedBox(height: 16),
                        ElevatedButton(
                          onPressed: _loadVersions,
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                )
              : _versions.isEmpty
                  ? Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(
                            Icons.history,
                            size: 64,
                            color: colorScheme.outlineVariant,
                          ),
                          const SizedBox(height: 16),
                          Text(
                            'No version history yet',
                            style: textTheme.titleMedium?.copyWith(
                              color: colorScheme.onSurfaceVariant,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            'Versions are created automatically when you\nedit a recipe\'s name, ingredients, or steps.',
                            textAlign: TextAlign.center,
                            style: textTheme.bodyMedium?.copyWith(
                              color: colorScheme.onSurfaceVariant,
                            ),
                          ),
                        ],
                      ),
                    )
                  : ListView.builder(
                      padding: const EdgeInsets.symmetric(
                          vertical: 16, horizontal: 16),
                      itemCount: _versions.length,
                      itemBuilder: (context, index) {
                        final version = _versions[index];
                        final isLast = index == _versions.length - 1;
                        final versionNumber =
                            version['version_number'] as int? ?? 0;
                        final changedFields =
                            (version['changed_fields'] as List?) ?? [];

                        return IntrinsicHeight(
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              // Timeline indicator
                              SizedBox(
                                width: 28,
                                child: Column(
                                  children: [
                                    if (index == 0)
                                      const SizedBox(height: 12)
                                    else
                                      Expanded(
                                        child: Container(
                                          width: 2,
                                          color: colorScheme.outlineVariant,
                                        ),
                                      ),
                                    Container(
                                      width: 12,
                                      height: 12,
                                      decoration: BoxDecoration(
                                        shape: BoxShape.circle,
                                        color: index == 0
                                            ? colorScheme.primary
                                            : colorScheme.outlineVariant,
                                      ),
                                    ),
                                    if (!isLast)
                                      Expanded(
                                        child: Container(
                                          width: 2,
                                          color: colorScheme.outlineVariant,
                                        ),
                                      )
                                    else
                                      const SizedBox(height: 12),
                                  ],
                                ),
                              ),
                              const SizedBox(width: 12),
                              // Version card
                              Expanded(
                                child: Padding(
                                  padding: const EdgeInsets.only(bottom: 12),
                                  child: InkWell(
                                    onTap: () {
                                      context.push(
                                        '/recipes/${widget.recipeId}/versions/${version['id']}',
                                        extra: {
                                          'versionNumber': versionNumber,
                                        },
                                      );
                                    },
                                    borderRadius: BorderRadius.circular(12),
                                    child: Container(
                                      padding: const EdgeInsets.all(12),
                                      decoration: BoxDecoration(
                                        color: index == 0
                                            ? colorScheme.primaryContainer
                                                .withValues(alpha: 0.3)
                                            : colorScheme
                                                .surfaceContainerHighest
                                                .withValues(alpha: 0.5),
                                        borderRadius:
                                            BorderRadius.circular(12),
                                        border: Border.all(
                                          color: index == 0
                                              ? colorScheme.primary
                                                  .withValues(alpha: 0.4)
                                              : colorScheme.outlineVariant,
                                        ),
                                      ),
                                      child: Column(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        children: [
                                          Row(
                                            children: [
                                              Text(
                                                'Version $versionNumber',
                                                style: textTheme.titleSmall
                                                    ?.copyWith(
                                                  fontWeight: FontWeight.w600,
                                                  color: index == 0
                                                      ? colorScheme.primary
                                                      : colorScheme
                                                          .onSurface,
                                                ),
                                              ),
                                              const Spacer(),
                                              Text(
                                                _formatDate(version[
                                                    'created_at'] as String?),
                                                style: textTheme.bodySmall
                                                    ?.copyWith(
                                                  color: colorScheme
                                                      .onSurfaceVariant,
                                                ),
                                              ),
                                              const SizedBox(width: 4),
                                              Icon(
                                                Icons.chevron_right,
                                                size: 16,
                                                color: colorScheme
                                                    .onSurfaceVariant,
                                              ),
                                            ],
                                          ),
                                          if (changedFields.isNotEmpty) ...[
                                            const SizedBox(height: 6),
                                            Wrap(
                                              spacing: 4,
                                              runSpacing: 4,
                                              children: changedFields
                                                  .map((field) {
                                                final fieldStr = field.toString();
                                                final isRestore = fieldStr.startsWith('restore:');
                                                if (isRestore) {
                                                  final fromVersion = fieldStr.substring('restore:'.length);
                                                  return Container(
                                                    padding: const EdgeInsets.symmetric(
                                                      horizontal: 8,
                                                      vertical: 2,
                                                    ),
                                                    decoration: BoxDecoration(
                                                      color: colorScheme.tertiaryContainer.withValues(alpha: 0.7),
                                                      borderRadius: BorderRadius.circular(12),
                                                    ),
                                                    child: Row(
                                                      mainAxisSize: MainAxisSize.min,
                                                      children: [
                                                        Icon(
                                                          Icons.restore,
                                                          size: 12,
                                                          color: colorScheme.onTertiaryContainer,
                                                        ),
                                                        const SizedBox(width: 3),
                                                        Text(
                                                          'Restored from v$fromVersion',
                                                          style: textTheme.labelSmall?.copyWith(
                                                            color: colorScheme.onTertiaryContainer,
                                                          ),
                                                        ),
                                                      ],
                                                    ),
                                                  );
                                                }
                                                final label = _fieldLabels[fieldStr] ?? fieldStr;
                                                return Container(
                                                  padding: const EdgeInsets
                                                      .symmetric(
                                                    horizontal: 8,
                                                    vertical: 2,
                                                  ),
                                                  decoration: BoxDecoration(
                                                    color: colorScheme
                                                        .secondaryContainer
                                                        .withValues(alpha: 0.5),
                                                    borderRadius:
                                                        BorderRadius.circular(
                                                            12),
                                                  ),
                                                  child: Text(
                                                    label,
                                                    style: textTheme.labelSmall
                                                        ?.copyWith(
                                                      color: colorScheme
                                                          .onSecondaryContainer,
                                                    ),
                                                  ),
                                                );
                                              }).toList(),
                                            ),
                                          ],
                                        ],
                                      ),
                                    ),
                                  ),
                                ),
                              ),
                            ],
                          ),
                        );
                      },
                    ),
    );
  }
}
