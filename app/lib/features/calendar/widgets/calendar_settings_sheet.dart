import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/di/injection.dart';
import '../models/calendar.dart';
import '../models/calendar_member.dart';
import '../providers/active_calendar_provider.dart';
import '../services/calendar_service.dart';
import 'share_calendar_sheet.dart';

/// Calendar settings bottom sheet: rename, edit description, delete.
///
/// Rename uses an explicit Save button (matches recipe-book settings
/// precedent — not autosave-on-blur). Delete is disabled when the
/// calendar is the user's only one (backend also enforces this with
/// CALENDAR_CANNOT_DELETE_LAST).
class CalendarSettingsSheet extends ConsumerStatefulWidget {
  final Calendar calendar;
  final bool isLastCalendar;

  const CalendarSettingsSheet({
    super.key,
    required this.calendar,
    required this.isLastCalendar,
  });

  @override
  ConsumerState<CalendarSettingsSheet> createState() =>
      _CalendarSettingsSheetState();
}

class _CalendarSettingsSheetState
    extends ConsumerState<CalendarSettingsSheet> {
  late final TextEditingController _nameCtrl;
  late final TextEditingController _descCtrl;
  bool _savingName = false;
  bool _savingDesc = false;
  bool _deleting = false;
  String? _error;

  // Members section state. Loaded on first build via _loadMembers; refreshed
  // on pull-to-refresh and after a successful invite.
  List<CalendarMember>? _members;
  bool _loadingMembers = false;
  String? _membersError;

  @override
  void initState() {
    super.initState();
    _nameCtrl = TextEditingController(text: widget.calendar.name);
    _descCtrl = TextEditingController(text: widget.calendar.description ?? '');
    _loadMembers();
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _descCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadMembers() async {
    setState(() {
      _loadingMembers = true;
      _membersError = null;
    });
    try {
      final members = await getIt<CalendarService>()
          .listCalendarMembers(widget.calendar.id);
      if (mounted) {
        setState(() {
          _members = members;
          _loadingMembers = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _membersError = 'Could not load members';
          _loadingMembers = false;
        });
      }
    }
  }

  Future<void> _openShareSheet() async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (_) => ShareCalendarSheet(
        calendarId: widget.calendar.id,
        calendarName: widget.calendar.name,
        onInvitationSent: _loadMembers,
      ),
    );
  }

  Future<void> _saveName() async {
    final newName = _nameCtrl.text.trim();
    if (newName.isEmpty || newName == widget.calendar.name) return;
    setState(() {
      _savingName = true;
      _error = null;
    });
    try {
      await getIt<CalendarService>()
          .updateCalendar(widget.calendar.id, name: newName);
      ref.invalidate(calendarsListProvider);
    } catch (_) {
      if (mounted) setState(() => _error = 'Failed to save name');
    } finally {
      if (mounted) setState(() => _savingName = false);
    }
  }

  Future<void> _saveDescription() async {
    final newDesc = _descCtrl.text.trim();
    if (newDesc == (widget.calendar.description ?? '')) return;
    setState(() {
      _savingDesc = true;
      _error = null;
    });
    try {
      await getIt<CalendarService>()
          .updateCalendar(widget.calendar.id, description: newDesc);
      ref.invalidate(calendarsListProvider);
    } catch (_) {
      if (mounted) setState(() => _error = 'Failed to save description');
    } finally {
      if (mounted) setState(() => _savingDesc = false);
    }
  }

  Future<void> _confirmDelete() async {
    if (widget.isLastCalendar) return;
    final membersCount = widget.calendar.memberCount;
    final message = membersCount > 1
        ? "Delete '${widget.calendar.name}'? $membersCount members will lose access. "
            'All meals will be archived.'
        : "Delete '${widget.calendar.name}'? All meals on this calendar "
            'will be archived. This cannot be undone.';

    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete calendar?'),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(ctx).colorScheme.error,
            ),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirm != true) return;

    setState(() => _deleting = true);
    try {
      await getIt<CalendarService>().deleteCalendar(widget.calendar.id);
      // After a delete: fall back to a sane active calendar. The
      // provider re-resolves based on its fallback chain once we
      // invalidate the list cache + clear the stored id (if the active
      // one was the deletion target, the persisted id is now stale).
      final activeId = ref.read(activeCalendarProvider).value;
      if (activeId == widget.calendar.id) {
        await ref.read(activeCalendarProvider.notifier).clearInvalid();
      } else {
        ref.invalidate(calendarsListProvider);
      }
      if (mounted) Navigator.of(context).pop('deleted');
    } catch (_) {
      if (mounted) {
        setState(() {
          _deleting = false;
          _error = 'Failed to delete calendar';
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.only(
          left: 20,
          right: 20,
          top: 20,
          bottom: 20 + MediaQuery.of(context).viewInsets.bottom,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Calendar Settings', style: theme.textTheme.titleLarge),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _nameCtrl,
                    decoration: const InputDecoration(labelText: 'Name'),
                  ),
                ),
                const SizedBox(width: 8),
                TextButton(
                  onPressed: _savingName ? null : _saveName,
                  child: _savingName
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Save'),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Expanded(
                  child: TextField(
                    controller: _descCtrl,
                    minLines: 1,
                    maxLines: 3,
                    decoration: const InputDecoration(
                      labelText: 'Description',
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                TextButton(
                  onPressed: _savingDesc ? null : _saveDescription,
                  child: _savingDesc
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Save'),
                ),
              ],
            ),
            const SizedBox(height: 20),
            Text('Members', style: theme.textTheme.titleMedium),
            const SizedBox(height: 8),
            _buildMembersSection(theme, colorScheme),
            const SizedBox(height: 24),
            if (_error != null) ...[
              Text(
                _error!,
                style: TextStyle(color: colorScheme.error),
              ),
              const SizedBox(height: 8),
            ],
            FilledButton(
              onPressed:
                  (_deleting || widget.isLastCalendar) ? null : _confirmDelete,
              style: FilledButton.styleFrom(
                backgroundColor: colorScheme.error,
              ),
              child: _deleting
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Delete calendar'),
            ),
            if (widget.isLastCalendar) ...[
              const SizedBox(height: 8),
              Text(
                "You can't delete your only calendar.",
                style: theme.textTheme.bodySmall?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                ),
                textAlign: TextAlign.center,
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildMembersSection(ThemeData theme, ColorScheme colorScheme) {
    if (_loadingMembers && _members == null) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 12),
        child: Center(child: CircularProgressIndicator()),
      );
    }
    if (_membersError != null) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            _membersError!,
            style: TextStyle(color: colorScheme.error),
          ),
          TextButton(
            onPressed: _loadMembers,
            child: const Text('Retry'),
          ),
        ],
      );
    }

    final members = _members ?? const <CalendarMember>[];
    return RefreshIndicator(
      onRefresh: _loadMembers,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxHeight: 220),
        child: ListView(
          shrinkWrap: true,
          physics: const AlwaysScrollableScrollPhysics(),
          children: [
            for (final m in members) _buildMemberTile(m, theme, colorScheme),
            if (widget.calendar.isOwner) ...[
              const SizedBox(height: 8),
              FilledButton.icon(
                onPressed: _openShareSheet,
                icon: const Icon(Icons.person_add_alt_1),
                label: const Text('Share Calendar'),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildMemberTile(
    CalendarMember m,
    ThemeData theme,
    ColorScheme colorScheme,
  ) {
    final title = m.isPending
        ? (m.email ?? m.name ?? 'Pending invitation')
        : (m.name ?? 'Member');
    final subtitle = m.isPending
        ? 'Pending • ${_roleLabel(m.role)}'
        : _roleLabel(m.role);
    final iconColor =
        m.isPending ? colorScheme.onSurfaceVariant : colorScheme.primary;
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Icon(
        m.isPending ? Icons.mail_outline : Icons.person,
        color: iconColor,
      ),
      title: Text(title),
      subtitle: Text(subtitle, style: theme.textTheme.bodySmall),
    );
  }

  String _roleLabel(String role) {
    switch (role) {
      case 'owner':
        return 'Owner';
      case 'editor':
        return 'Editor';
      default:
        return role;
    }
  }
}
