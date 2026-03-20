# Story 11.6: Hands-Free Voice Input in Cooking Mode

Status: done

## Story

As a user,
I want to interact with the AI via voice while cooking,
so that I can ask questions and add notes without touching my phone.

## Acceptance Criteria

1. **Microphone button in chat sheet** — A microphone icon button is visible next to the text input in `CookModeChatSheet`. Tapping it activates voice input. The button is styled with the cooking mode dark theme.
2. **Speech transcription** — When voice input is active, the user's speech is transcribed in real-time using the `speech_to_text` Flutter package and the platform's native speech recognition.
3. **Auto-send on silence** — When the user stops speaking (speech recognition returns final result), the transcribed text is automatically sent to the AI via the existing chat flow (same `ChatService.sendMessage()` with `recipeContext`).
4. **Haptic and visual feedback** — When voice input starts: haptic feedback (`HapticFeedback.mediumImpact()`) + mic button turns active (terracotta fill, pulsing animation or color change). When voice input stops: haptic feedback + button returns to normal.
5. **Platform permissions** — Android `RECORD_AUDIO` permission added to `AndroidManifest.xml`. iOS `NSMicrophoneUsageDescription` and `NSSpeechRecognitionUsageDescription` added to `Info.plist`.
6. **Graceful degradation** — If speech recognition is not available (denied permission, unsupported device), the mic button is hidden or disabled with a tooltip. No crash.

## Tasks / Subtasks

- [x] Task 1: Add `speech_to_text` package (AC: 2)
  - [x] Add `speech_to_text: ^7.0.0` to `app/pubspec.yaml` dependencies
  - [x] Run `flutter pub get` to install

- [x] Task 2: Add platform permissions (AC: 5)
  - [x] In `app/android/app/src/main/AndroidManifest.xml`: add `<uses-permission android:name="android.permission.RECORD_AUDIO"/>`
  - [x] In `app/ios/Runner/Info.plist`: add `NSMicrophoneUsageDescription` key with value "Palateful uses the microphone for hands-free voice input while cooking"
  - [x] In `app/ios/Runner/Info.plist`: add `NSSpeechRecognitionUsageDescription` key with value "Palateful uses speech recognition for hands-free voice input while cooking"

- [x] Task 3: Add voice input to `CookModeChatSheet` (AC: 1, 2, 3, 4, 6)
  - [x] Import `speech_to_text` package in `cook_mode_chat_sheet.dart`
  - [x] Add state: `_speechToText` (SpeechToText instance), `_isListening` (bool), `_speechAvailable` (bool)
  - [x] In `initState()`: initialize `_speechToText` and call `initialize()` to check availability. Set `_speechAvailable` based on result.
  - [x] Add `_startListening()` method: calls `_speechToText.listen(onResult: _onSpeechResult)`, sets `_isListening = true`, triggers `HapticFeedback.mediumImpact()`
  - [x] Add `_stopListening()` method: calls `_speechToText.stop()`, sets `_isListening = false`, triggers `HapticFeedback.selectionClick()`
  - [x] Add `_onSpeechResult(SpeechRecognitionResult result)` callback: updates `_controller.text` with `result.recognizedWords`. If `result.finalResult` is true, auto-call `_sendMessage()`.
  - [x] In the input area `Row`: add a mic `IconButton` to the left of the text field (or right, next to send button)
    - When `!_speechAvailable`: hide the button or show disabled
    - When `_isListening`: show active state (filled terracotta background, `Icons.mic` icon)
    - When not listening: show `Icons.mic_none` in warmIvory
    - `onPressed`: toggle `_isListening ? _stopListening() : _startListening()`
  - [x] In `dispose()`: cancel any active speech session

- [x] Task 4: Flutter widget tests (AC: 1, 6)
  - [x] In `app/test/cook_mode_test.dart`: add test that mic button icon exists (in non-DI context, test the icon rendering pattern)
  - [x] Run `flutter test` — all tests pass

## Dev Notes

### What Already Exists — DO NOT Recreate

**`CookModeChatSheet`** at `app/lib/features/recipes/cook_mode/widgets/cook_mode_chat_sheet.dart` — fully functional chat bottom sheet from Story 11.5. Has dark theme, SSE streaming, tool activity labels, recipe context. Just add voice input UI.

**Current input area** (cook_mode_chat_sheet.dart lines 208-255):
```dart
Container(
  padding: const EdgeInsets.fromLTRB(16, 8, 8, 16),
  child: SafeArea(
    top: false,
    child: Row(
      children: [
        Expanded(
          child: TextField(
            controller: _controller,
            // ...
            onSubmitted: (_) => _sendMessage(),
          ),
        ),
        const SizedBox(width: 8),
        IconButton(
          icon: const Icon(Icons.send, color: AppColors.terracotta),
          onPressed: _isSending ? null : _sendMessage,
        ),
      ],
    ),
  ),
),
```

Add the mic button between the TextField and the send button:
```dart
Row(children: [
  Expanded(child: TextField(...)),
  const SizedBox(width: 4),
  // Mic button
  if (_speechAvailable)
    IconButton(
      icon: Icon(
        _isListening ? Icons.mic : Icons.mic_none,
        color: _isListening ? AppColors.terracotta : AppColors.warmIvory,
      ),
      onPressed: _isListening ? _stopListening : _startListening,
      style: _isListening
          ? IconButton.styleFrom(
              backgroundColor: AppColors.withOpacity(AppColors.terracotta, 0.2),
            )
          : null,
    ),
  const SizedBox(width: 4),
  IconButton(
    icon: const Icon(Icons.send, color: AppColors.terracotta),
    onPressed: _isSending ? null : _sendMessage,
  ),
]),
```

