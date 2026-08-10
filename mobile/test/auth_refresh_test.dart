import 'package:test/test.dart';

import 'package:cissp_compass/core/refresh_gate.dart';

void main() {
  group('RefreshGate', () {
    test('concurrent callers share a single work invocation', () async {
      var calls = 0;
      final gate = RefreshGate<String>();

      Future<String> work() async {
        calls++;
        await Future<void>.delayed(const Duration(milliseconds: 40));
        return 'tok-$calls';
      }

      final results = await Future.wait([
        gate.runOnce(work),
        gate.runOnce(work),
        gate.runOnce(work),
      ]);

      expect(calls, 1);
      expect(results, everyElement(equals('tok-1')));
      expect(gate.isInflight, isFalse);
    });

    test('after completion a new call runs work again', () async {
      var calls = 0;
      final gate = RefreshGate<int>();
      Future<int> work() async => ++calls;

      expect(await gate.runOnce(work), 1);
      expect(await gate.runOnce(work), 2);
      expect(calls, 2);
    });

    test('failed work clears inflight so callers can retry', () async {
      var calls = 0;
      final gate = RefreshGate<String>();

      Future<String> failing() async {
        calls++;
        await Future<void>.delayed(const Duration(milliseconds: 10));
        throw StateError('refresh failed');
      }

      await expectLater(gate.runOnce(failing), throwsStateError);
      expect(gate.isInflight, isFalse);

      Future<String> ok() async {
        calls++;
        return 'ok';
      }

      expect(await gate.runOnce(ok), 'ok');
      expect(calls, 2);
    });
  });
}
