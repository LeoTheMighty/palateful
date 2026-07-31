import Foundation

/// Unit tests for the Share Extension's terminal-failure path (ifh-3).
///
/// These do NOT run under XCTest. The extension has no test target and
/// adding one would mean a simulator boot on every CI run; instead the
/// pure-logic extension sources compile for the host platform with plain
/// `swiftc` and this file drives them. `tools/share-extension-tests.sh`
/// builds and runs it; Xcode Cloud invokes that script from
/// `app/ios/ci_scripts/ci_post_clone.sh`.
///
/// Covers, per the ifh-3 acceptance criteria:
///   (a) markFailed persists the failure block into the App Group record
///   (b) markFailed with retryable == false posts a notification when
///       permission is already granted
///   (c) markFailed with retryable == true posts nothing
/// plus the denied / notDetermined permission fallbacks and the
/// legacy-record decode path the additive schema promises.

// MARK: - Test doubles

/// Records what UploadService asked of the notification center. Callbacks
/// fire synchronously so assertions can run on the next line.
final class FakeNotifier: FailureNotifying {
  struct Posted {
    let title: String
    let body: String
    let identifier: String
    let userInfo: [String: String]
  }

  var authorization: FailureNotificationAuthorization
  private(set) var posted: [Posted] = []
  private(set) var authorizationQueries = 0

  init(authorization: FailureNotificationAuthorization) {
    self.authorization = authorization
  }

  func currentAuthorization(_ completion: @escaping (FailureNotificationAuthorization) -> Void) {
    authorizationQueries += 1
    completion(authorization)
  }

  func post(title: String, body: String, identifier: String, userInfo: [String: String]) {
    posted.append(Posted(title: title, body: body, identifier: identifier, userInfo: userInfo))
  }
}

// MARK: - Tiny assertion harness

enum Check {
  static var failures: [String] = []

  static func isTrue(_ condition: Bool, _ message: String) {
    if !condition { failures.append(message) }
  }

  static func equal<T: Equatable>(_ actual: T, _ expected: T, _ message: String) {
    if actual != expected {
      failures.append("\(message) — expected \(expected), got \(actual)")
    }
  }
}

// MARK: - Fixtures

private let testSuiteName = "group.com.palateful.tests.ifh3"

private func makeContext() -> SharedContext {
  SharedContext(
    authJwt: "test-jwt",
    // Port 9 (discard) — Telemetry.emit is fire-and-forget, so its POST
    // failing instantly is exactly what we want in a test.
    authJwtExpiresAt: Date(timeIntervalSince1970: 4_102_444_800),
    userId: "user-1",
    apiBaseUrl: "http://127.0.0.1:9",
    recipeBooks: [],
    lastUsedBookId: nil
  )
}

private func makeRecord(id: String = "import-1", sourceType: String = "url") -> PendingImport {
  PendingImport(
    id: id,
    bookId: "book-1",
    sourceType: sourceType,
    url: "https://example.com/recipe",
    s3Key: nil,
    etag: nil,
    filename: nil,
    mimeType: nil,
    sizeBytes: nil,
    createdAt: 1_700_000_000_000
  )
}

private func makeService(notifier: FailureNotifying) -> UploadService {
  UploadService(
    sessionIdentifier: "com.palateful.share.tests",
    context: makeContext(),
    notifier: notifier
  )
}

private func resetAppGroup() {
  UserDefaults(suiteName: testSuiteName)?
    .removeObject(forKey: SharedStateKey.pendingImports)
}

// MARK: - Tests

