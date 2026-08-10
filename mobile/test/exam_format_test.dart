import 'package:test/test.dart';

import 'package:cissp_compass/features/exam/format.dart';

void main() {
  group('exam format', () {
    test('fmtCountdown under an hour is MM:SS', () {
      expect(fmtCountdown(65_000), '01:05');
      expect(fmtCountdown(0), '00:00');
      expect(fmtCountdown(-100), '00:00');
    });

    test('fmtCountdown over an hour includes hours', () {
      expect(fmtCountdown(3_661_000), '1:01:01');
    });

    test('isTimeCritical is true at or under 5 minutes', () {
      expect(isTimeCritical(5 * 60 * 1000), isTrue);
      expect(isTimeCritical(5 * 60 * 1000 - 1), isTrue);
      expect(isTimeCritical(5 * 60 * 1000 + 1), isFalse);
    });

    test('fmtPct rounds to nearest percent', () {
      expect(fmtPct(0.756), '76%');
      expect(fmtPct(1), '100%');
    });

    test('fmtDuration humanizes ms', () {
      expect(fmtDuration(45_000), '45s');
      expect(fmtDuration(90_000), '1m 30s');
      expect(fmtDuration(3_600_000), '1h 0m');
    });
  });
}
