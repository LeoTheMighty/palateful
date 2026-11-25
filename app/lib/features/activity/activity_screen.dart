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

  /// True while a provider-driven `animateTo` is in flight, so its settle
  /// isn't mistaken for a user gesture. Cleared when that settle arrives.
  bool _animatingFromProvider = false;

  @override
  void initState() {
    super.initState();
    // Seed the provider from the route's `?tab=` on mount when explicit;
    // otherwise pick the tab with more actionable items (tie → Notifications).
    // The router is the source of truth for the first frame; subsequent tab
    // switches flow provider → controller (and vice versa).
    // `tryFromWire`, not `fromWire`: an unrecognised value is NOT an
    // explicit request. `?tab=improts` from a truncated deep link or a
    // stale push payload used to count as one and latch the session to
    // Notifications permanently — the bug this story fixes, re-entered
    // through the front door.
    final routeTab = ActivityTab.tryFromWire(widget.initialTab);
    final hasExplicitTab = routeTab != null;
    final initial = hasExplicitTab
        ? routeTab
        : initialTabFromCounts(
            notifications: _readProvider.notificationsCount.value,
            importsActionable: _readProvider.importsActionableCount.value,
          );

    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final notifier = ref.read(activityTabProvider.notifier);
      if (hasExplicitTab) {
        // A route said which tab. Latch it, so a screen mounted earlier
        // without one cannot drag this one away when its counts resolve
        // (acttab1) — the provider is app-scoped and shared by every
        // mounted ActivityScreen.
        notifier.setTab(initial);
      } else if (ref.read(activityTabProvider) != initial) {
        notifier.suggestTab(initial);
      }
    });

    // Observability, not behaviour (acttab1). Until path URLs landed,
    // `?tab=` never reached this screen at all, so the explicit-beats-guess
    // rule had never been exercised — and with a window occluded there is
    // no rendering either, so nothing distinguished "Notifications
    // selected" from "Imports selected". One line makes the resolution
    // observable from the console instead of inferred from an empty DOM.
    debugPrint('ActivityScreen tab resolved: ${initial.wire} '
        '(explicit=$hasExplicitTab, raw=${widget.initialTab})');

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
    // One shot. These listeners live as long as the screen — which, for the
    // bottom-nav instance inside the shell's IndexedStack, is the life of
    // the process — so without this the "cold-start fallback" would keep
    // firing: a notification arriving 20 minutes later would throw a user
    // mid-scroll from Imports to Notifications. Cold start is the only
    // moment this guess is wanted.
    _dropCountListeners();
    final target = initialTabFromCounts(
      notifications: _readProvider.notificationsCount.value,
      importsActionable: _readProvider.importsActionableCount.value,
    );
    if (ref.read(activityTabProvider) == target) return;
    // `suggestTab`, not `setTab`: this is the guess from counts, and it
    // must lose to any deliberate choice — including one made by a
    // different screen that shares this provider.
    ref.read(activityTabProvider.notifier).suggestTab(target);
  }

  /// Idempotent — called on the first resolve and again on dispose.
  void _dropCountListeners() {
    _readProvider.notificationsCount.removeListener(_maybeAutoSwitchTab);
    _readProvider.importsActionableCount.removeListener(_maybeAutoSwitchTab);
  }

  @override
  void dispose() {
    _tabController.removeListener(_onControllerChange);
    _dropCountListeners();
    _tabController.dispose();
    super.dispose();
  }

  void _onControllerChange() {
    // Tab transitions fire twice — during the drag and when the new
    // index settles. Only write on the settle to avoid thrashing the
    // provider mid-swipe.
    if (_tabController.indexIsChanging) return;
    if (_syncingFromController) return;
    if (_animatingFromProvider) {
      // A programmatic `animateTo` settling, not a gesture. This used to
      // set `_userTouchedTab`, so the flag read "the user swiped" after
      // nobody had touched anything — harmless in effect, but it made the
      // flag mean something other than its name, and it is the only guard
      // left on the non-deliberate path.
      _animatingFromProvider = false;
      return;
    }
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
      _animatingFromProvider = true;
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
