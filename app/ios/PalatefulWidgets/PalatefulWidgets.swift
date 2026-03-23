import WidgetKit
import SwiftUI

// MARK: - App Group

let appGroupId = "group.com.palateful.app"

// MARK: - Colors

extension Color {
    static let palatefulCream = Color(red: 0.98, green: 0.96, blue: 0.93)
    static let palatefulChocolate = Color(red: 0.25, green: 0.16, blue: 0.10)
    static let palatefulTerracotta = Color(red: 0.80, green: 0.40, blue: 0.27)
    static let palatefulHazelnut = Color(red: 0.65, green: 0.49, blue: 0.36)
}

// MARK: - Next Meal Widget

struct NextMealEntry: TimelineEntry {
    let date: Date
    let mealName: String
    let mealTime: String?
    let mealType: String?
    let recipeId: String?
    let todayMeals: [[String: String]]
}

struct NextMealProvider: TimelineProvider {
    func placeholder(in context: Context) -> NextMealEntry {
        NextMealEntry(date: Date(), mealName: "Pasta Carbonara", mealTime: "6:30 PM", mealType: "dinner", recipeId: nil, todayMeals: [])
    }

    func getSnapshot(in context: Context, completion: @escaping (NextMealEntry) -> Void) {
        completion(loadEntry())
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<NextMealEntry>) -> Void) {
        let entry = loadEntry()
        let nextUpdate = Calendar.current.date(byAdding: .minute, value: 30, to: Date())!
        completion(Timeline(entries: [entry], policy: .after(nextUpdate)))
    }

    private func loadEntry() -> NextMealEntry {
        let defaults = UserDefaults(suiteName: appGroupId)

        var mealName = "No meals planned"
        var mealTime: String?
        var mealType: String?
        var recipeId: String?

        if let json = defaults?.string(forKey: "next_meal_json"),
           let data = json.data(using: .utf8),
           let dict = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            mealName = dict["name"] as? String ?? mealName
            mealTime = dict["time"] as? String
            mealType = dict["type"] as? String
            recipeId = dict["recipe_id"] as? String
        }

        var todayMeals: [[String: String]] = []
        if let json = defaults?.string(forKey: "today_meals_json"),
           let data = json.data(using: .utf8),
           let arr = try? JSONSerialization.jsonObject(with: data) as? [[String: String]] {
            todayMeals = arr
        }

        return NextMealEntry(date: Date(), mealName: mealName, mealTime: mealTime, mealType: mealType, recipeId: recipeId, todayMeals: todayMeals)
    }
}

struct NextMealSmallView: View {
    var entry: NextMealEntry

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Image(systemName: mealIcon(entry.mealType))
                    .foregroundColor(.palatefulTerracotta)
                    .font(.caption)
                if let time = entry.mealTime {
                    Text(time)
                        .font(.caption2)
                        .foregroundColor(.palatefulHazelnut)
                }
            }
            Spacer()
            Text(entry.mealName)
                .font(.headline)
                .fontWeight(.medium)
                .foregroundColor(.palatefulChocolate)
                .lineLimit(2)
            Text("Next meal")
                .font(.caption)
                .foregroundColor(.palatefulHazelnut)
        }
        .padding()
        .containerBackground(.palatefulCream, for: .widget)
    }
}

struct NextMealMediumView: View {
    var entry: NextMealEntry

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Image(systemName: "fork.knife")
                    .foregroundColor(.palatefulTerracotta)
                Text("Today's Meals")
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundColor(.palatefulHazelnut)
                Spacer()
            }

            if entry.todayMeals.isEmpty {
                Spacer()
                HStack {
                    Spacer()
                    VStack(spacing: 4) {
                        Image(systemName: "calendar")
                            .foregroundColor(.palatefulHazelnut)
                        Text("No meals planned")
                            .font(.caption)
                            .foregroundColor(.palatefulHazelnut)
                    }
                    Spacer()
                }
                Spacer()
            } else {
                ForEach(entry.todayMeals.prefix(4), id: \.self) { meal in
                    HStack(spacing: 8) {
                        Text(meal["time"] ?? "")
                            .font(.caption2)
                            .foregroundColor(.palatefulHazelnut)
                            .frame(width: 50, alignment: .leading)
                        Image(systemName: mealIcon(meal["type"]))
                            .font(.caption2)
                            .foregroundColor(.palatefulTerracotta)
                        Text(meal["name"] ?? "")
                            .font(.caption)
                            .foregroundColor(.palatefulChocolate)
                            .lineLimit(1)
                    }
                }
            }
        }
        .padding()
        .containerBackground(.palatefulCream, for: .widget)
    }
}

