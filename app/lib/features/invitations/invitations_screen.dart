import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';

class InvitationsScreen extends StatefulWidget {
  const InvitationsScreen({super.key});

  @override
  State<InvitationsScreen> createState() => _InvitationsScreenState();
}

class _InvitationsScreenState extends State<InvitationsScreen>
    with SingleTickerProviderStateMixin {
  final _apiClient = getIt<ApiClient>();
  late final TabController _tabController;

  List<dynamic> _received = [];
  List<dynamic> _sent = [];
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _loadInvitations();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadInvitations() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final results = await Future.wait([
        _apiClient.listReceivedInvitations(),
        _apiClient.listSentInvitations(),
      ]);
      if (mounted) {
        setState(() {
          _received = (results[0].data as List<dynamic>?) ?? [];
          _sent = (results[1].data as List<dynamic>?) ?? [];
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Could not load invitations. Please try again.';
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _accept(String id) async {
    try {
      await _apiClient.acceptInvitation(id);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Invitation accepted')),
        );
        _loadInvitations();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not accept invitation. Please try again.')),
        );
      }
    }
  }

  Future<void> _decline(String id) async {
    try {
      await _apiClient.declineInvitation(id);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Invitation declined')),
        );
        _loadInvitations();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not decline invitation. Please try again.')),
        );
      }
    }
  }

  Future<void> _revoke(String id) async {
    try {
      await _apiClient.revokeInvitation(id);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Invitation revoked')),
        );
        _loadInvitations();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not revoke invitation. Please try again.')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Invitations'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
        bottom: TabBar(
          controller: _tabController,
          tabs: [
            Tab(text: 'Received (${_received.length})'),
            Tab(text: 'Sent (${_sent.length})'),
          ],
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
                        Text(_error!, textAlign: TextAlign.center),
                        const SizedBox(height: 16),
                        ElevatedButton(
                          onPressed: _loadInvitations,
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                )
              : TabBarView(
                  controller: _tabController,
                  children: [
                    _buildReceivedTab(colorScheme),
                    _buildSentTab(colorScheme),
                  ],
                ),
    );
  }

  Widget _buildReceivedTab(ColorScheme colorScheme) {
    if (_received.isEmpty) {
      return const Center(
        child: Text('No pending invitations'),
      );
    }
    return RefreshIndicator(
      onRefresh: _loadInvitations,
      child: ListView.separated(
        padding: const EdgeInsets.symmetric(vertical: 8),
        itemCount: _received.length,
        separatorBuilder: (_, __) => const Divider(height: 1),
        itemBuilder: (context, index) {
          final inv = _received[index] as Map<String, dynamic>;
          final id = inv['id'] as String? ?? '';
          final resourceName = inv['resource_name'] as String? ?? 'a book';
          final role = inv['role_offered'] as String? ?? 'viewer';
          final fromUser = inv['from_user'] as Map<String, dynamic>?;
          final senderDisplay = fromUser?['username'] != null
              ? '@${fromUser!['username']}'
              : fromUser?['name'] as String? ?? 'Someone';

          return ListTile(
            leading: CircleAvatar(
              backgroundColor: colorScheme.secondaryContainer,
              child: Icon(Icons.mail_outline, color: colorScheme.onSecondaryContainer),
            ),
            title: Text('$senderDisplay invited you'),
            subtitle: Text('Join "$resourceName" as $role'),
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextButton(
                  onPressed: () => _decline(id),
                  child: const Text('Decline'),
                ),
                const SizedBox(width: 4),
                ElevatedButton(
                  onPressed: () => _accept(id),
                  child: const Text('Accept'),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildSentTab(ColorScheme colorScheme) {
    if (_sent.isEmpty) {
      return const Center(
        child: Text('No sent invitations'),
      );
    }
    return RefreshIndicator(
      onRefresh: _loadInvitations,
      child: ListView.separated(
        padding: const EdgeInsets.symmetric(vertical: 8),
        itemCount: _sent.length,
        separatorBuilder: (_, __) => const Divider(height: 1),
        itemBuilder: (context, index) {
          final inv = _sent[index] as Map<String, dynamic>;
          final id = inv['id'] as String? ?? '';
          final resourceName = inv['resource_name'] as String? ?? 'a book';
          final role = inv['role_offered'] as String? ?? 'viewer';
          final toUserId = inv['to_user_id'] as String?;
          final toEmail = inv['to_email'] as String?;
          final recipientDisplay = toUserId ?? toEmail ?? 'unknown';

          return ListTile(
            leading: CircleAvatar(
              backgroundColor: colorScheme.tertiaryContainer,
              child: Icon(Icons.send, color: colorScheme.onTertiaryContainer),
            ),
            title: Text('Invited $recipientDisplay'),
            subtitle: Text('"$resourceName" as $role'),
            trailing: TextButton(
              onPressed: () => _revoke(id),
              child: Text(
                'Revoke',
                style: TextStyle(color: colorScheme.error),
              ),
            ),
          );
        },
      ),
    );
  }
}
