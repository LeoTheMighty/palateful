import Foundation
import UniformTypeIdentifiers
import MobileCoreServices

/// UI state for the extension sheet. The view observes this — every case
/// below corresponds to one visual layout in ShareView. Ordering matters:
/// detection runs first, then readiness, then save, then terminal states.
enum ShareState: Equatable {
  case detecting
  case needsSignIn
  case jwtNearExpiry
  case unsupportedType
  case oversized(sizeBytes: Int64)
  case readyUrl(URL)
  case readyText(String)
  case readyFile(url: URL, sizeBytes: Int64, mimeType: String)
  case saving
  case saved
  case failed(errorCode: String, errorId: String?)
}

/// Error-code → user-visible copy. Matches the sie-3 AC exactly. Keep the
/// keys in sync with the backend's 4xx machine-readable error_code.
enum ShareErrorCopy {
  static func message(for code: String, errorId: String?) -> String {
    switch code {
    case "file_too_large":
      return "This file is too large to share. Open Palateful to import it from Files."
    case "unsupported_mime":
      return "Palateful can't read this type yet."
    case "jwt_expired":
      return "Open Palateful to refresh sign-in."
    case "rate_limited":
      return "You've hit your import limit — try again later."
    default:
      if let id = errorId, !id.isEmpty {
        return "Something went wrong. Try again. (ref \(id))"
      }
      return "Something went wrong. Try again."
    }
  }
}

/// View model. Keeps the SwiftUI layer entirely state-driven so snapshot
/// testing on a simulator doesn't need to exercise NSExtensionContext.
/// Everything above the "save()" fold is synchronous and cheap; save()
/// itself is designed to return within 100ms so the extension can call
/// extensionContext.completeRequest before the OS reaps the process.
@MainActor
final class ShareViewModel: ObservableObject {
  @Published var state: ShareState = .detecting
  @Published var selectedBookId: String?
  @Published var availableBooks: [SharedRecipeBook] = []
  @Published var multiItemTruncated: Int = 0

  let context: SharedContext?
  let uploadSessionIdentifier = "com.palateful.palateful.share.upload"

  /// Max upload size. Files above this fail closed before any network call
  /// fires. Text shares are also guarded since a 1 MB+ text blob is almost
  /// always a paste from something huge.
  static let maxUploadBytes: Int64 = 100 * 1024 * 1024

  /// Size threshold above which the sheet shows a pre-Save disclosure
  /// ("Uploading NN MB to Palateful"). Needed for App Store Review to
  /// avoid 4.1 / 5.1.1 rejections on unattended upload flows.
  static let disclosureBytesThreshold: Int64 = 10 * 1024 * 1024

  private let startTime = Date()

  init(context: SharedContext?) {
    self.context = context
    self.availableBooks = context?.recipeBooks.filter { !$0.isArchived } ?? []
    self.selectedBookId = context?.lastUsedBookId ?? availableBooks.first?.id
  }

  /// Called once by ShareViewController with the parsed NSExtensionItem
  /// attachments. If there are multiple items, only the first is processed
  /// and multiItemTruncated is set so the view shows a banner per sie-5.
  func startDetection(items: [NSExtensionItem]) {
    guard let context else {
      state = .needsSignIn
      return
    }

    if context.authJwt.isEmpty {
      state = .needsSignIn
      return
    }
    if context.isJwtNearExpiry {
      state = .jwtNearExpiry
      return
    }

    let attachments = items.flatMap { $0.attachments ?? [] }
    if attachments.isEmpty {
      state = .unsupportedType
      return
    }

    if attachments.count > 1 {
      multiItemTruncated = attachments.count - 1
      Telemetry.emit(
        "share_extension_multi_item_truncated",
        properties: ["count": attachments.count, "kept_type": "first"],
        context: context
      )
    }

    let provider = attachments[0]
    loadFirstProvider(provider)
  }

  private func loadFirstProvider(_ provider: NSItemProvider) {
    // URL path
    if provider.hasItemConformingToTypeIdentifier(UTType.url.identifier) {
      provider.loadItem(forTypeIdentifier: UTType.url.identifier, options: nil) { [weak self] item, _ in
        Task { @MainActor in
          guard let self else { return }
          if let url = item as? URL {
            self.state = .readyUrl(url)
          } else if let str = item as? String, let url = URL(string: str) {
            self.state = .readyUrl(url)
          } else {
            self.state = .unsupportedType
          }
        }
      }
      return
    }

    // Plain-text path
    if provider.hasItemConformingToTypeIdentifier(UTType.plainText.identifier) {
      provider.loadItem(forTypeIdentifier: UTType.plainText.identifier, options: nil) { [weak self] item, _ in
        Task { @MainActor in
          guard let self else { return }
          let str = (item as? String) ?? ""
          let bytes = Int64(str.utf8.count)
          if bytes > ShareViewModel.maxUploadBytes {
            self.state = .oversized(sizeBytes: bytes)
            if let ctx = self.context {
              Telemetry.emit(
                "share_extension_size_too_large",
                properties: ["kind": "text", "bytes": bytes],
                context: ctx
              )
            }
            return
          }
          self.state = .readyText(str)
        }
      }
      return
    }

    // Generic file / image / movie path — route through file URL so we
    // never load the full payload into memory (80 MB ceiling, sie-4 AC).
    let fileIdentifiers = [
      UTType.fileURL.identifier,
      UTType.image.identifier,
      UTType.movie.identifier,
      UTType.pdf.identifier,
      UTType.audio.identifier,
      UTType.data.identifier
    ]
    for typeId in fileIdentifiers {
      if provider.hasItemConformingToTypeIdentifier(typeId) {
        loadFileProvider(provider, typeId: typeId)
        return
      }
    }

    state = .unsupportedType
  }

