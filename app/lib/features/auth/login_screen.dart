import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/services/auth_service.dart';
import '../../core/services/api_client.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _authService = getIt<AuthService>();
  final _apiClient = getIt<ApiClient>();
  final _tokenController = TextEditingController();
  bool _isLoading = false;
  String? _error;
  bool _showTokenInput = false;

  @override
  void initState() {
    super.initState();
    if (_authService.isAuthenticated) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        final token = _authService.accessToken;
        if (token != null) {
          _apiClient.setAuthToken(token);
        }
        context.go('/');
      });
    }
  }

  Future<void> _loginWith({String? connection}) async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final success = await _authService.login(connection: connection);

      if (kIsWeb) {
        // Keep loading - page will redirect
        return;
      }

      if (!mounted) return;

      if (success) {
        final token = _authService.accessToken;
        if (token != null) {
          _apiClient.setAuthService(_authService);
          _apiClient.setAuthToken(token);
          await _fetchUserAndCheckOnboarding();
        }
        if (!mounted) return;
        setState(() => _isLoading = false);
        context.go('/');
      } else {
        setState(() {
          _error = 'Login failed. Please try again.';
          _isLoading = false;
        });
      }
    } catch (e) {
      if (!mounted) return;

      final errorMsg = e.toString().toLowerCase();
      final isAccountLinked = errorMsg.contains('account has been linked') ||
          errorMsg.contains('accounts have been linked');

      setState(() {
        _error = isAccountLinked
            ? 'Your accounts have been linked! Please sign in again.'
            : 'An error occurred: $e';
        _isLoading = false;
      });
    }
  }

  Future<void> _fetchUserAndCheckOnboarding() async {
    try {
      final response = await _apiClient.getMe();
      if (response.statusCode == 200) {
        final userData = response.data;
        _authService.updateOnboardingState(
          hasCompletedOnboarding: userData['has_completed_onboarding'] ?? false,
          defaultRecipeBookId: userData['default_recipe_book_id'],
        );
      }
    } catch (e) {
      debugPrint('Failed to fetch user data: $e');
    }
  }

  Future<void> _loginWithToken() async {
    final token = _tokenController.text.trim();
    if (token.isEmpty) {
      setState(() {
        _error = 'Please enter a valid token';
      });
      return;
    }

    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      _authService.setAccessToken(token);
      _apiClient.setAuthToken(token);
      await _fetchUserAndCheckOnboarding();

      if (!mounted) return;
      setState(() => _isLoading = false);
      context.go('/');
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'An error occurred: $e';
          _isLoading = false;
        });
      }
    }
  }

  @override
  void dispose() {
    _tokenController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 60),
              Icon(
                Icons.restaurant_menu,
                size: 80,
                color: colorScheme.primary,
              ),
              const SizedBox(height: 24),
              Text(
                'Palateful',
                style: textTheme.headlineLarge?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 8),
              Text(
                'Your personal recipe book',
                style: textTheme.bodyLarge?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 48),
              if (_error != null) ...[
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: colorScheme.errorContainer,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    _error!,
                    style: TextStyle(color: colorScheme.onErrorContainer),
                    textAlign: TextAlign.center,
                  ),
                ),
                const SizedBox(height: 16),
              ],
              if (!_showTokenInput) ...[
                // Google Sign-In Button
                _SocialSignInButton(
                  label: 'Sign in with Google',
                  iconWidget: const Text(
                    'G',
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.w700,
                      color: Color(0xFF4285F4),
                    ),
                  ),
                  onPressed: _isLoading ? null : () => _loginWith(connection: 'google-oauth2'),
                  backgroundColor: Colors.white,
                  foregroundColor: const Color(0xFF1F1F1F),
                  borderColor: const Color(0xFFDADCE0),
                ),
                const SizedBox(height: 12),

                // Apple Sign-In Button (iOS only)
                if (defaultTargetPlatform == TargetPlatform.iOS) ...[
                  _SocialSignInButton(
                    label: 'Sign in with Apple',
                    iconWidget: const Icon(Icons.apple, size: 24, color: Colors.white),
                    onPressed: _isLoading ? null : () => _loginWith(connection: 'apple'),
                    backgroundColor: Colors.black,
                    foregroundColor: Colors.white,
                  ),
                  const SizedBox(height: 12),
                ],

                // Loading indicator
                if (_isLoading)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 8),
                    child: Center(child: CircularProgressIndicator()),
                  ),

                const SizedBox(height: 8),

                // Other sign-in options
                TextButton(
                  onPressed: _isLoading ? null : () => _loginWith(),
                  child: Text(
                    'Other sign-in options',
                    style: TextStyle(color: colorScheme.onSurfaceVariant),
                  ),
                ),

                const SizedBox(height: 8),

                // Dev token input toggle
                TextButton(
                  onPressed: () {
                    setState(() {
                      _showTokenInput = true;
                    });
                  },
                  child: Text(
                    'Use access token instead (for testing)',
                    style: textTheme.bodySmall?.copyWith(
                      color: colorScheme.onSurfaceVariant,
                    ),
                  ),
                ),
              ],
              if (_showTokenInput) ...[
                Text(
                  'Enter Access Token',
                  style: textTheme.titleMedium,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                Text(
                  'Get a token from Auth0 Dashboard → APIs → Your API → Test tab',
                  style: textTheme.bodySmall?.copyWith(
                    color: colorScheme.onSurfaceVariant,
                  ),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: _tokenController,
                  decoration: const InputDecoration(
                    labelText: 'Access Token',
                    hintText: 'eyJ...',
                  ),
                  maxLines: 3,
                ),
                const SizedBox(height: 16),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: _isLoading ? null : _loginWithToken,
                    child: const Text('Continue with Token'),
                  ),
                ),
                const SizedBox(height: 8),
                TextButton(
                  onPressed: () {
                    setState(() {
                      _showTokenInput = false;
                      _error = null;
                    });
                  },
                  child: const Text('Back to sign in'),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// A branded social sign-in button following platform conventions.
class _SocialSignInButton extends StatelessWidget {
  final String label;
  final Widget iconWidget;
  final VoidCallback? onPressed;
  final Color backgroundColor;
  final Color foregroundColor;
  final Color? borderColor;

  const _SocialSignInButton({
    required this.label,
    required this.iconWidget,
    required this.onPressed,
    required this.backgroundColor,
    required this.foregroundColor,
    this.borderColor,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      height: 48,
      child: OutlinedButton.icon(
        onPressed: onPressed,
        icon: iconWidget,
        label: Text(
          label,
          style: TextStyle(
            color: foregroundColor,
            fontSize: 16,
            fontWeight: FontWeight.w500,
          ),
        ),
        style: OutlinedButton.styleFrom(
          backgroundColor: backgroundColor,
          side: BorderSide(color: borderColor ?? backgroundColor),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
    );
  }
}
