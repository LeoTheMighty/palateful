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
  static ActivityTab fromWire(String? value) =>
      tryFromWire(value) ?? ActivityTab.notifications;

  /// Parse a wire value, or null when it isn't one of ours.
  ///
  /// [fromWire] cannot tell `?tab=notifications` from `?tab=improts` — both
  /// come back as notifications. That difference matters to the latch in
  /// [ActivityTabNotifier]: a deliberate request should hold the tab for the
  /// session, a typo in a push payload or a truncated deep link should not.
  static ActivityTab? tryFromWire(String? value) {
    switch (value) {
      case 'imports':
        return ActivityTab.imports;
      case 'notifications':
        return ActivityTab.notifications;
      default:
        return null;
    }
  }

}

/// abi-4: pick the Activity tab to open when the route lacks an explicit
/// `?tab=` override. Lands on whichever side has more actionable items;
/// ties fall to Notifications (cold-start default).
///
/// Called from `ActivityScreen.initState` with the latest counts, and once
/// more if the counts resolve asynchronously AFTER mount (cold-start /
/// cache-cleared session). Two things stop it pulling the rug: it routes
/// through [ActivityTabNotifier.suggestTab], which loses to any deliberate
/// choice, and the screen drops its count listeners after the first resolve
/// so a later count change cannot move a tab the user is already reading.
ActivityTab initialTabFromCounts({
  required int notifications,
  required int importsActionable,
}) {
  if (importsActionable > notifications) return ActivityTab.imports;
  return ActivityTab.notifications;
}

/// The currently-selected Activity Hub tab.
///
/// App-scoped (not `autoDispose`) so a deliberate tab choice outlives any
/// one screen — which is also why it needs the latch below: every mounted
/// `ActivityScreen` reads and writes this one value. Cold-start defaults to
/// [ActivityTab.notifications]; [ActivityTabNotifier.reset] returns it there
/// on sign-out, since the process (and therefore this provider) outlives a
/// session.
///
/// Note a consequence: once something latches, a tab-less mount computes its
/// own `initial` from counts and its `suggestTab` no-ops, so this provider
/// can hold a tab the visible screen is not on. The `TabController` is the
/// visual source of truth and re-syncs on the next real change.
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

  /// Drop the latch and return to the cold-start default.
  ///
  /// Called on sign-out: the provider lives for the whole process, so
  /// without this the next user inherits the previous one's tab choice —
  /// and, worse, their latch, which would suppress the count-based pick for
  /// a user who has never chosen anything. Same symptom as the bug this
  /// story fixes, arrived at from a different direction.
  void reset() {
    _chosenDeliberately = false;
    state = ActivityTab.notifications;
  }
}

final activityTabProvider =
    NotifierProvider<ActivityTabNotifier, ActivityTab>(
  ActivityTabNotifier.new,
);
