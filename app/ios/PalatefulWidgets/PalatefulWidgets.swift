import WidgetKit
import SwiftUI

struct PalatefulProvider: TimelineProvider {
    let appGroupId = "group.com.palateful.app"

    func placeholder(in context: Context) -> PalatefulEntry {
        PalatefulEntry(date: Date(), nextMealName: "Loading...")
    }

    func getSnapshot(in context: Context, completion: @escaping (PalatefulEntry) -> Void) {
        let entry = PalatefulEntry(date: Date(), nextMealName: readNextMealName())
        completion(entry)
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<PalatefulEntry>) -> Void) {
        let entry = PalatefulEntry(date: Date(), nextMealName: readNextMealName())
        // Refresh every 30 minutes
        let nextUpdate = Calendar.current.date(byAdding: .minute, value: 30, to: Date())!
        let timeline = Timeline(entries: [entry], policy: .after(nextUpdate))
        completion(timeline)
    }

    private func readNextMealName() -> String {
        let defaults = UserDefaults(suiteName: appGroupId)
        return defaults?.string(forKey: "next_meal_name") ?? "No meals planned"
    }
}

struct PalatefulEntry: TimelineEntry {
    let date: Date
    let nextMealName: String
}

struct PalatefulWidgetEntryView: View {
    var entry: PalatefulProvider.Entry

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Image(systemName: "fork.knife")
                    .foregroundColor(.orange)
                Text("Palateful")
                    .font(.caption2)
                    .fontWeight(.semibold)
                    .foregroundColor(.secondary)
            }
            Spacer()
            Text(entry.nextMealName)
                .font(.headline)
                .fontWeight(.medium)
                .lineLimit(2)
            Text("Next meal")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding()
    }
}

@main
struct PalatefulWidgets: WidgetBundle {
    var body: some Widget {
        NextMealWidget()
    }
}

struct NextMealWidget: Widget {
    let kind: String = "NextMealWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: PalatefulProvider()) { entry in
            PalatefulWidgetEntryView(entry: entry)
        }
        .configurationDisplayName("Next Meal")
        .description("Shows your next planned meal.")
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}