/// (a) The failure block lands in the persisted App Group record — the
/// record is preserved, not dropped, so the reconciler and the
/// failed-imports UI can see it on next foreground.
func testMarkFailedPersistsFailureBlock() {
  resetAppGroup()
  let record = makeRecord()
  PendingImports.upsert(record)

  let before = Date()
  makeService(notifier: FakeNotifier(authorization: .granted))
    .markFailed(record: record, errorCode: "unsupported_mime", errorId: "err-9", retryable: false)
  let after = Date()

  let stored = PendingImports.all()
  Check.equal(stored.count, 1, "failed record must stay in the App Group")
  guard let saved = stored.first else { return }
  Check.equal(saved.id, record.id, "record identity preserved")
  Check.equal(saved.failed, true, "failed flag set")
  Check.equal(saved.errorCode, "unsupported_mime", "error_code persisted")
  Check.equal(saved.errorId, "err-9", "error_id persisted")
  Check.equal(saved.retryable, false, "retryable persisted")
  Check.equal(saved.url, record.url, "payload fields survive the failure write")
  Check.equal(saved.createdAt, record.createdAt, "created_at unchanged")
  guard let attemptedAt = saved.attemptedAt else {
    Check.isTrue(false, "attempted_at persisted")
    return
  }
  Check.isTrue(
    attemptedAt >= before.addingTimeInterval(-1) && attemptedAt <= after.addingTimeInterval(1),
    "attempted_at stamped at failure time"
  )
}

/// The persisted JSON uses snake_case keys so the Dart reconciler decodes
/// it without a custom decoder, and `attempted_at` is epoch millis (same
/// convention as `created_at`) rather than Swift's seconds-since-2001.
func testPersistedJsonUsesSnakeCaseKeys() {
  resetAppGroup()
  let record = makeRecord()
  PendingImports.upsert(record)
  makeService(notifier: FakeNotifier(authorization: .denied))
    .markFailed(record: record, errorCode: "file_too_large", errorId: nil, retryable: false)

  guard let json = UserDefaults(suiteName: testSuiteName)?
    .string(forKey: SharedStateKey.pendingImports),
    let data = json.data(using: .utf8),
    let array = (try? JSONSerialization.jsonObject(with: data)) as? [[String: Any]],
    let obj = array.first
  else {
    Check.isTrue(false, "pending imports JSON readable")
    return
  }
  Check.equal(obj["failed"] as? Bool, true, "failed key")
  Check.equal(obj["error_code"] as? String, "file_too_large", "error_code key")
  Check.equal(obj["retryable"] as? Bool, false, "retryable key")
  Check.isTrue(obj["attempted_at"] != nil, "attempted_at key present")
  Check.isTrue(
    (obj["attempted_at"] as? Double ?? 0) > 1_600_000_000_000,
    "attempted_at is epoch milliseconds"
  )
  Check.isTrue(obj["errorCode"] == nil, "no camelCase leakage")
}

/// (b) Permanent failure + permission already granted → one notification,
/// body keyed off the error code.
func testPermanentFailureSchedulesNotificationWhenGranted() {
  resetAppGroup()
  let record = makeRecord()
  PendingImports.upsert(record)
  let notifier = FakeNotifier(authorization: .granted)

  makeService(notifier: notifier)
    .markFailed(record: record, errorCode: "unsupported_mime", errorId: nil, retryable: false)

  Check.equal(notifier.posted.count, 1, "one notification for a permanent failure")
  guard let posted = notifier.posted.first else { return }
  Check.equal(posted.title, "Couldn't import to Palateful", "notification title")
  Check.equal(posted.body, errorCopy(for: "unsupported_mime"), "body keyed off error_code")
  Check.equal(posted.identifier, "share_import_failed_import-1", "identifier keyed by record id")
  Check.equal(posted.userInfo["import_id"], "import-1", "userInfo carries the record id")
  Check.equal(posted.userInfo["error_code"], "unsupported_mime", "userInfo carries the code")
}

/// (c) Retryable failure → silent. The reconciler will re-POST on next
/// foreground, so notifying would cry wolf.
func testRetryableFailureSchedulesNothing() {
  resetAppGroup()
  let record = makeRecord()
  PendingImports.upsert(record)
  let notifier = FakeNotifier(authorization: .granted)

  makeService(notifier: notifier)
    .markFailed(record: record, errorCode: "network", errorId: nil, retryable: true)

  Check.equal(notifier.posted.count, 0, "no notification for a retryable failure")
  Check.equal(notifier.authorizationQueries, 0, "permission isn't even queried")
  Check.equal(PendingImports.all().first?.retryable, true, "retryable persisted as true")
}

