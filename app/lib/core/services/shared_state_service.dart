import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:home_widget/home_widget.dart';

import 'error_reporter.dart';

/// Bridges auth + recipe-book state from Flutter into the iOS App Group so
/// the PalatefulShare extension can read it without round-tripping through
/// the main app. Writes are debounced 250 ms and failures log but never
/// block the caller — the share sheet falls back to a sign-in prompt if any
/// field is missing.
///
/// Key layout (UserDefaults in `group.com.palateful.app`, matching
/// `SharedStateKey` in PalatefulShare/SharedState.swift):
///
///   share_auth_jwt                    (String)
///   share_auth_jwt_expires_at         (double — ms since epoch)
///   share_user_id                     (String)
///   share_api_base_url                (String)
///   share_recipe_books                (String — JSON-encoded list)
///   share_last_used_book_id           (String?)
class SharedStateService {
  static const _appGroupId = 'group.com.palateful.app';
  static const _maxBooks = 50; // matches sie-3 AC cap
  static const _debounce = Duration(milliseconds: 250);

  bool _initialized = false;
  Timer? _debounceTimer;
  _PendingSync _pending = const _PendingSync();

  /// Initialize the bridge. Safe to call multiple times. iOS-only —
  /// App Groups + the share extension are an iOS feature; off-platform,
  /// home_widget throws MissingPluginException.
  Future<void> initialize() async {
    if (_initialized) return;
    if (kIsWeb || defaultTargetPlatform != TargetPlatform.iOS) return;
    try {
      await HomeWidget.setAppGroupId(_appGroupId);
      _initialized = true;
    } catch (e, st) {
      ErrorReporter.report(e, st, area: 'share_extension', operation: 'shared_state_init');
    }
  }

  /// Queue an auth sync. Safe to call repeatedly — writes are debounced.
  /// Pass `authJwt == null` to clear all auth fields (logout path).
  void syncAuth({
    required String? authJwt,
    required DateTime? authJwtExpiresAt,
    required String? userId,
    required String apiBaseUrl,
    String? lastUsedBookId,
  }) {
    _pending = _pending.copyWith(
      authJwt: authJwt,
      authJwtExpiresAt: authJwtExpiresAt,
      userId: userId,
      apiBaseUrl: apiBaseUrl,
      lastUsedBookId: lastUsedBookId,
      authTouched: true,
      lastUsedBookIdTouched: lastUsedBookId != null,
    );
    _scheduleFlush();
  }

  /// Queue a books sync. Caps the list at 50 entries (alphabetical +
  /// last-used-first is the caller's responsibility; this method only bounds
  /// storage). Archived books are kept so the share sheet can de-dupe by id.
  void syncRecipeBooks(List<SharedRecipeBook> books) {
    final bounded = books.length > _maxBooks
        ? books.sublist(0, _maxBooks)
        : books;
    _pending = _pending.copyWith(
      recipeBooks: bounded,
      recipeBooksTouched: true,
    );
    _scheduleFlush();
  }

  /// Clear everything — called on logout.
  void clear() {
    _debounceTimer?.cancel();
    _debounceTimer = null;
    _pending = const _PendingSync();
    // Fire immediately — logout should not leave stale auth in App Group.
    unawaited(_writeClear());
  }

  /// Force-flush any pending debounced writes. Useful in tests.
  Future<void> flushPending() async {
    _debounceTimer?.cancel();
    _debounceTimer = null;
    await _flush();
  }

  void _scheduleFlush() {
    _debounceTimer?.cancel();
    _debounceTimer = Timer(_debounce, () {
      unawaited(_flush());
    });
  }

