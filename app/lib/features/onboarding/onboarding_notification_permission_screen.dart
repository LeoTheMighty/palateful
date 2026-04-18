import 'dart:io';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../shared/widgets/buttons.dart';

/// Onboarding step: ask for notification permission once, before the
/// start-method selection. Records the recorded permission state based on
/// the OS authorization outcome (not the button pressed) so the in-app
/// state matches reality.
///
/// Possible outcomes recorded (from `AuthorizationStatus`):
///   authorized   → "granted"
///   provisional  → "provisional"
///   denied       → "declined"
///   notDetermined → "declined"  (user saw the system prompt then backed out)
/// Tapping "Not now" records "declined" without firing the OS prompt.
class OnboardingNotificationPermissionScreen extends StatefulWidget {
  final String name;

  const OnboardingNotificationPermissionScreen({
    super.key,
    required this.name,
  });

  @override
  State<OnboardingNotificationPermissionScreen> createState() =>
      _OnboardingNotificationPermissionScreenState();
}

class _OnboardingNotificationPermissionScreenState
    extends State<OnboardingNotificationPermissionScreen> {
  bool _isRequesting = false;

  String _statusFromAuth(AuthorizationStatus status) {
    switch (status) {
      case AuthorizationStatus.authorized:
        return 'granted';
      case AuthorizationStatus.provisional:
        return 'provisional';
      case AuthorizationStatus.denied:
        return 'declined';
      case AuthorizationStatus.notDetermined:
        return 'declined';
    }
  }

  /// Platforms where notifications aren't a thing (web) skip the step entirely.
  bool get _shouldAskOnThisPlatform =>
      !kIsWeb && (Platform.isIOS || Platform.isAndroid);

  Future<void> _turnOn() async {
    if (_isRequesting) return;

    setState(() => _isRequesting = true);

    String permissionStatus = 'declined';
    try {
      if (_shouldAskOnThisPlatform) {
        final settings = await FirebaseMessaging.instance.requestPermission(
          alert: true,
          badge: true,
          sound: true,
          provisional: false,
        );
        permissionStatus = _statusFromAuth(settings.authorizationStatus);
        debugPrint(
          'Onboarding permission outcome: ${settings.authorizationStatus} '
          '→ recorded=$permissionStatus',
        );
      }
    } catch (e) {
      // If the OS prompt fails for any reason, still proceed — declined is
      // the conservative state. User can re-enable later in iOS Settings.
      debugPrint('requestPermission failed in onboarding: $e');
    }

    if (!mounted) return;
    _goToStart(permissionStatus);
  }

  void _notNow() {
    _goToStart('declined');
  }

  void _goToStart(String notificationPermissionStatus) {
    context.pushReplacement(
      '/onboarding/start',
      extra: {
        'name': widget.name,
        'notification_permission_status': notificationPermissionStatus,
      },
    );
  }

  @override
  void initState() {
    super.initState();
    // On platforms where this doesn't apply (web), auto-skip.
    if (!_shouldAskOnThisPlatform) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _goToStart('declined');
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: Icon(Icons.arrow_back, color: colorScheme.onSurface),
          onPressed: () => context.pop(),
        ),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 16),
              Center(
                child: Icon(
                  Icons.notifications_active_outlined,
                  size: 72,
                  color: colorScheme.primary,
                ),
              ),
              const SizedBox(height: 24),
              Text(
                'Stay in the loop.',
                style: textTheme.headlineMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: colorScheme.onSurface,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 12),
              Text(
                "Palateful will only ping you about things that matter — "
                "when a recipe import you kicked off finishes, when a partner "
                "updates a shared book or shopping list, or when a friend "
                "shares something with you. You can turn this off any time "
                "in Settings.",
                style: textTheme.bodyMedium?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                  height: 1.4,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 32),
              PrimaryButton(
                label: _isRequesting ? 'Requesting…' : 'Turn on notifications',
                onPressed: _isRequesting ? null : _turnOn,
                isExpanded: true,
              ),
              const SizedBox(height: 12),
              TextButton(
                onPressed: _isRequesting ? null : _notNow,
                child: const Text('Not now'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
