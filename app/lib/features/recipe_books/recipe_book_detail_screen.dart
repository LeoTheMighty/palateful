import 'dart:async';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../core/theme/theme.dart';
import '../../core/utils/responsive.dart';
import '../../services/share_service.dart';
import '../../shared/widgets/empty_state.dart';
import 'services/recipe_book_sync_service.dart';

class RecipeBookDetailScreen extends StatefulWidget {
  final String recipeBookId;

  const RecipeBookDetailScreen({super.key, required this.recipeBookId});

  @override
  State<RecipeBookDetailScreen> createState() => _RecipeBookDetailScreenState();
}

class _RecipeBookDetailScreenState extends State<RecipeBookDetailScreen> {
  final _apiClient = getIt<ApiClient>();
  late final RecipeBookSyncService _syncService;
  Map<String, dynamic>? _recipeBook;
  List<dynamic> _recipes = [];
  bool _isLoading = true;
  String? _error;
  bool _isMovingOrCopying = false;
  String _userRole = 'owner';
  bool _isShared = false;

  // Real-time sync state
  StreamSubscription? _addedSub;
  StreamSubscription? _updatedSub;
  StreamSubscription? _removedSub;
  StreamSubscription? _stateSub;
  bool _wsConnected = false;
  bool _subscribed = false;

  // Multi-select state
  bool _isSelectMode = false;
  final Set<String> _selectedRecipeIds = {};
  bool _isBulkOperating = false;

  @override
  void initState() {
    super.initState();
    _syncService = getIt<RecipeBookSyncService>();
    _loadRecipeBook();
  }

  @override
  void dispose() {
    _addedSub?.cancel();
    _updatedSub?.cancel();
    _removedSub?.cancel();
    _stateSub?.cancel();
    _syncService.disconnectWebSocket();
    super.dispose();
  }

  void _subscribeToRealTime() {
    if (_subscribed) return;
    _subscribed = true;
    _syncService.connectWebSocket(widget.recipeBookId);

    _addedSub = _syncService.onRecipeAdded.listen((_) {
      if (mounted) _loadRecipeBook();
    });
    _updatedSub = _syncService.onRecipeUpdated.listen((_) {
      if (mounted) _loadRecipeBook();
    });
    _removedSub = _syncService.onRecipeRemoved.listen((recipeId) {
      if (!mounted) return;
      setState(() {
        _recipes.removeWhere((r) => r['id']?.toString() == recipeId);
      });
    });
    _stateSub = _syncService.onConnectionStateChange.listen((state) {
      if (!mounted) return;
      setState(() {
        _wsConnected = state == RecipeBookWebSocketState.connected;
      });
    });
  }

