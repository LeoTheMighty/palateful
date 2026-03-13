import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/di/injection.dart';
import '../../core/services/auth_service.dart';
import '../../core/services/api_client.dart';

/// Placeholder screen for the Profile tab.
/// Will be expanded with full user profile management in Story 1.3.
class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Profile')),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.person_outline, size: 64),
            const SizedBox(height: 16),
            const Text('Profile coming soon'),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: () async {
                final authService = getIt<AuthService>();
                final apiClient = getIt<ApiClient>();
                await authService.logout();
                apiClient.clearAuthToken();
                if (context.mounted) {
                  context.go('/login');
                }
              },
              icon: const Icon(Icons.logout),
              label: const Text('Logout'),
            ),
          ],
        ),
      ),
    );
  }
}