struct NextMealWidget: Widget {
    let kind = "NextMealWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: NextMealProvider()) { entry in
            if #available(iOS 17.0, *) {
                NextMealWidgetView(entry: entry)
            } else {
                NextMealWidgetView(entry: entry)
            }
        }
        .configurationDisplayName("Next Meal")
        .description("Shows your next planned meal.")
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}

struct NextMealWidgetView: View {
    @Environment(\.widgetFamily) var family
    var entry: NextMealEntry

    var body: some View {
        switch family {
        case .systemSmall:
            NextMealSmallView(entry: entry)
        case .systemMedium:
            NextMealMediumView(entry: entry)
        default:
            NextMealSmallView(entry: entry)
        }
    }
}

// MARK: - Shopping List Widget

struct ShoppingListEntry: TimelineEntry {
    let date: Date
    let listId: String?
    let listName: String
    let uncheckedCount: Int
    let items: [[String: String]]
}

struct ShoppingListProvider: TimelineProvider {
    func placeholder(in context: Context) -> ShoppingListEntry {
        ShoppingListEntry(date: Date(), listId: nil, listName: "Shopping", uncheckedCount: 5, items: [
            ["name": "Milk", "qty": "1 gal"],
            ["name": "Eggs", "qty": "1 doz"],
        ])
    }

    func getSnapshot(in context: Context, completion: @escaping (ShoppingListEntry) -> Void) {
        completion(loadEntry())
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<ShoppingListEntry>) -> Void) {
        let entry = loadEntry()
        let nextUpdate = Calendar.current.date(byAdding: .minute, value: 30, to: Date())!
        completion(Timeline(entries: [entry], policy: .after(nextUpdate)))
    }

    private func loadEntry() -> ShoppingListEntry {
        let defaults = UserDefaults(suiteName: appGroupId)

        guard let json = defaults?.string(forKey: "shopping_list_json"),
              let data = json.data(using: .utf8),
              let dict = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return ShoppingListEntry(date: Date(), listId: nil, listName: "Shopping", uncheckedCount: 0, items: [])
        }

        let items = (dict["items"] as? [[String: String]]) ?? []
        return ShoppingListEntry(
            date: Date(),
            listId: dict["list_id"] as? String,
            listName: dict["name"] as? String ?? "Shopping",
            uncheckedCount: dict["unchecked_count"] as? Int ?? 0,
            items: items
        )
    }
}

struct ShoppingListSmallView: View {
    var entry: ShoppingListEntry

    var body: some View {
        VStack {
            Image(systemName: "cart.fill")
                .font(.title2)
                .foregroundColor(.palatefulTerracotta)
            Spacer()
            if entry.uncheckedCount == 0 {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundColor(.green)
                Text("List empty")
                    .font(.caption)
                    .foregroundColor(.palatefulHazelnut)
            } else {
                Text("\(entry.uncheckedCount)")
                    .font(.title)
                    .fontWeight(.bold)
                    .foregroundColor(.palatefulChocolate)
                Text("items")
                    .font(.caption)
                    .foregroundColor(.palatefulHazelnut)
            }
        }
        .padding()
        .containerBackground(.palatefulCream, for: .widget)
    }
}

struct ShoppingListMediumView: View {
    var entry: ShoppingListEntry

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Image(systemName: "cart.fill")
                    .foregroundColor(.palatefulTerracotta)
                    .font(.caption)
                Text(entry.listName)
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundColor(.palatefulHazelnut)
                Spacer()
                Text("\(entry.uncheckedCount) items")
                    .font(.caption2)
                    .foregroundColor(.palatefulHazelnut)
            }

            if entry.items.isEmpty {
                Spacer()
                HStack {
                    Spacer()
                    VStack(spacing: 4) {
                        Image(systemName: "checkmark.circle")
                            .foregroundColor(.green)
                        Text("All done!")
                            .font(.caption)
                            .foregroundColor(.palatefulHazelnut)
                    }
                    Spacer()
                }
                Spacer()
            } else {
                ForEach(entry.items.prefix(5), id: \.self) { item in
                    ShoppingItemRow(item: item, listId: entry.listId)
                }
            }
        }
        .padding()
        .containerBackground(.palatefulCream, for: .widget)
    }
}

