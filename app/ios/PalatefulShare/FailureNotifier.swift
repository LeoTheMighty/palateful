import Foundation
import UserNotifications

/// Permission states the extension can act on. Collapsed from
/// `UNAuthorizationStatus` because the extension only ever needs the
/// yes/no/never-asked distinction — it must *query* permission and can
/// never request it (extensions cannot prompt).
enum FailureNotificationAuthorization: String {
  /// Already granted — `.authorized`, `.provisional`, or `.ephemeral`.
  case granted
  /// Explicitly refused by the user.
  case denied
  /// Never asked. The main app owns the prompt; the extension stays silent.
  case notDetermined
}

/// Seam over `UNUserNotificationCenter` so the failure path is unit-testable.
/// `UNUserNotificationCenter.current()` traps outside a real app/extension
/// bundle, so the tests inject a fake rather than the system implementation.
protocol FailureNotifying {
  /// Reads the current permission. Never requests it.
  func currentAuthorization(_ completion: @escaping (FailureNotificationAuthorization) -> Void)

  /// Posts an immediate local notification.
  func post(title: String, body: String, identifier: String, userInfo: [String: String])
}

/// Production implementation backed by the system notification center.
///
/// Both calls are asynchronous and the share sheet has usually already
/// dismissed by the time they run, so — exactly like `Telemetry.emit` — the
/// notification only lands if iOS lets the extension live long enough. That
/// is the same best-effort contract the rest of the post-dismiss pipeline
/// runs under; the persisted failure block is the durable surface.
struct SystemFailureNotifier: FailureNotifying {
  func currentAuthorization(_ completion: @escaping (FailureNotificationAuthorization) -> Void) {
    UNUserNotificationCenter.current().getNotificationSettings { settings in
      switch settings.authorizationStatus {
      case .authorized, .provisional, .ephemeral:
        completion(.granted)
      case .denied:
        completion(.denied)
      case .notDetermined:
        completion(.notDetermined)
      @unknown default:
        // A status Apple adds later is not something we can claim consent
        // from — stay silent rather than risk an unwanted notification.
        completion(.notDetermined)
      }
    }
  }

  func post(title: String, body: String, identifier: String, userInfo: [String: String]) {
    let content = UNMutableNotificationContent()
    content.title = title
    content.body = body
    content.userInfo = userInfo
    content.sound = nil
    // nil trigger = deliver as soon as the request is accepted.
    let request = UNNotificationRequest(
      identifier: identifier,
      content: content,
      trigger: nil
    )
    UNUserNotificationCenter.current().add(request, withCompletionHandler: nil)
  }
}

/// Title for every permanent-failure notification. Kept short so it isn't
/// truncated on the lock screen.
let failureNotificationTitle = "Couldn't import to Palateful"

/// User-facing body for a failure `error_code`. Mirrors the Dart
/// `importFailureCopy` map (ifh-5, `app/lib/core/state/import_failure_copy.dart`)
/// — the two must stay in sync so the notification and the in-app
/// FailedImportsSheet say the same thing about the same failure.
///
/// Unknown codes fall back to the code verbatim (same convention as the Dart
/// map), wrapped in a sentence so the body still reads as English.
func errorCopy(for code: String) -> String {
  switch code {
  case "network":
    return "No connection. Open Palateful to try again."
  case "unknown":
    return "Something went wrong. Open Palateful to try again."
  case "jwt_expired":
    return "Sign in to Palateful again to finish this import."
  case "file_too_large":
    return "That file is too large to import."
  case "unsupported_mime":
    return "That file type isn't supported yet."
  case "rate_limited":
    return "Too many imports right now. Try again in a few minutes."
  case "s3_put_failed":
    return "The upload didn't finish. Share it again to retry."
  case "object_not_ready":
    return "The upload wasn't ready in time. Share it again to retry."
  case "cross_user_key":
    return "That upload belongs to a different account."
  case "recipe_book_access_denied":
    return "You don't have access to that recipe book."
  case "recipe_book_not_found":
    return "That recipe book no longer exists."
  default:
    return "Import failed (\(code)). Open Palateful to try again."
  }
}
