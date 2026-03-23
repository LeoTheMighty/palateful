import ActivityKit
import SwiftUI
import WidgetKit

// MARK: - Activity Attributes

struct CookingTimerAttributes: ActivityAttributes {
    public struct ContentState: Codable, Hashable {
        var endTime: Date
        var isComplete: Bool
    }

    var timerLabel: String
    var recipeName: String
    var originalDuration: TimeInterval
}

// MARK: - Live Activity Widget

@available(iOS 16.1, *)
struct CookingTimerLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: CookingTimerAttributes.self) { context in
            // Lock screen banner
            lockScreenView(context: context)
        } dynamicIsland: { context in
            DynamicIsland {
                // Expanded view
                DynamicIslandExpandedRegion(.leading) {
                    VStack(alignment: .leading, spacing: 4) {
                        Label(context.attributes.timerLabel, systemImage: "timer")
                            .font(.caption)
                            .foregroundColor(.palatefulTerracotta)
                        Text(context.attributes.recipeName)
                            .font(.caption2)
                            .foregroundColor(.secondary)
                            .lineLimit(1)
                    }
                }
                DynamicIslandExpandedRegion(.trailing) {
                    if context.state.isComplete {
                        VStack {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundColor(.green)
                                .font(.title2)
                            Text("Done!")
                                .font(.caption)
                                .fontWeight(.bold)
                        }
                    } else {
                        Text(context.state.endTime, style: .timer)
                            .font(.title)
                            .fontWeight(.bold)
                            .monospacedDigit()
                            .foregroundColor(.palatefulChocolate)
                    }
                }
                DynamicIslandExpandedRegion(.bottom) {
                    if !context.state.isComplete {
                        // Progress bar
                        ProgressView(
                            timerInterval: Date()...context.state.endTime,
                            countsDown: true
                        )
                        .tint(.palatefulTerracotta)
                    }
                }
            } compactLeading: {
                Image(systemName: context.state.isComplete ? "checkmark.circle.fill" : "timer")
                    .foregroundColor(context.state.isComplete ? .green : .palatefulTerracotta)
            } compactTrailing: {
                if context.state.isComplete {
                    Text("Done")
                        .font(.caption)
                        .foregroundColor(.green)
                } else {
                    Text(context.state.endTime, style: .timer)
                        .monospacedDigit()
                        .font(.caption)
                }
            } minimal: {
                if context.state.isComplete {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                } else {
                    Text(context.state.endTime, style: .timer)
                        .monospacedDigit()
                        .font(.caption2)
                }
            }
        }
    }

    @ViewBuilder
    private func lockScreenView(context: ActivityViewContext<CookingTimerAttributes>) -> some View {
        HStack(spacing: 16) {
            VStack(alignment: .leading, spacing: 4) {
                Label(context.attributes.timerLabel, systemImage: "timer")
                    .font(.subheadline)
                    .fontWeight(.semibold)
                Text(context.attributes.recipeName)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            Spacer()
            if context.state.isComplete {
                VStack {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                        .font(.title)
                    Text("Done!")
                        .font(.caption)
                        .fontWeight(.bold)
                }
            } else {
                Text(context.state.endTime, style: .timer)
                    .font(.title)
                    .fontWeight(.bold)
                    .monospacedDigit()
            }
        }
        .padding()
    }
}
