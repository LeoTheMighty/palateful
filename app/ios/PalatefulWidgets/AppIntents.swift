import AppIntents
import Foundation

let widgetAppGroupId = "group.com.palateful.app"

// MARK: - Shopping List Intents

@available(iOS 17.0, *)
struct ToggleShoppingItemIntent: AppIntent {
    static var title: LocalizedStringResource = "Check Off Shopping Item"
    static var description: IntentDescription = "Mark a shopping list item as checked or unchecked"

    @Parameter(title: "Item ID")
    var itemId: String

    @Parameter(title: "List ID")
    var listId: String

    @Parameter(title: "Checked")
    var checked: Bool

    init() {}

    init(itemId: String, listId: String, checked: Bool) {
        self.itemId = itemId
        self.listId = listId
        self.checked = checked
    }

    func perform() async throws -> some IntentResult {
        // Update UserDefaults immediately for instant widget feedback
        let defaults = UserDefaults(suiteName: widgetAppGroupId)
        var pendingChanges = (defaults?.array(forKey: "pending_shopping_changes") as? [[String: Any]]) ?? []
        pendingChanges.append([
            "item_id": itemId,
            "list_id": listId,
            "checked": checked,
            "timestamp": Date().timeIntervalSince1970,
        ])
        defaults?.set(pendingChanges, forKey: "pending_shopping_changes")

        return .result()
    }
}

// MARK: - Siri Shortcuts

@available(iOS 16.0, *)
struct WhatsForDinnerIntent: AppIntent {
    static var title: LocalizedStringResource = "What's for Dinner?"
    static var description: IntentDescription = "Check your next planned meal"

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let defaults = UserDefaults(suiteName: widgetAppGroupId)
        guard let json = defaults?.string(forKey: "next_meal_json"),
              let data = json.data(using: .utf8),
              let dict = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let name = dict["name"] as? String else {
            return .result(dialog: "You don't have any meals planned. Open Palateful to plan something!")
        }

        let time = dict["time"] as? String
        if let time = time {
            return .result(dialog: "You have \(name) at \(time).")
        }
        return .result(dialog: "Your next meal is \(name).")
    }
}

@available(iOS 16.0, *)
struct AddToShoppingListIntent: AppIntent {
    static var title: LocalizedStringResource = "Add to Shopping List"
    static var description: IntentDescription = "Add an item to your shopping list"

    @Parameter(title: "Item Name")
    var itemName: String

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let defaults = UserDefaults(suiteName: widgetAppGroupId)
        var pendingAdds = (defaults?.array(forKey: "pending_shopping_adds") as? [[String: String]]) ?? []
        pendingAdds.append(["name": itemName])
        defaults?.set(pendingAdds, forKey: "pending_shopping_adds")

        return .result(dialog: "Added \(itemName) to your shopping list.")
    }
}

@available(iOS 16.0, *)
struct ShoppingListCountIntent: AppIntent {
    static var title: LocalizedStringResource = "Shopping List Count"
    static var description: IntentDescription = "How many items are on your shopping list?"

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let defaults = UserDefaults(suiteName: widgetAppGroupId)
        guard let json = defaults?.string(forKey: "shopping_list_json"),
              let data = json.data(using: .utf8),
              let dict = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let count = dict["unchecked_count"] as? Int else {
            return .result(dialog: "Your shopping list is empty.")
        }

        if count == 0 {
            return .result(dialog: "Your shopping list is empty. All done!")
        }
        return .result(dialog: "You have \(count) item\(count == 1 ? "" : "s") on your shopping list.")
    }
}

@available(iOS 16.0, *)
struct StartTimerIntent: AppIntent {
    static var title: LocalizedStringResource = "Start Cooking Timer"
    static var description: IntentDescription = "Start a cooking timer"
    static var openAppWhenRun: Bool = true

    @Parameter(title: "Minutes", default: 5)
    var minutes: Int

    @Parameter(title: "Label", default: "Timer")
    var label: String

    func perform() async throws -> some IntentResult & ProvidesDialog {
        // Write timer request to UserDefaults — Flutter reads on launch
        let defaults = UserDefaults(suiteName: widgetAppGroupId)
        defaults?.set([
            "minutes": minutes,
            "label": label,
            "timestamp": Date().timeIntervalSince1970,
        ], forKey: "pending_timer_request")

        return .result(dialog: "Starting a \(minutes)-minute timer.")
    }
}

// MARK: - App Shortcuts Provider

@available(iOS 16.0, *)
struct PalatefulShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: WhatsForDinnerIntent(),
            phrases: [
                "What's for dinner in \(.applicationName)?",
                "What am I cooking in \(.applicationName)?",
            ],
            shortTitle: "What's for Dinner?",
            systemImageName: "fork.knife"
        )
        AppShortcut(
            intent: AddToShoppingListIntent(),
            phrases: [
                "Add \(\.$itemName) to my \(.applicationName) shopping list",
                "Put \(\.$itemName) on the \(.applicationName) list",
            ],
            shortTitle: "Add to Shopping List",
            systemImageName: "cart.badge.plus"
        )
        AppShortcut(
            intent: ShoppingListCountIntent(),
            phrases: [
                "How many items on my \(.applicationName) shopping list?",
                "What's on my \(.applicationName) list?",
            ],
            shortTitle: "Shopping List Count",
            systemImageName: "cart"
        )
        AppShortcut(
            intent: StartTimerIntent(),
            phrases: [
                "Start a \(\.$minutes) minute timer in \(.applicationName)",
                "Set a \(.applicationName) timer for \(\.$minutes) minutes",
            ],
            shortTitle: "Start Timer",
            systemImageName: "timer"
        )
    }
}
