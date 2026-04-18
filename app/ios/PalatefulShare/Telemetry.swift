import Foundation

/// Fire-and-forget telemetry for the Share Extension. Every event lands in
/// POST /v1/events with the `share_extension_*` name prefix. The extension
/// is a short-lived process, so every emit() dispatches on the default
/// URLSession (ephemeral) and does not block the UI. Failures log only.
enum Telemetry {
  static func emit(
    _ event: String,
    properties: [String: Any] = [:],
    context: SharedContext
  ) {
    guard let url = URL(string: "\(context.apiBaseUrl)/v1/events") else {
      return
    }

    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    request.setValue("Bearer \(context.authJwt)", forHTTPHeaderField: "Authorization")

    let body: [String: Any] = [
      "event_name": event,
      "properties": properties,
      "source": "ios_share_extension"
    ]
    request.httpBody = try? JSONSerialization.data(withJSONObject: body, options: [])

    // Ephemeral session — telemetry isn't important enough to survive
    // extension death. If the extension lives long enough for the POST to
    // land, great; if not, we drop the event.
    let task = URLSession.shared.dataTask(with: request) { _, _, _ in }
    task.resume()
  }
}
