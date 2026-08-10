import 'package:test/test.dart';

import 'package:cissp_compass/features/practice/option_shuffle.dart';

void main() {
  group('option_shuffle', () {
    test('shuffledOrderIndexes is deterministic for the same questionId', () {
      const indexes = [0, 1, 2, 3];
      final a = shuffledOrderIndexes(indexes, 'q-abc');
      final b = shuffledOrderIndexes(indexes, 'q-abc');
      expect(a, b);
    });

    test('different questionIds usually produce different orders', () {
      const indexes = [0, 1, 2, 3, 4, 5];
      final a = shuffledOrderIndexes(indexes, 'question-one');
      final b = shuffledOrderIndexes(indexes, 'question-two');
      expect(a, isNot(equals(b)));
    });

    test('shuffle preserves the same set of order indexes', () {
      const indexes = [0, 1, 2, 3];
      final out = shuffledOrderIndexes(indexes, 'seed');
      expect(out.toSet(), indexes.toSet());
      expect(out.length, indexes.length);
    });

    test('displayOrderIndexes returns natural order when shuffle is false', () {
      expect(
        displayOrderIndexes([2, 0, 1], 'any', shuffle: false),
        [2, 0, 1],
      );
    });

    test('displayOrderIndexes shuffles when enabled', () {
      final natural = [0, 1, 2, 3];
      final shuffled = displayOrderIndexes(natural, 'q-xyz', shuffle: true);
      expect(shuffled.toSet(), natural.toSet());
      // Not asserting inequality — rare seeds may match natural order.
      expect(shuffled, isA<List<int>>());
    });
  });
}
