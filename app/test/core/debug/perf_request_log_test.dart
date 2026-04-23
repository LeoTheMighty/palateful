import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/debug/perf_request_log.dart';

PerfRequestEntry _entry(int i) => PerfRequestEntry(
      timestamp: DateTime(2026, 4, 23, 0, 0, i),
      method: 'GET',
      path: '/v1/item/$i',
      statusCode: 200,
      duration: Duration(milliseconds: i),
    );

void main() {
  setUp(() => PerfRequestLog.instance.clear());

  group('PerfRequestLog', () {
    test('add prepends newest entry first', () {
      PerfRequestLog.instance.add(_entry(1));
      PerfRequestLog.instance.add(_entry(2));
      PerfRequestLog.instance.add(_entry(3));

      final entries = PerfRequestLog.instance.entries.value;
      expect(entries.map((e) => e.path), [
        '/v1/item/3',
        '/v1/item/2',
        '/v1/item/1',
      ]);
    });

    test('capacity 100 — oldest drops on overflow', () {
      for (var i = 0; i < 105; i++) {
        PerfRequestLog.instance.add(_entry(i));
      }
      final entries = PerfRequestLog.instance.entries.value;
      expect(entries.length, PerfRequestLog.capacity);
      // Newest stays on top, oldest retained is index 5 (0..4 dropped).
      expect(entries.first.path, '/v1/item/104');
      expect(entries.last.path, '/v1/item/5');
    });

    test('clear empties the buffer', () {
      PerfRequestLog.instance.add(_entry(1));
      expect(PerfRequestLog.instance.entries.value, isNotEmpty);
      PerfRequestLog.instance.clear();
      expect(PerfRequestLog.instance.entries.value, isEmpty);
    });

    test('ValueNotifier fires on add', () {
      var ticks = 0;
      void listener() => ticks++;
      PerfRequestLog.instance.entries.addListener(listener);
      addTearDown(() =>
          PerfRequestLog.instance.entries.removeListener(listener));

      PerfRequestLog.instance.add(_entry(1));
      PerfRequestLog.instance.add(_entry(2));
      expect(ticks, 2);
    });
  });
}
