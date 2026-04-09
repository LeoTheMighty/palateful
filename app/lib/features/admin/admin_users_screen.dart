import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';

class AdminUsersScreen extends StatefulWidget {
  const AdminUsersScreen({super.key});

  @override
  State<AdminUsersScreen> createState() => _AdminUsersScreenState();
}

class _AdminUsersScreenState extends State<AdminUsersScreen> {
  final _apiClient = getIt<ApiClient>();
  final _scrollController = ScrollController();

  bool _isLoading = true;
  String? _error;
  List<dynamic> _users = [];
  int _offset = 0;
  bool _hasMore = true;
  bool _isLoadingMore = false;
  static const _pageSize = 50;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    _fetchUsers();
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >=
            _scrollController.position.maxScrollExtent - 200 &&
        !_isLoadingMore &&
        _hasMore) {
      _loadMore();
    }
  }

  Future<void> _fetchUsers() async {
    setState(() {
      _isLoading = true;
      _error = null;
      _offset = 0;
      _users = [];
      _hasMore = true;
    });

    try {
      final response = await _apiClient.getAdminUsers(limit: _pageSize, offset: 0);
      if (!mounted) return;

      final data = response.data;
      final List<dynamic> items = data is Map && data['users'] != null
          ? data['users'] as List<dynamic>
          : (data is List ? data : []);

      setState(() {
        _users = items;
        _offset = items.length;
        _hasMore = items.length >= _pageSize;
        _isLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = 'Failed to load users: $e';
        _isLoading = false;
      });
    }
  }

  Future<void> _loadMore() async {
    if (_isLoadingMore || !_hasMore) return;

    setState(() => _isLoadingMore = true);

    try {
      final response = await _apiClient.getAdminUsers(limit: _pageSize, offset: _offset);
      if (!mounted) return;

      final data = response.data;
      final List<dynamic> items = data is Map && data['users'] != null
          ? data['users'] as List<dynamic>
          : (data is List ? data : []);

      setState(() {
        _users.addAll(items);
        _offset += items.length;
        _hasMore = items.length >= _pageSize;
        _isLoadingMore = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _isLoadingMore = false);
    }
  }

  Future<void> _toggleAdmin(int index) async {
    final user = _users[index] as Map<String, dynamic>;
    final userId = user['id'] as String;
    final currentIsAdmin = user['is_admin'] as bool? ?? false;
    final name = user['name'] as String? ?? user['email'] as String? ?? 'this user';

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(currentIsAdmin ? 'Remove Admin' : 'Grant Admin'),
        content: Text(
          currentIsAdmin
              ? 'Remove admin privileges from $name?'
              : 'Grant admin privileges to $name?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: Text(currentIsAdmin ? 'Remove' : 'Grant'),
          ),
        ],
      ),
    );

    if (confirmed != true || !mounted) return;

    try {
      await _apiClient.updateUserAdmin(userId, !currentIsAdmin);
      if (!mounted) return;

      setState(() {
        final updatedUser = Map<String, dynamic>.from(user);
        updatedUser['is_admin'] = !currentIsAdmin;
        _users[index] = updatedUser;
      });

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            !currentIsAdmin
                ? '$name is now an admin'
                : 'Admin removed from $name',
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to update admin status: $e')),
      );
    }
  }

  String _formatDate(String? dateStr) {
    if (dateStr == null) return '';
    try {
      final dt = DateTime.parse(dateStr);
      return '${dt.month}/${dt.day}/${dt.year}';
    } catch (_) {
      return dateStr;
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(
        title: Text('Users', style: textTheme.titleLarge),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.error_outline, size: 64, color: colorScheme.error),
                      const SizedBox(height: 16),
                      Text(_error!, style: textTheme.bodyMedium, textAlign: TextAlign.center),
                      const SizedBox(height: 16),
                      FilledButton.icon(
                        onPressed: _fetchUsers,
                        icon: const Icon(Icons.refresh),
                        label: const Text('Retry'),
                      ),
                    ],
                  ),
                )
              : _users.isEmpty
                  ? Center(
                      child: Text('No users found', style: textTheme.bodyLarge),
                    )
                  : RefreshIndicator(
                      onRefresh: _fetchUsers,
                      child: ListView.builder(
                        controller: _scrollController,
                        itemCount: _users.length + (_isLoadingMore ? 1 : 0),
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        itemBuilder: (context, index) {
                          if (index == _users.length) {
                            return const Center(
                              child: Padding(
                                padding: EdgeInsets.all(16),
                                child: CircularProgressIndicator(),
                              ),
                            );
                          }

                          final user = _users[index] as Map<String, dynamic>;
                          final name = user['name'] as String? ?? 'No name';
                          final email = user['email'] as String? ?? '';
                          final username = user['username'] as String?;
                          final isAdmin = user['is_admin'] as bool? ?? false;
                          final createdAt = user['created_at'] as String?;

                          return ListTile(
                            leading: CircleAvatar(
                              backgroundColor: isAdmin
                                  ? colorScheme.primaryContainer
                                  : colorScheme.surfaceContainerHighest,
                              child: Icon(
                                isAdmin ? Icons.admin_panel_settings : Icons.person,
                                color: isAdmin
                                    ? colorScheme.onPrimaryContainer
                                    : colorScheme.onSurfaceVariant,
                              ),
                            ),
                            title: Row(
                              children: [
                                Flexible(
                                  child: Text(
                                    name,
                                    style: textTheme.bodyMedium?.copyWith(
                                      fontWeight: FontWeight.w600,
                                    ),
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                                if (isAdmin) ...[
                                  const SizedBox(width: 8),
                                  Container(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 6,
                                      vertical: 2,
                                    ),
                                    decoration: BoxDecoration(
                                      color: colorScheme.primary,
                                      borderRadius: BorderRadius.circular(4),
                                    ),
                                    child: Text(
                                      'ADMIN',
                                      style: textTheme.labelSmall?.copyWith(
                                        color: colorScheme.onPrimary,
                                        fontWeight: FontWeight.bold,
                                        fontSize: 10,
                                      ),
                                    ),
                                  ),
                                ],
                              ],
                            ),
                            subtitle: Text(
                              [
                                if (username != null) '@$username',
                                email,
                                if (createdAt != null) 'Joined ${_formatDate(createdAt)}',
                              ].where((s) => s.isNotEmpty).join(' - '),
                              style: textTheme.bodySmall?.copyWith(
                                color: colorScheme.onSurfaceVariant,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                            trailing: Switch(
                              value: isAdmin,
                              onChanged: (_) => _toggleAdmin(index),
                            ),
                          );
                        },
                      ),
                    ),
    );
  }
}
