import 'package:test/test.dart';

import 'package:cissp_compass/features/exam/cat_runner_state.dart';

/// Integration-style proof that the CAT language toggle path used by
/// `_CatExamBody` never advances position / increments nextCallCount.
void main() {
  test('UI language toggle sequence never calls afterNext', () {
    // Mirrors _loadNext then SegmentedButton onSelectionChanged.
    var state = const CatRunnerState(
      languageMode: 'en',
      position: 0,
      questionId: '',
    );
    var nextHits = 0;

    CatRunnerState loadNext({
      required int position,
      required String questionId,
      required String languageMode,
    }) {
      nextHits++;
      return state
          .copyWithLanguage(languageMode)
          .afterNext(position: position, questionId: questionId);
    }

    state = loadNext(position: 0, questionId: 'q1', languageMode: 'en');
    expect(nextHits, 1);
    expect(state.nextCallCount, 1);

    // Language toggles — same code path as the SegmentedButton handler.
    state = state.copyWithLanguage('zh');
    state = state.copyWithLanguage('bilingual');
    state = state.copyWithLanguage('en');

    expect(nextHits, 1);
    expect(state.nextCallCount, 1);
    expect(state.position, 0);
    expect(state.questionId, 'q1');
  });
}
