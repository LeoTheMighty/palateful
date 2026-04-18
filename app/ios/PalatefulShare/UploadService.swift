import Foundation

/// Background-capable pipeline that turns a PendingImport into an
/// ImportJob on the server. The flow diverges by sourceType:
///
///   url / text → POST /v1/recipe-books/{book}/import  (no upload)
///   image / pdf / audio / video_file / file / spreadsheet →
///       POST /v1/imports/upload-url  (ephemeral session, small JSON)
///       PUT  <presigned>  (background URLSession, streams from file)
///       POST /v1/recipe-books/{book}/import with {s3_key, etag}
///       retry /import up to 3× × 500 ms on 409 object_not_ready
///
/// The PUT uses a background URLSessionConfiguration so iOS keeps the
/// upload alive even if the extension process is reaped. The /upload-url
/// and /import calls use the ephemeral shared session — they're small
/// JSON round-trips that complete in milliseconds, so we don't need the
/// background machinery for them. If the extension dies before /import
/// fires, the main app's PendingImportsReconciler resubmits on foreground
/// (server is idempotent by Idempotency-Key).
///
/// Memory budget per sie-4 AC: <80 MB RSS on 100 MB video upload. That
/// budget comes "for free" from uploadTask(with:fromFile:) — URLSession
/// streams from disk without buffering the entire payload. Patterns that
/// would buffer the full file in memory (and blow the 120 MB extension
/// ceiling) are lint-blocked by ci_post_clone.sh — see the grep there.
final class UploadService: NSObject {
  private let sessionIdentifier: String
  private let context: SharedContext
  private lazy var backgroundSession: URLSession = {
    let config = URLSessionConfiguration.background(withIdentifier: sessionIdentifier)
    config.sessionSendsLaunchEvents = true
    config.isDiscretionary = false
    config.sharedContainerIdentifier = SharedState.appGroupId
    return URLSession(configuration: config, delegate: self, delegateQueue: nil)
  }()
  private let ephemeralSession = URLSession(configuration: .ephemeral)

