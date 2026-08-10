/// Pure CAT runner UI state — language toggle must never advance the item.
///
/// [copyWithLanguage] is the only mutation path for the in-runner content
/// language control. It must leave [position], [questionId], and any
/// "next" counters unchanged (FR-CAT forward-only / no-advance invariant).
class CatRunnerState {
  const CatRunnerState({
    required this.languageMode,
    required this.position,
    required this.questionId,
    this.nextCallCount = 0,
  });

  final String languageMode;
  final int position;
  final String questionId;

  /// Test/observability counter: increments only when `/next` would be called.
  final int nextCallCount;

  CatRunnerState copyWithLanguage(String mode) => CatRunnerState(
        languageMode: mode,
        position: position,
        questionId: questionId,
        nextCallCount: nextCallCount,
      );

  CatRunnerState afterNext({
    required int position,
    required String questionId,
  }) =>
      CatRunnerState(
        languageMode: languageMode,
        position: position,
        questionId: questionId,
        nextCallCount: nextCallCount + 1,
      );
}
