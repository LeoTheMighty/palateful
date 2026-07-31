import Foundation

/// A pending import persisted by the Share Extension to the App Group. The
/// extension writes these on Save, kicks off a background URLSession, and
/// calls completeRequest. The main app reconciles on foreground — it reads
/// every record, re-fires the /import call (server is idempotent by
/// idempotency_key = id), and removes the record on success.
///
/// Keys are intentionally snake_case so the Flutter reconciler can decode
/// the same JSON without custom decoders.
///
/// The failure block (`failed` / `error_code` / `error_id` / `retryable` /
/// `attempted_at`) is written by `UploadService.markFailed` when the
/// extension gives up on a share. It is additive: records written by an
/// older build simply omit those keys and decode to the safe defaults
/// (`failed == false`, everything else nil), so no migration is needed in
/// either direction.
struct PendingImport: Codable, Identifiable {
  let id: String
  let bookId: String
  let sourceType: String
  let url: String?
  let s3Key: String?
  let etag: String?
  let filename: String?
  let mimeType: String?
  let sizeBytes: Int64?
  let createdAt: Double

  // MARK: Failure metadata (ifh-3)

  /// True once the extension has permanently given up on this record.
  let failed: Bool
  /// Server `error_code` (or a locally-derived one — `network`,
  /// `s3_put_failed`, `unknown`) for the failure that killed the record.
  let errorCode: String?
  /// Server-issued correlation id, when the error body carried one.
  let errorId: String?
  /// Whether re-POSTing could plausibly succeed. Read from the server's
  /// top-level `retryable` field when present, else derived from the
  /// status code. nil on legacy records — readers should treat nil as
  /// "unknown, assume retryable".
  let retryable: Bool?
  /// When the failing attempt happened, epoch **milliseconds** — same
  /// convention as `createdAt` so the Dart side reads a plain number
  /// rather than Swift's seconds-since-2001 `Date` encoding.
  let attemptedAtMs: Double?

  /// `attemptedAtMs` as a `Date`. Computed, so it stays out of the
  /// encoded App Group JSON.
  var attemptedAt: Date? {
    attemptedAtMs.map { Date(timeIntervalSince1970: $0 / 1000.0) }
  }

  enum CodingKeys: String, CodingKey {
    case id
    case bookId = "book_id"
    case sourceType = "source_type"
    case url
    case s3Key = "s3_key"
    case etag
    case filename
    case mimeType = "mime_type"
    case sizeBytes = "size_bytes"
    case createdAt = "created_at"
    case failed
    case errorCode = "error_code"
    case errorId = "error_id"
    case retryable
    case attemptedAtMs = "attempted_at"
  }

  init(
    id: String,
    bookId: String,
    sourceType: String,
    url: String?,
    s3Key: String?,
    etag: String?,
    filename: String?,
    mimeType: String?,
    sizeBytes: Int64?,
    createdAt: Double,
    failed: Bool = false,
    errorCode: String? = nil,
    errorId: String? = nil,
    retryable: Bool? = nil,
    attemptedAt: Date? = nil
  ) {
    self.id = id
    self.bookId = bookId
    self.sourceType = sourceType
    self.url = url
    self.s3Key = s3Key
    self.etag = etag
    self.filename = filename
    self.mimeType = mimeType
    self.sizeBytes = sizeBytes
    self.createdAt = createdAt
    self.failed = failed
    self.errorCode = errorCode
    self.errorId = errorId
    self.retryable = retryable
    self.attemptedAtMs = attemptedAt.map { $0.timeIntervalSince1970 * 1000 }
  }

  /// Hand-rolled so a record written by a build that predates the failure
  /// block still decodes — the synthesized decoder would throw on the
  /// missing non-optional `failed` key and take the whole array with it.
  init(from decoder: Decoder) throws {
    let c = try decoder.container(keyedBy: CodingKeys.self)
    id = try c.decode(String.self, forKey: .id)
    bookId = try c.decode(String.self, forKey: .bookId)
    sourceType = try c.decode(String.self, forKey: .sourceType)
    url = try c.decodeIfPresent(String.self, forKey: .url)
    s3Key = try c.decodeIfPresent(String.self, forKey: .s3Key)
    etag = try c.decodeIfPresent(String.self, forKey: .etag)
    filename = try c.decodeIfPresent(String.self, forKey: .filename)
    mimeType = try c.decodeIfPresent(String.self, forKey: .mimeType)
    sizeBytes = try c.decodeIfPresent(Int64.self, forKey: .sizeBytes)
    createdAt = try c.decodeIfPresent(Double.self, forKey: .createdAt) ?? 0
    failed = try c.decodeIfPresent(Bool.self, forKey: .failed) ?? false
    errorCode = try c.decodeIfPresent(String.self, forKey: .errorCode)
    errorId = try c.decodeIfPresent(String.self, forKey: .errorId)
    retryable = try c.decodeIfPresent(Bool.self, forKey: .retryable)
    attemptedAtMs = try c.decodeIfPresent(Double.self, forKey: .attemptedAtMs)
  }

  /// Copy of this record carrying the failure block. Everything else is
  /// preserved so the main-app reconciler still has the payload it needs
  /// to re-POST (or, for a dead PUT, to explain what was lost).
  func markingFailed(
    errorCode: String,
    errorId: String?,
    retryable: Bool,
    at attemptedAt: Date = Date()
  ) -> PendingImport {
    PendingImport(
      id: id,
      bookId: bookId,
      sourceType: sourceType,
      url: url,
      s3Key: s3Key,
      etag: etag,
      filename: filename,
      mimeType: mimeType,
      sizeBytes: sizeBytes,
      createdAt: createdAt,
      failed: true,
      errorCode: errorCode,
      errorId: errorId,
      retryable: retryable,
      attemptedAt: attemptedAt
    )
  }
}

enum PendingImports {
  static func all() -> [PendingImport] {
    guard let defaults = SharedState.defaults() else { return [] }
    guard let json = defaults.string(forKey: SharedStateKey.pendingImports),
          let data = json.data(using: .utf8) else {
      return []
    }
    return (try? JSONDecoder().decode([PendingImport].self, from: data)) ?? []
  }

  static func upsert(_ record: PendingImport) {
    var list = all()
    if let existing = list.firstIndex(where: { $0.id == record.id }) {
      list[existing] = record
    } else {
      list.append(record)
    }
    write(list)
  }

  static func remove(id: String) {
    let list = all().filter { $0.id != id }
    write(list)
  }

  private static func write(_ list: [PendingImport]) {
    guard let defaults = SharedState.defaults() else { return }
    guard let data = try? JSONEncoder().encode(list),
          let json = String(data: data, encoding: .utf8) else {
      return
    }
    defaults.set(json, forKey: SharedStateKey.pendingImports)
  }
}
