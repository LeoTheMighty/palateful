import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../core/services/error_reporter.dart';
import '../../core/router/app_router.dart';
import '../../core/services/auth_service.dart';
import '../../shared/widgets/buttons.dart';
import '../../shared/widgets/error_banner.dart';
import '../recipes/add_recipe/add_recipe_sheet.dart';

/// Start method selection for recipe book population.
class OnboardingStartScreen extends StatefulWidget {
  final String name;

  const OnboardingStartScreen({
    super.key,
    required this.name,
  });

  @override
  State<OnboardingStartScreen> createState() => _OnboardingStartScreenState();
}

class _OnboardingStartScreenState extends State<OnboardingStartScreen> {
  final _apiClient = getIt<ApiClient>();
  final _authService = getIt<AuthService>();
  bool _isLoading = false;
  String? _error;
  String? _errorDetail;

  /// Escape hatch for users stuck on a bad token: logout clears
  /// credentials and the router's refreshListenable redirects to /login.
  Future<void> _signOutAndReturnToLogin() async {
    await _authService.logout();
  }

  Future<void> _selectStartMethod(String method) async {
    setState(() {
      _isLoading = true;
      _error = null;
      _errorDetail = null;
    });

    try {
      final response = await _apiClient.completeOnboarding(
        name: widget.name,
        startMethod: method,
      );

      if (!mounted) return;

      if (response.statusCode == 200) {
        final data = response.data;
        // Update auth service with onboarding state and default recipe book ID
        // Fall back to user's existing default if recipe_book is null (double-completion guard)
        _authService.updateOnboardingState(
          hasCompletedOnboarding: true,
          defaultRecipeBookId: data?['recipe_book']?['id'] ??
              data?['user']?['default_recipe_book_id'],
        );

        // Claim any pending email invitations (best-effort, ignore errors)
        try {
          await _apiClient.claimInvitations();
        } catch (_) {}

        if (!mounted) return;
        setState(() {
          _isLoading = false;
        });
        context.go('/');
        if (method == 'import') {
          WidgetsBinding.instance.addPostFrameCallback((_) {
            final ctx = rootNavigatorKey.currentContext;
            if (ctx != null) {
              showModalBottomSheet(
                context: ctx,
                isScrollControlled: true,
                backgroundColor: Colors.transparent,
                builder: (_) => const AddRecipeSheet(),
              );
            }
          });
        }
      } else {
        setState(() {
          _error = 'Failed to complete setup. Please try again.';
          _isLoading = false;
        });
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = 'An error occurred. Please try again.';
        _errorDetail = ErrorReporter.detail(e);
        _isLoading = false;
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
              Text(
                'How would you like to start?',
                style: textTheme.headlineMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: colorScheme.onSurface,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 8),
              Text(
                "We'll create your personal recipe book",
                style: textTheme.bodyLarge?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 32),
              if (_error != null) ...[
                ErrorBanner(message: _error!, detail: _errorDetail),
                const SizedBox(height: 12),
                OutlinedButton.icon(
                  onPressed: _signOutAndReturnToLogin,
                  icon: const Icon(Icons.logout, size: 18),
                  label: const Text('Back to sign in'),
                ),
                const SizedBox(height: 16),
              ],
              if (_isLoading)
                Center(
                  child: Padding(
                    padding: const EdgeInsets.all(48),
                    child: CircularProgressIndicator(color: colorScheme.primary),
                  ),
                )
              else ...[
                _StartMethodCard(
                  icon: Icons.explore,
                  title: 'Browse Public Recipes',
                  description: 'Discover recipes from the community and save your favorites',
                  onTap: () => _selectStartMethod('browse'),
                ),
                const SizedBox(height: 16),
                _StartMethodCard(
                  icon: Icons.upload_file,
                  title: 'Import From Existing Source',
                  description: 'Bring in recipes from websites, files, or other apps',
                  onTap: () => _selectStartMethod('import'),
                ),
                const SizedBox(height: 16),
                _StartMethodCard(
                  icon: Icons.edit_note,
                  title: 'Start from Scratch',
                  description: 'Add your own recipes manually, one at a time',
                  onTap: () => _selectStartMethod('scratch'),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _StartMethodCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final String description;
  final VoidCallback onTap;

  const _StartMethodCard({
    required this.icon,
    required this.title,
    required this.description,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return ScaleTapButton(
      onPressed: () {
        HapticFeedback.selectionClick();
        onTap();
      },
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: colorScheme.surfaceContainerLow,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: colorScheme.outlineVariant),
        ),
        child: Row(
          children: [
            Container(
              width: 56,
              height: 56,
              decoration: BoxDecoration(
                color: colorScheme.primaryContainer,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(
                icon,
                size: 28,
                color: colorScheme.primary,
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                      color: colorScheme.onSurface,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    description,
                    style: textTheme.bodyMedium?.copyWith(
                      color: colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
            Icon(
              Icons.chevron_right,
              color: colorScheme.outline,
            ),
          ],
        ),
      ),
    );
  }
}
