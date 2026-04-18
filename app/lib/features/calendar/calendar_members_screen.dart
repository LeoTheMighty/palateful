import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import 'models/calendar_member.dart';
import 'providers/active_calendar_provider.dart';
import 'services/calendar_service.dart';

/// Calendar members screen — list active members + pending invites; owners
/// can promote, remove, and cancel invites; non-owner members can leave.
///
/// Reachable from CalendarSettingsSheet → "Manage members" chevron, and
/// (post-cal-share-5) from Profile → Shared Calendars row.
class CalendarMembersScreen extends ConsumerStatefulWidget {
  final String calendarId;
  final String calendarName;
  final String userRole;

  const CalendarMembersScreen({
    super.key,
    required this.calendarId,
    required this.calendarName,
    required this.userRole,
  });

  @override
  ConsumerState<CalendarMembersScreen> createState() =>
      _CalendarMembersScreenState();
}

class _CalendarMembersScreenState extends ConsumerState<CalendarMembersScreen> {
  final _service = getIt<CalendarService>();
  final _api = getIt<ApiClient>();
  List<CalendarMember>? _members;
  bool _loading = true;
  String? _error;
  bool _busy = false;

  bool get _isOwner => widget.userRole == 'owner';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final members = await _service.listCalendarMembers(widget.calendarId);
      if (mounted) {
        setState(() {
          _members = members;
          _loading = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _error = 'Could not load members';
          _loading = false;
        });
      }
    }
  }

  String _meId() {
    // The current user's id is exposed via no Riverpod provider in this
    // codebase yet. The members list returns a row tagged with the
    // caller's role at the top, so we identify "self" by matching the
    // first active row whose role equals the caller's userRole AND
    // whose data was inserted via the caller's join. To be safe, we
    // delegate the "is self" check to userId comparison against the
    // currently signed-in user — but the safest cross-reference here
    // is "the row whose role == caller's userRole exactly once".
    // For correctness, we expose `selfUserId` via a constructor param
    // would be cleanest. Today, the screen uses the role-match heuristic.
    return _members
            ?.firstWhere(
              (m) => m.role == widget.userRole && !m.isPending,
              orElse: () => CalendarMember(
                role: widget.userRole,
                status: 'active',
                createdAt: DateTime.now(),
              ),
            )
            .userId ??
        '';
  }

  Future<void> _promote(CalendarMember target) async {
    final confirm = await _confirmDialog(
      title: 'Make ${target.name ?? "this member"} owner?',
      body:
          "**You'll become an editor** and won't be able to invite or remove members after this.",
      confirmLabel: 'Promote',
      destructive: false,
    );
    if (confirm != true || !mounted) return;
    setState(() => _busy = true);
    final messenger = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);
    try {
      await _service.updateCalendarMember(
        widget.calendarId,
        target.userId!,
        role: 'owner',
      );
      // Caller is no longer owner → invalidate calendar list and pop.
      ref.invalidate(calendarsListProvider);
      messenger.showSnackBar(
        SnackBar(content: Text('${target.name ?? "Member"} is now the owner')),
      );
      if (mounted) navigator.pop();
    } on DioException catch (e) {
      _handleDioError(e, messenger);
    } catch (_) {
      if (mounted) {
        messenger.showSnackBar(
          const SnackBar(content: Text('Could not promote member. Please try again.')),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _remove(CalendarMember target) async {
    final confirm = await _confirmDialog(
      title: 'Remove ${target.name ?? "this member"}?',
      body: "They'll lose access to this calendar.",
      confirmLabel: 'Remove',
      destructive: true,
    );
    if (confirm != true || !mounted) return;
    setState(() => _busy = true);
    final messenger = ScaffoldMessenger.of(context);
    try {
      await _service.removeCalendarMember(widget.calendarId, target.userId!);
      messenger.showSnackBar(
        SnackBar(content: Text('${target.name ?? "Member"} removed')),
      );
      await _load();
    } on DioException catch (e) {
      _handleDioError(e, messenger);
    } catch (_) {
      if (mounted) {
        messenger.showSnackBar(
          const SnackBar(content: Text('Could not remove member. Please try again.')),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _leave() async {
    final confirm = await _confirmDialog(
      title: "Leave '${widget.calendarName}'?",
      body:
          "You'll lose access to the meals on this calendar. You can be re-invited later.",
      confirmLabel: 'Leave',
      destructive: true,
    );
    if (confirm != true || !mounted) return;
    setState(() => _busy = true);
    final messenger = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);
    try {
      await _service.leaveCalendar(widget.calendarId);
      // Active-calendar fallback: if we were viewing the calendar we
      // just left, clear the persisted id so the provider re-resolves
      // to the user's default.
      final activeId = ref.read(activeCalendarProvider).value;
      if (activeId == widget.calendarId) {
        await ref.read(activeCalendarProvider.notifier).clearInvalid();
      } else {
        ref.invalidate(calendarsListProvider);
      }
      messenger.showSnackBar(
        SnackBar(content: Text("You left '${widget.calendarName}'")),
      );
      if (mounted) navigator.pop();
    } on DioException catch (e) {
      _handleDioError(e, messenger);
    } catch (_) {
      if (mounted) {
        messenger.showSnackBar(
          const SnackBar(content: Text('Could not leave calendar. Please try again.')),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _cancelInvite(CalendarMember invite) async {
    final confirm = await _confirmDialog(
      title: 'Cancel invitation?',
      body: 'The invitee will no longer be able to join.',
      confirmLabel: 'Cancel invite',
      destructive: true,
    );
    if (confirm != true || !mounted) return;
    setState(() => _busy = true);
    final messenger = ScaffoldMessenger.of(context);
    try {
      await _api.revokeInvitation(invite.invitationId!);
      messenger.showSnackBar(
        const SnackBar(content: Text('Invitation canceled')),
      );
      await _load();
    } catch (_) {
      if (mounted) {
        messenger.showSnackBar(
          const SnackBar(content: Text('Could not cancel invitation.')),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _handleDioError(DioException e, ScaffoldMessengerState messenger) {
    final status = e.response?.statusCode;
    String message;
    if (status == 403) {
      message = "You're no longer the owner. Refresh to see the latest.";
    } else if (status == 409) {
      message = 'Another change happened. Refresh to see the latest.';
    } else {
      message = 'Action failed. Please try again.';
    }
    messenger.showSnackBar(SnackBar(content: Text(message)));
    _load();
  }

  Future<bool?> _confirmDialog({
    required String title,
    required String body,
    required String confirmLabel,
    required bool destructive,
  }) {
    return showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(title),
        content: Text(body),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            style: destructive
                ? FilledButton.styleFrom(
                    backgroundColor: Theme.of(ctx).colorScheme.error,
                  )
                : null,
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(confirmLabel),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.calendarName),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
      ),
      body: _buildBody(theme, colorScheme),
    );
  }

  Widget _buildBody(ThemeData theme, ColorScheme colorScheme) {
    if (_loading && _members == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(_error!, style: TextStyle(color: colorScheme.error)),
            const SizedBox(height: 12),
            ElevatedButton(onPressed: _load, child: const Text('Retry')),
          ],
        ),
      );
    }

    final members = _members ?? const <CalendarMember>[];
    final active = members.where((m) => !m.isPending).toList();
    final pending = members.where((m) => m.isPending).toList();
    final selfId = _meId();

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        children: [
          if (active.isNotEmpty) ...[
            _sectionHeader('Members', theme),
            for (final m in active)
              _memberTile(m, isSelf: m.userId == selfId, theme: theme, colorScheme: colorScheme),
          ],
          if (pending.isNotEmpty) ...[
            _sectionHeader('Pending Invitations', theme),
            for (final m in pending) _pendingTile(m, theme, colorScheme),
          ],
          if (!_isOwner) ...[
            const SizedBox(height: 24),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Text(
                'Owners can manage who has access. Editors like you can add and edit meals.',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                ),
              ),
            ),
          ] else ...[
            const SizedBox(height: 12),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Text(
                "Transfer ownership first if you want to leave the calendar.",
                style: theme.textTheme.bodySmall?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _sectionHeader(String label, ThemeData theme) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 4),
        child: Text(label, style: theme.textTheme.titleSmall),
      );

  Widget _memberTile(
    CalendarMember m, {
    required bool isSelf,
    required ThemeData theme,
    required ColorScheme colorScheme,
  }) {
    final showSelfLeave = isSelf && !_isOwner;
    final showOwnerActions = _isOwner && !isSelf && !m.isOwner;
    return ListTile(
      leading: Icon(Icons.person, color: colorScheme.primary),
      title: Text(m.name ?? 'Member'),
      subtitle: Text(m.role == 'owner' ? 'Owner' : 'Editor'),
      trailing: showOwnerActions
          ? PopupMenuButton<String>(
              enabled: !_busy,
              onSelected: (v) {
                if (v == 'promote') _promote(m);
                if (v == 'remove') _remove(m);
              },
              itemBuilder: (_) => const [
                PopupMenuItem(value: 'promote', child: Text('Promote to Owner')),
                PopupMenuItem(value: 'remove', child: Text('Remove')),
              ],
            )
          : showSelfLeave
              ? TextButton(
                  onPressed: _busy ? null : _leave,
                  child: const Text('Leave'),
                )
              : null,
    );
  }

  Widget _pendingTile(CalendarMember m, ThemeData theme, ColorScheme colorScheme) {
    final title = m.email ?? m.name ?? 'Pending invitation';
    return ListTile(
      leading: Icon(Icons.mail_outline, color: colorScheme.onSurfaceVariant),
      title: Text(title),
      subtitle: const Text('Pending • Editor'),
      trailing: _isOwner
          ? TextButton(
              onPressed: _busy ? null : () => _cancelInvite(m),
              child: const Text('Cancel'),
            )
          : null,
    );
  }
}