struct ShoppingListWidget: Widget {
    let kind = "ShoppingListWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: ShoppingListProvider()) { entry in
            ShoppingListWidgetView(entry: entry)
        }
        .configurationDisplayName("Shopping List")
        .description("See your shopping list items at a glance.")
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}

struct ShoppingListWidgetView: View {
    @Environment(\.widgetFamily) var family
    var entry: ShoppingListEntry

    var body: some View {
        switch family {
        case .systemSmall:
            ShoppingListSmallView(entry: entry)
        case .systemMedium:
            ShoppingListMediumView(entry: entry)
        default:
            ShoppingListSmallView(entry: entry)
        }
    }
}

// MARK: - Lock Screen Widgets

@available(iOS 16.0, *)
struct NextMealLockWidget: Widget {
    let kind = "NextMealLockWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: NextMealProvider()) { entry in
            NextMealLockView(entry: entry)
        }
        .configurationDisplayName("Next Meal")
        .description("Next meal on your lock screen.")
        .supportedFamilies([.accessoryCircular, .accessoryRectangular])
    }
}

@available(iOS 16.0, *)
struct NextMealLockView: View {
    @Environment(\.widgetFamily) var family
    var entry: NextMealEntry

    var body: some View {
        switch family {
        case .accessoryCircular:
            VStack(spacing: 2) {
                Image(systemName: mealIcon(entry.mealType))
                    .font(.caption)
                Text(entry.mealTime ?? "--")
                    .font(.caption2)
                    .fontWeight(.semibold)
            }
        case .accessoryRectangular:
            VStack(alignment: .leading, spacing: 2) {
                if let time = entry.mealTime {
                    Text(time)
                        .font(.caption)
                        .fontWeight(.semibold)
                }
                Text(entry.mealName)
                    .font(.caption)
                    .lineLimit(2)
            }
        default:
            EmptyView()
        }
    }
}

@available(iOS 16.0, *)
struct ShoppingCountLockWidget: Widget {
    let kind = "ShoppingCountLockWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: ShoppingListProvider()) { entry in
            VStack(spacing: 2) {
                Image(systemName: "cart.fill")
                    .font(.caption)
                Text("\(entry.uncheckedCount)")
                    .font(.headline)
                    .fontWeight(.bold)
            }
        }
        .configurationDisplayName("Shopping Count")
        .description("Shopping list item count.")
        .supportedFamilies([.accessoryCircular])
    }
}

// MARK: - Widget Bundle

@main
struct PalatefulWidgets: WidgetBundle {
    var body: some Widget {
        NextMealWidget()
        ShoppingListWidget()
        if #available(iOS 16.0, *) {
            NextMealLockWidget()
            ShoppingCountLockWidget()
        }
        if #available(iOS 16.1, *) {
            CookingTimerLiveActivity()
        }
    }
}

// MARK: - Interactive Shopping Item Row

struct ShoppingItemRow: View {
    let item: [String: String]
    let listId: String?

    var body: some View {
        HStack {
            if #available(iOS 17.0, *), let itemId = item["id"], let listId = listId {
                Button(intent: ToggleShoppingItemIntent(itemId: itemId, listId: listId, checked: true)) {
                    itemContent
                }
                .buttonStyle(.plain)
            } else {
                itemContent
            }
        }
    }

    private var itemContent: some View {
        HStack {
            Circle()
                .fill(Color.palatefulTerracotta.opacity(0.3))
                .frame(width: 6, height: 6)
            Text(item["name"] ?? "")
                .font(.caption)
                .foregroundColor(.palatefulChocolate)
                .lineLimit(1)
            Spacer()
            if let qty = item["qty"], !qty.isEmpty {
                Text(qty)
                    .font(.caption2)
                    .foregroundColor(.palatefulHazelnut)
            }
        }
    }
}

// MARK: - Helpers

func mealIcon(_ type: String?) -> String {
    switch type?.lowercased() {
    case "breakfast": return "cup.and.saucer.fill"
    case "lunch": return "leaf.fill"
    case "dinner": return "fork.knife"
    case "snack": return "birthday.cake.fill"
    default: return "fork.knife"
    }
}