  Future<void> _flush() async {
    if (!_initialized) {
      await initialize();
      if (!_initialized) return;
    }
    final p = _pending;
    _pending = const _PendingSync();

    try {
      if (p.authTouched) {
        await HomeWidget.saveWidgetData('share_auth_jwt', p.authJwt ?? '');
        await HomeWidget.saveWidgetData<double>(
          'share_auth_jwt_expires_at',
          p.authJwtExpiresAt?.millisecondsSinceEpoch.toDouble() ?? 0.0,
        );
        await HomeWidget.saveWidgetData('share_user_id', p.userId ?? '');
        await HomeWidget.saveWidgetData('share_api_base_url', p.apiBaseUrl ?? '');
      }
      if (p.lastUsedBookIdTouched) {
        await HomeWidget.saveWidgetData(
          'share_last_used_book_id',
          p.lastUsedBookId ?? '',
        );
      }
      if (p.recipeBooksTouched) {
        final encoded = jsonEncode(p.recipeBooks?.map((b) => b.toJson()).toList() ?? []);
        await HomeWidget.saveWidgetData('share_recipe_books', encoded);
      }
    } catch (e, st) {
      ErrorReporter.report(e, st, area: 'share_extension', operation: 'shared_state_flush');
      debugPrint('SharedStateService flush error: $e');
    }
  }

  Future<void> _writeClear() async {
    if (!_initialized) {
      await initialize();
      if (!_initialized) return;
    }
    try {
      await HomeWidget.saveWidgetData('share_auth_jwt', '');
      await HomeWidget.saveWidgetData<double>('share_auth_jwt_expires_at', 0.0);
      await HomeWidget.saveWidgetData('share_user_id', '');
      await HomeWidget.saveWidgetData('share_api_base_url', '');
      await HomeWidget.saveWidgetData('share_recipe_books', '[]');
      await HomeWidget.saveWidgetData('share_last_used_book_id', '');
    } catch (e, st) {
      ErrorReporter.report(e, st, area: 'share_extension', operation: 'shared_state_clear');
    }
  }
}

/// A recipe book entry as seen by the Share Extension. Matches the Swift
/// `SharedRecipeBook` decoder — keep keys in sync.
class SharedRecipeBook {
  final String id;
  final String name;
  final bool isPersonal;
  final bool isArchived;

  const SharedRecipeBook({
    required this.id,
    required this.name,
    required this.isPersonal,
    required this.isArchived,
  });

  factory SharedRecipeBook.fromMap(Map<String, dynamic> map) => SharedRecipeBook(
        id: map['id'] as String,
        name: (map['name'] as String?) ?? '',
        isPersonal: (map['is_personal'] as bool?) ?? false,
        isArchived: (map['is_archived'] as bool?) ?? false,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'is_personal': isPersonal,
        'is_archived': isArchived,
      };
}

class _PendingSync {
  final String? authJwt;
  final DateTime? authJwtExpiresAt;
  final String? userId;
  final String? apiBaseUrl;
  final String? lastUsedBookId;
  final List<SharedRecipeBook>? recipeBooks;
  final bool authTouched;
  final bool lastUsedBookIdTouched;
  final bool recipeBooksTouched;

  const _PendingSync({
    this.authJwt,
    this.authJwtExpiresAt,
    this.userId,
    this.apiBaseUrl,
    this.lastUsedBookId,
    this.recipeBooks,
    this.authTouched = false,
    this.lastUsedBookIdTouched = false,
    this.recipeBooksTouched = false,
  });

  _PendingSync copyWith({
    String? authJwt,
    DateTime? authJwtExpiresAt,
    String? userId,
    String? apiBaseUrl,
    String? lastUsedBookId,
    List<SharedRecipeBook>? recipeBooks,
    bool? authTouched,
    bool? lastUsedBookIdTouched,
    bool? recipeBooksTouched,
  }) =>
      _PendingSync(
        authJwt: authJwt ?? this.authJwt,
        authJwtExpiresAt: authJwtExpiresAt ?? this.authJwtExpiresAt,
        userId: userId ?? this.userId,
        apiBaseUrl: apiBaseUrl ?? this.apiBaseUrl,
        lastUsedBookId: lastUsedBookId ?? this.lastUsedBookId,
        recipeBooks: recipeBooks ?? this.recipeBooks,
        authTouched: authTouched ?? this.authTouched,
        lastUsedBookIdTouched: lastUsedBookIdTouched ?? this.lastUsedBookIdTouched,
        recipeBooksTouched: recipeBooksTouched ?? this.recipeBooksTouched,
      );
}
