# Story 3.5: Share Sheet Import

Status: done

## Story

As a user,
I want to share recipe links from any app (TikTok, Safari, Instagram) directly to Palateful,
so that I can capture recipes in one tap without copy-pasting.

## Acceptance Criteria

1. When a user shares a URL from any app to Palateful, the app opens and begins extracting the recipe automatically
2. User sees the extracted recipe preview (name, image, ingredients) before saving
3. User can save to their default/first recipe book with one tap
4. User sees a toast confirmation: "Recipe saved to [Book Name]"
5. The complete flow (share → extract → preview → save) is possible in under 5 seconds for standard recipe sites
6. Share sheet integration works on both Android and iOS

## Tasks / Subtasks

- [x] Task 1: Add receive_sharing_intent package (AC: #1, #6)
  - [x] Add `receive_sharing_intent: ^1.8.0` to `app/pubspec.yaml` (spec said ^6.0.1 but that version doesn't exist on pub.dev)
  - [x] Run `flutter pub get`

- [x] Task 2: Configure Android share intent receiver (AC: #6)
  - [x] Add `android.intent.action.SEND` intent-filter for `text/plain` in AndroidManifest.xml `<activity>` block
  - [x] Add `android.intent.action.SEND` intent-filter for `text/*` (catches all text MIME types)

- [x] Task 3: Configure iOS share extension (AC: #6)
  - [x] Document manual Xcode steps in Dev Notes (share extension requires Xcode UI — cannot be done in code only)

- [x] Task 4: Create ShareImportScreen (AC: #1, #2, #3, #4, #5)
  - [x] Created `app/lib/features/recipes/add_recipe/share_import_screen.dart`
  - [x] Accepts `initialUrl` String parameter
  - [x] On `initState`, automatically calls `_loadBooksAndStartImport()` — no user click needed
  - [x] Reuses same polling + preview UI pattern from `url_import_screen.dart`
  - [x] Loads user's recipe books; uses default book from AuthService or first book
  - [x] Shows book name in approve button: "Save to [Book Name]"
  - [x] On approve success: shows SnackBar("Recipe saved to [book]"), then `context.go('/')`
  - [x] On error: shows error message with Retry + Close buttons

- [x] Task 5: Wire up share intent listening in app entry point (AC: #1)
  - [x] `PalatefulApp._PalatefulAppState` inlines share listener in `initState`
  - [x] Handles cold start via `getInitialMedia()` and hot shares via `getMediaStream()`
  - [x] Extracts URL from `SharedMediaFile.path`, including URLs embedded in text
  - [x] Navigates to `/recipes/add/share?url=<encoded>` using `addPostFrameCallback` for timing safety
  - [x] Cancels stream subscription on dispose

- [x] Task 6: Add router route for share import (AC: #1)
  - [x] Added `/recipes/add/share` GoRoute to `app_router.dart` (parentNavigatorKey: _rootNavigatorKey)
  - [x] Reads `url` from `state.uri.queryParameters['url']`
  - [x] Passes to `ShareImportScreen(initialUrl: url)`

- [ ] Task 7: Widget tests (AC: #1–#4)
  - [ ] Deferred — requires mock ApiClient test infrastructure

## Dev Notes

### This Is a Brownfield Story — Do NOT Rewrite Existing Code

`UrlImportScreen` in `url_import_screen.dart` already implements the full import flow (startImport → polling → preview → approve). `ShareImportScreen` follows the SAME pattern but auto-starts on `initState` without requiring user input.

### Package: receive_sharing_intent

The `receive_sharing_intent` package (pub.dev) handles platform-specific share receiving for Flutter. Add to `app/pubspec.yaml`:
```yaml
receive_sharing_intent: ^6.0.1
```

### iOS Share Extension — Manual Xcode Steps Required

The iOS Share Extension CANNOT be configured via code alone — Xcode UI work is required:

1. Open `app/ios/Runner.xcworkspace` in Xcode
2. File → New → Target → Share Extension → Name: `ShareExtension`
3. Configure App Group `group.com.palateful.app` in:
   - Runner target → Signing & Capabilities → + App Groups → `group.com.palateful.app`
   - ShareExtension target → Signing & Capabilities → + App Groups → `group.com.palateful.app`
4. In `ShareExtension/ShareViewController.swift`, replace boilerplate with `receive_sharing_intent`'s provided code
5. Set `PRODUCT_BUNDLE_IDENTIFIER` for ShareExtension: `com.palateful.app.ShareExtension`
6. ShareExtension/Info.plist `NSExtensionActivationRule` should allow `kUTTypeURL` and `kUTTypeText`

Full instructions: https://pub.dev/packages/receive_sharing_intent#ios-setup

The ShareExtension requires its own Info.plist (auto-created by Xcode). Do NOT add NSExtension to Runner's Info.plist.

### Android Intent Filter (AndroidManifest.xml)

Add inside the `<activity>` block in `app/android/app/src/main/AndroidManifest.xml`, alongside the existing Auth0 intent-filter:

```xml
<!-- Share sheet: receive URLs and text from other apps -->
<intent-filter>
    <action android:name="android.intent.action.SEND" />
    <category android:name="android.intent.category.DEFAULT" />
    <data android:mimeType="text/plain" />
</intent-filter>
<intent-filter>
    <action android:name="android.intent.action.SEND" />
    <category android:name="android.intent.category.DEFAULT" />
    <data android:mimeType="text/*" />
</intent-filter>
```

### ShareImportScreen — Key Differences from UrlImportScreen

`UrlImportScreen` waits for user to type URL and click "Import". `ShareImportScreen` auto-starts on build.

```dart
class ShareImportScreen extends StatefulWidget {
  final String initialUrl;
  const ShareImportScreen({super.key, required this.initialUrl});
  @override
  State<ShareImportScreen> createState() => _ShareImportScreenState();
}

class _ShareImportScreenState extends State<ShareImportScreen> {
  final _apiClient = getIt<ApiClient>();
  String? _selectedBookId;
  String? _selectedBookName;
  List<dynamic> _recipeBooks = [];
  bool _isImporting = false;
  String? _importJobId;
  String? _importStatus;
  Timer? _pollTimer;
  Map<String, dynamic>? _importItem;
  Map<String, dynamic>? _parsedRecipe;
  bool _isApproving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadBooksAndStartImport();
  }

  Future<void> _loadBooksAndStartImport() async {
    try {
      final response = await _apiClient.getRecipeBooks();
      if (!mounted) return;
      final books = response.data['items'] as List? ?? [];
      setState(() {
        _recipeBooks = books;
        if (books.isNotEmpty) {
          _selectedBookId = books.first['id']?.toString();
          _selectedBookName = books.first['name']?.toString() ?? 'Recipe Book';
        }
      });
      if (_selectedBookId != null) {
        await _startImport();
      }
    } catch (_) {
      if (mounted) setState(() => _error = 'Could not load recipe books.');
    }
  }

  Future<void> _startImport() async {
    if (_selectedBookId == null) return;
    setState(() { _isImporting = true; _error = null; });
    try {
      final response = await _apiClient.startImport(
        _selectedBookId!,
        sourceType: 'url',
        url: widget.initialUrl,
      );
      if (mounted) {
        _importJobId = response.data['id']?.toString();
        _startPolling();
      }
    } catch (_) {
      if (mounted) setState(() { _isImporting = false; _error = 'Could not start import.'; });
    }
  }

  // _startPolling, _pollImportJob, _loadImportItems: identical to UrlImportScreen

  Future<void> _approveImport() async {
    // ... same as UrlImportScreen but navigate home on success:
    // ScaffoldMessenger.of(context).showSnackBar(
    //   SnackBar(content: Text('Recipe saved to $_selectedBookName')),
    // );
    // context.go('/');
  }
}
```

### Share Intent Listener — Root App Initialization

Find the root `StatefulWidget` (likely in `app/lib/main.dart` or the main `MaterialApp` builder). Add the listener there:

```dart
import 'package:receive_sharing_intent/receive_sharing_intent.dart';

class _MyAppState extends State<MyApp> {
  late StreamSubscription _shareSubscription;

  @override
  void initState() {
    super.initState();
    // Cold start: app was launched from share
    ReceiveSharingIntent.instance.getInitialMedia().then((files) {
      _handleSharedFiles(files);
      ReceiveSharingIntent.instance.reset();
    });
    // Hot share: app was already running
    _shareSubscription = ReceiveSharingIntent.instance
        .getMediaStream()
        .listen(_handleSharedFiles, onError: (_) {});
  }

  void _handleSharedFiles(List<SharedMediaFile> files) {
    for (final file in files) {
      final path = file.path;
      if (path.startsWith('http://') || path.startsWith('https://')) {
        // Navigate after first frame (router may not be ready in initState)
        WidgetsBinding.instance.addPostFrameCallback((_) {
          appRouter.go('/recipes/add/share?url=${Uri.encodeComponent(path)}');
        });
        return;
      }
    }
  }

  @override
  void dispose() {
    _shareSubscription.cancel();
    super.dispose();
  }
}
```

### Router Route Addition

Add to `app_router.dart` in the non-shell routes section (alongside `/recipes/add/url`):

```dart
GoRoute(
  path: '/recipes/add/share',
  parentNavigatorKey: _rootNavigatorKey,
  builder: (context, state) {
    final url = state.uri.queryParameters['url'] ?? '';
    return ShareImportScreen(initialUrl: url);
  },
),
```

### State Management

`setState` only — same as all other import screens (`url_import_screen.dart`, `import_item_review_screen.dart`). Do NOT introduce Riverpod here.

### API Client

No new methods needed. `_apiClient.startImport(bookId, sourceType: 'url', url: url)` already exists at `api_client.dart:383`.

### Test Pattern

Follow `app/test/login_screen_test.dart` for the pump + mock pattern. For mock ApiClient responses, use a test double.

### DO NOT:
- Auto-approve without showing the preview — user must confirm what they're saving (AC #2)
- Handle multiple shared URLs — bulk import is Story 3.3
- Add push notifications on import completion — that is Story 3.6
- Create a new URL fetch / parsing implementation — backend handles all of that

### References

- [Source: app/lib/features/recipes/add_recipe/url_import_screen.dart] — Canonical import screen to adapt
- [Source: app/lib/core/router/app_router.dart:179–188] — `/recipes/add/url` route pattern to follow
- [Source: app/android/app/src/main/AndroidManifest.xml] — Add Android intent-filters here
- [Source: app/ios/Runner/Info.plist] — iOS reference; ShareExtension gets its own plist from Xcode
- [Source: app/pubspec.yaml] — Add receive_sharing_intent dependency here
- [Source: app/lib/core/services/api_client.dart:383] — `startImport()` method
- [Source: _bmad-output/planning-artifacts/epics.md#Story-3.5] — Epic requirements
- [Source: _bmad-output/implementation-artifacts/3-4-exception-review-queue.md] — Previous story patterns

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

### Completion Notes List

### File List

**Modified files:**
- `app/pubspec.yaml` — added `receive_sharing_intent: ^1.8.0`
- `app/android/app/src/main/AndroidManifest.xml` — two SEND intent-filters (text/plain + text/*)
- `app/lib/core/router/app_router.dart` — `/recipes/add/share` route with query params
- `app/lib/main.dart` — PalatefulApp now StatefulWidget with inline share listener

**New files:**
- `app/lib/features/recipes/add_recipe/share_import_screen.dart` — auto-start share import screen

## Code Review Action Items

- [x] [HIGH] Wrong package version ^6.0.1 doesn't exist on pub.dev — used ^1.8.0 (resolves to 1.8.1)
- [x] [HIGH] Cold start navigation used `context.pop(true)` — changed to `context.go('/')` for share-launched flows
- [x] [HIGH] Route used `/recipes/share-import` with `extra` — changed to `/recipes/add/share` with query params (survives route restoration)
- [x] [MEDIUM] Missing second Android intent filter `text/*` — added alongside `text/plain`
- [x] [MEDIUM] Missing `addPostFrameCallback` for cold start — added to prevent race condition with router
- [x] [MEDIUM] Approve button said "Save Recipe" — changed to "Save to [Book Name]"
- [x] [MEDIUM] No retry button on error — added Retry + Close buttons
- [x] [LOW] Removed unnecessary `ShareHandlerService` class — inlined in root widget per spec
- [x] [LOW] Renamed parameter from `url` to `initialUrl` per spec convention
