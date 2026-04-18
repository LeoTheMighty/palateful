import 'dart:async';

import 'package:flutter/foundation.dart';

import 'package:palateful/core/constants/ingredient_units.dart';
import 'package:palateful/core/services/api_client.dart';

/// Async-fetch hook for the live alias map. Implemented in production by
/// `ApiClient.getUnitAliases`; tests pass their own.
typedef AliasMapFetcher = Future<Map<String, dynamic>?> Function();

Future<Map<String, dynamic>?> _defaultFetcher(ApiClient client) async {
  final response = await client.getUnitAliases();
  final body = response.data as Map<String, dynamic>?;
  // The Endpoint base wraps payloads in {"data": {...}, "success": true,
  // ...}. Some legacy clients/tests return the raw body — handle both.
  return (body?['data'] as Map<String, dynamic>?) ?? body;
}

/// Session-scoped alias → canonical-unit map for the `UnitInput` coerce-on-blur
/// path (riip-5).
///
/// Seeded *synchronously* with the hardcoded fallback map (so a user typing
/// "tablespoon" before the network fetch lands still gets coerced to "tbsp"),
/// then replaced with the live server-side seed when
/// `GET /v1/units/aliases` returns.
///
/// `coerce()` is the single public entry point used by the widget. It is
/// synchronous by design — `_coerceUnit` in the widget runs on focus-loss
/// and on the space keystroke, both of which need an immediate answer.
class SessionAliasMap extends ChangeNotifier {
  SessionAliasMap(ApiClient apiClient)
      : _fetcher = (() => _defaultFetcher(apiClient));

  /// Test seam — let tests inject a fetcher without an ApiClient.
  @visibleForTesting
  SessionAliasMap.withFetcher(AliasMapFetcher fetcher) : _fetcher = fetcher;

  final AliasMapFetcher _fetcher;

  // Defaults to the hardcoded fallback. `init()` swaps in the live seed.
  Map<String, String> _aliases = Map<String, String>.from(kFallbackUnitAliases);
  Set<String> _canonical = kCuratedUnits.toSet();
  bool _initialized = false;

  /// Public read-only view of the current alias map. Lower-cased keys.
  Map<String, String> get aliases => Map<String, String>.unmodifiable(_aliases);

  /// Canonical token set (`units.name`). Lower-cased.
  Set<String> get canonical => Set<String>.unmodifiable(_canonical);

  /// True once the live server fetch has populated the map. The widget
  /// can fall back to the hardcoded seed regardless; this is mainly for
  /// telemetry.
  bool get isInitialized => _initialized;

  /// Coerce a typed unit string to its canonical token, or return the
  /// trimmed/lowercased input on miss. Mirrors the backend
  /// `normalize_unit_display` rules (riip-1) so the client and server
  /// converge on the same canonical token without a round trip.
  ///
  /// - `null` / empty / whitespace → null (nothing to coerce).
  /// - Trim, lowercase, strip trailing `.,;`.
  /// - Already canonical → return as-is.
  /// - Alias hit → return canonical.
  /// - Miss → return the normalized input (caller can keep the raw if it
  ///   prefers — but persisting the normalized form keeps history clean).
  String? coerce(String? raw) {
    if (raw == null) return null;
    final trimmed = raw.trim();
    if (trimmed.isEmpty) return raw;
    var normalized = trimmed.toLowerCase();
    normalized = normalized.replaceAll(RegExp(r'[.,;]+$'), '');
    if (normalized.isEmpty) return raw;
    if (_canonical.contains(normalized)) return normalized;
    final hit = _aliases[normalized];
    if (hit != null) return hit;
    return normalized;
  }

  /// Best-effort live fetch of the alias map. Failures fall back silently
  /// to the hardcoded seed already loaded; logged at debug only because
  /// the user-visible behavior is identical.
  Future<void> init() async {
    if (_initialized) return;
    try {
      final payload = await _fetcher();
      if (payload == null) return;

      final liveAliases = (payload['aliases'] as Map?)?.map(
        (k, v) => MapEntry(k.toString().toLowerCase(), v.toString()),
      );
      final liveCanonical = (payload['canonical'] as List?)
          ?.map((e) => e.toString().toLowerCase())
          .toSet();

      if (liveAliases != null) _aliases = liveAliases;
      if (liveCanonical != null) _canonical = liveCanonical;
      _initialized = true;
      notifyListeners();
    } catch (_) {
      // Stay on the hardcoded seed — coerce() still works.
    }
  }
}
