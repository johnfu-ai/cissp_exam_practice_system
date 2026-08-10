import 'package:test/test.dart';

import 'package:cissp_compass/features/exam/cat_runner_state.dart';

void main() {
  group('CatRunnerState language toggle', () {
    test('copyWithLanguage only changes languageMode', () {
      const initial = CatRunnerState(
        languageMode: 'en',
        position: 7,
        questionId: 'q-42',
        nextCallCount: 3,
      );

      final toggled = initial.copyWithLanguage('zh');

      expect(toggled.languageMode, 'zh');
      expect(toggled.position, initial.position);
      expect(toggled.questionId, initial.questionId);
      expect(toggled.nextCallCount, initial.nextCallCount);
    });

    test('bilingual toggle still does not advance or call next', () {
      var state = const CatRunnerState(
        languageMode: 'en',
        position: 0,
        questionId: 'q-first',
      );
      state = state.copyWithLanguage('bilingual');
      state = state.copyWithLanguage('en');

      expect(state.position, 0);
      expect(state.questionId, 'q-first');
      expect(state.nextCallCount, 0);
    });

    test('afterNext is the only path that increments nextCallCount', () {
      var state = const CatRunnerState(
        languageMode: 'zh',
        position: 0,
        questionId: 'q-a',
      );
      state = state.copyWithLanguage('en');
      expect(state.nextCallCount, 0);

      state = state.afterNext(position: 1, questionId: 'q-b');
      expect(state.position, 1);
      expect(state.questionId, 'q-b');
      expect(state.nextCallCount, 1);
      expect(state.languageMode, 'en');
    });
  });
}
