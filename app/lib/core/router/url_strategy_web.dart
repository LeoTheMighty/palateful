import 'package:flutter_web_plugins/url_strategy.dart';

/// Switch Flutter web from hash URLs to path URLs.
///
/// **Without this, the router only ever sees the fragment.** Flutter web
/// defaults to `HashUrlStrategy`, so `palateful.app/activity?tab=notifications`
/// (no `#`) resolves to `location=/` — the app lands on Home while the
/// address bar says otherwise. Measured on one bundle, one session,
/// sixty seconds apart, the `#` being the only difference:
///
///     uri=…/#/activity?tab=notifications  ->  location=/activity
///     uri=…/activity?tab=notifications    ->  location=/
///
/// Needs no server change: the path form already returns the app rather
/// than a 404 (verified against the deployed site).
///
/// Behind a conditional import because `flutter_web_plugins` is web-only
/// and importing it breaks mobile builds — same seam as
/// `auth_service_stub.dart` / `auth_service_web.dart`.
void useAppUrlStrategy() => usePathUrlStrategy();
