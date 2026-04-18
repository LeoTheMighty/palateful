import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../core/services/auth_service.dart';
import '../../shared/widgets/buttons.dart';
import '../../core/services/error_reporter.dart';
import '../../shared/widgets/error_banner.dart';

/// Onboarding welcome screen where users confirm their name.
class OnboardingWelcomeScreen extends StatefulWidget {
  const OnboardingWelcomeScreen({super.key});

  @override
  State<OnboardingWelcomeScreen> createState() => _OnboardingWelcomeScreenState();
}

class _OnboardingWelcomeScreenState extends State<OnboardingWelcomeScreen> {
  final _apiClient = getIt<ApiClient>();
  final _authService = getIt<AuthService>();
  final _nameController = TextEditingController();
  bool _isLoading = true;
  String? _error;
  String? _errorDetail;

  @override
  void initState() {
    super.initState();
    _loadUserData();
  }

  Future<void> _loadUserData() async {
    try {
      final response = await _apiClient.getMe();
      if (!mounted) return;
      final userData = response.data;

      // Check if user already completed onboarding (stale state from startup)
      if (userData['has_completed_onboarding'] == true) {
        _authService.updateOnboardingState(
          hasCompletedOnboarding: true,
          defaultRecipeBookId: userData['default_recipe_book_id'],
        );
        setState(() {
          _isLoading = false;
        });
        // Router redirect will take us home
        return;
      }

      // Pre-fill with OAuth-obtained name
      if (userData['name'] != null) {
        _nameController.text = userData['name'];
      }

      setState(() {
        _isLoading = false;
      });
    } catch (e) {
      debugPrint('OnboardingWelcomeScreen._loadUserData error: $e');
      if (!mounted) return;
      setState(() {
        _error = 'Failed to load user data. Please try again.';
        _errorDetail = ErrorReporter.detail(e);
        _isLoading = false;
      });
    }
  }

  void _continue() {
    final name = _nameController.text.trim();
    if (name.isEmpty) {
      setState(() {
        _error = 'Please enter your name';
      });
      return;
    }

    // Notification-permission step runs before start-method selection;
    // it forwards the name + recorded permission status.
    context.push('/onboarding/notifications', extra: {'name': name});
  }

  /// Escape hatch for users stuck on a bad token (e.g. Auth0 issuer
  /// mismatch): logout clears credentials and the router's
  /// `refreshListenable` on AuthService redirects to `/login`.
  Future<void> _signOutAndReturnToLogin() async {
    await _authService.logout();
  }

  Future<void> _retryLoad() async {
    setState(() {
      _error = null;
      _errorDetail = null;
      _isLoading = true;
    });
    await _loadUserData();
  }

  @override
  void dispose() {
    _nameController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    if (_isLoading) {
      return Scaffold(
        body: Center(
          child: CircularProgressIndicator(color: colorScheme.primary),
        ),
      );
    }

    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 48),
              Icon(
                Icons.restaurant_menu,
                size: 80,
                color: colorScheme.primary,
              ),
              const SizedBox(height: 24),
              Text(
                'Welcome to Palateful!',
                style: textTheme.headlineLarge?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: colorScheme.onSurface,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 8),
              Text(
                'Your recipes, all in one place',
                style: textTheme.bodyLarge?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 32),
              // Feature highlight cards
              _FeatureCard(
                icon: Icons.upload_file,
                title: 'Import',
                description: 'Bring recipes from anywhere — URLs, photos, or files',
              ),
              const SizedBox(height: 12),
              _FeatureCard(
                icon: Icons.menu_book,
                title: 'Organize',
                description: 'Recipe books keep your collection sorted your way',
              ),
              const SizedBox(height: 12),
              _FeatureCard(
                icon: Icons.restaurant,
                title: 'Cook',
                description: 'Hands-free cooking mode with step-by-step guidance',
              ),
              const SizedBox(height: 32),
              if (_error != null) ...[
                ErrorBanner(message: _error!, detail: _errorDetail),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: _retryLoad,
                        icon: const Icon(Icons.refresh, size: 18),
                        label: const Text('Try again'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: _signOutAndReturnToLogin,
                        icon: const Icon(Icons.logout, size: 18),
                        label: const Text('Back to sign in'),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
              ],
              Text(
                'What should we call you?',
                style: textTheme.titleMedium?.copyWith(
                  color: colorScheme.onSurface,
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _nameController,
                decoration: const InputDecoration(
                  labelText: 'Your Name',
                  hintText: 'Enter your name',
                ),
                textCapitalization: TextCapitalization.words,
                onChanged: (_) {
                  if (_error != null) {
                    setState(() {
                      _error = null;
                    });
                  }
                },
                onSubmitted: (_) => _continue(),
              ),
              const SizedBox(height: 32),
              PrimaryButton(
                label: 'Continue',
                onPressed: _continue,
                isExpanded: true,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _FeatureCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final String description;

  const _FeatureCard({
    required this.icon,
    required this.title,
    required this.description,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: colorScheme.primaryContainer,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(
              icon,
              size: 22,
              color: colorScheme.primary,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w600,
                    color: colorScheme.onSurface,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  description,
                  style: textTheme.bodySmall?.copyWith(
                    color: colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
