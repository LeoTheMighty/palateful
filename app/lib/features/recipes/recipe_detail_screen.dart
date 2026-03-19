import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../shopping_cart/models/shopping_list.dart';
import '../shopping_cart/services/shopping_cart_service.dart';

class RecipeDetailScreen extends StatefulWidget {
  final String recipeId;

  const RecipeDetailScreen({super.key, required this.recipeId});

  @override
  State<RecipeDetailScreen> createState() => _RecipeDetailScreenState();
}

class _RecipeDetailScreenState extends State<RecipeDetailScreen> {
  final _apiClient = getIt<ApiClient>();
  Map<String, dynamic>? _recipe;
  List<dynamic> _ingredients = [];
  List<dynamic> _notes = [];
  bool _isLoading = true;
  String? _error;
  final Set<int> _checkedIngredients = {};
  bool _isFavorite = false;
  bool _isTogglingFavorite = false;
  bool _isMovingOrCopying = false;
  bool _isAddingNote = false;
  final _noteController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadRecipe();
  }

  @override
  void dispose() {
    _noteController.dispose();
    super.dispose();
  }

  Future<void> _loadRecipe() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final response = await _apiClient.getRecipe(widget.recipeId);
      if (mounted) {
        setState(() {
          _recipe = response.data;
          _ingredients = response.data['ingredients'] ?? [];
          _notes = (response.data['notes'] as List?) ?? [];
          _isFavorite = response.data['is_favorite'] == true;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Failed to load recipe: $e';
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _toggleFavorite() async {
    if (_isTogglingFavorite) return;
    setState(() => _isTogglingFavorite = true);

    // Optimistic update
    final wasFavorite = _isFavorite;
    setState(() => _isFavorite = !_isFavorite);

    try {
      await _apiClient.toggleFavorite(widget.recipeId);
    } catch (e) {
      if (mounted) {
        setState(() => _isFavorite = wasFavorite);
      }
    } finally {
      if (mounted) {
        setState(() => _isTogglingFavorite = false);
      }
    }
  }

  Future<void> _addIngredientsToCart() async {
    final recipeId = _recipe?['id'] as String?;
    if (recipeId == null) return;

    final service = getIt<ShoppingCartService>();
    List<ShoppingList> lists;
    try {
      lists = await service.getShoppingLists();
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Failed to load shopping lists')),
      );
      return;
    }

    if (lists.isEmpty) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content: Text('No shopping lists — tap + to create one')),
      );
      return;
    }

    ShoppingList? selectedList;
    if (lists.length == 1) {
      selectedList = lists.first;
    } else {
      if (!mounted) return;
      selectedList = await showModalBottomSheet<ShoppingList>(
        context: context,
        builder: (context) => ListView.builder(
          itemCount: lists.length,
          itemBuilder: (context, i) => ListTile(
            leading: const Icon(Icons.shopping_cart_outlined),
            title: Text(lists[i].name.isEmpty ? 'Shopping List' : lists[i].name),
            subtitle: Text('${lists[i].uncheckedCount} items'),
            onTap: () => Navigator.of(context).pop(lists[i]),
          ),
        ),
      );
    }

    if (selectedList == null) return;
    if (!mounted) return;

    try {
      final result = await service.populateFromRecipe(selectedList.id, recipeId);
      if (!mounted) return;
      final count = result.itemsAdded;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
              'Added $count ingredient${count == 1 ? '' : 's'} to ${selectedList.name.isEmpty ? 'Shopping List' : selectedList.name}'),
        ),
      );
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Failed to add ingredients to cart')),
      );
    }
  }

  Future<void> _archiveRecipe() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Archive Recipe?'),
        content: const Text(
          'This recipe will be moved to your archive. You can restore it anytime.',
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

    try {
      HapticFeedback.selectionClick();
      await _apiClient.deleteRecipe(widget.recipeId);
      if (mounted) {
        context.pop();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Recipe archived')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not archive recipe. Please try again.')),
        );
      }
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

  Future<void> _moveRecipe() async {
    if (_isMovingOrCopying) return;
    final currentBookId = _recipe?['recipe_book_id']?.toString();
    final book = await _showBookPicker(excludeBookId: currentBookId);
    if (book == null) return;

    setState(() => _isMovingOrCopying = true);
    try {
      HapticFeedback.selectionClick();
      await _apiClient.moveRecipe(widget.recipeId, book['id']);
      if (mounted) {
        context.pop();
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Recipe moved to ${book['name']}')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not move recipe. Please try again.')),
        );
      }
    } finally {
      if (mounted) setState(() => _isMovingOrCopying = false);
    }
  }

  Future<void> _copyRecipe() async {
    if (_isMovingOrCopying) return;
    final currentBookId = _recipe?['recipe_book_id']?.toString();
    final book = await _showBookPicker(excludeBookId: currentBookId);
    if (book == null) return;

    setState(() => _isMovingOrCopying = true);
    try {
      HapticFeedback.selectionClick();
      await _apiClient.copyRecipe(widget.recipeId, book['id']);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Recipe copied to ${book['name']}')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not copy recipe. Please try again.')),
        );
      }
    } finally {
      if (mounted) setState(() => _isMovingOrCopying = false);
    }
  }

  Future<Map<String, dynamic>?> _showOwnedBookPicker({String? excludeBookId}) async {
    try {
      final response = await _apiClient.getRecipeBooks();
      final books = ((response.data['items'] as List?) ?? [])
          .where((b) =>
              b['id']?.toString() != excludeBookId &&
              b['user_role'] == 'owner')
          .toList();

      if (!mounted) return null;
      if (books.isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('No personal books available to fork into')),
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
                    'Fork into...',
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

  Future<void> _forkRecipe() async {
    if (_isMovingOrCopying) return;
    final currentBookId = _recipe?['recipe_book_id']?.toString();
    final messenger = ScaffoldMessenger.of(context);
    final book = await _showOwnedBookPicker(excludeBookId: currentBookId);
    if (book == null) return;

    setState(() => _isMovingOrCopying = true);
    try {
      HapticFeedback.selectionClick();
      final response = await _apiClient.forkRecipe(
          widget.recipeId, book['id']);
      final forkedId = response.data['id'] as String?;
      if (mounted && forkedId != null) {
        messenger.showSnackBar(
          SnackBar(content: Text('Forked to ${book['name']}')),
        );
        context.push('/recipes/$forkedId');
      }
    } catch (e) {
      if (mounted) {
        messenger.showSnackBar(
          const SnackBar(content: Text('Could not fork recipe. Please try again.')),
        );
      }
    } finally {
      if (mounted) setState(() => _isMovingOrCopying = false);
    }
  }

  void _startCooking() {
    context.push('/recipes/${widget.recipeId}/cook');
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      floatingActionButton: !_isLoading && _error == null
          ? FloatingActionButton.extended(
              onPressed: _startCooking,
              icon: const Icon(Icons.restaurant),
              label: const Text('Start Cooking'),
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
                            style: TextStyle(
                                color: colorScheme.onErrorContainer),
                            textAlign: TextAlign.center,
                          ),
                        ),
                        const SizedBox(height: 16),
                        ElevatedButton(
                          onPressed: _loadRecipe,
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                )
              : CustomScrollView(
                  slivers: [
                    // App Bar
                    SliverAppBar(
                      expandedHeight: _recipe?['image_url'] != null ? 200 : 0,
                      pinned: true,
                      leading: IconButton(
                        icon: const Icon(Icons.arrow_back),
                        onPressed: () => context.pop(),
                      ),
                      flexibleSpace: _recipe?['image_url'] != null
                          ? FlexibleSpaceBar(
                              background: Image.network(
                                _recipe!['image_url'],
                                fit: BoxFit.cover,
                              ),
                            )
                          : null,
                      title: Text(_recipe?['name'] ?? 'Recipe'),
                      actions: [
                        IconButton(
                          icon: Icon(
                            _isFavorite ? Icons.favorite : Icons.favorite_border,
                            color: _isFavorite ? Colors.red : null,
                          ),
                          onPressed: _toggleFavorite,
                        ),
                        if (_recipe?['can_edit'] == true)
                          IconButton(
                            icon: const Icon(Icons.edit_outlined),
                            onPressed: () async {
                              await context.push('/recipes/${widget.recipeId}/edit');
                              _loadRecipe();
                            },
                          ),
                        PopupMenuButton<String>(
                          onSelected: (value) {
                            if (value == 'add_to_cart') {
                              _addIngredientsToCart();
                            } else if (value == 'move') {
                              _moveRecipe();
                            } else if (value == 'copy') {
                              _copyRecipe();
                            } else if (value == 'fork') {
                              _forkRecipe();
                            } else if (value == 'archive') {
                              _archiveRecipe();
                            }
                          },
                          itemBuilder: (context) => [
                            const PopupMenuItem(
                              value: 'add_to_cart',
                              child: Row(
                                children: [
                                  Icon(Icons.shopping_cart_outlined),
                                  SizedBox(width: 8),
                                  Text('Add to Cart'),
                                ],
                              ),
                            ),
                            if (_recipe?['can_edit'] == true)
                              const PopupMenuItem(
                                value: 'move',
                                child: Row(
                                  children: [
                                    Icon(Icons.drive_file_move_outlined),
                                    SizedBox(width: 8),
                                    Text('Move to Book...'),
                                  ],
                                ),
                              ),
                            const PopupMenuItem(
                              value: 'copy',
                              child: Row(
                                children: [
                                  Icon(Icons.copy_outlined),
                                  SizedBox(width: 8),
                                  Text('Copy to Book...'),
                                ],
                              ),
                            ),
                            const PopupMenuItem(
                              value: 'fork',
                              child: Row(
                                children: [
                                  Icon(Icons.call_split_outlined),
                                  SizedBox(width: 8),
                                  Text('Make My Copy'),
                                ],
                              ),
                            ),
                            if (_recipe?['can_edit'] == true)
                              PopupMenuItem(
                                value: 'archive',
                                child: Row(
                                  children: [
                                    Icon(Icons.archive_outlined,
                                        color: Theme.of(context).colorScheme.error),
                                    const SizedBox(width: 8),
                                    Text('Archive',
                                        style: TextStyle(
                                            color: Theme.of(context).colorScheme.error)),
                                  ],
                                ),
                              ),
                          ],
                        ),
                      ],
                    ),

                    // Content
                    SliverPadding(
                      padding: const EdgeInsets.all(16),
                      sliver: SliverList(
                        delegate: SliverChildListDelegate([
                          // Lineage badge (fork provenance)
                          if (_recipe?['forked_from_recipe_name'] != null) ...[
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                              decoration: BoxDecoration(
                                color: colorScheme.secondaryContainer,
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Icon(Icons.call_split_outlined,
                                      size: 14, color: colorScheme.onSecondaryContainer),
                                  const SizedBox(width: 6),
                                  Flexible(
                                    child: Text(
                                      'Forked from: ${_recipe!['forked_from_recipe_name']} (${_recipe!['forked_from_book_name'] ?? 'unknown book'})',
                                      style: textTheme.labelSmall?.copyWith(
                                          color: colorScheme.onSecondaryContainer),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            const SizedBox(height: 12),
                          ],

                          // Recipe info
                          if (_recipe?['description'] != null) ...[
                            Text(
                              _recipe!['description'],
                              style: textTheme.bodyLarge?.copyWith(
                                  color: colorScheme.onSurfaceVariant),
                            ),
                            const SizedBox(height: 16),
                          ],

                          // Time and servings
                          Wrap(
                            spacing: 16,
                            runSpacing: 8,
                            children: [
                              if (_recipe?['prep_time'] != null)
                                _InfoChip(
                                  icon: Icons.timer_outlined,
                                  label: 'Prep: ${_recipe!['prep_time']} min',
                                ),
                              if (_recipe?['cook_time'] != null)
                                _InfoChip(
                                  icon: Icons.local_fire_department_outlined,
                                  label: 'Cook: ${_recipe!['cook_time']} min',
                                ),
                              if (_recipe?['servings'] != null)
                                _InfoChip(
                                  icon: Icons.people_outline,
                                  label: 'Serves ${_recipe!['servings']}',
                                ),
                            ],
                          ),
                          // Version history badge
                          if ((_recipe?['version_count'] as int? ?? 0) > 0) ...[
                            const SizedBox(height: 12),
                            GestureDetector(
                              onTap: () => context.push(
                                '/recipes/${widget.recipeId}/versions',
                                extra: {'recipeName': _recipe?['name'] ?? ''},
                              ),
                              child: _InfoChip(
                                icon: Icons.history,
                                label: 'v${_recipe!['version_count']} — tap to view history',
                              ),
                            ),
                          ],
                          const SizedBox(height: 24),

                          // Ingredients section
                          Text(
                            'Ingredients',
                            style: textTheme.titleLarge,
                          ),
                          const SizedBox(height: 8),
                          ...(_ingredients.asMap().entries.map((entry) {
                            final index = entry.key;
                            final ing = entry.value;
                            final ingredientInfo = ing['ingredient'];
                            return CheckboxListTile(
                              value: _checkedIngredients.contains(index),
                              onChanged: (checked) {
                                setState(() {
                                  if (checked == true) {
                                    _checkedIngredients.add(index);
                                  } else {
                                    _checkedIngredients.remove(index);
                                  }
                                });
                              },
                              title: Text(
                                '${ing['quantity_display']} ${ing['unit_display']} ${ingredientInfo?['canonical_name'] ?? 'Unknown'}',
                                style: _checkedIngredients.contains(index)
                                    ? TextStyle(
                                        decoration: TextDecoration.lineThrough,
                                        color: colorScheme.outline,
                                      )
                                    : null,
                              ),
                              subtitle: ing['notes'] != null
                                  ? Text(ing['notes'])
                                  : null,
                              controlAffinity: ListTileControlAffinity.leading,
                              contentPadding: EdgeInsets.zero,
                            );
                          })),
                          const SizedBox(height: 24),

                          // Steps section (structured) or legacy instructions fallback
                          if ((_recipe?['steps'] as List?)?.isNotEmpty == true) ...[
                            Text(
                              'Steps',
                              style: textTheme.titleLarge,
                            ),
                            const SizedBox(height: 8),
                            ...(_recipe!['steps'] as List).asMap().entries.map((entry) {
                              final index = entry.key;
                              final step = entry.value;
                              return Padding(
                                padding: const EdgeInsets.only(bottom: 12),
                                child: Row(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Container(
                                      width: 32,
                                      height: 32,
                                      decoration: BoxDecoration(
                                        color: colorScheme.surfaceContainerHighest,
                                        borderRadius: BorderRadius.circular(8),
                                      ),
                                      child: Center(
                                        child: Text(
                                          '${index + 1}',
                                          style: textTheme.bodyMedium?.copyWith(
                                            fontWeight: FontWeight.w600,
                                            color: colorScheme.secondary,
                                          ),
                                        ),
                                      ),
                                    ),
                                    const SizedBox(width: 12),
                                    Expanded(
                                      child: Padding(
                                        padding: const EdgeInsets.only(top: 6),
                                        child: Text(
                                          step['instruction'] ?? '',
                                          style: textTheme.bodyLarge
                                              ?.copyWith(height: 1.5),
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              );
                            }),
                          ] else if (_recipe?['instructions'] != null) ...[
                            Text(
                              'Instructions',
                              style: textTheme.titleLarge,
                            ),
                            const SizedBox(height: 8),
                            Container(
                              padding: const EdgeInsets.all(16),
                              decoration: BoxDecoration(
                                color: colorScheme.surfaceContainerHighest,
                                borderRadius: BorderRadius.circular(12),
                                border: Border.all(
                                    color: colorScheme.outlineVariant),
                              ),
                              child: Text(
                                _recipe!['instructions'],
                                style: textTheme.bodyLarge
                                    ?.copyWith(height: 1.6),
                              ),
                            ),
                          ],
                          const SizedBox(height: 24),

                          // Tags section
                          if ((_recipe?['tags'] as List?)?.isNotEmpty == true) ...[
                            Text(
                              'Tags',
                              style: textTheme.titleLarge,
                            ),
                            const SizedBox(height: 8),
                            Wrap(
                              spacing: 8,
                              runSpacing: 4,
                              children: (_recipe!['tags'] as List)
                                  .map((tag) => Chip(
                                        label: Text(tag.toString()),
                                        backgroundColor: colorScheme
                                            .surfaceContainerHighest,
                                      ))
                                  .toList(),
                            ),
                            const SizedBox(height: 24),
                          ],

                          // Source URL
                          if (_recipe?['source_url'] != null &&
                              (_recipe!['source_url'] as String).isNotEmpty) ...[
                            InkWell(
                              onTap: () => launchUrl(
                                Uri.parse(_recipe!['source_url']),
                                mode: LaunchMode.externalApplication,
                              ),
                              child: Row(
                                children: [
                                  Icon(Icons.link,
                                      size: 18, color: colorScheme.secondary),
                                  const SizedBox(width: 8),
                                  Expanded(
                                    child: Text(
                                      _recipe!['source_url'],
                                      style: TextStyle(
                                        color: colorScheme.secondary,
                                        decoration: TextDecoration.underline,
                                      ),
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            const SizedBox(height: 24),
                          ],

                          // Notes section — visible to all recipe members
                          ...[
                            Text('Notes', style: textTheme.titleLarge),
                            const SizedBox(height: 8),
                            ..._notes.map((note) => _buildNoteCard(note as Map<String, dynamic>, colorScheme, textTheme)),
                            const SizedBox(height: 12),
                            _buildAddNoteInput(colorScheme),
                            const SizedBox(height: 24),
                          ],

                          const SizedBox(height: 32),
                        ]),
                      ),
                    ),
                  ],
                ),
    );
  }

  Widget _buildNoteCard(Map<String, dynamic> note, ColorScheme colorScheme, TextTheme textTheme) {
    // Show delete for all members — backend enforces authorization
    // (creator OR book owner may delete; editor on others' notes will get 403 with snackbar)
    const canDelete = true;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: colorScheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(note['body'] as String, style: textTheme.bodyMedium),
                  const SizedBox(height: 4),
                  Text(
                    _formatNoteDate(note['created_at'] as String?),
                    style: textTheme.labelSmall?.copyWith(color: colorScheme.onSurfaceVariant),
                  ),
                ],
              ),
            ),
            if (canDelete)
              IconButton(
                icon: Icon(Icons.delete_outline, size: 18, color: colorScheme.onSurfaceVariant),
                onPressed: () => _deleteNote(note['id'] as String),
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(),
                visualDensity: VisualDensity.compact,
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildAddNoteInput(ColorScheme colorScheme) {
    return Row(
      children: [
        Expanded(
          child: TextField(
            controller: _noteController,
            decoration: const InputDecoration(hintText: 'Add a note...'),
            maxLines: null,
            textInputAction: TextInputAction.newline,
          ),
        ),
        IconButton(
          icon: _isAddingNote
              ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
              : const Icon(Icons.send),
          onPressed: _isAddingNote ? null : _submitNote,
        ),
      ],
    );
  }

  Future<void> _submitNote() async {
    final body = _noteController.text.trim();
    if (body.isEmpty) return;
    setState(() => _isAddingNote = true);
    try {
      final response = await _apiClient.addRecipeNote(widget.recipeId, body);
      if (mounted) {
        final newNote = response.data as Map<String, dynamic>;
        setState(() {
          _notes = [..._notes, newNote];
          _isAddingNote = false;
        });
        _noteController.clear();
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isAddingNote = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to add note: $e')),
        );
      }
    }
  }

  Future<void> _deleteNote(String noteId) async {
    try {
      await _apiClient.deleteRecipeNote(widget.recipeId, noteId);
      if (mounted) {
        setState(() {
          _notes = _notes.where((n) => (n as Map)['id'] != noteId).toList();
        });
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to delete note: $e')),
        );
      }
    }
  }

  String _formatNoteDate(String? isoDate) {
    if (isoDate == null) return '';
    try {
      final dt = DateTime.parse(isoDate).toLocal();
      final now = DateTime.now();
      final diff = now.difference(dt);
      if (diff.inMinutes < 1) return 'just now';
      if (diff.inHours < 1) return '${diff.inMinutes}m ago';
      if (diff.inDays < 1) return '${diff.inHours}h ago';
      if (diff.inDays < 7) return '${diff.inDays}d ago';
      return '${dt.day}/${dt.month}/${dt.year}';
    } catch (_) {
      return isoDate;
    }
  }
}

class _InfoChip extends StatelessWidget {
  final IconData icon;
  final String label;

  const _InfoChip({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: colorScheme.secondaryContainer.withValues(alpha: 0.4),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: colorScheme.secondary),
          const SizedBox(width: 6),
          Text(
            label,
            style: TextStyle(
              color: colorScheme.secondary,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }
}
