import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'import_history_screen.dart';
import 'notifications_tab.dart';
import 'providers/activity_tab_provider.dart';

/// Activity Hub shell — two top-of-screen tabs (Notifications | Imports)
/// on a single `/activity` route.
///
/// Story ahr-2 owns the tab strip + tab controller sync with
/// [activityTabProvider]. Story ahr-3 lifted the Notifications body
/// into its own [NotificationsTab] widget (with swipe-to-archive + 3s
/// undo). The Imports tab body still delegates to the legacy
/// [ImportHistoryScreen] in `embedded: true` mode until ahr-4 replaces
/// it with the color-sectioned layout.
///
/// Deep-link schema:
///  - `/activity?tab=<notifications|imports>` — canonical.
///  - `/activity?filter=imports` — legacy; router redirects to
///    `?tab=imports` for one release (ahr-7 retires).
class ActivityScreen extends ConsumerStatefulWidget {
  final String? initialTab;

  const ActivityScreen({super.key, this.initialTab});

  @override
  ConsumerState<ActivityScreen> createState() => _ActivityScreenState();
}

class _ActivityScreenState extends ConsumerState<ActivityScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController;
  bool _syncingFromController = false;

  @override
  void initState() {
    super.initState();
    // Seed the provider from the route's `?tab=` on mount — the router
    // is the source of truth for the first frame; subsequent tab
    // switches flow provider → controller (and vice versa).
    final initial = ActivityTab.fromWire(widget.initialTab);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      if (ref.read(activityTabProvider) != initial) {
        ref.read(activityTabProvider.notifier).setTab(initial);
      }
    });

    _tabController = TabController(
      length: ActivityTab.values.length,
      vsync: this,
      initialIndex: initial.index,
    );
    _tabController.addListener(_onControllerChange);
  }

  @override
  void dispose() {
    _tabController.removeListener(_onControllerChange);
    _tabController.dispose();
    super.dispose();
  }

  void _onControllerChange() {
    // Tab transitions fire twice — during the drag and when the new
    // index settles. Only write on the settle to avoid thrashing the
    // provider mid-swipe.
    if (_tabController.indexIsChanging) return;
    if (_syncingFromController) return;
    final next = ActivityTab.values[_tabController.index];
    if (ref.read(activityTabProvider) != next) {
      _syncingFromController = true;
      ref.read(activityTabProvider.notifier).setTab(next);
      _syncingFromController = false;
    }
  }

  void _syncControllerFromProvider(ActivityTab tab) {
    if (_tabController.index != tab.index) {
      _tabController.animateTo(tab.index);
    }
  }

  @override
  Widget build(BuildContext context) {
    // Keep the TabController following the provider so external sources
    // (deep-link, push notification) can drive the selection.
    ref.listen<ActivityTab>(activityTabProvider, (prev, next) {
      _syncControllerFromProvider(next);
    });

    return Scaffold(
      appBar: AppBar(
        title: const Text('Activity'),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: 'Notifications'),
            Tab(text: 'Imports'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: const [
          NotificationsTab(),
          _ImportsTabBody(),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Imports tab body — ahr-2 delegates to the legacy [ImportHistoryScreen]
// body so Leo still sees his imports. ahr-4 replaces this with the
// color-sectioned layout (In Progress / Needs Review / Failed /
// Auto-Imported) + swipe-to-archive + see-all footer.
// ---------------------------------------------------------------------------

class _ImportsTabBody extends StatelessWidget {
  const _ImportsTabBody();

  @override
  Widget build(BuildContext context) {
    // Render the existing screen content without its own Scaffold/AppBar.
    return const ImportHistoryScreen(embedded: true);
  }
}
