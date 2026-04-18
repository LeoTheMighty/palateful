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
  bool _partnerActivity = true;
  bool _autoApproveImports = true;
  String _quietHoursStart = '22:00';
  String _quietHoursEnd = '08:00';
  String _timezone = 'America/Denver';
  AuthorizationStatus? _osPermissionStatus;

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
        _partnerActivity = data['partner_activity'] as bool? ?? true;
        _autoApproveImports = data['auto_approve_imports'] as bool? ?? true;
        _quietHoursStart = data['quiet_hours_start'] as String? ?? '22:00';
        _quietHoursEnd = data['quiet_hours_end'] as String? ?? '08:00';
        _timezone = data['timezone'] as String? ?? 'America/Denver';
        _osPermissionStatus = osStatus;
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

        // Household notifications
        _buildSectionHeader('Household', textTheme),
        const SizedBox(height: 12),
        _buildToggleTile(
          icon: Icons.people_outlined,
          label: 'Partner Activity',
          subtitle: 'Notify when a partner shares a book or adds a recipe',
          value: _partnerActivity,
          onChanged: (value) {
            setState(() => _partnerActivity = value);
            _updatePreference(partnerActivity: value);
          },
          colorScheme: colorScheme,
          textTheme: textTheme,
        ),

        const SizedBox(height: 32),

        // Import settings
        _buildSectionHeader('Imports', textTheme),
        const SizedBox(height: 12),
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
    required ValueChanged<bool> onChanged,
    required ColorScheme colorScheme,
    required TextTheme textTheme,
  }) {
    return Material(
      color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: Row(
          children: [
            Icon(icon, color: colorScheme.onSurfaceVariant),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(label, style: textTheme.bodyLarge),
                  Text(
                    subtitle,
                    style: textTheme.bodySmall?.copyWith(
                      color: colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
            Switch(value: value, onChanged: onChanged),
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
