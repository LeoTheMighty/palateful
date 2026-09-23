import 'package:flutter/foundation.dart' show visibleForTesting;
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// The two tabs on the Activity Hub.
///
/// Principle 1 of the epic: one route (`/activity`) with two top-of-screen
/// tabs. No bottom-nav duplication.
enum ActivityTab {
  /// Non-import activities — invitations, partner actions, meal reminders.
  notifications,

  /// Import pipeline — four color sections (blue/yellow/red/green) + see-all.
  imports;

  /// Canonical wire value for the `?tab=<value>` query parameter.
  String get wire => name;

  /// Parse a wire value; unknown / null falls back to notifications
  /// (cold-start default).
  static ActivityTab fromWire(String? value) {
    switch (value) {
      case 'imports':
        return ActivityTab.imports;
      case 'notifications':
        return ActivityTab.notifications;
      default:
        return ActivityTab.notifications;
    }
  }

}

/// abi-4: pick the Activity tab to open when the route lacks an explicit
/// `?tab=` override. Lands on whichever side has more actionable items;
/// ties fall to Notifications (cold-start default).
///
/// Called from `ActivityScreen.initState` with the latest counts, and
/// again in a post-frame callback if the counts resolve asynchronously
/// AFTER mount (cold-start / cache-cleared session). The screen's
/// `_userTouchedTab` latch blocks the second call if the user has
/// already manually swiped a tab — no rug-pull.
ActivityTab initialTabFromCounts({
  required int notifications,
  required int importsActionable,
}) {
  if (importsActionable > notifications) return ActivityTab.imports;
  return ActivityTab.notifications;
}

/// The currently-selected Activity Hub tab.
///
/// App-scoped (not `autoDispose`) so tab switches within a session are
/// remembered. Cold-start defaults to [ActivityTab.notifications] (a new
/// process always starts fresh). The `ActivityScreen` initializes the
/// provider from the route's `?tab=` query param on mount, then syncs
/// the `TabController` to follow.
class ActivityTabNotifier extends Notifier<ActivityTab> {
  /// True once something chose this tab deliberately — a route's `?tab=`,
  /// or the user's own swipe. Blocks the count-based guess from overriding
  /// it.
  ///
  /// acttab1: this provider is app-scoped, so a screen mounted WITHOUT a
  /// `?tab=` keeps count listeners alive and calls [setTab] when they
  /// resolve — moving every other mounted screen with it, including one
  /// that was just routed to an explicit tab. Measured in
  /// `activity_screen_tab_override_test`: tapping "1 import in progress"
  /// pushed `/activity?tab=imports`, the older screen's listener resolved
  /// (a pending parser batch contributes 0 to `imports_actionable`), and
  /// the new screen was dragged to Notifications. Per-screen latches
  /// cannot fix that — the state being fought over is shared, so the latch
  /// belongs with it.
  bool _chosenDeliberately = false;

  @override
  ActivityTab build() => ActivityTab.notifications;

  /// Select a tab because something asked for it: a route parameter or a
  /// user gesture. Latches out the count-based guess for this session.
  void setTab(ActivityTab tab) {
    _chosenDeliberately = true;
    state = tab;
  }

  /// Select a tab from resolved counts. A no-op once [setTab] has run, so
  /// a late-resolving count cannot pull the rug out from under a
  /// deliberate choice.
  void suggestTab(ActivityTab tab) {
    if (_chosenDeliberately) return;
    state = tab;
  }

  /// Test-only: reset the latch. The provider is app-scoped, so without
  /// this a single deliberate selection would leak across test cases.
  @visibleForTesting
  void resetForTest() {
    _chosenDeliberately = false;
    state = ActivityTab.notifications;
  }
}

final activityTabProvider =
    NotifierProvider<ActivityTabNotifier, ActivityTab>(
  ActivityTabNotifier.new,
);