  Future<void> _loadRecipeBook() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final response = await _apiClient.getRecipeBook(widget.recipeBookId);
      if (mounted) {
        final isShared = response.data['is_shared'] as bool? ?? false;
        setState(() {
          _recipeBook = response.data;
          _recipes = response.data['recipes'] ?? [];
          _userRole = response.data['user_role'] as String? ?? 'owner';
          _isShared = isShared;
          _isLoading = false;
        });
        if (isShared) _subscribeToRealTime();
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Could not load recipe book. Please try again.';
          _isLoading = false;
        });
      }
    }
  }

  void _exitSelectMode() {
    setState(() {
      _isSelectMode = false;
      _selectedRecipeIds.clear();
    });
  }

  void _enterSelectMode({String? initialRecipeId}) {
    setState(() {
      _isSelectMode = true;
      _selectedRecipeIds.clear();
      if (initialRecipeId != null) {
        _selectedRecipeIds.add(initialRecipeId);
      }
    });
  }

  void _toggleRecipeSelection(String recipeId) {
    setState(() {
      if (_selectedRecipeIds.contains(recipeId)) {
        _selectedRecipeIds.remove(recipeId);
        if (_selectedRecipeIds.isEmpty) {
          _isSelectMode = false;
        }
      } else {
        _selectedRecipeIds.add(recipeId);
      }
    });
  }

  Future<void> _archiveRecipeBook() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Archive Recipe Book?'),
        content: const Text(
          'This book and its recipes will be moved to your archive. You can restore it anytime.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Archive'),
          ),
        ],
      ),
    );

    if (confirm == true) {
      try {
        HapticFeedback.selectionClick();
        await _apiClient.archiveRecipeBook(widget.recipeBookId);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Recipe book archived')),
          );
          context.pop();
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Could not archive recipe book. Please try again.')),
          );
        }
      }
    }
  }

  Future<void> _renameRecipeBook() async {
    final nameController = TextEditingController(text: _recipeBook?['name'] ?? '');
    final descriptionController = TextEditingController(text: _recipeBook?['description'] ?? '');

    try {
      final result = await showDialog<bool>(
        context: context,
        builder: (context) {
          return StatefulBuilder(
            builder: (context, setDialogState) {
              final nameIsEmpty = nameController.text.trim().isEmpty;
              return AlertDialog(
                title: const Text('Edit Recipe Book'),
                content: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    TextField(
                      controller: nameController,
                      decoration: const InputDecoration(
                        labelText: 'Name',
                      ),
                      autofocus: true,
                      onChanged: (_) => setDialogState(() {}),
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: descriptionController,
                      decoration: const InputDecoration(
                        labelText: 'Description (optional)',
                      ),
                      maxLines: 2,
                    ),
                  ],
                ),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.pop(context, false),
                    child: const Text('Cancel'),
                  ),
                  ElevatedButton(
                    onPressed: nameIsEmpty
                        ? null
                        : () => Navigator.pop(context, true),
                    child: const Text('Save'),
                  ),
                ],
              );
            },
          );
        },
      );

      if (result == true) {
        try {
          await _apiClient.updateRecipeBook(widget.recipeBookId, {
            'name': nameController.text,
            'description': descriptionController.text.isEmpty
                ? null
                : descriptionController.text,
          });
          _loadRecipeBook();
        } catch (e) {
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Could not update recipe book. Please try again.')),
            );
          }
        }
      }
    } finally {
      nameController.dispose();
      descriptionController.dispose();
    }
  }

  Future<Map<String, dynamic>?> _showBookPicker({String? excludeBookId}) async {
    try {
      final response = await _apiClient.getRecipeBooks();
      final books = ((response.data['items'] as List?) ?? [])
          .where((b) => b['id']?.toString() != excludeBookId)
          .toList();

      if (!mounted) return null;
      if (books.isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('No other books available')),
        );
        return null;
      }

      return showModalBottomSheet<Map<String, dynamic>>(
        context: context,
        isScrollControlled: true,
        builder: (context) => ConstrainedBox(
          constraints: BoxConstraints(
            maxHeight: MediaQuery.of(context).size.height * 0.6,
          ),
          child: SafeArea(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
                  child: Text(
                    'Choose a book',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                Flexible(
                  child: ListView(
                    shrinkWrap: true,
                    children: books.map((book) => ListTile(
                          leading: const Icon(Icons.menu_book_outlined),
                          title: Text(book['name'] ?? 'Untitled'),
                          subtitle: Text('${book['recipe_count'] ?? 0} recipes'),
                          onTap: () => Navigator.pop(context, book),
                        )).toList(),
                  ),
                ),
                const SizedBox(height: 8),
              ],
            ),
          ),
        ),
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not load books. Please try again.')),
        );
      }
      return null;
    }
  }

  // Bulk action handlers
  Future<void> _bulkMove() async {
    if (_isBulkOperating || _selectedRecipeIds.isEmpty) return;

    final book = await _showBookPicker(excludeBookId: widget.recipeBookId);
    if (book == null) return;

    setState(() => _isBulkOperating = true);
    try {
      HapticFeedback.selectionClick();
      final count = _selectedRecipeIds.length;
      await _apiClient.bulkMoveRecipes(_selectedRecipeIds.toList(), book['id']);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('$count recipes moved to ${book['name']}')),
        );
        _exitSelectMode();
        _loadRecipeBook();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not move recipes. Please try again.')),
        );
      }
    } finally {
      if (mounted) setState(() => _isBulkOperating = false);
    }
  }

  Future<void> _bulkArchive() async {
    if (_isBulkOperating || _selectedRecipeIds.isEmpty) return;

    final count = _selectedRecipeIds.length;
    final confirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Archive $count recipes?'),
        content: const Text(
          'These recipes will be moved to your archive. You can restore them anytime.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Archive'),
          ),
        ],
      ),
    );

    if (confirm != true) return;

    setState(() => _isBulkOperating = true);
    try {
      HapticFeedback.selectionClick();
      await _apiClient.bulkArchiveRecipes(_selectedRecipeIds.toList());
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('$count recipes archived')),
        );
        _exitSelectMode();
        _loadRecipeBook();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not archive recipes. Please try again.')),
        );
      }
    } finally {
      if (mounted) setState(() => _isBulkOperating = false);
    }
  }

  Future<void> _bulkTags() async {
    if (_isBulkOperating || _selectedRecipeIds.isEmpty) return;

    final tagController = TextEditingController();
    bool isAddMode = true;

    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              title: const Text('Update Tags'),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  SegmentedButton<bool>(
                    segments: const [
                      ButtonSegment(value: true, label: Text('Add Tags')),
                      ButtonSegment(value: false, label: Text('Remove Tags')),
                    ],
                    selected: {isAddMode},
                    onSelectionChanged: (selected) {
                      setDialogState(() => isAddMode = selected.first);
                    },
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: tagController,
                    decoration: InputDecoration(
                      labelText: isAddMode ? 'Tags to add' : 'Tags to remove',
                      hintText: 'e.g. quick, easy, italian',
                    ),
                    autofocus: true,
                  ),
                ],
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Cancel'),
                ),
                ElevatedButton(
                  onPressed: () {
                    final tags = tagController.text
                        .split(',')
                        .map((t) => t.trim())
                        .where((t) => t.isNotEmpty)
                        .toList();
                    if (tags.isEmpty) return;
                    Navigator.pop(context, {
                      'isAdd': isAddMode,
                      'tags': tags,
                    });
                  },
                  child: const Text('Apply'),
                ),
              ],
            );
          },
        );
      },
    );

    if (result == null) {
      tagController.dispose();
      return;
    }

    tagController.dispose();

    setState(() => _isBulkOperating = true);
    try {
      HapticFeedback.selectionClick();
      final tags = result['tags'] as List<String>;
      final count = _selectedRecipeIds.length;
      await _apiClient.bulkUpdateTags(
        _selectedRecipeIds.toList(),
        addTags: result['isAdd'] == true ? tags : null,
        removeTags: result['isAdd'] == false ? tags : null,
      );
      if (mounted) {
        final action = result['isAdd'] == true ? 'added to' : 'removed from';
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Tags $action $count recipes')),
        );
        _exitSelectMode();
        _loadRecipeBook();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not update tags. Please try again.')),
        );
      }
    } finally {
      if (mounted) setState(() => _isBulkOperating = false);
    }
  }

  Future<void> _shareBook() async {
    try {
      final shareService = ShareService();
      await shareService.shareRecipeBook(
        recipeBookId: widget.recipeBookId,
        recipeBookName: _recipeBook?['name'] ?? 'Recipe Book',
        context: context,
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to share — please try again')),
        );
      }
    }
  }

  Future<void> _addRecipe() async {
    await context.push('/recipes/add/wizard', extra: {
      'recipeBookId': widget.recipeBookId,
    });
    if (mounted) _loadRecipeBook();
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      appBar: _isSelectMode
          ? AppBar(
              leading: IconButton(
                icon: const Icon(Icons.close),
                onPressed: _exitSelectMode,
              ),
              title: Text('${_selectedRecipeIds.length} selected'),
              actions: [
                IconButton(
                  icon: Icon(
                    _selectedRecipeIds.length == _recipes.length
                        ? Icons.deselect
                        : Icons.select_all,
                  ),
                  onPressed: () {
                    setState(() {
                      if (_selectedRecipeIds.length == _recipes.length) {
                        _selectedRecipeIds.clear();
                      } else {
                        _selectedRecipeIds.clear();
                        for (final recipe in _recipes) {
                          final id = recipe['id']?.toString();
                          if (id != null) _selectedRecipeIds.add(id);
                        }
                      }
                    });
                  },
                ),
              ],
            )
          : AppBar(
              title: _isShared
                  ? Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Flexible(
                          child: Text(
                            _recipeBook?['name'] ?? 'Recipe Book',
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        const SizedBox(width: 8),
                        Container(
                          width: 8,
                          height: 8,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: _wsConnected ? context.appColors.success : context.appColors.textDisabled,
                          ),
                        ),
                      ],
                    )
                  : Text(_recipeBook?['name'] ?? 'Recipe Book'),
              leading: IconButton(
                icon: const Icon(Icons.arrow_back),
                onPressed: () => context.pop(),
              ),
              actions: [
                if (_userRole == 'owner' || _userRole == 'editor')
                  IconButton(
                    icon: const Icon(Icons.ios_share),
                    tooltip: 'Share',
                    onPressed: _shareBook,
                  ),
                if (_isShared && _userRole == 'owner')
                  IconButton(
                    icon: const Icon(Icons.group),
                    tooltip: 'Members',
                    onPressed: () async {
                      await context.push(
                        '/recipe-books/${widget.recipeBookId}/members?role=$_userRole',
                      );
                    },
                  ),
                if (_recipes.isNotEmpty && _userRole != 'viewer')
                  IconButton(
                    icon: const Icon(Icons.checklist),
                    onPressed: () => _enterSelectMode(),
                  ),
                if (_userRole != 'viewer')
                  PopupMenuButton<String>(
                    onSelected: (value) {
                      if (value == 'edit') {
                        _renameRecipeBook();
                      } else if (value == 'import_url') {
                        context.push('/recipes/add/url', extra: {
                          'recipeBookId': widget.recipeBookId,
                        }).then((_) => _loadRecipeBook());
                      } else if (value == 'import_photo') {
                        context.push('/recipes/add/photo', extra: {
                          'recipeBookId': widget.recipeBookId,
                        }).then((_) => _loadRecipeBook());
                      } else if (value == 'bulk_import') {
                        context.push('/recipes/add/bulk-urls', extra: {
                          'recipeBookId': widget.recipeBookId,
                        }).then((_) => _loadRecipeBook());
                      } else if (value == 'archive') {
                        _archiveRecipeBook();
                      }
                    },
                    itemBuilder: (context) => [
                      const PopupMenuItem(
                        value: 'edit',
                        child: Row(
                          children: [
                            Icon(Icons.edit_outlined),
                            SizedBox(width: 8),
                            Text('Edit'),
                          ],
                        ),
                      ),
                      const PopupMenuItem(
                        value: 'import_url',
                        child: Row(
                          children: [
                            Icon(Icons.link),
                            SizedBox(width: 8),
                            Text('Import from URL'),
                          ],
                        ),
                      ),
                      const PopupMenuItem(
                        value: 'import_photo',
                        child: Row(
                          children: [
                            Icon(Icons.camera_alt),
                            SizedBox(width: 8),
                            Text('Import from Photo'),
                          ],
                        ),
                      ),
                      const PopupMenuItem(
                        value: 'bulk_import',
                        child: Row(
                          children: [
                            Icon(Icons.playlist_add),
                            SizedBox(width: 8),
                            Text('Bulk Import URLs'),
                          ],
                        ),
                      ),
                      if (_userRole == 'owner')
                        PopupMenuItem(
                          value: 'archive',
                          child: Row(
                            children: [
                              Icon(Icons.archive_outlined, color: colorScheme.error),
                              const SizedBox(width: 8),
                              Text('Archive', style: TextStyle(color: colorScheme.error)),
                            ],
                          ),
                        ),
                    ],
                  ),
              ],
            ),
      floatingActionButton: _isSelectMode || _userRole == 'viewer'
          ? null
          : FloatingActionButton(
              heroTag: null, // avoid hero conflict during push to wizard
              onPressed: _addRecipe,
              child: const Icon(Icons.add),
            ),
      bottomNavigationBar: _isSelectMode && _selectedRecipeIds.isNotEmpty
          ? SafeArea(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                  children: [
                    _BulkActionButton(
                      icon: Icons.drive_file_move_outlined,
                      label: 'Move',
                      onTap: _isBulkOperating ? null : _bulkMove,
                    ),
                    _BulkActionButton(
                      icon: Icons.label_outlined,
                      label: 'Tags',
                      onTap: _isBulkOperating ? null : _bulkTags,
                    ),
                    _BulkActionButton(
                      icon: Icons.archive_outlined,
                      label: 'Archive',
                      color: colorScheme.error,
                      onTap: _isBulkOperating ? null : _bulkArchive,
                    ),
                  ],
                ),
              ),
            )
          : null,
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: colorScheme.errorContainer,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            _error!,
                            style: TextStyle(color: colorScheme.onErrorContainer),
                            textAlign: TextAlign.center,
                          ),
                        ),
                        const SizedBox(height: 16),
                        ElevatedButton(
                          onPressed: _loadRecipeBook,
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _loadRecipeBook,
                  child: Center(
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 720),
                      child: ListView(
                        padding: const EdgeInsets.all(16),
                        children: [
                          // Description
                          if (_recipeBook?['description'] != null) ...[
                            Text(
                              _recipeBook!['description'],
                              style: textTheme.bodyLarge?.copyWith(
                                color: colorScheme.onSurfaceVariant,
                              ),
                            ),
                            const SizedBox(height: 16),
                          ],

                          // Recipes header
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(
                                'Recipes (${_recipes.length})',
                                style: textTheme.titleMedium,
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),

                          // Recipes list or empty state
                          if (_recipes.isEmpty)
                            SizedBox(
                              height: MediaQuery.of(context).size.height * 0.4,
                              child: EmptyStateWidget(
                                icon: Icons.restaurant_menu,
                                title: 'Add your first recipe',
                                subtitle: 'Tap + to add a recipe to this book',
                                actionLabel: 'Add Recipe',
                                actionIcon: Icons.add,
                                onAction: _addRecipe,
                              ),
                            )
                          else
                            Builder(
                              builder: (context) {
                                final columns = ResponsiveUtils.recipeGridColumns(context);
                                final cards = _recipes.map((recipe) {
                                  final recipeId = recipe['id']?.toString();
                                  final isSelected = recipeId != null && _selectedRecipeIds.contains(recipeId);
                                  return _RecipeCard(
                                    recipe: recipe,
                                    isSelectMode: _isSelectMode,
                                    isSelected: isSelected,
                                    onTap: _isSelectMode
                                        ? () {
                                            if (recipeId != null) _toggleRecipeSelection(recipeId);
                                          }
                                        : () async {
                                            await context.push('/recipes/${recipe['id']}');
                                            _loadRecipeBook();
                                          },
                                    onLongPress: _isSelectMode || _userRole == 'viewer'
                                        ? null
                                        : () {
                                            if (recipeId != null) {
                                              _enterSelectMode(initialRecipeId: recipeId);
                                            }
                                          },
                                  );
                                }).toList();

                                if (columns == 1) {
                                  return Column(children: cards);
                                }
                                return GridView.count(
                                  crossAxisCount: columns,
                                  crossAxisSpacing: 8,
                                  mainAxisSpacing: 8,
                                  childAspectRatio: 0.75,
                                  shrinkWrap: true,
                                  physics: const NeverScrollableScrollPhysics(),
                                  children: cards,
                                );
                              },
                            ),
                        ],
                      ),
                    ),
                  ),
                ),
    );
  }
}

