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

/// The currently-selected Activity Hub tab.
///
/// App-scoped (not `autoDispose`) so tab switches within a session are
/// remembered. Cold-start defaults to [ActivityTab.notifications] (a new
/// process always starts fresh). The `ActivityScreen` initializes the
/// provider from the route's `?tab=` query param on mount, then syncs
/// the `TabController` to follow.
class ActivityTabNotifier extends Notifier<ActivityTab> {
  @override
  ActivityTab build() => ActivityTab.notifications;

  void setTab(ActivityTab tab) {
    state = tab;
  }
}

final activityTabProvider =
    NotifierProvider<ActivityTabNotifier, ActivityTab>(
  ActivityTabNotifier.new,
);
