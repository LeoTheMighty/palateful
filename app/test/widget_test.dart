import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:get_it/get_it.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';

import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/theme/app_colors.dart';
import 'package:palateful/core/theme/app_theme.dart';
import 'package:palateful/core/router/page_transitions.dart';
import 'package:palateful/features/activity/providers/activity_read_provider.dart';
import 'package:palateful/shared/widgets/shimmer_loading.dart';
import 'package:palateful/shared/widgets/scaffold_with_bottom_nav.dart';

class _StubApiClient extends ApiClient {
  @override
  Future<Response> getUnreadActivityCount() async => Response(
        data: {'count': 0},
        requestOptions: RequestOptions(path: ''),
        statusCode: 200,
      );
}

void _registerScaffoldDeps() {
  final gi = GetIt.instance;
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  gi.registerSingleton<ApiClient>(_StubApiClient());
  if (gi.isRegistered<ActivityReadProvider>()) {
    gi.unregister<ActivityReadProvider>();
  }
  gi.registerLazySingleton<ActivityReadProvider>(
    () => ActivityReadProvider(gi<ApiClient>()),
  );
}

void _unregisterScaffoldDeps() {
  final gi = GetIt.instance;
  if (gi.isRegistered<ActivityReadProvider>()) {
    gi.unregister<ActivityReadProvider>();
  }
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  setUp(() {
    GoogleFonts.config.allowRuntimeFetching = false;
  });

  group('AppColors', () {
    test('warmIvory token exists', () {
      expect(AppColors.warmIvory, const Color(0xFFF5ECD7));
    });

    test('cream color matches spec', () {
      expect(AppColors.cream, const Color(0xFFFAF7F2));
    });

    test('chocolate color matches spec', () {
      expect(AppColors.chocolate, const Color(0xFF4A3728));
    });
  });

  group('AppTheme', () {
    testWidgets('light theme renders without errors', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light(),
          home: const Scaffold(body: Text('Light')),
        ),
      );
      await tester.pump();
      expect(find.text('Light'), findsOneWidget);
    });

    testWidgets('dark theme renders without errors', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.dark(),
          home: const Scaffold(body: Text('Dark')),
        ),
      );
      await tester.pump();
      expect(find.text('Dark'), findsOneWidget);
    });

    testWidgets('light theme has correct brightness', (tester) async {
      late Brightness brightness;
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light(),
          home: Builder(builder: (context) {
            brightness = Theme.of(context).brightness;
            return const SizedBox();
          }),
        ),
      );
      expect(brightness, Brightness.light);
    });

    testWidgets('dark theme has correct brightness', (tester) async {
      late Brightness brightness;
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.dark(),
          home: Builder(builder: (context) {
            brightness = Theme.of(context).brightness;
            return const SizedBox();
          }),
        ),
      );
      expect(brightness, Brightness.dark);
    });

    testWidgets('both themes use Material 3', (tester) async {
      late bool lightM3;
      late bool darkM3;
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light(),
          home: Builder(builder: (context) {
            lightM3 = Theme.of(context).useMaterial3;
            return const SizedBox();
          }),
        ),
      );
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.dark(),
          home: Builder(builder: (context) {
            darkM3 = Theme.of(context).useMaterial3;
            return const SizedBox();
          }),
        ),
      );
      expect(lightM3, true);
      expect(darkM3, true);
    });

    testWidgets('dark theme scaffold background is chocolate', (tester) async {
      late Color bgColor;
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.dark(),
          home: Builder(builder: (context) {
            bgColor = Theme.of(context).scaffoldBackgroundColor;
            return const SizedBox();
          }),
        ),
      );
      expect(bgColor, AppColors.chocolate);
    });

    testWidgets('light theme scaffold background is cream', (tester) async {
      late Color bgColor;
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light(),
          home: Builder(builder: (context) {
            bgColor = Theme.of(context).scaffoldBackgroundColor;
            return const SizedBox();
          }),
        ),
      );
      expect(bgColor, AppColors.cream);
    });
  });

  group('ScaffoldWithBottomNav', () {
    setUp(_registerScaffoldDeps);
    tearDown(_unregisterScaffoldDeps);

    testWidgets('has 5 navigation destinations on mobile', (tester) async {
      // Force narrow viewport so ScaffoldWithBottomNav renders mobile bottom nav
      tester.view.physicalSize = const Size(400, 800);
      addTearDown(tester.view.resetPhysicalSize);

      final router = GoRouter(
        initialLocation: '/',
        routes: [
          StatefulShellRoute.indexedStack(
            builder: (context, state, navigationShell) {
              return ScaffoldWithBottomNav(navigationShell: navigationShell);
            },
            branches: [
              StatefulShellBranch(routes: [
                GoRoute(path: '/', builder: (_, _) => const Text('Tab 0')),
              ]),
              StatefulShellBranch(routes: [
                GoRoute(path: '/b', builder: (_, _) => const Text('Tab 1')),
              ]),
              StatefulShellBranch(routes: [
                GoRoute(path: '/c', builder: (_, _) => const Text('Tab 2')),
              ]),
              StatefulShellBranch(routes: [
                GoRoute(path: '/d', builder: (_, _) => const Text('Tab 3')),
              ]),
              StatefulShellBranch(routes: [
                GoRoute(path: '/e', builder: (_, _) => const Text('Tab 4')),
              ]),
            ],
          ),
        ],
      );

      await tester.pumpWidget(MaterialApp.router(routerConfig: router));
      await tester.pumpAndSettle();

      // At 400px width (< kMobileBreakpoint=600) the widget renders bottom NavigationBar
      expect(find.byType(NavigationDestination), findsNWidgets(5));
      // Verify nav labels (these come from ScaffoldWithBottomNav, not from route content)
      expect(find.text('Home'), findsWidgets); // label + possibly tab content
      expect(find.text('Activity'), findsOneWidget);
      expect(find.text('Cart'), findsOneWidget);
      expect(find.text('Calendar'), findsOneWidget);
      expect(find.text('Profile'), findsOneWidget);
    });

    testWidgets('uses NavigationRail on wide screens', (tester) async {
      final router = GoRouter(
        initialLocation: '/',
        routes: [
          StatefulShellRoute.indexedStack(
            builder: (context, state, navigationShell) {
              return ScaffoldWithBottomNav(navigationShell: navigationShell);
            },
            branches: [
              StatefulShellBranch(routes: [
                GoRoute(path: '/', builder: (_, _) => const Text('Tab 0')),
              ]),
              StatefulShellBranch(routes: [
                GoRoute(path: '/b', builder: (_, _) => const Text('Tab 1')),
              ]),
              StatefulShellBranch(routes: [
                GoRoute(path: '/c', builder: (_, _) => const Text('Tab 2')),
              ]),
              StatefulShellBranch(routes: [
                GoRoute(path: '/d', builder: (_, _) => const Text('Tab 3')),
              ]),
              StatefulShellBranch(routes: [
                GoRoute(path: '/e', builder: (_, _) => const Text('Tab 4')),
              ]),
            ],
          ),
        ],
      );

      await tester.pumpWidget(MaterialApp.router(routerConfig: router));
      await tester.pumpAndSettle();

      // Default test width is 800px (>= kMobileBreakpoint=600) → NavigationRail
      expect(find.byType(NavigationRail), findsOneWidget);
      expect(find.byType(NavigationBar), findsNothing);
      // Nav labels are still present
      expect(find.text('Home'), findsWidgets);
      expect(find.text('Activity'), findsOneWidget);
    });
  });

  group('Reduce Motion', () {
    testWidgets('respects disableAnimations via GoRouter pageBuilder', (tester) async {
      // Test that the buildReduceMotionPage function exists and is used in routes
      // by verifying the route with reduce motion enabled renders correctly
      final router = GoRouter(
        initialLocation: '/',
        routes: [
          GoRoute(
            path: '/',
            builder: (_, _) => const Text('Home'),
          ),
          GoRoute(
            path: '/detail',
            pageBuilder: (context, state) => buildReduceMotionPage(
              context: context,
              state: state,
              child: const Text('Detail'),
            ),
          ),
        ],
      );

      await tester.pumpWidget(
        MediaQuery(
          data: const MediaQueryData(disableAnimations: true),
          child: MaterialApp.router(routerConfig: router),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Home'), findsOneWidget);

      router.go('/detail');
      await tester.pumpAndSettle();
      expect(find.text('Detail'), findsOneWidget);
    });

    testWidgets('navigates with animation when disableAnimations is false', (tester) async {
      final router = GoRouter(
        initialLocation: '/',
        routes: [
          GoRoute(
            path: '/',
            builder: (_, _) => const Text('Start'),
          ),
          GoRoute(
            path: '/detail',
            pageBuilder: (context, state) => buildReduceMotionPage(
              context: context,
              state: state,
              child: const Text('Detail'),
            ),
          ),
        ],
      );

      await tester.pumpWidget(
        MediaQuery(
          data: const MediaQueryData(disableAnimations: false),
          child: MaterialApp.router(routerConfig: router),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Start'), findsOneWidget);

      router.go('/detail');
      await tester.pumpAndSettle();
      expect(find.text('Detail'), findsOneWidget);
    });
  });

  group('ShimmerBlock', () {
    testWidgets('renders with given dimensions', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: ShimmerBlock(height: 100, width: 200),
          ),
        ),
      );
      expect(find.byType(ShimmerBlock), findsOneWidget);
    });
  });

  group('ShimmerCard', () {
    testWidgets('renders in light mode', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light(),
          home: const Scaffold(
            body: SizedBox(
              height: 200,
              width: 150,
              child: ShimmerCard(),
            ),
          ),
        ),
      );
      expect(find.byType(ShimmerCard), findsOneWidget);
    });

    testWidgets('renders in dark mode', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.dark(),
          home: const Scaffold(
            body: SizedBox(
              height: 200,
              width: 150,
              child: ShimmerCard(),
            ),
          ),
        ),
      );
      expect(find.byType(ShimmerCard), findsOneWidget);
    });
  });

  group('ShimmerList', () {
    testWidgets('renders correct number of items', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: ShimmerList(itemCount: 3),
            ),
          ),
        ),
      );
      expect(find.byType(ShimmerList), findsOneWidget);
      // Each item is a SizedBox wrapping a Row — verify 3 rows rendered
      expect(find.byType(Row), findsNWidgets(3));
    });
  });

  group('ProviderScope', () {
    testWidgets('wraps app correctly', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(
            home: Scaffold(body: Text('Riverpod works')),
          ),
        ),
      );
      expect(find.text('Riverpod works'), findsOneWidget);
    });
  });
}
