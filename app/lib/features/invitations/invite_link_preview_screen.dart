import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../core/services/error_reporter.dart';
import '../../shared/widgets/error_banner.dart';

class InviteLinkPreviewScreen extends StatefulWidget {
  final String token;

  const InviteLinkPreviewScreen({super.key, required this.token});

  @override
  State<InviteLinkPreviewScreen> createState() => _InviteLinkPreviewScreenState();
}

class _InviteLinkPreviewScreenState extends State<InviteLinkPreviewScreen> {
  final _apiClient = getIt<ApiClient>();

  Map<String, dynamic>? _previewData;
  bool _isLoading = true;
  String? _error;
  String? _errorDetail;
  bool _isJoining = false;

  @override
  void initState() {
    super.initState();
    _loadPreview();
  }

  Future<void> _loadPreview() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final response = await _apiClient.previewInviteLink(widget.token);
      if (mounted) {
        setState(() {
          _previewData = response.data as Map<String, dynamic>?;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Could not load invite link. It may be invalid or expired.';
          _errorDetail = ErrorReporter.detail(e);
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _join() async {
    setState(() => _isJoining = true);
    try {
      final response = await _apiClient.joinViaLink(widget.token);
      if (!mounted) return;
      final data = response.data as Map<String, dynamic>?;
      final resourceId = data?['resource_id'] as String?;
      if (resourceId != null) {
        context.go('/');
        context.push('/recipe-books/$resourceId');
      } else {
        context.go('/');
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isJoining = false);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not join. Please try again.')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Join Invitation'),
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
                        Icon(Icons.link_off,
                            size: 48, color: colorScheme.onSurfaceVariant),
                        const SizedBox(height: 16),
                        Text(_error!, textAlign: TextAlign.center),
                        const SizedBox(height: 16),
                        ElevatedButton(
                          onPressed: _loadPreview,
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                )
              : _buildPreviewBody(colorScheme, textTheme),
    );
  }

  Widget _buildPreviewBody(ColorScheme colorScheme, TextTheme textTheme) {
    final data = _previewData!;
    final state = data['state'] as String? ?? 'inactive';
    final resourceName = data['resource_name'] as String? ?? 'a recipe book';
    final roleOffered = data['role_offered'] as String? ?? 'viewer';
    final createdBy = data['created_by'] as Map<String, dynamic>?;
    final inviterDisplay = createdBy?['username'] != null
        ? '@${createdBy!['username']}'
        : createdBy?['name'] as String? ?? 'Someone';
    final resourceId = data['resource_id'] as String?;

    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const SizedBox(height: 32),
          Icon(Icons.book, size: 64, color: colorScheme.primary),
          const SizedBox(height: 24),
          Text(
            resourceName,
            style: textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.bold),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 8),
          Text(
            '$inviterDisplay invited you to join',
            style: textTheme.bodyLarge?.copyWith(color: colorScheme.onSurfaceVariant),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: colorScheme.secondaryContainer,
              borderRadius: BorderRadius.circular(16),
            ),
            child: Text(
              'Role: $roleOffered',
              style: textTheme.labelMedium?.copyWith(
                color: colorScheme.onSecondaryContainer,
                fontWeight: FontWeight.w600,
              ),
              textAlign: TextAlign.center,
            ),
          ),
          const SizedBox(height: 48),
          _buildAction(state, resourceId, colorScheme, textTheme),
        ],
      ),
    );
  }

  Widget _buildAction(
    String state,
    String? resourceId,
    ColorScheme colorScheme,
    TextTheme textTheme,
  ) {
    switch (state) {
      case 'active':
        return ElevatedButton(
          onPressed: _isJoining ? null : _join,
          style: ElevatedButton.styleFrom(
            padding: const EdgeInsets.symmetric(vertical: 16),
          ),
          child: _isJoining
              ? const SizedBox(
                  height: 20,
                  width: 20,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('Join'),
        );

      case 'already_member':
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: colorScheme.tertiaryContainer,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                'You are already a member of this book.',
                style: TextStyle(color: colorScheme.onTertiaryContainer),
                textAlign: TextAlign.center,
              ),
            ),
            const SizedBox(height: 16),
            if (resourceId != null)
              OutlinedButton(
                onPressed: () {
                  context.go('/');
                  context.push('/recipe-books/$resourceId');
                },
                child: const Text('View Book'),
              ),
          ],
        );

      case 'expired':
        return _buildStateMessage(
          colorScheme,
          icon: Icons.timer_off,
          message: 'This invite link has expired.',
        );

      case 'full':
        return _buildStateMessage(
          colorScheme,
          icon: Icons.group_off,
          message: 'This invite link has reached its usage limit.',
        );

      case 'inactive':
      default:
        return _buildStateMessage(
          colorScheme,
          icon: Icons.link_off,
          message: 'This invite link has been deactivated.',
        );
    }
  }

  Widget _buildStateMessage(
    ColorScheme colorScheme, {
    required IconData icon,
    required String message,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: colorScheme.errorContainer,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Icon(icon, color: colorScheme.onErrorContainer),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              message,
              style: TextStyle(color: colorScheme.onErrorContainer),
            ),
          ),
        ],
      ),
    );
  }
}
