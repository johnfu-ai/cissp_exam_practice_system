import 'package:cissp_api/cissp_api.dart';
import 'package:test/test.dart';

import 'package:cissp_compass/features/practice/runner_machine.dart';

AnswerResult _result({required bool correct, List<int> selected = const [0]}) {
  return AnswerResult(
    isCorrect: correct,
    correctIndexes: const [0],
    selectedIndexes: selected,
    correctRationale: const Localized(en: 'why'),
    keyPointSummary: const Localized(en: 'kp'),
    perOption: const [],
  );
}

void main() {
  group('runner_machine', () {
    test('initial state is selecting when no previous answer', () {
      final s = initialRunnerState(null);
      expect(s.phase, RunnerPhase.selecting);
      expect(s.selected, isEmpty);
      expect(s.result, isNull);
    });

    test('initial state is submitted when previous answer exists', () {
      final s = initialRunnerState(
        const PreviousAnswer(selected: [1, 2], isCorrect: false),
      );
      expect(s.phase, RunnerPhase.submitted);
      expect(s.selected, [1, 2]);
    });

    test('single-choice toggle replaces selection', () {
      var s = initialRunnerState(null);
      s = toggleSelection(s, 0, 'single_choice');
      expect(s.selected, [0]);
      s = toggleSelection(s, 2, 'single_choice');
      expect(s.selected, [2]);
    });

    test('multiple-choice toggle adds and removes', () {
      var s = initialRunnerState(null);
      s = toggleSelection(s, 1, 'multiple_choice');
      s = toggleSelection(s, 0, 'multiple_choice');
      expect(s.selected, [0, 1]);
      s = toggleSelection(s, 1, 'multiple_choice');
      expect(s.selected, [0]);
    });

    test('toggle is a no-op after submit', () {
      var s = initialRunnerState(null);
      s = toggleSelection(s, 0, 'single_choice');
      s = markSubmitted(s, _result(correct: true));
      final after = toggleSelection(s, 1, 'single_choice');
      expect(after.selected, [0]);
      expect(after.phase, RunnerPhase.submitted);
    });

    test('canSubmit requires selecting phase with non-empty selection', () {
      expect(canSubmit(initialRunnerState(null)), isFalse);
      final withSel = toggleSelection(initialRunnerState(null), 0, 'single_choice');
      expect(canSubmit(withSel), isTrue);
      final submitted = markSubmitted(withSel, _result(correct: false));
      expect(canSubmit(submitted), isFalse);
    });

    test('markSubmitted attaches result and moves to submitted', () {
      final s = toggleSelection(initialRunnerState(null), 0, 'single_choice');
      final result = _result(correct: true);
      final next = markSubmitted(s, result);
      expect(next.phase, RunnerPhase.submitted);
      expect(next.result, same(result));
      expect(next.selected, [0]);
    });
  });
}