  /// Tracks the file URL + book_id for in-flight PUT tasks so the delegate
  /// can advance the state machine on didCompleteWithError.
  private var inflight: [Int: InflightUpload] = [:]
  private let inflightLock = NSLock()

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
      startUploadUrl(record: record)
    }
  }

  // MARK: - Step 1: /v1/imports/upload-url

  private func startUploadUrl(record: PendingImport) {
    guard let url = URL(string: "\(context.apiBaseUrl)/v1/imports/upload-url") else {
      return
    }
    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    request.setValue("Bearer \(context.authJwt)", forHTTPHeaderField: "Authorization")

    let payload: [String: Any] = [
      "filename": record.filename ?? "share.bin",
      "mime_type": record.mimeType ?? "application/octet-stream",
      "size_bytes": record.sizeBytes ?? 0
    ]
    request.httpBody = try? JSONSerialization.data(withJSONObject: payload, options: [])

    let task = ephemeralSession.dataTask(with: request) { [weak self] data, response, error in
      guard let self else { return }
      if let error = error {
        self.markFailed(record: record, errorCode: mapNetworkError(error), errorId: nil)
        return
      }
      let status = (response as? HTTPURLResponse)?.statusCode ?? 0
      guard (200...299).contains(status), let data = data else {
        let (code, id) = parseErrorPayload(data: data, fallbackStatus: status)
        self.markFailed(record: record, errorCode: code, errorId: id)
        return
      }
      guard let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
            let uploadUrlStr = obj["upload_url"] as? String,
            let uploadUrl = URL(string: uploadUrlStr),
            let s3Key = obj["s3_key"] as? String else {
        self.markFailed(record: record, errorCode: "unknown", errorId: nil)
        return
      }
      let headers = obj["required_headers"] as? [String: String] ?? [:]
      var updated = record
      updated = PendingImport(
        id: updated.id,
        bookId: updated.bookId,
        sourceType: updated.sourceType,
        url: updated.url,
        s3Key: s3Key,
        etag: nil,
        filename: updated.filename,
        mimeType: updated.mimeType,
        sizeBytes: updated.sizeBytes,
        createdAt: updated.createdAt
      )
      PendingImports.upsert(updated)
      self.startBackgroundPut(record: updated, uploadUrl: uploadUrl, headers: headers)
    }
    task.resume()
  }

  // MARK: - Step 2: PUT to S3 (background)

  private func startBackgroundPut(
    record: PendingImport,
    uploadUrl: URL,
    headers: [String: String]
  ) {
    guard let filename = record.filename else { return }
    // Look up the source file inside the extension sandbox. The NSItemProvider
    // handed us a file URL earlier; we persisted it in the ShareViewModel.
    // For the current design the file path is NOT in PendingImport (we only
    // persist what's needed for server-side dedupe). Instead, the caller
    // passes the URL via startFileUpload.
    _ = filename
    _ = uploadUrl
    _ = headers
    // Overload in startFileUpload does the actual PUT. This branch is
    // only reachable if startFileUpload was not called first.
  }

  /// File-path entry point. Called by ShareViewController with the file URL
  /// captured from the NSItemProvider. This bypasses the DRY submit path
  /// because the file URL can't survive crossing App Group — so the
  /// extension must own the PUT until it's done.
  func startFileUpload(record: PendingImport, fileURL: URL) {
    startUploadUrl(recordWithFile: record, fileURL: fileURL)
  }

  private func startUploadUrl(recordWithFile record: PendingImport, fileURL: URL) {
    guard let url = URL(string: "\(context.apiBaseUrl)/v1/imports/upload-url") else {
      return
    }
    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    request.setValue("Bearer \(context.authJwt)", forHTTPHeaderField: "Authorization")
    let payload: [String: Any] = [
      "filename": record.filename ?? fileURL.lastPathComponent,
      "mime_type": record.mimeType ?? "application/octet-stream",
      "size_bytes": record.sizeBytes ?? 0
    ]
    request.httpBody = try? JSONSerialization.data(withJSONObject: payload, options: [])

    let task = ephemeralSession.dataTask(with: request) { [weak self] data, response, error in
      guard let self else { return }
      if let error = error {
        self.markFailed(record: record, errorCode: mapNetworkError(error), errorId: nil)
        return
      }
      let status = (response as? HTTPURLResponse)?.statusCode ?? 0
      guard (200...299).contains(status), let data = data,
            let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
            let uploadUrlStr = obj["upload_url"] as? String,
            let uploadUrl = URL(string: uploadUrlStr),
            let s3Key = obj["s3_key"] as? String
      else {
        let (code, id) = parseErrorPayload(data: data, fallbackStatus: status)
        self.markFailed(record: record, errorCode: code, errorId: id)
        return
      }
      let headers = obj["required_headers"] as? [String: String] ?? [:]
      let updated = PendingImport(
        id: record.id,
        bookId: record.bookId,
        sourceType: record.sourceType,
        url: nil,
        s3Key: s3Key,
        etag: nil,
        filename: record.filename,
        mimeType: record.mimeType,
        sizeBytes: record.sizeBytes,
        createdAt: record.createdAt
      )
      PendingImports.upsert(updated)
      self.firePut(record: updated, uploadUrl: uploadUrl, headers: headers, fileURL: fileURL)
    }
    task.resume()
  }

  private func firePut(
    record: PendingImport,
    uploadUrl: URL,
    headers: [String: String],
    fileURL: URL
  ) {
    var putRequest = URLRequest(url: uploadUrl)
    putRequest.httpMethod = "PUT"
    for (k, v) in headers {
      putRequest.setValue(v, forHTTPHeaderField: k)
    }
    // Stream from file — never buffer the payload. This is the core
    // guarantee behind the 80 MB RSS ceiling.
    let task = backgroundSession.uploadTask(with: putRequest, fromFile: fileURL)
    task.taskDescription = "s3_put:\(record.id)"
    inflightLock.lock()
    inflight[task.taskIdentifier] = InflightUpload(record: record, phase: .putting)
    inflightLock.unlock()
    task.resume()
  }

  // MARK: - Step 3: /import (with 409 retry)

  private func submitImport(record: PendingImport, attempt: Int = 0) {
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
    if let u = record.url { payload["url"] = u }
    if let s = record.s3Key { payload["s3_key"] = s }
    if let e = record.etag { payload["etag"] = e }
    if let fn = record.filename { payload["filename"] = fn }
    if let mt = record.mimeType { payload["mime_type"] = mt }

    request.httpBody = try? JSONSerialization.data(withJSONObject: payload, options: [])

    let task = ephemeralSession.dataTask(with: request) { [weak self] data, response, error in
      guard let self else { return }
      if error != nil {
        // Network error — let the main-app reconciler retry on foreground.
        return
      }
      let status = (response as? HTTPURLResponse)?.statusCode ?? 0
      if (200...299).contains(status) {
        PendingImports.remove(id: record.id)
        return
      }
      if status == 409, attempt < 3 {
        // Per AC: retry 3× with 500 ms backoff.
        DispatchQueue.global().asyncAfter(deadline: .now() + .milliseconds(500)) {
          self.submitImport(record: record, attempt: attempt + 1)
        }
        return
      }
      let (code, id) = parseErrorPayload(data: data, fallbackStatus: status)
      self.markFailed(record: record, errorCode: code, errorId: id)
    }
    task.resume()
  }

  // MARK: - Helpers

  private func markFailed(record: PendingImport, errorCode: String, errorId: String?) {
    // We don't currently surface failure from a dead extension to the
    // user (the share sheet has already dismissed). Telemetry captures
    // the event. Persistent record stays in the App Group so the main
    // app's reconciler can also log it.
    Telemetry.emit(
      "share_extension_failed",
      properties: [
        "error_code": errorCode,
        "error_id": errorId ?? "",
        "source_type": record.sourceType
      ],
      context: context
    )
  }
}

