import 'dart:async';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';

class SearchScreen extends StatefulWidget {
  const SearchScreen({super.key});

  @override
  State<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends State<SearchScreen> {
  final _apiClient = getIt<ApiClient>();
  final _searchController = TextEditingController();
  Timer? _debounce;

  bool _isLoading = false;
  String? _error;
  List<dynamic> _myRecipes = [];
  List<dynamic> _publicRecipes = [];
  List<dynamic> _users = [];
  bool _hasSearched = false;

  // Filter state — reset when query text changes
  String? _filterBookId;
  Set<String> _filterTags = {};
  int? _maxTotalTime;

  @override
  void dispose() {
    _searchController.dispose();
    _debounce?.cancel();
    super.dispose();
  }

  void _onSearchChanged(String query) {
    _debounce?.cancel();
    // Reset stale filters when user types a new query
    setState(() {
      _filterBookId = null;
      _filterTags.clear();
      _maxTotalTime = null;
    });
    if (query.length < 2) {
      setState(() {
        _myRecipes = [];
        _publicRecipes = [];
        _users = [];
        _hasSearched = false;
        _error = null;
      });
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 300), () {
      _performSearch(query);
    });
  }

  void _onFilterChanged() {
    _performSearch(_searchController.text);
  }

  Future<void> _performSearch(String query) async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final response = await _apiClient.search(
        query,
        bookId: _filterBookId,
        tags: _filterTags.isEmpty ? null : _filterTags.toList(),
        maxPrepTime: _maxTotalTime,
        maxCookTime: _maxTotalTime,
      );
      if (mounted) {
        setState(() {
          _myRecipes = response.data['my_recipes'] ?? [];
          _publicRecipes = response.data['public_recipes'] ?? [];
          _users = response.data['users'] ?? [];
          _isLoading = false;
          _hasSearched = true;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Search failed: $e';
          _isLoading = false;
          _hasSearched = true;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
        title: TextField(
          controller: _searchController,
          autofocus: true,
          decoration: InputDecoration(
            hintText: 'Search recipes, people...',
            border: InputBorder.none,
            hintStyle: TextStyle(color: colorScheme.onSurfaceVariant),
          ),
          style: const TextStyle(fontSize: 16),
          onChanged: _onSearchChanged,
        ),
        actions: [
          if (_searchController.text.isNotEmpty)
            IconButton(
              icon: const Icon(Icons.close, size: 20),
              onPressed: () {
                _searchController.clear();
                _onSearchChanged('');
              },
            ),
        ],
      ),
      body: Column(
        children: [
          if (_hasSearched && !_isLoading && (_myRecipes.isNotEmpty || _publicRecipes.isNotEmpty))
            _buildFilterRow(),
          Expanded(child: _buildBody()),
        ],
      ),
    );
  }

  List<MapEntry<String, String>> _availableBooks() {
    final seen = <String>{};
    final books = <MapEntry<String, String>>[];
    for (final r in _myRecipes) {
      final id = r['recipe_book_id'] as String?;
      final name = r['recipe_book_name'] as String?;
      if (id != null && name != null && seen.add(id)) {
        books.add(MapEntry(id, name));
      }
    }
    return books;
  }

  List<String> _availableTags() {
    final tagCounts = <String, int>{};
    for (final r in [..._myRecipes, ..._publicRecipes]) {
      for (final tag in (r['tags'] as List? ?? [])) {
        final t = tag as String;
        tagCounts[t] = (tagCounts[t] ?? 0) + 1;
      }
    }
    final sorted = tagCounts.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    return sorted.take(10).map((e) => e.key).toList();
  }

