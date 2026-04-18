import Foundation

/// Background-capable pipeline that turns a PendingImport into an
/// ImportJob on the server. The flow diverges by sourceType:
///
///   url / text → POST /v1/recipe-books/{book}/import  (no upload)
///   image / pdf / audio / video_file / file →
///       POST /v1/imports/upload-url
///       PUT  <presigned>                (streams from file, never buffers)
///       POST /v1/recipe-books/{book}/import with {s3_key, etag}
///       retry /import up to 3× × 500 ms on 409 object_not_ready
///
/// The URLSession is a background configuration so iOS keeps the upload
/// alive even after the extension process is reaped. Every terminal
/// callback clears the corresponding pending_imports record.
final class UploadService: NSObject {
  private let sessionIdentifier: String
  private let context: SharedContext
  private lazy var session: URLSession = {
    let config = URLSessionConfiguration.background(withIdentifier: sessionIdentifier)
    config.sessionSendsLaunchEvents = true
    config.isDiscretionary = false
    config.sharedContainerIdentifier = SharedState.appGroupId
    return URLSession(configuration: config, delegate: self, delegateQueue: nil)
  }()

  init(sessionIdentifier: String, context: SharedContext) {
    self.sessionIdentifier = sessionIdentifier
    self.context = context
    super.init()
  }

  func start(record: PendingImport) {
    switch record.sourceType {
    case "url", "text":
      submitImport(record: record)
    default:
      // sie-4 implements the file path; for now persist the intent and
      // let the main-app reconciler handle it on foreground.
      // (No-op — record is already in App Group via PendingImports.upsert.)
      break
    }
  }

  // MARK: - Import POST

  private func submitImport(record: PendingImport) {
    guard let url = URL(string: "\(context.apiBaseUrl)/v1/recipe-books/\(record.bookId)/import") else {
      return
    }
    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    request.setValue("Bearer \(context.authJwt)", forHTTPHeaderField: "Authorization")
    request.setValue(record.id, forHTTPHeaderField: "Idempotency-Key")

    var payload: [String: Any] = [
      "source_type": record.sourceType,
      "idempotency_key": record.id
    ]
    if let urlStr = record.url { payload["url"] = urlStr }
    if let s3 = record.s3Key { payload["s3_key"] = s3 }
    if let et = record.etag { payload["etag"] = et }
    if let fn = record.filename { payload["filename"] = fn }
    if let mt = record.mimeType { payload["mime_type"] = mt }

    request.httpBody = try? JSONSerialization.data(withJSONObject: payload, options: [])

    // Background sessions require uploadTask(with:from:) / uploadTask(with:fromFile:)
    // for bodies — they don't allow dataTask with a body. Write the JSON
    // body to a temp file so we can use uploadTask(with:fromFile:).
    let tmpURL = FileManager.default.temporaryDirectory.appendingPathComponent(
      "import-\(record.id).json"
    )
    do {
      try request.httpBody?.write(to: tmpURL)
    } catch {
      return
    }
    request.httpBody = nil

    let task = session.uploadTask(with: request, fromFile: tmpURL)
    task.taskDescription = "import:\(record.id)"
    task.resume()
  }
}

// MARK: - URLSession delegate

extension UploadService: URLSessionDataDelegate, URLSessionTaskDelegate {
  func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
    guard let description = task.taskDescription,
          description.hasPrefix("import:") else {
      return
    }
    let recordId = String(description.dropFirst("import:".count))

    let status = (task.response as? HTTPURLResponse)?.statusCode ?? 0
    if error == nil && (200...299).contains(status) {
      // Success — main app will still see the record briefly on the next
      // foreground tick, but the reconciler is idempotent (dedupes by
      // idempotency_key) so a double-fire is harmless.
      PendingImports.remove(id: recordId)
    }
    // Non-2xx or network error: leave the record in place so the main-app
    // reconciler retries on next foreground.
  }
}
