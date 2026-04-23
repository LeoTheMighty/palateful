//
//  MetricKitReceiver.swift
//  Runner
//
//  cla-7: bridge iOS MetricKit payloads onto a Flutter EventChannel so the
//  Dart `ClientLatencyIngest` can enqueue them as `metrickit_daily` events.
//
//  Release-build only — MetricKit doesn't deliver meaningful payloads from
//  Debug or Profile builds (Apple populates the daily aggregate from
//  TestFlight / App Store installs), and we don't want to pollute dev
//  traces with fake data. Wrapped in `#if !DEBUG` at the AppDelegate call
//  site; the class itself is compiled unconditionally so `import`
//  statements don't go stale.
//
//  EventChannel contract (Dart side consumes):
//    - channel name: "com.palateful.metrickit"
//    - event payload: [String: Any] with the seven top-level fields the
//      epic calls out (launch_time_ms, hang_time_ms, scroll_hitch_ratio,
//      cpu_time_ms, disk_write_kb, cellular_upload_kb, memory_peak_mb)
//      plus "raw_payload" (the full MXMetricPayload.jsonRepresentation()
//      parsed into a dict) if it fits under the messenger size cap.
//
//  If the serialized payload exceeds ~900KB we drop "raw_payload" and set
//  "payload_truncated" = true rather than try to chunk — the top-level
//  fields are still shipped and the operator can investigate the rare
//  truncated case manually.
//

import Flutter
import MetricKit

@available(iOS 13.0, *)
class MetricKitReceiver: NSObject, MXMetricManagerSubscriber, FlutterStreamHandler {
  static let channelName = "com.palateful.metrickit"
  private static let maxRawPayloadBytes = 900_000

  private var eventSink: FlutterEventSink?
  // MetricKit fires the first callback on app launch — the Dart side may
  // not have subscribed yet. Buffer up to a handful of payloads in memory
  // so the first-launch payload isn't lost. Cap the queue so a runaway
  // OS callback can't grow it unbounded.
  private var pendingPayloads: [[String: Any]] = []
  private let maxPendingPayloads = 8

  override init() {
    super.init()
    MXMetricManager.shared.add(self)
  }

  deinit {
    MXMetricManager.shared.remove(self)
  }

  // MARK: - MXMetricManagerSubscriber

  func didReceive(_ payloads: [MXMetricPayload]) {
    for payload in payloads {
      let dict = Self.payloadToDict(payload)
      forward(dict)
    }
  }

  @available(iOS 14.0, *)
  func didReceive(_ payloads: [MXDiagnosticPayload]) {
    // v1 only forwards metric payloads — diagnostic payloads (hangs,
    // crashes, disk writes, CPU exceptions) are forwarded by Crashlytics
    // already; bringing them here would duplicate a channel we already
    // own. Revisit if we need deeper drill-in per incident.
  }

  // MARK: - FlutterStreamHandler

  func onListen(withArguments arguments: Any?, eventSink events: @escaping FlutterEventSink) -> FlutterError? {
    eventSink = events
    // Drain anything we buffered before the Dart side subscribed.
    for payload in pendingPayloads {
      events(payload)
    }
    pendingPayloads.removeAll()
    return nil
  }

  func onCancel(withArguments arguments: Any?) -> FlutterError? {
    eventSink = nil
    return nil
  }

  // MARK: - Private

  private func forward(_ dict: [String: Any]) {
    if let sink = eventSink {
      sink(dict)
      return
    }
    if pendingPayloads.count >= maxPendingPayloads {
      pendingPayloads.removeFirst()
    }
    pendingPayloads.append(dict)
  }

  /// Extract the seven headline fields and (optionally) the full
  /// `jsonRepresentation()` of the payload. Static so tests can exercise
  /// the parsing without spinning up MXMetricManager.
  static func payloadToDict(_ payload: MXMetricPayload) -> [String: Any] {
    var result: [String: Any] = [:]

    // 1. Launch time — histogram median as a rough "p50 launch."
    if let launch = payload.applicationLaunchMetrics {
      if let firstBucket = launch.histogrammedTimeToFirstDraw.bucketEnumerator.nextObject() as? MXHistogramBucket<UnitDuration> {
        let ms = firstBucket.bucketStart.converted(to: .milliseconds).value
        result["launch_time_ms"] = Int(ms)
      }
    }

    // 2. Hang time — first bucket's start as a rough "headline hang."
    if let responsiveness = payload.applicationResponsivenessMetrics {
      if let firstBucket = responsiveness.histogrammedApplicationHangTime.bucketEnumerator.nextObject() as? MXHistogramBucket<UnitDuration> {
        let ms = firstBucket.bucketStart.converted(to: .milliseconds).value
        result["hang_time_ms"] = Int(ms)
      }
    }

    // 3. Scroll-hitch ratio (iOS 14+)
    if #available(iOS 14.0, *) {
      if let animation = payload.animationMetrics {
        result["scroll_hitch_ratio"] = animation.scrollHitchTimeRatio.value
      }
    }

    // 4. Cumulative CPU time over the 24h window — doubles as the event's
    // `duration_ms` on the Dart side (see metrickit_bridge.dart).
    if let cpu = payload.cpuMetrics {
      let ms = cpu.cumulativeCPUTime.converted(to: .milliseconds).value
      result["cpu_time_ms"] = Int(ms)
    }

    // 5. Cumulative logical disk writes (kB).
    if let disk = payload.diskIOMetrics {
      let kb = disk.cumulativeLogicalWrites.converted(to: .kilobytes).value
      result["disk_write_kb"] = Int(kb)
    }

    // 6. Cellular upload (kB).
    if let network = payload.networkTransferMetrics {
      let kb = network.cumulativeCellularUpload.converted(to: .kilobytes).value
      result["cellular_upload_kb"] = Int(kb)
    }

    // 7. Peak memory usage (MB).
    if let memory = payload.memoryMetrics {
      let mb = memory.peakMemoryUsage.converted(to: .megabytes).value
      result["memory_peak_mb"] = Int(mb)
    }

    // Full payload — kept verbatim in `extra.raw_payload` so operators can
    // query fields we didn't hoist above without a schema change. Dropped
    // on the rare >900KB payload (busy-user rolling-window outliers) to
    // stay under the Flutter binary messenger cap.
    let rawJson = payload.jsonRepresentation()
    if rawJson.count <= maxRawPayloadBytes {
      if let obj = try? JSONSerialization.jsonObject(with: rawJson) as? [String: Any] {
        result["raw_payload"] = obj
      }
    } else {
      result["payload_truncated"] = true
      result["payload_bytes"] = rawJson.count
    }

    return result
  }
}
