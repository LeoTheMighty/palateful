import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/di/injection.dart';
import '../calendar/models/calendar.dart';
import '../calendar/services/calendar_service.dart';

/// SharedCalendarsScreen — low-prominence profile surface listing every
/// calendar the user is an editor on (i.e. shared with them, not owned).
///
/// Reachable from Profile → "Shared Calendars" tile. Tapping a row deep-links
/// to the calendar's members screen.
class SharedCalendarsScreen extends StatefulWidget {
  const SharedCalendarsScreen({super.key});

  @override
  State<SharedCalendarsScreen> createState() => _SharedCalendarsScreenState();
}

class _SharedCalendarsScreenState extends State<SharedCalendarsScreen> {
  final _service = getIt<CalendarService>();
  List<Calendar>? _calendars;
  bool _loading = true;
  String? _error;

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
      final all = await _service.listCalendars();
      if (mounted) {
        setState(() {
          _calendars = all.where((c) => !c.isOwner).toList();
          _loading = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _error = 'Could not load shared calendars';
          _loading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Shared Calendars'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
      ),
      body: _buildBody(theme, colorScheme),
    );
  }

  Widget _buildBody(ThemeData theme, ColorScheme colorScheme) {
    if (_loading) {
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
    final calendars = _calendars ?? const <Calendar>[];
    if (calendars.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 32),
          child: Text(
            "No shared calendars yet. When someone invites you to their calendar, it'll show up here.",
            textAlign: TextAlign.center,
            style: theme.textTheme.bodyMedium?.copyWith(
              color: colorScheme.onSurfaceVariant,
            ),
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.separated(
        padding: const EdgeInsets.symmetric(vertical: 8),
        itemCount: calendars.length,
        separatorBuilder: (_, _) => const Divider(height: 1),
        itemBuilder: (context, index) {
          final c = calendars[index];
          final memberLabel =
              c.memberCount == 1 ? '1 member' : '${c.memberCount} members';
          return ListTile(
            leading: Icon(Icons.calendar_today, color: colorScheme.primary),
            title: Text(c.name),
            subtitle: Text(memberLabel),
            trailing: const Icon(Icons.chevron_right),
            onTap: () {
              context.push(
                '/calendar/${c.id}/members'
                '?role=${c.userRole}'
                '&name=${Uri.encodeQueryComponent(c.name)}',
              );
            },
          );
        },
      ),
    );
  }
}
