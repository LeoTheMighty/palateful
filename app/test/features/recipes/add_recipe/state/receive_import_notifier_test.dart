import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/recipes/add_recipe/state/receive_import_notifier.dart';

// sru-1 unit tests. Covers:
//   - table-driven content-type detection across the epic's regression
//     matrix (.jpg .heic .pdf .mp3 .m4a .wav .mp4 .mov .csv .xlsx .txt
//     .docx .zip .rtf + missing-MIME infer-from-extension)
//   - first-frame dedup guard (same path+mtime+size within 2 s is no-op)
//   - state-transition monotonicity: detecting → uploading → navigating

void main() {
  group('detectBranch — MIME hint', () {
    test('image mime variants → image', () {
      for (final m in [
        'image/jpeg',
        'image/png',
        'image/heic',
        'image/webp',
        // wildcard fall-through
        'image/bmp',
      ]) {
        expect(detectBranch(mime: m), ReceiveBranch.image, reason: m);
      }
    });

    test('application/pdf → pdf', () {
      expect(detectBranch(mime: 'application/pdf'), ReceiveBranch.pdf);
    });

    test('audio mime variants → audio', () {
      for (final m in ['audio/mpeg', 'audio/mp4', 'audio/wav', 'audio/aac']) {
        expect(detectBranch(mime: m), ReceiveBranch.audio, reason: m);
      }
    });

    test('video mime variants → video', () {
      for (final m in ['video/mp4', 'video/quicktime', 'video/webm']) {
        expect(detectBranch(mime: m), ReceiveBranch.video, reason: m);
      }
    });

    test('spreadsheet mime variants → spreadsheet', () {
      for (final m in [
        'text/csv',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      ]) {
        expect(detectBranch(mime: m), ReceiveBranch.spreadsheet, reason: m);
      }
    });

    test('text/plain → text', () {
      expect(detectBranch(mime: 'text/plain'), ReceiveBranch.text);
    });

    test('application/octet-stream → unsupported', () {
      expect(
        detectBranch(mime: 'application/octet-stream'),
        ReceiveBranch.unsupported,
      );
    });
  });

  group('detectBranch — extension fallback', () {
    test('missing MIME + image extensions → image', () {
      for (final ext in ['jpg', 'jpeg', 'png', 'heic', 'heif', 'webp']) {
        expect(detectBranch(filename: 'x.$ext'), ReceiveBranch.image,
            reason: ext);
      }
    });

    test('missing MIME + media extensions → correct branch', () {
      expect(detectBranch(filename: 'a.pdf'), ReceiveBranch.pdf);
      expect(detectBranch(filename: 'a.mp3'), ReceiveBranch.audio);
      expect(detectBranch(filename: 'a.m4a'), ReceiveBranch.audio);
      expect(detectBranch(filename: 'a.wav'), ReceiveBranch.audio);
      expect(detectBranch(filename: 'a.mp4'), ReceiveBranch.video);
      expect(detectBranch(filename: 'a.mov'), ReceiveBranch.video);
      expect(detectBranch(filename: 'a.csv'), ReceiveBranch.spreadsheet);
      expect(detectBranch(filename: 'a.xlsx'), ReceiveBranch.spreadsheet);
      expect(detectBranch(filename: 'a.txt'), ReceiveBranch.text);
    });

    test('explicitly-unsupported extensions → unsupported', () {
      for (final ext in ['docx', 'zip', 'rtf', 'doc']) {
        expect(detectBranch(filename: 'a.$ext'), ReceiveBranch.unsupported,
            reason: ext);
      }
    });

    test('path used when filename missing', () {
      expect(
        detectBranch(path: '/sandbox/abc/def.pdf'),
        ReceiveBranch.pdf,
      );
    });

    test('no signal → unsupported', () {
      expect(detectBranch(), ReceiveBranch.unsupported);
      expect(detectBranch(mime: ''), ReceiveBranch.unsupported);
    });
  });

  group('ReceiveImportNotifier — dedup guard', () {
    test('second fire with same dedup key within window is no-op', () {
      final n = ReceiveImportNotifier();
      addTearDown(n.dispose);
      final key = computeDedupKey(
        path: '/sandbox/a.pdf',
        mtimeMicros: 1,
        sizeBytes: 1024,
      );
      final first = n.onDetect(
        mime: 'application/pdf',
        path: '/sandbox/a.pdf',
        dedupKey: key,
      );
      final second = n.onDetect(
        mime: 'application/pdf',
        path: '/sandbox/a.pdf',
        dedupKey: key,
      );
      expect(first, ReceiveBranch.pdf);
      expect(second, isNull);
    });

    test('dedup keys differ when mtime or size changes', () {
      final a = computeDedupKey(path: '/p', mtimeMicros: 1, sizeBytes: 1);
      final b = computeDedupKey(path: '/p', mtimeMicros: 2, sizeBytes: 1);
      final c = computeDedupKey(path: '/p', mtimeMicros: 1, sizeBytes: 2);
      expect(a, isNot(b));
      expect(a, isNot(c));
      expect(b, isNot(c));
    });
  });

  group('ReceiveImportNotifier — monotonic transitions', () {
    test('detecting → uploading → navigating', () {
      final n = ReceiveImportNotifier();
      addTearDown(n.dispose);
      expect(n.value.phase, ReceivePhase.detecting);
      n.onDetect(mime: 'application/pdf');
      expect(n.value.phase, ReceivePhase.detecting);
      expect(n.value.branch, ReceiveBranch.pdf);

      n.enterUploading(total: 1_000);
      expect(n.value.phase, ReceivePhase.uploading);
      expect(n.value.totalBytes, 1_000);

      n.updateUploadProgress(uploaded: 500);
      expect(n.value.uploadedBytes, 500);

      n.enterNavigating('/activity?tab=imports');
      expect(n.value.phase, ReceivePhase.navigating);
      expect(n.value.destination, '/activity?tab=imports');
    });

    test('error path carries code + message', () {
      final n = ReceiveImportNotifier();
      addTearDown(n.dispose);
      n.enterError(ReceiveErrorCode.network, 'no signal');
      expect(n.value.phase, ReceivePhase.error);
      expect(n.value.errorCode, ReceiveErrorCode.network);
      expect(n.value.errorMessage, 'no signal');
    });
  });

  group('classifyHttpStatus', () {
    test('maps common statuses to the right error code', () {
      expect(classifyHttpStatus(401), ReceiveErrorCode.unauthorized);
      expect(classifyHttpStatus(403), ReceiveErrorCode.unauthorized);
      expect(classifyHttpStatus(409), ReceiveErrorCode.objectNotReady);
      expect(classifyHttpStatus(413), ReceiveErrorCode.tooLarge);
      expect(classifyHttpStatus(429), ReceiveErrorCode.rateLimited);
      expect(classifyHttpStatus(500), ReceiveErrorCode.unknown);
    });
  });
}
