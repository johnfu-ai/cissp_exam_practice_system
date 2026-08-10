import 'package:test/test.dart';

import 'package:cissp_compass/core/session_tracker.dart';

void main() {
  group('session_tracker', () {
    test('trackSessionId puts id first and dedupes', () {
      final ids = trackSessionId(['a', 'b'], 'b');
      expect(ids, ['b', 'a']);
    });

    test('trackSessionId caps at max', () {
      var ids = <String>[];
      for (var i = 0; i < 12; i++) {
        ids = trackSessionId(ids, 'id-$i', max: 10);
      }
      expect(ids.length, 10);
      expect(ids.first, 'id-11');
      expect(ids.contains('id-0'), isFalse);
      expect(ids.contains('id-1'), isFalse);
    });

    test('untrackSessionId removes matching id', () {
      expect(untrackSessionId(['a', 'b', 'c'], 'b'), ['a', 'c']);
    });

    test('listSessionIds returns an unmodifiable copy', () {
      final src = ['x'];
      final listed = listSessionIds(src);
      expect(listed, ['x']);
      expect(() => listed.add('y'), throwsUnsupportedError);
    });
  });
}
