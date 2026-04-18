import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Live count of "actionable" imports — In Progress + Needs Review +
/// Failed. Green (Auto-Imported) is excluded per epic AC12: "Imports
/// tab badge = actionable imports only". The same formula is intended
/// to back the bottom-nav Activity badge's imports contribution so
/// the two numbers never disagree (ahr-7 wires the bottom-nav end).
///
/// `ImportsTab` writes this after each successful fetch; consumers
/// (the tab's own header badge, bottom-nav) read via `ref.watch`.
class ImportsActionableBadgeNotifier extends Notifier<int> {
  @override
  int build() => 0;

  void set(int value) {
    if (state == value) return;
    state = value;
  }
}

final importsActionableBadgeProvider =
    NotifierProvider<ImportsActionableBadgeNotifier, int>(
  ImportsActionableBadgeNotifier.new,
);
