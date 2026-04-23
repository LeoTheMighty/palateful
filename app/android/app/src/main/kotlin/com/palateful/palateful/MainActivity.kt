package com.palateful.palateful

import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.EventChannel

class MainActivity : FlutterActivity() {
    // cla-8: held strong so the JankStats listener survives past
    // configureFlutterEngine. Only started in release builds.
    private var jankStatsBridge: JankStatsBridge? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        // cla-8: JankStats bridge. Release-only — JankStats on debug
        // builds reports misleading numbers because of dev-mode
        // debuggability overhead; gating at the call site keeps dev
        // traces clean.
        if (!BuildConfig.DEBUG) {
            val bridge = JankStatsBridge(this)
            val channel = EventChannel(
                flutterEngine.dartExecutor.binaryMessenger,
                JankStatsBridge.CHANNEL_NAME,
            )
            channel.setStreamHandler(bridge)
            bridge.start()
            jankStatsBridge = bridge
        }
    }

    override fun onDestroy() {
        jankStatsBridge?.stop()
        jankStatsBridge = null
        super.onDestroy()
    }
}