  private func loadFileProvider(_ provider: NSItemProvider, typeId: String) {
    provider.loadItem(forTypeIdentifier: typeId, options: nil) { [weak self] item, _ in
      Task { @MainActor in
        guard let self else { return }
        guard let url = (item as? URL) ?? ((item as? Data).flatMap { _ in nil }) else {
          self.state = .unsupportedType
          return
        }
        let size = Self.fileSize(at: url)
        if size > ShareViewModel.maxUploadBytes {
          self.state = .oversized(sizeBytes: size)
          if let ctx = self.context {
            Telemetry.emit(
              "share_extension_size_too_large",
              properties: ["kind": "file", "bytes": size],
              context: ctx
            )
          }
          return
        }
        let mime = Self.mimeType(for: url)
        self.state = .readyFile(url: url, sizeBytes: size, mimeType: mime)
      }
    }
  }

  /// Persists a pending_imports record to the App Group and hands off to the
  /// background URLSession. Returns the record id if persisted; nil if the
  /// current state is not saveable. Designed to return in <100ms so the
  /// caller can immediately call extensionContext.completeRequest.
  func save() -> PendingImport? {
    guard let context else { return nil }
    let bookId = selectedBookId ?? context.lastUsedBookId ?? ""
    guard !bookId.isEmpty else {
      state = .failed(errorCode: "missing_book", errorId: nil)
      return nil
    }

    let record: PendingImport
    switch state {
    case .readyUrl(let url):
      record = PendingImport(
        id: UUID().uuidString.lowercased(),
        bookId: bookId,
        sourceType: "url",
        url: url.absoluteString,
        s3Key: nil,
        etag: nil,
        filename: nil,
        mimeType: nil,
        sizeBytes: nil,
        createdAt: Date().timeIntervalSince1970 * 1000
      )
    case .readyText(let text):
      record = PendingImport(
        id: UUID().uuidString.lowercased(),
        bookId: bookId,
        sourceType: "text",
        url: text,
        s3Key: nil,
        etag: nil,
        filename: nil,
        mimeType: "text/plain",
        sizeBytes: Int64(text.utf8.count),
        createdAt: Date().timeIntervalSince1970 * 1000
      )
    case .readyFile(let url, let size, let mime):
      // File path: the background upload will be fired from
      // ShareViewController after save() returns. We just persist the
      // intent here so reconciliation works even if the upload is killed.
      record = PendingImport(
        id: UUID().uuidString.lowercased(),
        bookId: bookId,
        sourceType: Self.sourceType(for: mime),
        url: nil,
        s3Key: nil,
        etag: nil,
        filename: url.lastPathComponent,
        mimeType: mime,
        sizeBytes: size,
        createdAt: Date().timeIntervalSince1970 * 1000
      )
    default:
      return nil
    }

    PendingImports.upsert(record)

    Telemetry.emit(
      "share_extension_latency_ms",
      properties: [
        "ms": Int(Date().timeIntervalSince(startTime) * 1000),
        "source_type": record.sourceType,
        "book_id": bookId
      ],
      context: context
    )
    state = .saved
    return record
  }

  func markCancelled() {
    if let context {
      Telemetry.emit(
        "share_extension_cancelled",
        properties: ["state": String(describing: state)],
        context: context
      )
    }
  }

  // MARK: - Static helpers

  static func fileSize(at url: URL) -> Int64 {
    if let attrs = try? FileManager.default.attributesOfItem(atPath: url.path) {
      if let n = attrs[.size] as? NSNumber {
        return n.int64Value
      }
    }
    return 0
  }

  static func mimeType(for url: URL) -> String {
    if let type = UTType(filenameExtension: url.pathExtension),
       let mime = type.preferredMIMEType {
      return mime
    }
    return "application/octet-stream"
  }

  static func sourceType(for mime: String) -> String {
    switch mime {
    case _ where mime.hasPrefix("image/"): return "image"
    case "application/pdf": return "pdf"
    case _ where mime.hasPrefix("audio/"): return "audio"
    case _ where mime.hasPrefix("video/"): return "video_file"
    case _ where mime.hasPrefix("text/"): return "text"
    case "application/vnd.ms-excel",
         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
         "text/csv":
      return "spreadsheet"
    default:
      return "file"
    }
  }
}
