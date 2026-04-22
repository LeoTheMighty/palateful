import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';

import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../core/services/error_reporter.dart';
import '../../core/services/push_notification_service.dart';
import '../../shared/widgets/error_banner.dart';

class NotificationPreferencesScreen extends StatefulWidget {
  const NotificationPreferencesScreen({super.key});

  @override
  State<NotificationPreferencesScreen> createState() =>
      _NotificationPreferencesScreenState();
}

class _NotificationPreferencesScreenState
    extends State<NotificationPreferencesScreen> {
  final _apiClient = getIt<ApiClient>();
  final _pushService = getIt<PushNotificationService>();

  bool _isLoading = true;
  String? _error;
  String? _errorDetail;

  bool _pushEnabled = true;
  bool _autoApproveImports = true;
  String _quietHoursStart = '22:00';
  String _quietHoursEnd = '08:00';
  String _timezone = 'America/Denver';
  AuthorizationStatus? _osPermissionStatus;

  // Per-category opt-out toggles. Order = display order on the screen.
  // Keys MUST match the backend `NOTIFICATION_CATEGORIES` set in
  // libraries/utils/utils/services/push_notification.py.
  static const _categoryDefinitions = <_CategoryDef>[
    _CategoryDef('meals', 'Meal reminders', Icons.restaurant_menu_outlined,
        'Invites, time-of-meal reminders, and updates'),
    _CategoryDef('timers', 'Timers', Icons.timer_outlined,
        'Background alerts when a cook timer finishes'),
    _CategoryDef('shopping', 'Shopping', Icons.shopping_cart_outlined,
        'List updates, items checked off, deadline reminders'),
    _CategoryDef('partner_activity', 'Partner activity', Icons.people_outline,
        'When a partner adds a recipe or shares a book'),
    _CategoryDef('imports', 'Imports', Icons.cloud_download_outlined,
        '"Ready to review" pushes after a recipe import finishes'),
    _CategoryDef('friends_invitations', 'Friends & invitations',
        Icons.person_add_alt_outlined,
        'Friend requests, book/calendar invites, and acceptances'),
  ];

  Map<String, bool> _categories = {
    for (final c in _categoryDefinitions) c.key: true,
  };

  @override
  void initState() {
    super.initState();
    _loadPreferences();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Refresh OS permission state when the screen is resumed (e.g. after the
    // user came back from iOS Settings).
    _refreshOsPermissionStatus();
  }

  Future<void> _refreshOsPermissionStatus() async {
    if (!_pushService.isAvailable) return;
    final status = await _pushService.getPermissionStatus();
    if (!mounted) return;
    setState(() => _osPermissionStatus = status);
  }

  Future<void> _loadPreferences() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final response = await _apiClient.getNotificationPreferences();
      if (!mounted) return;

      final data = response.data as Map<String, dynamic>;
      final osStatus = _pushService.isAvailable
          ? await _pushService.getPermissionStatus()
          : null;
      if (!mounted) return;
      setState(() {
        _pushEnabled = data['push_enabled'] as bool? ?? true;
        _autoApproveImports = data['auto_approve_imports'] as bool? ?? true;
        _quietHoursStart = data['quiet_hours_start'] as String? ?? '22:00';
        _quietHoursEnd = data['quiet_hours_end'] as String? ?? '08:00';
        _timezone = data['timezone'] as String? ?? 'America/Denver';
        _osPermissionStatus = osStatus;
        _categories = _readCategories(data['categories']);
        _isLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = 'Failed to load notification preferences.';
        _errorDetail = ErrorReporter.detail(e);
        _isLoading = false;
      });
    }
  }

  bool get _osGranted =>
      _osPermissionStatus == AuthorizationStatus.authorized ||
      _osPermissionStatus == AuthorizationStatus.provisional;

  Future<void> _handlePushToggle(bool value) async {
    if (!value) {
      setState(() => _pushEnabled = false);
      _updatePreference(pushEnabled: false);
      return;
    }

    // Turning on: make sure the OS permission is granted and the device's
    // FCM token is registered with the backend before we flip the pref.
    // autoPrompt=true because this is a user-initiated action — they just
    // tapped the toggle and expect the OS prompt immediately (push-diag-2).
    final status = await _pushService.ensureRegistered(autoPrompt: true);
    if (!mounted) return;

    final granted = status == AuthorizationStatus.authorized ||
        status == AuthorizationStatus.provisional;

    setState(() => _osPermissionStatus = status);

    if (granted) {
      setState(() => _pushEnabled = true);
      _updatePreference(pushEnabled: true);
    } else {
      await _showOpenSettingsDialog();
    }
  }

  Future<void> _showOpenSettingsDialog() async {
    final opened = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Notifications are off'),
        content: const Text(
          "Palateful can't send notifications until you allow them in "
          'your device settings.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Not now'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Open Settings'),
          ),
        ],
      ),
    );
    if (opened == true) {
      await _pushService.openOsSettings();
    }
  }

  Map<String, bool> _readCategories(dynamic raw) {
    final result = <String, bool>{
      for (final c in _categoryDefinitions) c.key: true,
    };
    if (raw is Map) {
      for (final entry in raw.entries) {
        final key = entry.key;
        if (key is String && result.containsKey(key) && entry.value is bool) {
          result[key] = entry.value as bool;
        }
      }
    }
    return result;
  }

  Future<void> _toggleCategory(String key, bool value) async {
    final previous = _categories[key] ?? true;
    if (previous == value) return;
    setState(() {
      _categories = {..._categories, key: value};
    });
    try {
      await _apiClient.updateNotificationPreferences(
        categories: {key: value},
      );
    } catch (e, st) {
      ErrorReporter.report(
        e,
        st,
        area: 'push',
        operation: 'preferences.category.save',
      );
      if (!mounted) return;
      // Revert local state on failure.
      setState(() {
        _categories = {..._categories, key: previous};
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Failed to save preference.')),
      );
    }
  }

  Future<void> _updatePreference({
    bool? pushEnabled,
    bool? partnerActivity,
    bool? autoApproveImports,
    String? quietHoursStart,
    String? quietHoursEnd,
    String? timezone,
  }) async {
    try {
      await _apiClient.updateNotificationPreferences(
        pushEnabled: pushEnabled,
        partnerActivity: partnerActivity,
        autoApproveImports: autoApproveImports,
        quietHoursStart: quietHoursStart,
        quietHoursEnd: quietHoursEnd,
        timezone: timezone,
      );
    } catch (e, st) {
      ErrorReporter.report(
        e,
        st,
        area: 'push',
        operation: 'preferences.save',
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Failed to save preference.')),
      );
      // Reload to get server state
      _loadPreferences();
    }
  }

  Future<void> _pickTime({
    required String current,
    required String label,
    required void Function(String) onPicked,
  }) async {
    final parts = current.split(':');
    final hour = int.tryParse(parts[0]) ?? 22;
    final minute = int.tryParse(parts.length > 1 ? parts[1] : '0') ?? 0;

    final picked = await showTimePicker(
      context: context,
      initialTime: TimeOfDay(hour: hour, minute: minute),
      helpText: label,
    );

    if (picked != null && mounted) {
      final formatted =
          '${picked.hour.toString().padLeft(2, '0')}:${picked.minute.toString().padLeft(2, '0')}';
      onPicked(formatted);
    }
  }

  String _formatTime(String time) {
    final parts = time.split(':');
    final hour = int.tryParse(parts[0]) ?? 0;
    final minute = int.tryParse(parts.length > 1 ? parts[1] : '0') ?? 0;
    final tod = TimeOfDay(hour: hour, minute: minute);
    final period = tod.period == DayPeriod.am ? 'AM' : 'PM';
    final h = tod.hourOfPeriod == 0 ? 12 : tod.hourOfPeriod;
    return '$h:${minute.toString().padLeft(2, '0')} $period';
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(
        title: Text(
          'Notifications',
          style: Theme.of(context).textTheme.titleLarge,
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _buildErrorState(colorScheme)
              : _buildContent(colorScheme, textTheme),
    );
  }

  Widget _buildErrorState(ColorScheme colorScheme) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.error_outline, size: 64, color: colorScheme.error),
            const SizedBox(height: 16),
            Text(_error!, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: _loadPreferences,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildContent(ColorScheme colorScheme, TextTheme textTheme) {
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        // Push notifications master toggle
        _buildSectionHeader('Push Notifications', textTheme),
        const SizedBox(height: 12),
        _buildToggleTile(
          icon: Icons.notifications_outlined,
          label: 'Push Notifications',
          subtitle: 'Receive notifications on this device',
          value: _pushEnabled,
          onChanged: _handlePushToggle,
          colorScheme: colorScheme,
          textTheme: textTheme,
        ),
        if (_pushEnabled &&
            _pushService.isAvailable &&
            _osPermissionStatus != null &&
            !_osGranted) ...[
          const SizedBox(height: 12),
          _buildOsPermissionWarning(colorScheme, textTheme),
        ],

        const SizedBox(height: 32),

        // Per-category opt-out — the load-bearing surface for this epic.
        _buildSectionHeader('Notifications by category', textTheme),
        const SizedBox(height: 4),
        Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: Text(
            _pushEnabled
                ? 'Mute any single category without disabling all push.'
                : 'Turn the master switch on to manage individual categories.',
            style: textTheme.bodySmall?.copyWith(
              color: colorScheme.onSurfaceVariant,
            ),
          ),
        ),
        for (var i = 0; i < _categoryDefinitions.length; i++) ...[
          if (i > 0) const SizedBox(height: 8),
          _buildToggleTile(
            icon: _categoryDefinitions[i].icon,
            label: _categoryDefinitions[i].label,
            subtitle: _categoryDefinitions[i].subtitle,
            value: _categories[_categoryDefinitions[i].key] ?? true,
            onChanged: _pushEnabled
                ? (value) =>
                    _toggleCategory(_categoryDefinitions[i].key, value)
                : null,
            colorScheme: colorScheme,
            textTheme: textTheme,
            enabled: _pushEnabled,
          ),
        ],

        const SizedBox(height: 32),

        // Import behavior — NOT a notification opt-out. Controls whether
        // the import pipeline auto-approves high-confidence extractions
        // (skipping the review step entirely).
        _buildSectionHeader('Import behavior', textTheme),
        const SizedBox(height: 4),
        Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: Text(
            'Not a notification setting — controls whether confident imports auto-save.',
            style: textTheme.bodySmall?.copyWith(
              color: colorScheme.onSurfaceVariant,
            ),
          ),
        ),
        _buildToggleTile(
          icon: Icons.auto_awesome,
          label: 'Auto-save high-confidence imports',
          subtitle: 'Skip review when AI is confident about the recipe',
          value: _autoApproveImports,
          onChanged: (value) {
            setState(() => _autoApproveImports = value);
            _updatePreference(autoApproveImports: value);
          },
          colorScheme: colorScheme,
          textTheme: textTheme,
        ),

        const SizedBox(height: 32),

        // Quiet hours
        _buildSectionHeader('Quiet Hours', textTheme),
        const SizedBox(height: 4),
        Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: Text(
            'Notifications will be silenced during quiet hours.',
            style: textTheme.bodySmall?.copyWith(
              color: colorScheme.onSurfaceVariant,
            ),
          ),
        ),
        _buildTapTile(
          icon: Icons.bedtime_outlined,
          label: 'Start',
          value: _formatTime(_quietHoursStart),
          onTap: () => _pickTime(
            current: _quietHoursStart,
            label: 'Quiet hours start',
            onPicked: (time) {
              setState(() => _quietHoursStart = time);
              _updatePreference(quietHoursStart: time);
            },
          ),
          colorScheme: colorScheme,
          textTheme: textTheme,
        ),
        const SizedBox(height: 8),
        _buildTapTile(
          icon: Icons.wb_sunny_outlined,
          label: 'End',
          value: _formatTime(_quietHoursEnd),
          onTap: () => _pickTime(
            current: _quietHoursEnd,
            label: 'Quiet hours end',
            onPicked: (time) {
              setState(() => _quietHoursEnd = time);
              _updatePreference(quietHoursEnd: time);
            },
          ),
          colorScheme: colorScheme,
          textTheme: textTheme,
        ),

        const SizedBox(height: 32),

        // Timezone
        _buildSectionHeader('Timezone', textTheme),
        const SizedBox(height: 12),
        _buildTapTile(
          icon: Icons.public,
          label: 'Timezone',
          value: _timezone.replaceAll('_', ' ').replaceAll('/', ' / '),
          onTap: () => _showTimezoneDialog(),
          colorScheme: colorScheme,
          textTheme: textTheme,
        ),
      ],
    );
  }

  Future<void> _showTimezoneDialog() async {
    const timezones = [
      'America/New_York',
      'America/Chicago',
      'America/Denver',
      'America/Los_Angeles',
      'America/Phoenix',
      'America/Anchorage',
      'Pacific/Honolulu',
      'Europe/London',
      'Europe/Paris',
      'Europe/Berlin',
      'Asia/Tokyo',
      'Asia/Shanghai',
      'Australia/Sydney',
    ];

    final result = await showDialog<String>(
      context: context,
      builder: (context) {
        return SimpleDialog(
          title: Text(
            'Select Timezone',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          children: timezones.map((tz) {
            final display = tz.replaceAll('_', ' ').replaceAll('/', ' / ');
            return SimpleDialogOption(
              onPressed: () => Navigator.of(context).pop(tz),
              child: Row(
                children: [
                  if (tz == _timezone)
                    Icon(Icons.check,
                        size: 20,
                        color: Theme.of(context).colorScheme.primary)
                  else
                    const SizedBox(width: 20),
                  const SizedBox(width: 12),
                  Text(display),
                ],
              ),
            );
          }).toList(),
        );
      },
    );

    if (result != null && result != _timezone && mounted) {
      setState(() => _timezone = result);
      _updatePreference(timezone: result);
    }
  }

  Widget _buildSectionHeader(String title, TextTheme textTheme) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Text(
        title,
        style: textTheme.titleMedium?.copyWith(
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  Widget _buildToggleTile({
    required IconData icon,
    required String label,
    required String subtitle,
    required bool value,
    required ValueChanged<bool>? onChanged,
    required ColorScheme colorScheme,
    required TextTheme textTheme,
    bool enabled = true,
  }) {
    final foreground = enabled
        ? colorScheme.onSurface
        : colorScheme.onSurface.withValues(alpha: 0.38);
    final muted = enabled
        ? colorScheme.onSurfaceVariant
        : colorScheme.onSurfaceVariant.withValues(alpha: 0.38);
    return Material(
      color: colorScheme.surfaceContainerHighest.withValues(
        alpha: enabled ? 0.5 : 0.25,
      ),
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: Row(
          children: [
            Icon(icon, color: muted),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label,
                    style: textTheme.bodyLarge?.copyWith(color: foreground),
                  ),
                  Text(
                    subtitle,
                    style: textTheme.bodySmall?.copyWith(color: muted),
                  ),
                ],
              ),
            ),
            Switch(value: value, onChanged: enabled ? onChanged : null),
          ],
        ),
      ),
    );
  }

  Widget _buildOsPermissionWarning(
      ColorScheme colorScheme, TextTheme textTheme) {
    return Material(
      color: colorScheme.errorContainer.withValues(alpha: 0.6),
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(Icons.warning_amber_rounded, color: colorScheme.onErrorContainer),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Notifications blocked at the device level',
                    style: textTheme.bodyMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                      color: colorScheme.onErrorContainer,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'This toggle is on, but your device is not allowing '
                    'notifications for Palateful. Open Settings to enable.',
                    style: textTheme.bodySmall?.copyWith(
                      color: colorScheme.onErrorContainer,
                    ),
                  ),
                  const SizedBox(height: 8),
                  TextButton(
                    style: TextButton.styleFrom(
                      padding: EdgeInsets.zero,
                      minimumSize: Size.zero,
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      foregroundColor: colorScheme.onErrorContainer,
                    ),
                    onPressed: () async {
                      await _pushService.openOsSettings();
                    },
                    child: const Text('Open Settings'),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTapTile({
    required IconData icon,
    required String label,
    required String value,
    required VoidCallback onTap,
    required ColorScheme colorScheme,
    required TextTheme textTheme,
  }) {
    return Material(
      color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          child: Row(
            children: [
              Icon(icon, color: colorScheme.onSurfaceVariant),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      label,
                      style: textTheme.bodySmall?.copyWith(
                        color: colorScheme.onSurfaceVariant,
                      ),
                    ),
                    Text(value, style: textTheme.bodyLarge),
                  ],
                ),
              ),
              Icon(Icons.chevron_right, color: colorScheme.onSurfaceVariant),
            ],
          ),
        ),
      ),
    );
  }
}

class _CategoryDef {
  const _CategoryDef(this.key, this.label, this.icon, this.subtitle);
  final String key;
  final String label;
  final IconData icon;
  final String subtitle;
}