// MARK: - URLSession delegate

extension UploadService: URLSessionDataDelegate, URLSessionTaskDelegate {
  func urlSession(
    _ session: URLSession,
    task: URLSessionTask,
    didCompleteWithError error: Error?
  ) {
    let id = task.taskIdentifier
    inflightLock.lock()
    let entry = inflight.removeValue(forKey: id)
    inflightLock.unlock()
    guard let entry else { return }

    let status = (task.response as? HTTPURLResponse)?.statusCode ?? 0
    switch entry.phase {
    case .putting:
      guard error == nil, (200...299).contains(status) else {
        // PUT failed — reconciler on foreground will NOT be able to
        // retry because it doesn't have the file URL. For now the share
        // is effectively lost. Telemetry below so we can measure how
        // often this happens.
        markFailed(record: entry.record, errorCode: "s3_put_failed", errorId: nil)
        return
      }
      let etag = (task.response as? HTTPURLResponse)?
        .value(forHTTPHeaderField: "Etag")?
        .trimmingCharacters(in: CharacterSet(charactersIn: "\""))
      let updated = PendingImport(
        id: entry.record.id,
        bookId: entry.record.bookId,
        sourceType: entry.record.sourceType,
        url: entry.record.url,
        s3Key: entry.record.s3Key,
        etag: etag,
        filename: entry.record.filename,
        mimeType: entry.record.mimeType,
        sizeBytes: entry.record.sizeBytes,
        createdAt: entry.record.createdAt
      )
      PendingImports.upsert(updated)
      submitImport(record: updated)
    }
  }
}

private struct InflightUpload {
  enum Phase { case putting }
  let record: PendingImport
  let phase: Phase
}

private func parseErrorPayload(data: Data?, fallbackStatus: Int) -> (String, String?) {
  guard let data = data,
        let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
    return (errorCodeForStatus(fallbackStatus), nil)
  }
  let code = (obj["error_code"] as? String) ?? errorCodeForStatus(fallbackStatus)
  let id = obj["error_id"] as? String
  return (code, id)
}

private func errorCodeForStatus(_ status: Int) -> String {
  switch status {
  case 401, 403: return "jwt_expired"
  case 413: return "file_too_large"
  case 415: return "unsupported_mime"
  case 429: return "rate_limited"
  default: return "unknown"
  }
}

private func mapNetworkError(_ error: Error) -> String {
  let code = (error as NSError).code
  if code == NSURLErrorNotConnectedToInternet ||
     code == NSURLErrorNetworkConnectionLost ||
     code == NSURLErrorTimedOut {
    return "network"
  }
  return "unknown"
}