**Haptic feedback pattern** from cooking mode (cook_mode_screen.dart):
```dart
import 'package:flutter/services.dart';
HapticFeedback.mediumImpact();  // on start listening
HapticFeedback.selectionClick(); // on stop listening
```

**Platform permissions patterns:**

Android (`app/android/app/src/main/AndroidManifest.xml`):
```xml
<uses-permission android:name="android.permission.RECORD_AUDIO"/>
```

iOS (`app/ios/Runner/Info.plist`):
```xml
<key>NSMicrophoneUsageDescription</key>
<string>Palateful uses the microphone for hands-free voice input while cooking</string>
<key>NSSpeechRecognitionUsageDescription</key>
<string>Palateful uses speech recognition for hands-free voice input while cooking</string>
```

### speech_to_text Package Usage

```dart
import 'package:speech_to_text/speech_to_text.dart';
import 'package:speech_to_text/speech_recognition_result.dart';

final _speechToText = SpeechToText();
bool _speechAvailable = false;

// In initState or init method:
_speechAvailable = await _speechToText.initialize(
  onError: (error) => setState(() => _isListening = false),
  onStatus: (status) {
    if (status == 'done' || status == 'notListening') {
      setState(() => _isListening = false);
    }
  },
);

// Start listening:
await _speechToText.listen(
  onResult: (SpeechRecognitionResult result) {
    setState(() => _controller.text = result.recognizedWords);
    if (result.finalResult && result.recognizedWords.isNotEmpty) {
      _sendMessage();
    }
  },
  listenFor: const Duration(seconds: 30),
  pauseFor: const Duration(seconds: 3),
  localeId: 'en_US',
);

// Stop listening:
await _speechToText.stop();

// In dispose:
_speechToText.cancel();
```

**Key notes:**
- `initialize()` returns `bool` — false if permission denied or unavailable
- `listen()` is async, `onResult` fires for partial and final results
- `result.finalResult == true` when speech recognition detects end of utterance
- `pauseFor: Duration(seconds: 3)` auto-stops after 3 seconds of silence
- `listenFor: Duration(seconds: 30)` max listening time
- The `onStatus` callback fires with 'listening', 'notListening', 'done' statuses

### Architecture Decision: Voice in Chat Sheet Only

Voice input lives entirely in `CookModeChatSheet`. It does NOT require:
- Backend changes (voice → text → existing chat flow)
- New API endpoints
- Changes to `agent_loop.py` or `ChatService`
- Changes to `CookModeScreen` (the AI button already opens the sheet)

The flow is: User taps AI button → sheet opens → user taps mic → speaks → text sent via existing `_sendMessage()`.

### Do NOT Touch

- `services/api/` — no backend changes needed
- `libraries/agent/` — no tool changes
- `app/lib/features/chat/` — chat infrastructure unchanged
- `app/lib/features/recipes/cook_mode/cook_mode_screen.dart` — unchanged (AI button already works)

### File Locations

- `app/pubspec.yaml` — add speech_to_text dependency
- `app/android/app/src/main/AndroidManifest.xml` — RECORD_AUDIO permission
- `app/ios/Runner/Info.plist` — microphone + speech recognition descriptions
- `app/lib/features/recipes/cook_mode/widgets/cook_mode_chat_sheet.dart` — voice input UI + logic
- `app/test/cook_mode_test.dart` — widget tests

### References

- `CookModeChatSheet` input area [Source: app/lib/features/recipes/cook_mode/widgets/cook_mode_chat_sheet.dart:208-255]
- Haptic feedback pattern [Source: app/lib/features/recipes/cook_mode/cook_mode_screen.dart:211,239,250]
- Android manifest [Source: app/android/app/src/main/AndroidManifest.xml]
- iOS Info.plist [Source: app/ios/Runner/Info.plist]
- Story 11.5 completion (CookModeChatSheet architecture) [Source: _bmad-output/implementation-artifacts/11-5-ai-in-cooking-mode-questions-and-answers.md]
- speech_to_text package docs: https://pub.dev/packages/speech_to_text

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- `speech_to_text: ^7.0.0` added to pubspec.yaml. Package uses native platform speech recognition (Google Speech on Android, Apple Speech on iOS).
- `SpeechToText.initialize()` called in `initState()` — returns `false` if permission denied or unavailable. Mic button hidden when `_speechAvailable == false`.
- Voice flow: tap mic → `_startListening()` with haptic → speech streams into `_controller.text` → on `result.finalResult` auto-calls `_sendMessage()` → AI response streams in.
- `pauseFor: Duration(seconds: 3)` stops listening after 3s silence. `listenFor: Duration(seconds: 30)` max.
- Android `RECORD_AUDIO` permission added. iOS `NSMicrophoneUsageDescription` + `NSSpeechRecognitionUsageDescription` added.
- 9 cook mode tests pass, 388 backend tests pass, 11 chat tests pass.

### File List

- `app/pubspec.yaml`
- `app/pubspec.lock`
- `app/android/app/src/main/AndroidManifest.xml`
- `app/ios/Runner/Info.plist`
- `app/lib/features/recipes/cook_mode/widgets/cook_mode_chat_sheet.dart`
- `app/test/cook_mode_test.dart`
