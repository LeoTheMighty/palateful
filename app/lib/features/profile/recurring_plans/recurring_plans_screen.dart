import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/di/injection.dart';
import '../../calendar/models/meal_event.dart';
import '../../calendar/services/meal_calendar_service.dart';
import 'widgets/rule_row.dart';

/// Manage-screen for every recurrence rule the user owns (or shares).
class RecurringPlansScreen extends StatefulWidget {
  const RecurringPlansScreen({super.key});

  @override
  State<RecurringPlansScreen> createState() => _RecurringPlansScreenState();
}

class _RecurringPlansScreenState extends State<RecurringPlansScreen>
    with WidgetsBindingObserver {
  final _service = getIt<MealCalendarService>();

  List<RecurrenceRule> _rules = [];
  bool _loading = true;
  String? _loadError;
  bool _showEndedWhenAllEnded = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _load();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _load();
    }
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _loadError = null;
    });
    try {
      final rules = await _service.listRecurrenceRules();
      if (!mounted) return;
      setState(() {
        _rules = rules;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loadError = e.toString();
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Recurring plans')),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _body(),
      ),
    );
  }

  Widget _body() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_loadError != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text("Couldn't load your recurring plans."),
              const SizedBox(height: 12),
              FilledButton(
                onPressed: _load,
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    final today = DateTime.now();
    final active = _rules.where((r) => !_isEnded(r, today)).toList();
    final ended = _rules.where((r) => _isEnded(r, today)).toList();

    if (active.isEmpty && ended.isEmpty) {
      return _emptyState(noneEver: true);
    }
    if (active.isEmpty && !_showEndedWhenAllEnded) {
      return _emptyState(noneEver: false, endedCount: ended.length);
    }

    final visible = [
      ...active,
      if (_showEndedWhenAllEnded || active.isNotEmpty) ...ended,
    ];

    return ListView.separated(
      physics: const AlwaysScrollableScrollPhysics(),
      itemCount: visible.length,
      separatorBuilder: (_, _) => const Divider(height: 1),
      itemBuilder: (_, i) {
        final rule = visible[i];
        return RuleRow(
          rule: rule,
          isEnded: _isEnded(rule, today),
          onTap: () => _openEditSheet(rule),
        );
      },
    );
  }

  Widget _emptyState({required bool noneEver, int endedCount = 0}) {
    final colorScheme = Theme.of(context).colorScheme;
    return SingleChildScrollView(
      physics: const AlwaysScrollableScrollPhysics(),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(24, 80, 24, 24),
        child: Column(
          children: [
            Icon(
              Icons.event_repeat_outlined,
              size: 48,
              color: colorScheme.onSurfaceVariant,
            ),
            const SizedBox(height: 16),
            if (noneEver) ...[
              const Text(
                'No recurring meal plans yet.',
                style: TextStyle(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 8),
              const Text(
                'Create one from the calendar.',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 16),
              FilledButton.icon(
                icon: const Icon(Icons.calendar_today_outlined),
                label: const Text('Open calendar'),
                onPressed: () => context.go('/calendar'),
              ),
            ] else ...[
              const Text(
                'No active recurring plans.',
                style: TextStyle(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 8),
              TextButton(
                onPressed: () => setState(() => _showEndedWhenAllEnded = true),
                child: Text('$endedCount ended plan${endedCount == 1 ? '' : 's'} hidden — tap to show'),
              ),
            ],
          ],
        ),
      ),
    );
  }

  bool _isEnded(RecurrenceRule r, DateTime today) {
    final e = r.endDate;
    if (e == null) return false;
    return e.isBefore(DateTime(today.year, today.month, today.day));
  }

  Future<void> _openEditSheet(RecurrenceRule rule) async {
    final result = await showModalBottomSheet<_EditResult>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _RuleEditSheet(rule: rule, service: _service),
    );
    if (result == null) return;
    if (result.reload) _load();
  }
}

class _EditResult {
  final bool reload;
  const _EditResult({required this.reload});
}

class _RuleEditSheet extends StatefulWidget {
  final RecurrenceRule rule;
  final MealCalendarService service;

  const _RuleEditSheet({required this.rule, required this.service});

  @override
  State<_RuleEditSheet> createState() => _RuleEditSheetState();
}

class _RuleEditSheetState extends State<_RuleEditSheet> {
  bool _saving = false;

  @override
  Widget build(BuildContext context) {
    final rule = widget.rule;
    return Padding(
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
          Text(
            rule.title ?? 'Recurring meal',
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 20),
          const Text(
            'Edit from the plan-meal sheet or remove the entire series below.',
          ),
          const SizedBox(height: 20),
          FilledButton.tonalIcon(
            icon: const Icon(Icons.delete_outline),
            label: const Text('Delete series'),
            onPressed: _saving ? null : _confirmDelete,
          ),
          const SizedBox(height: 8),
          TextButton(
            onPressed: _saving ? null : () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  Future<void> _confirmDelete() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete this entire series?'),
        content: const Text('Past occurrences stay.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;

    setState(() => _saving = true);
    try {
      await widget.service.deleteRecurrenceRule(widget.rule.id);
      if (!mounted) return;
      Navigator.pop(context, const _EditResult(reload: true));
    } catch (_) {
      if (!mounted) return;
      setState(() => _saving = false);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Couldn't delete series. Try again.")),
      );
    }
  }
}
