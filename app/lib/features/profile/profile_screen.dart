import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:share_plus/share_plus.dart';
import 'package:shimmer/shimmer.dart';

import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../services/share_service.dart';
import '../../core/services/auth_service.dart';
import '../../core/services/push_notification_service.dart';
import '../../providers/theme_mode_provider.dart';
import '../../core/services/error_reporter.dart';
import '../../shared/widgets/error_banner.dart';
import '../chat/chat_service.dart';

class ProfileScreen extends ConsumerStatefulWidget {
  const ProfileScreen({super.key});

  @override
  ConsumerState<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends ConsumerState<ProfileScreen> {
  final _apiClient = getIt<ApiClient>();
  final _authService = getIt<AuthService>();

  bool _isLoading = true;
  bool _isExporting = false;
  String? _error;
  String? _errorDetail;

  // Profile data
  String? _name;
  String? _email;
  String? _picture;
  String? _username;
  DateTime? _createdAt;
  DateTime? _usernameChangedAt;

  @override
  void initState() {
    super.initState();
    _fetchProfile();
  }

  Future<void> _fetchProfile() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final response = await _apiClient.getMe();
      if (!mounted) return;

      final data = response.data as Map<String, dynamic>;
      setState(() {
        _name = data['name'] as String?;
        _email = data['email'] as String?;
        _picture = data['picture'] as String?;
        _username = data['username'] as String?;
        _createdAt = data['created_at'] != null
            ? DateTime.parse(data['created_at'] as String)
            : null;
        _usernameChangedAt = data['username_changed_at'] != null
            ? DateTime.parse(data['username_changed_at'] as String)
            : null;
        _isLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = 'Failed to load profile. Please try again.';
        _errorDetail = ErrorReporter.detail(e);
        _isLoading = false;
      });
    }
  }

  Future<void> _showEditNameDialog() async {
    final controller = TextEditingController(text: _name ?? '');
    bool isSaving = false;
    String? dialogError;

    final result = await showDialog<String>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return PopScope(
              canPop: !isSaving,
              child: AlertDialog(
              title: Text(
                'Edit Display Name',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                    controller: controller,
                    autofocus: true,
                    decoration: const InputDecoration(
                      labelText: 'Display Name',
                      hintText: 'Enter your name',
                    ),
                    textCapitalization: TextCapitalization.words,
                    enabled: !isSaving,
                  ),
                  if (dialogError != null) ...[
                    const SizedBox(height: 8),
                    Text(
                      dialogError!,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ],
              ),
              actions: [
                TextButton(
                  onPressed: isSaving
                      ? null
                      : () => Navigator.of(context).pop(null),
                  child: const Text('Cancel'),
                ),
                FilledButton(
                  onPressed: isSaving
                      ? null
                      : () async {
                          final newName = controller.text.trim();
                          if (newName.isEmpty) {
                            setDialogState(() {
                              dialogError = 'Name cannot be empty';
                            });
                            return;
                          }

                          setDialogState(() {
                            isSaving = true;
                            dialogError = null;
                          });

                          try {
                            await _apiClient.updateProfile(name: newName);
                            if (context.mounted) {
                              Navigator.of(context).pop(newName);
                            }
                          } catch (e) {
                            if (context.mounted) {
                              setDialogState(() {
                                isSaving = false;
                                dialogError = 'Failed to save. Please try again.';
                              });
                            }
                          }
                        },
                  child: isSaving
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Save'),
                ),
              ],
            ),
            );
          },
        );
      },
    );

    if (result != null && mounted) {
      setState(() {
        _name = result;
      });
    }
  }

  Future<void> _showEditUsernameDialog() async {
    final controller = TextEditingController(text: _username ?? '');
    bool isSaving = false;
    String? dialogError;
    String? availabilityStatus; // 'available', 'taken', 'invalid_format', 'reserved', 'checking'
    Timer? debounceTimer;

    final result = await showDialog<String>(
      context: context,
      builder: (dialogContext) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            void checkAvailability(String value) {
              debounceTimer?.cancel();
              final username = value.trim().toLowerCase();

              if (username.isEmpty || username == _username) {
                setDialogState(() {
                  availabilityStatus = null;
                  dialogError = null;
                });
                return;
              }

              if (username.length < 3) {
                setDialogState(() {
                  availabilityStatus = 'invalid_format';
                  dialogError = 'Username must be at least 3 characters';
                });
                return;
              }

              setDialogState(() {
                availabilityStatus = 'checking';
                dialogError = null;
              });

              debounceTimer = Timer(const Duration(milliseconds: 500), () async {
                try {
                  if (!context.mounted) return;
                  final response = await _apiClient.checkUsername(username);
                  if (!context.mounted) return;
                  final data = response.data as Map<String, dynamic>;
                  final available = data['available'] as bool;
                  final reason = data['reason'] as String?;
                  final message = data['message'] as String?;

                  setDialogState(() {
                    if (available) {
                      availabilityStatus = 'available';
                      dialogError = null;
                    } else {
                      availabilityStatus = reason ?? 'taken';
                      dialogError = message;
                    }
                  });
                } catch (e) {
                  if (context.mounted) {
                    setDialogState(() {
                      availabilityStatus = null;
                      dialogError = 'Could not check availability';
                    });
                  }
                }
              });
            }

            Widget? suffixIcon;
            if (availabilityStatus == 'checking') {
              suffixIcon = const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              );
            } else if (availabilityStatus == 'available') {
              suffixIcon = Icon(
                Icons.check_circle,
                color: Theme.of(context).colorScheme.primary,
              );
            } else if (availabilityStatus != null && availabilityStatus != 'checking') {
              suffixIcon = Icon(
                Icons.cancel,
                color: Theme.of(context).colorScheme.error,
              );
            }

            final bool hasUsernameChanged = _username != null &&
                _usernameChangedAt != null &&
                _usernameChangedAt!.isAfter(
                    DateTime.now().subtract(const Duration(days: 30)));

            return PopScope(
              canPop: !isSaving,
              child: AlertDialog(
              title: Text(
                _username != null ? 'Change Username' : 'Set Username',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (hasUsernameChanged) ...[
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: Theme.of(context).colorScheme.tertiaryContainer,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Row(
                        children: [
                          Icon(
                            Icons.info_outline,
                            size: 16,
                            color: Theme.of(context).colorScheme.onTertiaryContainer,
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              'Username can only be changed once every 30 days.',
                              style: TextStyle(
                                fontSize: 12,
                                color: Theme.of(context).colorScheme.onTertiaryContainer,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 12),
                  ],
                  TextField(
                    controller: controller,
                    autofocus: true,
                    decoration: InputDecoration(
                      labelText: 'Username',
                      hintText: 'e.g. chef_leo',
                      prefixText: '@',
                      suffixIcon: suffixIcon != null
                          ? Padding(
                              padding: const EdgeInsets.all(12),
                              child: suffixIcon,
                            )
                          : null,
                    ),
                    enabled: !isSaving,
                    onChanged: checkAvailability,
                  ),
                  if (dialogError != null) ...[
                    const SizedBox(height: 8),
                    Text(
                      dialogError!,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                        fontSize: 12,
                      ),
                    ),
                  ],
                  const SizedBox(height: 8),
                  Text(
                    '3-20 characters. Letters, numbers, underscores.',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                  ),
                ],
              ),
              actions: [
                TextButton(
                  onPressed: isSaving
                      ? null
                      : () {
                          debounceTimer?.cancel();
                          Navigator.of(context).pop(null);
                        },
                  child: const Text('Cancel'),
                ),
                FilledButton(
                  onPressed: (isSaving || availabilityStatus != 'available')
                      ? null
                      : () async {
                          final newUsername = controller.text.trim().toLowerCase();

                          setDialogState(() {
                            isSaving = true;
                            dialogError = null;
                          });

                          try {
                            await _apiClient.setUsername(newUsername);
                            debounceTimer?.cancel();
                            if (context.mounted) {
                              Navigator.of(context).pop(newUsername);
                            }
                          } catch (e) {
                            if (context.mounted) {
                              setDialogState(() {
                                isSaving = false;
                                dialogError = 'Failed to save. Please try again.';
                              });
                            }
                          }
                        },
                  child: isSaving
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Save'),
                ),
              ],
            ),
            );
          },
        );
      },
    );

    if (result != null && mounted) {
      setState(() {
        _username = result;
        _usernameChangedAt = DateTime.now();
      });
    }
  }

  String _formatDate(DateTime date) {
    const months = [
      'January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December',
    ];
    return '${months[date.month - 1]} ${date.year}';
  }

  Future<void> _exportCollection() async {
    if (_isExporting) return;
    setState(() => _isExporting = true);
    try {
      final response = await _apiClient.exportRecipes();
      final jsonString = jsonEncode(response.data);
      final bytes = Uint8List.fromList(utf8.encode(jsonString));
      final timestamp = DateTime.now()
          .toIso8601String()
          .replaceAll(':', '-')
          .substring(0, 19);
      await Share.shareXFiles(
        [
          XFile.fromData(
            bytes,
            name: 'palateful_recipes_$timestamp.json',
            mimeType: 'application/json',
          )
        ],
        subject: 'My Palateful Recipe Collection',
        sharePositionOrigin: ShareService.originFrom(context),
      );
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Export failed — please try again')),
        );
      }
    } finally {
      if (mounted) setState(() => _isExporting = false);
    }
  }

  Future<void> _openAiAssistant() async {
    try {
      final chatService = ChatService(_apiClient.dio);
      final thread = await chatService.createThread();
      if (mounted) {
        context.push('/chat/${thread.id}');
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to open AI Assistant: $e')),
        );
      }
    }
  }

  Future<void> _logout() async {
    // Unregister FCM token before clearing credentials so the API call
    // still has a valid auth token.
    await getIt<PushNotificationService>().unregisterToken();
    await _authService.logout();
    _apiClient.clearAuthToken();
    if (!mounted) return;
    context.go('/login');
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(
        title: Text(
          'Profile',
          style: Theme.of(context).textTheme.titleLarge,
        ),
      ),
      body: _isLoading
          ? _buildLoadingState()
          : _error != null
              ? _buildErrorState(colorScheme, textTheme)
              : _buildProfileContent(colorScheme, textTheme),
    );
  }

  Widget _buildLoadingState() {
    return Shimmer.fromColors(
      baseColor: Theme.of(context).colorScheme.surfaceContainerHighest,
      highlightColor: Theme.of(context).colorScheme.surface,
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            const CircleAvatar(radius: 48),
            const SizedBox(height: 16),
            Container(height: 20, width: 150, color: Colors.white),
            const SizedBox(height: 8),
            Container(height: 14, width: 200, color: Colors.white),
            const SizedBox(height: 32),
            Container(height: 56, width: double.infinity, color: Colors.white),
            const SizedBox(height: 12),
            Container(height: 56, width: double.infinity, color: Colors.white),
          ],
        ),
      ),
    );
  }

  Widget _buildErrorState(ColorScheme colorScheme, TextTheme textTheme) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.error_outline,
              size: 64,
              color: colorScheme.error,
            ),
            const SizedBox(height: 16),
            ErrorBanner(message: _error!, detail: _errorDetail),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: _fetchProfile,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildProfileContent(ColorScheme colorScheme, TextTheme textTheme) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          // Avatar
          _buildAvatar(colorScheme),
          const SizedBox(height: 16),

          // Display name
          Text(
            _name ?? 'No name set',
            style: textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
          if (_email != null) ...[
            const SizedBox(height: 4),
            Text(
              _email!,
              style: textTheme.bodyMedium?.copyWith(
                color: colorScheme.onSurfaceVariant,
              ),
            ),
          ],
          if (_createdAt != null) ...[
            const SizedBox(height: 4),
            Text(
              'Member since ${_formatDate(_createdAt!)}',
              style: textTheme.bodySmall?.copyWith(
                color: colorScheme.onSurfaceVariant,
              ),
            ),
          ],

          const SizedBox(height: 32),

          // Edit Profile section
          _buildSectionHeader('Edit Profile', textTheme),
          const SizedBox(height: 12),
          _buildProfileTile(
            icon: Icons.person_outline,
            label: 'Display Name',
            value: _name ?? 'Not set',
            onTap: _showEditNameDialog,
            colorScheme: colorScheme,
            textTheme: textTheme,
          ),
          const SizedBox(height: 8),
          _buildProfileTile(
            icon: Icons.alternate_email,
            label: 'Username',
            value: _username != null ? '@$_username' : 'Set username',
            onTap: _showEditUsernameDialog,
            colorScheme: colorScheme,
            textTheme: textTheme,
            valueColor: _username == null ? colorScheme.primary : null,
          ),

          const SizedBox(height: 32),

          // Recipes section
          _buildSectionHeader('Recipes', textTheme),
          const SizedBox(height: 12),
          _buildProfileTile(
            icon: Icons.archive_outlined,
            label: 'Archived Recipes',
            value: 'View and restore archived recipes',
            onTap: () => context.push('/recipes/archived'),
            colorScheme: colorScheme,
            textTheme: textTheme,
          ),
          const SizedBox(height: 8),
          _buildProfileTile(
            icon: Icons.download_outlined,
            label: 'Export Collection',
            value: _isExporting ? 'Exporting...' : 'Download all your recipes as JSON',
            onTap: _isExporting ? () {} : _exportCollection,
            colorScheme: colorScheme,
            textTheme: textTheme,
          ),

          const SizedBox(height: 32),

          // Appearance section
          _buildSectionHeader('Appearance', textTheme),
          const SizedBox(height: 12),
          _buildThemeModeSelector(colorScheme, textTheme),
          const SizedBox(height: 16),
          _buildFontStyleSelector(colorScheme, textTheme),

          const SizedBox(height: 32),

          // Settings section
          _buildSectionHeader('Settings', textTheme),
          const SizedBox(height: 12),
          if (_authService.isAdmin) ...[
            _buildProfileTile(
              icon: Icons.admin_panel_settings_outlined,
              label: 'Admin Dashboard',
              value: 'Manage users, view logs and errors',
              onTap: () => context.push('/admin'),
              colorScheme: colorScheme,
              textTheme: textTheme,
            ),
            const SizedBox(height: 8),
            _buildProfileTile(
              icon: Icons.chat_bubble_outline,
              label: 'AI Assistant (internal)',
              value: 'Open the in-app chat surface',
              onTap: _openAiAssistant,
              colorScheme: colorScheme,
              textTheme: textTheme,
            ),
            const SizedBox(height: 8),
          ],
          _buildProfileTile(
            icon: Icons.mail_outline,
            label: 'Invitations',
            value: 'View and manage invitations',
            onTap: () => context.push('/invitations'),
            colorScheme: colorScheme,
            textTheme: textTheme,
          ),
          const SizedBox(height: 8),
          _buildProfileTile(
            icon: Icons.notifications_outlined,
            label: 'Notifications',
            value: 'Push notifications & quiet hours',
            onTap: () => context.push('/profile/notifications'),
            colorScheme: colorScheme,
            textTheme: textTheme,
          ),

          const SizedBox(height: 32),

          // Account section
          _buildSectionHeader('Account', textTheme),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: _logout,
              icon: Icon(Icons.logout, color: colorScheme.error),
              label: Text(
                'Logout',
                style: TextStyle(color: colorScheme.error),
              ),
              style: OutlinedButton.styleFrom(
                side: BorderSide(color: colorScheme.error.withValues(alpha: 0.5)),
                padding: const EdgeInsets.symmetric(vertical: 12),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildThemeModeSelector(ColorScheme colorScheme, TextTheme textTheme) {
    final currentMode = ref.watch(themeModeProvider);
    const modes = [
      (ThemeMode.system, Icons.brightness_auto, 'System'),
      (ThemeMode.light, Icons.light_mode, 'Light'),
      (ThemeMode.dark, Icons.dark_mode, 'Dark'),
    ];

    return Material(
      color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Row(
          children: modes.map((entry) {
            final (mode, icon, label) = entry;
            final isSelected = currentMode == mode;
            return Expanded(
              child: GestureDetector(
                onTap: () => ref.read(themeModeProvider.notifier).setThemeMode(mode),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  padding: const EdgeInsets.symmetric(vertical: 10),
                  decoration: BoxDecoration(
                    color: isSelected
                        ? colorScheme.primary.withValues(alpha: 0.12)
                        : Colors.transparent,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        icon,
                        size: 22,
                        color: isSelected
                            ? colorScheme.primary
                            : colorScheme.onSurfaceVariant,
                      ),
                      const SizedBox(height: 4),
                      Text(
                        label,
                        style: textTheme.labelSmall?.copyWith(
                          color: isSelected
                              ? colorScheme.primary
                              : colorScheme.onSurfaceVariant,
                          fontWeight:
                              isSelected ? FontWeight.w600 : FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            );
          }).toList(),
        ),
      ),
    );
  }

  Widget _buildFontStyleSelector(ColorScheme colorScheme, TextTheme textTheme) {
    final currentFont = ref.watch(fontStyleProvider);
    const options = [
      (FontStyle.classic, 'Classic', 'Serif'),
      (FontStyle.modern, 'Modern', 'Sans'),
    ];

    return Material(
      color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Row(
          children: options.map((entry) {
            final (style, label, subtitle) = entry;
            final isSelected = currentFont == style;
            return Expanded(
              child: GestureDetector(
                onTap: () => ref.read(fontStyleProvider.notifier).setFontStyle(style),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 8),
                  decoration: BoxDecoration(
                    color: isSelected
                        ? colorScheme.primary.withValues(alpha: 0.12)
                        : Colors.transparent,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        style == FontStyle.classic
                            ? Icons.font_download_outlined
                            : Icons.text_fields,
                        size: 22,
                        color: isSelected
                            ? colorScheme.primary
                            : colorScheme.onSurfaceVariant,
                      ),
                      const SizedBox(height: 4),
                      Text(
                        label,
                        style: textTheme.labelSmall?.copyWith(
                          color: isSelected
                              ? colorScheme.primary
                              : colorScheme.onSurfaceVariant,
                          fontWeight:
                              isSelected ? FontWeight.w600 : FontWeight.w500,
                        ),
                      ),
                      Text(
                        subtitle,
                        style: textTheme.labelSmall?.copyWith(
                          fontSize: 10,
                          color: isSelected
                              ? colorScheme.primary.withValues(alpha: 0.7)
                              : colorScheme.onSurfaceVariant.withValues(alpha: 0.7),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            );
          }).toList(),
        ),
      ),
    );
  }

  Widget _buildAvatar(ColorScheme colorScheme) {
    if (_picture != null && _picture!.isNotEmpty) {
      return CachedNetworkImage(
        imageUrl: _picture!,
        imageBuilder: (context, imageProvider) => CircleAvatar(
          radius: 48,
          backgroundImage: imageProvider,
        ),
        placeholder: (context, url) => CircleAvatar(
          radius: 48,
          backgroundColor: colorScheme.primaryContainer,
          child: Icon(
            Icons.person,
            size: 48,
            color: colorScheme.onPrimaryContainer,
          ),
        ),
        errorWidget: (context, url, error) => CircleAvatar(
          radius: 48,
          backgroundColor: colorScheme.primaryContainer,
          child: Icon(
            Icons.person,
            size: 48,
            color: colorScheme.onPrimaryContainer,
          ),
        ),
      );
    }

    return CircleAvatar(
      radius: 48,
      backgroundColor: colorScheme.primaryContainer,
      child: Icon(
        Icons.person,
        size: 48,
        color: colorScheme.onPrimaryContainer,
      ),
    );
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

  Widget _buildProfileTile({
    required IconData icon,
    required String label,
    required String value,
    required VoidCallback onTap,
    required ColorScheme colorScheme,
    required TextTheme textTheme,
    Color? valueColor,
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
                    Text(
                      value,
                      style: textTheme.bodyLarge?.copyWith(
                        color: valueColor,
                      ),
                    ),
                  ],
                ),
              ),
              Icon(
                Icons.chevron_right,
                color: colorScheme.onSurfaceVariant,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
