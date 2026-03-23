import SwiftUI
import WidgetKit

// MARK: - Control Center Widgets (iOS 18+)

@available(iOS 18.0, *)
struct QuickTimerControl: ControlWidget {
    var body: some ControlWidgetConfiguration {
        StaticControlConfiguration(kind: "QuickTimerControl") {
            ControlWidgetButton(action: StartTimerIntent()) {
                Label("5 Min Timer", systemImage: "timer")
            }
        }
        .displayName("Quick Timer")
        .description("Start a 5-minute cooking timer.")
    }
}

@available(iOS 18.0, *)
struct ShoppingListControl: ControlWidget {
    var body: some ControlWidgetConfiguration {
        StaticControlConfiguration(kind: "ShoppingListControl") {
            ControlWidgetButton(action: ShoppingListCountIntent()) {
                let count = readShoppingCount()
                Label("\(count) Items", systemImage: "cart.fill")
            }
        }
        .displayName("Shopping List")
        .description("See your shopping list count.")
    }
}

@available(iOS 18.0, *)
private func readShoppingCount() -> Int {
    let defaults = UserDefaults(suiteName: widgetAppGroupId)
    guard let json = defaults?.string(forKey: "shopping_list_json"),
          let data = json.data(using: .utf8),
          let dict = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
        return 0
    }
    return dict["unchecked_count"] as? Int ?? 0
}
