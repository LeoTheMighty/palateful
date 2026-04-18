import Flutter
import UIKit
import FirebaseMessaging
import UserNotifications

@main
@objc class AppDelegate: FlutterAppDelegate {
  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
  ) -> Bool {
    // Firebase is configured by the Flutter firebase_core plugin during
    // GeneratedPluginRegistrant.register. The firebase_messaging plugin
    // also owns Messaging.delegate and UNUserNotificationCenter.delegate
    // — we must NOT take those over or the plugin can't forward events
    // to Dart. Our job here is just APNs-token forwarding (defensive,
    // the plugin also does it) and a belt-and-braces registration nudge.
    GeneratedPluginRegistrant.register(with: self)
    return super.application(application, didFinishLaunchingWithOptions: launchOptions)
  }

  // Forward the APNs device token into Firebase so FCM can pair the APNs
  // route with the FCM token. The firebase_messaging plugin also handles
  // this via its application-lifecycle forwarder; setting it here is a
  // defensive belt-and-braces against plugin regression. Idempotent.
  override func application(
    _ application: UIApplication,
    didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
  ) {
    Messaging.messaging().apnsToken = deviceToken
    let tokenString = deviceToken.map { String(format: "%02.2hhx", $0) }.joined()
    print("APNs device token received: \(tokenString.prefix(12))…")
    super.application(application, didRegisterForRemoteNotificationsWithDeviceToken: deviceToken)
  }

  override func application(
    _ application: UIApplication,
    didFailToRegisterForRemoteNotificationsWithError error: Error
  ) {
    print("APNs register failed: \(error)")
    super.application(application, didFailToRegisterForRemoteNotificationsWithError: error)
  }

  override func applicationDidBecomeActive(_ application: UIApplication) {
    super.applicationDidBecomeActive(application)
    ensureAPNsRegistered()
  }

  // Belt-and-braces: if the firebase_messaging plugin ever regresses and
  // stops auto-calling registerForRemoteNotifications() post-grant, this
  // catches up on the next foreground. Gated on authorization status so
  // a first-launch where the user kills the app mid-onboarding does NOT
  // trigger registration before permission is granted.
  private func ensureAPNsRegistered() {
    UNUserNotificationCenter.current().getNotificationSettings { settings in
      let authorized = settings.authorizationStatus == .authorized
                    || settings.authorizationStatus == .provisional
      guard authorized else { return }
      DispatchQueue.main.async {
        if !UIApplication.shared.isRegisteredForRemoteNotifications {
          UIApplication.shared.registerForRemoteNotifications()
        }
      }
    }
  }
}
