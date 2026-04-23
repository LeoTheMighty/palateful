import Flutter
import UIKit
import FirebaseMessaging
import UserNotifications

@main
@objc class AppDelegate: FlutterAppDelegate {
  private var pushChannel: FlutterMethodChannel?
  private var apnsRegistrationTimer: Timer?
  // cla-7: held strong so the MXMetricManagerSubscriber registration
  // survives past `didFinishLaunchingWithOptions`. Only populated in
  // release builds (see `#if !DEBUG` below).
  private var metricKitReceiver: NSObject?
  private var metricKitChannel: FlutterEventChannel?

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

    if let controller = window?.rootViewController as? FlutterViewController {
      pushChannel = FlutterMethodChannel(
        name: "palateful/push",
        binaryMessenger: controller.binaryMessenger
      )

      // cla-7: MetricKit bridge. MetricKit only delivers meaningful
      // payloads from release builds (TestFlight / App Store installs),
      // so we gate at compile time — no cost and no dev-mode noise.
      #if !DEBUG
      if #available(iOS 13.0, *) {
        let receiver = MetricKitReceiver()
        let channel = FlutterEventChannel(
          name: MetricKitReceiver.channelName,
          binaryMessenger: controller.binaryMessenger
        )
        channel.setStreamHandler(receiver)
        metricKitReceiver = receiver
        metricKitChannel = channel
      }
      #endif
    }

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
    cancelAPNsTimeoutTimer()
    super.application(application, didRegisterForRemoteNotificationsWithDeviceToken: deviceToken)
  }

  override func application(
    _ application: UIApplication,
    didFailToRegisterForRemoteNotificationsWithError error: Error
  ) {
    let nsError = error as NSError
    print("APNs register failed: \(nsError.domain)#\(nsError.code): \(nsError.localizedDescription)")
    cancelAPNsTimeoutTimer()
    pushChannel?.invokeMethod(
      "apnsRegistrationFailed",
      arguments: [
        "domain": nsError.domain,
        "code": nsError.code,
        "description": nsError.localizedDescription,
      ]
    )
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
          self.startAPNsTimeoutTimer()
        }
      }
    }
  }

  // Start a 10s watchdog after registerForRemoteNotifications. If neither
  // didRegister nor didFailToRegister fires within 10s we report a silent
  // hang via the Flutter MethodChannel so Crashlytics captures the case
  // where APNs is unreachable. Timer is invalidated on either callback.
  private func startAPNsTimeoutTimer() {
    cancelAPNsTimeoutTimer()
    apnsRegistrationTimer = Timer.scheduledTimer(withTimeInterval: 10.0, repeats: false) { [weak self] _ in
      DispatchQueue.main.async {
        self?.pushChannel?.invokeMethod("apnsRegistrationTimeout", arguments: nil)
      }
    }
  }

  private func cancelAPNsTimeoutTimer() {
    apnsRegistrationTimer?.invalidate()
    apnsRegistrationTimer = nil
  }
}