  Widget _buildFilterRow() {
    final availableBooks = _availableBooks();
    final availableTags = _availableTags();
    const timeOptions = [15, 30, 60];

    if (availableBooks.isEmpty && availableTags.isEmpty) {
      return const SizedBox.shrink();
    }

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      child: Row(
        children: [
          for (final entry in availableBooks)
            Padding(
              padding: const EdgeInsets.only(right: 6),
              child: FilterChip(
                label: Text(entry.value),
                selected: _filterBookId == entry.key,
                onSelected: (selected) {
                  setState(() {
                    _filterBookId = selected ? entry.key : null;
                  });
                  _onFilterChanged();
                },
              ),
            ),
          for (final t in timeOptions)
            Padding(
              padding: const EdgeInsets.only(right: 6),
              child: FilterChip(
                label: Text('≤${t}min'),
                selected: _maxTotalTime == t,
                onSelected: (selected) {
                  setState(() {
                    _maxTotalTime = selected ? t : null;
                  });
                  _onFilterChanged();
                },
              ),
            ),
          for (final tag in availableTags)
            Padding(
              padding: const EdgeInsets.only(right: 6),
              child: FilterChip(
                label: Text('#$tag'),
                selected: _filterTags.contains(tag),
                onSelected: (selected) {
                  setState(() {
                    if (selected) {
                      _filterTags.add(tag);
                    } else {
                      _filterTags.remove(tag);
                    }
                  });
                  _onFilterChanged();
                },
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildBody() {
    final colorScheme = Theme.of(context).colorScheme;

    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(
            _error!,
            style: TextStyle(color: colorScheme.onSurfaceVariant),
            textAlign: TextAlign.center,
          ),
        ),
      );
    }

    if (!_hasSearched) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              'Search your recipes',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: colorScheme.onSurface,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              'Find recipes by name, ingredient, or tag',
              style: TextStyle(color: colorScheme.onSurfaceVariant),
            ),
          ],
        ),
      );
    }

    final hasResults =
        _myRecipes.isNotEmpty || _publicRecipes.isNotEmpty || _users.isNotEmpty;

    if (!hasResults) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.search_off, size: 48, color: colorScheme.outline),
            const SizedBox(height: 16),
            Text(
              'No results for "${_searchController.text}"',
              style: TextStyle(
                color: colorScheme.onSurfaceVariant,
                fontSize: 16,
              ),
            ),
          ],
        ),
      );
    }

    return ListView(
      padding: const EdgeInsets.symmetric(vertical: 8),
      children: [
        if (_myRecipes.isNotEmpty) ...[
          _buildSectionHeader('My Recipes'),
          ..._myRecipes.map((r) => _buildRecipeTile(r, isPublic: false)),
        ],
        if (_publicRecipes.isNotEmpty) ...[
          _buildSectionHeader('Public Recipes'),
          ..._publicRecipes.map((r) => _buildRecipeTile(r, isPublic: true)),
        ],
        if (_users.isNotEmpty) ...[
          _buildSectionHeader('People'),
          ..._users.map(_buildUserTile),
        ],
      ],
    );
  }

  Widget _buildSectionHeader(String title) {
    final colorScheme = Theme.of(context).colorScheme;

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 4),
      child: Text(
        title.toUpperCase(),
        style: TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w600,
          color: colorScheme.outline,
          letterSpacing: 0.8,
        ),
      ),
    );
  }

  Widget _buildRecipeTile(dynamic recipe, {required bool isPublic}) {
    final colorScheme = Theme.of(context).colorScheme;
    final prepTime = recipe['prep_time'] as int?;
    final cookTime = recipe['cook_time'] as int?;
    final totalTime = (prepTime ?? 0) + (cookTime ?? 0);
    final bookName = recipe['recipe_book_name'] as String? ?? '';
    final ingredients = (recipe['ingredients'] as List?)?.cast<String>() ?? [];

    String contextLine = bookName;
    if (isPublic) {
      final owner = recipe['owner'];
      final username = owner?['username'] as String?;
      if (username != null) {
        contextLine = 'by @$username';
      }
    }
    if (totalTime > 0) {
      contextLine += ' · ${totalTime}m';
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      child: Card(
        clipBehavior: Clip.antiAlias,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        child: InkWell(
          onTap: () => context.push('/recipes/${recipe['id']}'),
          child: SizedBox(
            height: 100,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Photo-dominant image: 100×100
                SizedBox(
                  width: 100,
                  child: recipe['image_url'] != null
                      ? Image.network(
                          recipe['image_url'] as String,
                          fit: BoxFit.cover,
                          loadingBuilder: (context, child, progress) =>
                              progress == null ? child : _buildRecipeIcon(size: 100),
                          errorBuilder: (context, error, stack) => _buildRecipeIcon(size: 100),
                        )
                      : _buildRecipeIcon(size: 100),
                ),

                // Recipe details
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(12, 10, 8, 10),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          recipe['name'] as String? ?? 'Untitled',
                          style: const TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w600,
                          ),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                        if (contextLine.isNotEmpty) ...[
                          const SizedBox(height: 2),
                          Text(
                            contextLine,
                            style: TextStyle(
                              fontSize: 12,
                              color: colorScheme.outline,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                        if (ingredients.isNotEmpty) ...[
                          const SizedBox(height: 2),
                          Text(
                            ingredients.take(3).join(', '),
                            style: TextStyle(
                              fontSize: 12,
                              color: colorScheme.outline,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ],
                    ),
                  ),
                ),

                // Chevron
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: Icon(Icons.chevron_right, color: colorScheme.outline),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildRecipeIcon({double size = 100}) {
    final colorScheme = Theme.of(context).colorScheme;

    return Container(
      width: size,
      height: size,
      color: colorScheme.primaryContainer,
      child: Icon(
        Icons.restaurant,
        size: size * 0.4,
        color: colorScheme.onSurfaceVariant,
      ),
    );
  }

  Widget _buildUserTile(dynamic user) {
    final colorScheme = Theme.of(context).colorScheme;
    final username = user['username'] as String?;
    final name = user['name'] as String?;
    final status = user['friendship_status'] as String? ?? 'none';

    String statusLabel = '';
    if (status == 'friends') statusLabel = 'Friends';
    if (status == 'request_sent') statusLabel = 'Request sent';
    if (status == 'request_received') statusLabel = 'Pending';

    return ListTile(
      leading: CircleAvatar(
        radius: 24,
        backgroundColor: colorScheme.primaryContainer,
        backgroundImage:
            user['picture'] != null ? NetworkImage(user['picture']) : null,
        child: user['picture'] == null
            ? Icon(Icons.person, color: colorScheme.onSurfaceVariant)
            : null,
      ),
      title: Text(username != null ? '@$username' : 'Unknown'),
      subtitle: Row(
        children: [
          if (name != null)
            Flexible(
              child: Text(
                name,
                style: TextStyle(
                  color: colorScheme.outline,
                  fontSize: 13,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          if (name != null && statusLabel.isNotEmpty)
            Text(
              ' · ',
              style: TextStyle(color: colorScheme.outline, fontSize: 13),
            ),
          if (statusLabel.isNotEmpty)
            Text(
              statusLabel,
              style: TextStyle(
                color: colorScheme.outline,
                fontSize: 13,
              ),
            ),
        ],
      ),
      trailing: Icon(Icons.chevron_right, color: colorScheme.outline),
      onTap: () {
        // TODO: Navigate to user profile
      },
    );
  }
}
