package com.palateful.palateful

import android.app.Activity
import android.os.Handler
import android.os.Looper
import androidx.metrics.performance.JankStats
import io.flutter.plugin.common.EventChannel

/**
 * cla-8: bridges AndroidX JankStats frame data onto a Flutter EventChannel
 * so the Dart `ClientLatencyIngest` can enqueue per-minute jank aggregates
 * as `jankstats_daily` events.
 *
 * JankStats fires per-frame; we roll up over a 60 s window (jank frame
 * count, total jank duration, worst-frame duration, total frame count)
 * and emit a single event per window — mirrors how `FrameJankAggregator`
 * does it on the Flutter side, but uses OS-level hitch detection from
 * `androidx.metrics:metrics-performance` which catches jank the
 * Flutter engine doesn't (compositor-side stalls, device thermal
 * throttling, etc.).
 *
 * Release-build only — the AppDelegate equivalent on iOS uses
 * `#if !DEBUG`; here we gate at the call-site in [MainActivity] via
 * `BuildConfig.DEBUG`.
 *
 * EventChannel contract:
 *   - name: "com.palateful.jankstats"
 *   - event payload: Map<String, Any> with keys:
 *       "jank_frame_count"        — Int, # of jank frames in the window
 *       "total_frame_count"       — Int, total frames (jank + non-jank)
 *       "total_jank_duration_ms"  — Long, sum of jank-frame UI durations
 *       "max_jank_duration_ms"    — Long, worst single frame duration
 */
class JankStatsBridge(private val activity: Activity) : EventChannel.StreamHandler {
    companion object {
        const val CHANNEL_NAME = "com.palateful.jankstats"
        private const val AGGREGATION_INTERVAL_MS = 60_000L
        // Cap buffered events so an OS callback loop can't grow
        // unbounded if Dart never subscribes. Eight minutes of backlog
        // is plenty for first-launch timing.
        private const val MAX_PENDING_PAYLOADS = 8
    }

    private val handler = Handler(Looper.getMainLooper())
    private var eventSink: EventChannel.EventSink? = null
    private val pendingPayloads = ArrayDeque<Map<String, Any>>()

    private var jankStats: JankStats? = null

    // Aggregation state — only touched on the main thread.
    private var jankFrameCount: Int = 0
    private var totalFrameCount: Int = 0
    private var totalJankDurationMs: Long = 0
    private var maxJankDurationMs: Long = 0

    private val flushRunnable = object : Runnable {
        override fun run() {
            flush()
            handler.postDelayed(this, AGGREGATION_INTERVAL_MS)
        }
    }

    fun start() {
        if (jankStats != null) return
        jankStats = JankStats.createAndTrack(activity.window) { frameData ->
            totalFrameCount++
            if (frameData.isJank) {
                jankFrameCount++
                val frameMs = frameData.frameDurationUiNanos / 1_000_000
                totalJankDurationMs += frameMs
                if (frameMs > maxJankDurationMs) maxJankDurationMs = frameMs
            }
        }
        handler.postDelayed(flushRunnable, AGGREGATION_INTERVAL_MS)
    }

    fun stop() {
        jankStats?.isTrackingEnabled = false
        jankStats = null
        handler.removeCallbacks(flushRunnable)
    }

    override fun onListen(arguments: Any?, events: EventChannel.EventSink?) {
        eventSink = events
        while (pendingPayloads.isNotEmpty()) {
            val payload = pendingPayloads.removeFirst()
            events?.success(payload)
        }
    }

    override fun onCancel(arguments: Any?) {
        eventSink = null
    }

    private fun flush() {
        if (totalFrameCount == 0) return
        val payload: Map<String, Any> = mapOf(
            "jank_frame_count" to jankFrameCount,
            "total_frame_count" to totalFrameCount,
            "total_jank_duration_ms" to totalJankDurationMs,
            "max_jank_duration_ms" to maxJankDurationMs,
        )
        val sink = eventSink
        if (sink != null) {
            sink.success(payload)
        } else {
            if (pendingPayloads.size >= MAX_PENDING_PAYLOADS) {
                pendingPayloads.removeFirst()
            }
            pendingPayloads.addLast(payload)
        }
        // Reset the window.
        jankFrameCount = 0
        totalFrameCount = 0
        totalJankDurationMs = 0
        maxJankDurationMs = 0
    }
}
