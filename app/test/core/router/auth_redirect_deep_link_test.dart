import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/router/app_router.dart';

/// Web deep links and refreshes used to land on Home.
///
/// Two independent measurements (0e, 2026-09-25) with the app opened at
/// `/activity?tab=notifications` and `/pantry`: the console showed
/// `onLoad` receiving the right URL, then
/// `Router redirect: location=/login … → nav.push /`. The router was
/// constructed with `initialLocation: '/login'`, so it started there
/// instead of adopting the browser URL, and the "authenticated and
/// onboarded but on the login page" rule forwarded to `/`. **`/` was not a
/// fallback — it was the only reachable entry point on a cold load.**
///
/// User-visible: refresh anywhere but Home returns you Home, bookmarks
/// don't work, shared in-app links don't work, Back into a route reloads
/// to Home.
///
/// These tests drive `resolveAuthRedirect` rather than a widget tree,
/// which is why it was extracted: as a closure inside `GoRouter`, none of
/// these branches could be asserted without booting the app, and the
/// deep-link case shipped broken because nothing checked it cheaply.
void main() {
  setUp(resetRouter); // clears the static pending link between cases

  String? redirect({
    required String location,
    String? fullUri,
    bool authed = true,
    bool onboarded = true,
    bool admin = false,
  }) =>
      resolveAuthRedirect(
        location: location,
        fullUri: fullUri ?? location,
        isAuthenticated: authed,
        hasCompletedOnboarding: onboarded,
        isAdmin: admin,
      );

  group('an authenticated user keeps the route they asked for', () {
    test('a deep link is not redirected at all', () {
      expect(redirect(location: '/pantry'), isNull);
      expect(
        redirect(location: '/activity', fullUri: '/activity?tab=notifications'),
        isNull,
        reason: 'this is the exact URL 0e measured landing on Home',
      );
    });

    test('Home itself still needs no redirect', () {
      expect(redirect(location: '/'), isNull);
    });
  });

  group('an unauthenticated deep link survives the login round trip', () {
    test('it goes to login, then back to the requested route', () {
      expect(
        redirect(
            location: '/activity',
            fullUri: '/activity?tab=notifications',
            authed: false),
        '/login',
      );
      // ...user signs in; the router re-evaluates on the login page.
      expect(
        redirect(location: '/login'),
        '/activity?tab=notifications',
        reason: 'sending them to / here is the bug in a second place — the '
            'route was remembered and then thrown away',
      );
    });

    test('the query string is preserved, not just the path', () {
      redirect(location: '/activity', fullUri: '/activity?tab=imports',
          authed: false);
      expect(redirect(location: '/login'), '/activity?tab=imports');
    });

    test('the pending link is consumed, not replayed', () {
      redirect(location: '/pantry', authed: false);
      expect(redirect(location: '/login'), '/pantry');
      // A later arrival at /login — a real logout, say — must go Home,
      // not back to a route from a previous session.
      expect(redirect(location: '/login'), '/');
    });

    test('it survives the onboarding detour too', () {
      expect(redirect(location: '/pantry', authed: false), '/login');
      expect(
        redirect(location: '/login', onboarded: false),
        '/onboarding/welcome',
      );
      expect(redirect(location: '/onboarding/welcome'), '/pantry');
    });
  });

  group('no redirect loops', () {
    test('login is not a pending destination for itself', () {
      // Nothing captured /login, but be explicit: if it ever did, the
      // "already onboarded" branch would return to /login forever.
      expect(redirect(location: '/login'), '/');
    });

    test('an onboarding page is not a pending destination', () {
      redirect(location: '/onboarding/notifications', authed: false);
      expect(redirect(location: '/login'), '/');
    });

    test('an unauthenticated user already on login stays put', () {
      expect(redirect(location: '/login', authed: false), isNull);
    });
  });

  group('the rules that must not regress', () {
    test('an unauthenticated user is sent to login', () {
      expect(redirect(location: '/pantry', authed: false), '/login');
    });

    test('public share pages are reachable without auth', () {
      expect(
        redirect(location: '/recipe-public/abc', authed: false),
        isNull,
        reason: 'a stranger tapping a share link must hit the screen',
      );
      expect(redirect(location: '/meal-public/abc', authed: false), isNull);
    });

    test('a public share page does not force onboarding', () {
      expect(
        redirect(location: '/recipe-public/abc', onboarded: false),
        isNull,
      );
    });

    test('an un-onboarded user goes to onboarding', () {
      expect(redirect(location: '/pantry', onboarded: false),
          '/onboarding/welcome');
    });

    test('a non-admin is kept out of /admin', () {
      expect(redirect(location: '/admin/users'), '/');
    });

    test('an admin reaches /admin', () {
      expect(redirect(location: '/admin/users', admin: true), isNull);
    });
  });

  test('resetRouter clears a pending link', () {
    redirect(location: '/pantry', authed: false);
    expect(pendingDeepLink, '/pantry');
    resetRouter();
    expect(pendingDeepLink, isNull,
        reason: 'a leftover pending link would redirect the next boot '
            'somewhere nobody asked for');
  });
}
