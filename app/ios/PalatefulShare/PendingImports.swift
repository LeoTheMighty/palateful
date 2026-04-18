import Foundation

/// A pending import persisted by the Share Extension to the App Group. The
/// extension writes these on Save, kicks off a background URLSession, and
/// calls completeRequest. The main app reconciles on foreground — it reads
/// every record, re-fires the /import call (server is idempotent by
/// idempotency_key = id), and removes the record on success.
///
/// Keys are intentionally snake_case so the Flutter reconciler can decode
/// the same JSON without custom decoders.
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
