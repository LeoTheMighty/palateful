import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// cla-12 AC5 — re-verifiable inspection test for the Firebase
/// Performance scope lockdown. These tests parse the iOS `Info.plist`
/// and Android `AndroidManifest.xml` on disk and assert the expected
/// scope flags are present. If a future PR removes or renames the
/// flags, CI catches the regression before a release cuts and we lose
/// the lockdown silently.
///
/// The test does NOT assert that Firebase actually honors the flags at
/// runtime — the Firebase SDK doesn't publish a Dart-reachable
/// introspection hook. Runtime verification is the manual 24 h
/// Firebase Console check in the epic's AC + the runbook section in
/// docs/PERFORMANCE_OPS.md.
void main() {
  test('iOS Info.plist has firebase_performance_collection_enabled=true', () {
    final plist = File('ios/Runner/Info.plist').readAsStringSync();
    expect(
      plist.contains('<key>firebase_performance_collection_enabled</key>'),
      isTrue,
      reason: 'cla-12: iOS collection toggle key missing from Info.plist',
    );
    // The key pair format in a plist has the <true/> (or <false/>) tag
    // on the line immediately after the <key> — match with a simple
    // substring check that spans both lines.
    expect(
      plist.contains(RegExp(
        r'<key>firebase_performance_collection_enabled</key>\s*<true\s*/>',
        multiLine: true,
      )),
      isTrue,
      reason: 'cla-12: iOS collection toggle must be <true/>, not <false/>',
    );
  });

  test('Android manifest pins Firebase Performance scope lockdown meta-data',
      () {
    final manifest =
        File('android/app/src/main/AndroidManifest.xml').readAsStringSync();
    expect(
      manifest.contains('firebase_performance_collection_enabled'),
      isTrue,
      reason: 'cla-12: Android collection toggle missing from manifest',
    );
    expect(
      manifest.contains('firebase_performance_auto_activity_trace_enabled'),
      isTrue,
      reason:
          'cla-12: Android auto-activity-trace lockdown missing from manifest',
    );
    // Crude but reliable: the `_enabled` pair must be "true" and the
    // `_auto_activity_trace_enabled` must be "false". Match the common
    // AAPT-normalized form.
    expect(
      manifest.contains(RegExp(
        r'firebase_performance_collection_enabled"\s*android:value="true"',
      )),
      isTrue,
      reason: 'cla-12: collection_enabled must be "true"',
    );
    expect(
      manifest.contains(RegExp(
        r'firebase_performance_auto_activity_trace_enabled"\s*android:value="false"',
      )),
      isTrue,
      reason: 'cla-12: auto_activity_trace_enabled must be "false"',
    );
  });
}
