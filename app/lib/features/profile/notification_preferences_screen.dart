import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';

class NotificationPreferencesScreen extends StatefulWidget {
  const NotificationPreferencesScreen({super.key});

  @override
  State<NotificationPreferencesScreen> createState() =>
      _NotificationPreferencesScreenState();
}

class _NotificationPreferencesScreenState
    extends State<NotificationPreferencesScreen> {
  final _apiClient = getIt<ApiClient>();

  bool _isLoading = true;
  String? _error;

  bool _pushEnabled = true;
  String _quietHoursStart = '22:00';
  String _quietHoursEnd = '08:00';
  String _timezone = 'America/Denver';

  @override
  void initState() {
    super.initState();
    _loadPreferences();
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
      setState(() {
        _pushEnabled = data['push_enabled'] as bool? ?? true;
        _quietHoursStart = data['quiet_hours_start'] as String? ?? '22:00';
        _quietHoursEnd = data['quiet_hours_end'] as String? ?? '08:00';
        _timezone = data['timezone'] as String? ?? 'America/Denver';
        _isLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = 'Failed to load notification preferences.';
        _isLoading = false;
      });
    }
  }

  Future<void> _updatePreference({
    bool? pushEnabled,
    String? quietHoursStart,
    String? quietHoursEnd,
    String? timezone,
  }) async {
    try {
      await _apiClient.updateNotificationPreferences(
        pushEnabled: pushEnabled,
        quietHoursStart: quietHoursStart,
        quietHoursEnd: quietHoursEnd,
        timezone: timezone,
      );
    } catch (e) {
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
          style: GoogleFonts.playfairDisplay(fontWeight: FontWeight.w600),
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
          onChanged: (value) {
            setState(() => _pushEnabled = value);
            _updatePreference(pushEnabled: value);
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
            style: GoogleFonts.playfairDisplay(fontWeight: FontWeight.w600),
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
        style: GoogleFonts.playfairDisplay(
          textStyle: textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w600,
          ),
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
