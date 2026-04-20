import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/di/injection.dart';
import 'imports_tab.dart';
import 'notifications_tab.dart';
import 'providers/activity_read_provider.dart';
import 'providers/activity_tab_provider.dart';

/// Activity Hub shell — two top-of-screen tabs (Notifications | Imports)
/// on a single `/activity` route.
///
/// Story ahr-2 owns the tab strip + tab controller sync with
/// [activityTabProvider]. Story ahr-3 lifted the Notifications body
/// into its own [NotificationsTab] widget (with swipe-to-archive + 3s
/// undo). Story ahr-4 replaced the embedded ImportHistoryScreen body
/// with [ImportsTab] — four color sections + `ImportRow` + swipe
/// rules (blue is read-only; others archive with 3s undo).
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

  /// abi-4 manual-override latch. Flips true on any user-driven tab
  /// swipe/tap. Once latched, the async auto-switch from resolved counts
  /// is suppressed — no rug-pull if the user already picked a tab while
  /// the counts were still loading.
  bool _userTouchedTab = false;

  /// abi-4: the provider that serves the structured unread-count payload.
  /// Read here to compute the initial tab when the route lacks an
  /// explicit `?tab=` and to auto-switch once counts resolve.
  final ActivityReadProvider _readProvider = getIt<ActivityReadProvider>();

  @override
  void initState() {
    super.initState();
    // Seed the provider from the route's `?tab=` on mount when explicit;
    // otherwise pick the tab with more actionable items (tie → Notifications).
    // The router is the source of truth for the first frame; subsequent tab
    // switches flow provider → controller (and vice versa).
    final hasExplicitTab = widget.initialTab != null;
    final initial = hasExplicitTab
        ? ActivityTab.fromWire(widget.initialTab)
        : initialTabFromCounts(
            notifications: _readProvider.notificationsCount.value,
            importsActionable: _readProvider.importsActionableCount.value,
          );

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

    // abi-4: cold-start fallback. If the route had no `?tab=` AND counts
    // hadn't resolved at mount, listen for the first resolve and
    // auto-switch — but only if the user hasn't manually swiped yet.
    if (!hasExplicitTab) {
      _readProvider.notificationsCount.addListener(_maybeAutoSwitchTab);
      _readProvider.importsActionableCount.addListener(_maybeAutoSwitchTab);
    }
  }

  void _maybeAutoSwitchTab() {
    if (!mounted) return;
    if (_userTouchedTab) return;
    final target = initialTabFromCounts(
      notifications: _readProvider.notificationsCount.value,
      importsActionable: _readProvider.importsActionableCount.value,
    );
    if (ref.read(activityTabProvider) == target) return;
    ref.read(activityTabProvider.notifier).setTab(target);
  }

  @override
  void dispose() {
    _tabController.removeListener(_onControllerChange);
    _readProvider.notificationsCount.removeListener(_maybeAutoSwitchTab);
    _readProvider.importsActionableCount.removeListener(_maybeAutoSwitchTab);
    _tabController.dispose();
    super.dispose();
  }

  void _onControllerChange() {
    // Tab transitions fire twice — during the drag and when the new
    // index settles. Only write on the settle to avoid thrashing the
    // provider mid-swipe.
    if (_tabController.indexIsChanging) return;
    if (_syncingFromController) return;
    // abi-4: user has explicitly touched a tab. Latch the override flag
    // so the async auto-switch from resolved counts doesn't fire.
    _userTouchedTab = true;
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
          ImportsTab(),
        ],
      ),
    );
  }
}
