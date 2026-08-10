import 'package:cissp_compass/features/exam/format.dart';
import 'package:test/test.dart';

void main() {
  test('fmtCountdown formats three hours', () {
    expect(fmtCountdown(3 * 3600 * 1000), '3:00:00');
  });
}
