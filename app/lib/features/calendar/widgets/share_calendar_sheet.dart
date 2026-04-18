import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:share_plus/share_plus.dart';

import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';
import '../../../services/share_service.dart';

/// Share Calendar bottom sheet — invite by email/username + invite-link tabs.
///
/// Modeled after `_showInviteBottomSheet` in `recipe_book_members_screen.dart`
/// (the established sharing UX pattern). Calendars only support `editor` role,
/// so there's no role selector — the role is implicit.
///
/// On success → callback fires (so the caller can refresh members + close).
/// Errors are translated into user-friendly snackbars based on the backend
/// error code returned by the API.
class ShareCalendarSheet extends StatefulWidget {
  final String calendarId;
  final String calendarName;
  final VoidCallback onInvitationSent;

  const ShareCalendarSheet({
    super.key,
    required this.calendarId,
    required this.calendarName,
    required this.onInvitationSent,
  });

  @override
  State<ShareCalendarSheet> createState() => _ShareCalendarSheetState();
}

class _ShareCalendarSheetState extends State<ShareCalendarSheet> {
  final _apiClient = getIt<ApiClient>();
  final _inputController = TextEditingController();
  String? _generatedLink;
  bool _isSending = false;
  bool _isGenerating = false;

  @override
  void dispose() {
    _inputController.dispose();
    super.dispose();
  }

  String _errorMessageForCode(int? code, String input) {
    // Codes mirror libraries/utils/utils/classes/error_code.py.
    switch (code) {
      case 247:
        return "You can't invite yourself.";
      case 248:
        return "$input is already a member of this calendar.";
      case 242:
        return "You already invited $input.";
      case 262:
        return 'Calendar not found.';
      case 263:
        return 'Only the calendar owner can invite new members.';
      default:
        return "Could not send invitation. Check the email/username and try again.";
    }
  }

  Future<void> _send() async {
    final input = _inputController.text.trim();
    if (input.isEmpty) return;
    setState(() => _isSending = true);
    final isEmail = input.contains('@') && input.contains('.');
    // A typed email like "@alice" with no dot falls through to username.
    final body = <String, dynamic>{
      'resource_type': 'calendar',
      'resource_id': widget.calendarId,
      'role_offered': 'editor',
      if (isEmail) 'to_email': input
      else 'to_username': input.replaceFirst('@', ''),
    };
    final messenger = ScaffoldMessenger.of(context);
    try {
      await _apiClient.sendInvitation(body);
      if (!mounted) return;
      widget.onInvitationSent();
      Navigator.of(context).pop();
      messenger.showSnackBar(
        SnackBar(content: Text('Invitation sent to $input')),
      );
    } on DioException catch (e) {
      final code = (e.response?.data is Map<String, dynamic>)
          ? (e.response!.data as Map<String, dynamic>)['error_code'] as int?
          : null;
      if (mounted) {
        setState(() => _isSending = false);
        messenger.showSnackBar(
          SnackBar(content: Text(_errorMessageForCode(code, input))),
        );
      }
    } catch (_) {
      if (mounted) {
        setState(() => _isSending = false);
        messenger.showSnackBar(
          const SnackBar(content: Text('Could not send invitation. Please try again.')),
        );
      }
    }
  }

  Future<void> _generateLink() async {
    setState(() => _isGenerating = true);
    final messenger = ScaffoldMessenger.of(context);
    try {
      final response = await _apiClient.createInviteLink({
        'resource_type': 'calendar',
        'resource_id': widget.calendarId,
        'role_offered': 'editor',
      });
      final link = response.data['deep_link'] as String?;
      if (mounted) {
        setState(() {
          _generatedLink = link;
          _isGenerating = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() => _isGenerating = false);
        messenger.showSnackBar(
          const SnackBar(content: Text('Could not create invite link. Please try again.')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return DefaultTabController(
      length: 2,
      child: Padding(
        padding: EdgeInsets.only(
          bottom: MediaQuery.of(context).viewInsets.bottom,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: 8),
            Text(
              'Share ${widget.calendarName}',
              style: theme.textTheme.titleMedium,
            ),
            const TabBar(
              tabs: [
                Tab(text: 'By email/username'),
                Tab(text: 'Invite link'),
              ],
            ),
            SizedBox(
              height: 280,
              child: TabBarView(
                children: [
                  _buildDirectInviteTab(),
                  _buildInviteLinkTab(theme),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDirectInviteTab() {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          TextField(
            controller: _inputController,
            decoration: const InputDecoration(
              labelText: 'Email or @username',
              hintText: 'jane@example.com or @jane',
            ),
            onChanged: (_) => setState(() {}),
          ),
          const SizedBox(height: 8),
          const Text(
            'Members get full edit access to every meal on this calendar.',
            style: TextStyle(fontSize: 12),
          ),
          const SizedBox(height: 16),
          ElevatedButton(
            onPressed: _inputController.text.trim().isEmpty || _isSending
                ? null
                : _send,
            child: _isSending
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('Send Invite'),
          ),
        ],
      ),
    );
  }

  Widget _buildInviteLinkTab(ThemeData theme) {
    final linkExists = _generatedLink != null;
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (!linkExists) ...[
            const Text(
              'Anyone with this link can join as an editor.',
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _isGenerating ? null : _generateLink,
              child: _isGenerating
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Generate link'),
            ),
          ] else ...[
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: theme.colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                _generatedLink!,
                style: theme.textTheme.bodySmall,
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () {
                      Clipboard.setData(ClipboardData(text: _generatedLink!));
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Link copied')),
                      );
                    },
                    icon: const Icon(Icons.copy),
                    label: const Text('Copy'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: () {
                      Share.share(
                        _generatedLink!,
                        sharePositionOrigin:
                            ShareService.originFrom(context),
                      );
                    },
                    icon: const Icon(Icons.share),
                    label: const Text('Share'),
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}