/// Permission is queried, never requested — an extension cannot present the
/// prompt, so anything short of already-granted degrades to telemetry only.
func testNotificationSkippedWithoutPermission() {
  for status in [FailureNotificationAuthorization.denied, .notDetermined] {
    resetAppGroup()
    let record = makeRecord()
    PendingImports.upsert(record)
    let notifier = FakeNotifier(authorization: status)

    makeService(notifier: notifier)
      .markFailed(record: record, errorCode: "jwt_expired", errorId: nil, retryable: false)

    Check.equal(notifier.authorizationQueries, 1, "permission queried once (\(status.rawValue))")
    Check.equal(notifier.posted.count, 0, "no notification when \(status.rawValue)")
    Check.equal(
      PendingImports.all().first?.failed,
      true,
      "record still marked failed when \(status.rawValue)"
    )
  }
}

/// The failure block is additive: a record written by a build that predates
/// it must still decode, with safe defaults, rather than throwing and
/// taking the whole array down.
func testLegacyRecordDecodesWithSafeDefaults() {
  resetAppGroup()
  let legacy = """
  [{"id":"legacy-1","book_id":"book-1","source_type":"url",\
  "url":"https://example.com","created_at":1700000000000}]
  """
  UserDefaults(suiteName: testSuiteName)?
    .set(legacy, forKey: SharedStateKey.pendingImports)

  let all = PendingImports.all()
  Check.equal(all.count, 1, "legacy record decodes")
  guard let record = all.first else { return }
  Check.equal(record.failed, false, "failed defaults to false")
  Check.isTrue(record.errorCode == nil, "error_code defaults to nil")
  Check.isTrue(record.retryable == nil, "retryable defaults to nil (unknown)")
  Check.isTrue(record.attemptedAt == nil, "attempted_at defaults to nil")
}

/// Every code the Dart `importFailureCopy` map ships must have Swift copy;
/// unknown codes fall back to the code verbatim so the body still names the
/// failure rather than going blank.
func testErrorCopyCoversKnownCodes() {
  let codes = [
    "network", "unknown", "jwt_expired", "file_too_large", "unsupported_mime",
    "rate_limited", "s3_put_failed", "object_not_ready", "cross_user_key",
    "recipe_book_access_denied", "recipe_book_not_found"
  ]
  for code in codes {
    let copy = errorCopy(for: code)
    Check.isTrue(!copy.isEmpty, "copy exists for \(code)")
    Check.isTrue(!copy.contains(code), "copy for \(code) is prose, not the raw code")
  }
  Check.isTrue(
    errorCopy(for: "brand_new_server_code").contains("brand_new_server_code"),
    "unknown code falls back to the code verbatim"
  )
}

// MARK: - Runner

@main
enum ShareExtensionTests {
  static func main() {
    SharedState.appGroupIdOverride = testSuiteName

    let tests: [(String, () -> Void)] = [
      ("markFailed persists the failure block", testMarkFailedPersistsFailureBlock),
      ("persisted JSON uses snake_case keys", testPersistedJsonUsesSnakeCaseKeys),
      ("permanent failure notifies when granted", testPermanentFailureSchedulesNotificationWhenGranted),
      ("retryable failure notifies nothing", testRetryableFailureSchedulesNothing),
      ("notification skipped without permission", testNotificationSkippedWithoutPermission),
      ("legacy record decodes with safe defaults", testLegacyRecordDecodesWithSafeDefaults),
      ("errorCopy covers known codes", testErrorCopyCoversKnownCodes)
    ]

    var failed = 0
    for (name, body) in tests {
      Check.failures = []
      body()
      if Check.failures.isEmpty {
        print("  ok   \(name)")
      } else {
        failed += 1
        print("  FAIL \(name)")
        for failure in Check.failures { print("       - \(failure)") }
      }
    }

    // Leave no residue in the host's preferences.
    UserDefaults.standard.removePersistentDomain(forName: testSuiteName)

    print("\n\(tests.count - failed)/\(tests.count) passed")
    exit(failed == 0 ? 0 : 1)
  }
}
