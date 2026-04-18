import Foundation

enum SharedStateKey {
  static let authJwt = "share_auth_jwt"
  static let authJwtExpiresAt = "share_auth_jwt_expires_at"
  static let userId = "share_user_id"
  static let apiBaseUrl = "share_api_base_url"
  static let recipeBooks = "share_recipe_books"
  static let lastUsedBookId = "share_last_used_book_id"
  static let pendingImports = "share_pending_imports"
}

struct SharedRecipeBook: Codable {
  let id: String
  let name: String
  let isPersonal: Bool
  let isArchived: Bool

  enum CodingKeys: String, CodingKey {
    case id
    case name
    case isPersonal = "is_personal"
    case isArchived = "is_archived"
  }
}

struct SharedContext {
  let authJwt: String
  let authJwtExpiresAt: Date
  let userId: String
  let apiBaseUrl: String
  let recipeBooks: [SharedRecipeBook]
  let lastUsedBookId: String?

  var isJwtNearExpiry: Bool {
    authJwtExpiresAt.timeIntervalSinceNow < 300
  }
}

enum SharedState {
  static let appGroupId = "group.com.palateful.app"

  static func defaults() -> UserDefaults? {
    UserDefaults(suiteName: appGroupId)
  }

  static func read() -> SharedContext? {
    guard let defaults = defaults() else { return nil }
    guard let jwt = defaults.string(forKey: SharedStateKey.authJwt), !jwt.isEmpty else {
      return nil
    }
    let expiresMs = defaults.double(forKey: SharedStateKey.authJwtExpiresAt)
    guard expiresMs > 0 else { return nil }
    let expiresAt = Date(timeIntervalSince1970: expiresMs / 1000.0)

    guard let userId = defaults.string(forKey: SharedStateKey.userId), !userId.isEmpty else {
      return nil
    }
    guard let apiBaseUrl = defaults.string(forKey: SharedStateKey.apiBaseUrl),
          !apiBaseUrl.isEmpty else {
      return nil
    }

    var books: [SharedRecipeBook] = []
    if let booksJson = defaults.string(forKey: SharedStateKey.recipeBooks),
       let data = booksJson.data(using: .utf8) {
      books = (try? JSONDecoder().decode([SharedRecipeBook].self, from: data)) ?? []
    }

    let lastUsedBookId = defaults.string(forKey: SharedStateKey.lastUsedBookId)

    return SharedContext(
      authJwt: jwt,
      authJwtExpiresAt: expiresAt,
      userId: userId,
      apiBaseUrl: apiBaseUrl,
      recipeBooks: books,
      lastUsedBookId: lastUsedBookId
    )
  }
}