class _BulkActionButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color? color;
  final VoidCallback? onTap;

  const _BulkActionButton({
    required this.icon,
    required this.label,
    this.color,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final effectiveColor = color ?? Theme.of(context).colorScheme.primary;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: onTap != null ? effectiveColor : effectiveColor.withValues(alpha: 0.4)),
            const SizedBox(height: 4),
            Text(
              label,
              style: TextStyle(
                fontSize: 12,
                color: onTap != null ? effectiveColor : effectiveColor.withValues(alpha: 0.4),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _RecipeCard extends StatelessWidget {
  final dynamic recipe;
  final VoidCallback onTap;
  final VoidCallback? onLongPress;
  final bool isSelectMode;
  final bool isSelected;

  const _RecipeCard({
    required this.recipe,
    required this.onTap,
    this.onLongPress,
    this.isSelectMode = false,
    this.isSelected = false,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final imageUrl = recipe['image_url'] as String?;
    final tags = (recipe['tags'] as List?)?.cast<String>() ?? [];

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      clipBehavior: Clip.antiAlias,
      shape: isSelected
          ? RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
              side: BorderSide(color: colorScheme.primary, width: 2),
            )
          : null,
      child: InkWell(
        onTap: onTap,
        onLongPress: onLongPress,
        child: Stack(
          children: [
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Hero image area (~60% of card)
                SizedBox(
                  height: 180,
                  width: double.infinity,
                  child: imageUrl != null
                      ? CachedNetworkImage(
                          imageUrl: imageUrl,
                          fit: BoxFit.cover,
                          placeholder: (context, url) => Container(
                            color: colorScheme.surfaceContainerHighest,
                            child: const Center(
                              child: CircularProgressIndicator(strokeWidth: 2),
                            ),
                          ),
                          errorWidget: (context, url, error) => Container(
                            color: colorScheme.surfaceContainerHighest,
                            child: Icon(
                              Icons.restaurant,
                              size: 48,
                              color: colorScheme.onSurfaceVariant,
                            ),
                          ),
                        )
                      : Container(
                          color: colorScheme.surfaceContainerHighest,
                          child: Icon(
                            Icons.restaurant,
                            size: 48,
                            color: colorScheme.onSurfaceVariant,
                          ),
                        ),
                ),

                // Recipe info
                Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        recipe['name'] ?? 'Untitled',
                        style: textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 6),

                      // Metadata chips
                      Wrap(
                        spacing: 8,
                        runSpacing: 4,
                        children: [
                          if (recipe['prep_time'] != null)
                            _MetadataChip(
                              icon: Icons.timer_outlined,
                              label: 'Prep ${recipe['prep_time']}m',
                            ),
                          if (recipe['cook_time'] != null)
                            _MetadataChip(
                              icon: Icons.local_fire_department_outlined,
                              label: 'Cook ${recipe['cook_time']}m',
                            ),
                          if (recipe['servings'] != null)
                            _MetadataChip(
                              icon: Icons.people_outline,
                              label: 'Serves ${recipe['servings']}',
                            ),
                        ],
                      ),

                      // Tags
                      if (tags.isNotEmpty) ...[
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 6,
                          runSpacing: 4,
                          children: tags
                              .map((tag) => Chip(
                                    label: Text(tag),
                                    labelStyle: textTheme.labelSmall,
                                    materialTapTargetSize:
                                        MaterialTapTargetSize.shrinkWrap,
                                    visualDensity: VisualDensity.compact,
                                    backgroundColor:
                                        colorScheme.surfaceContainerHighest,
                                    padding: EdgeInsets.zero,
                                  ))
                              .toList(),
                        ),
                      ],
                    ],
                  ),
                ),
              ],
            ),
            // Selection checkbox overlay
            if (isSelectMode)
              Positioned(
                top: 8,
                right: 8,
                child: Container(
                  decoration: BoxDecoration(
                    color: isSelected
                        ? colorScheme.primary
                        : colorScheme.surface.withValues(alpha: 0.8),
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: isSelected ? colorScheme.primary : colorScheme.outline,
                      width: 2,
                    ),
                  ),
                  padding: const EdgeInsets.all(2),
                  child: Icon(
                    isSelected ? Icons.check : null,
                    size: 18,
                    color: isSelected ? colorScheme.onPrimary : Colors.transparent,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _MetadataChip extends StatelessWidget {
  final IconData icon;
  final String label;

  const _MetadataChip({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 14, color: colorScheme.outline),
        const SizedBox(width: 4),
        Text(
          label,
          style: textTheme.bodySmall?.copyWith(
            color: colorScheme.outline,
          ),
        ),
      ],
    );
  }
}
