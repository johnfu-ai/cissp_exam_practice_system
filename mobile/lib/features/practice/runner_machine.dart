import 'package:cissp_api/cissp_api.dart';

enum RunnerPhase { selecting, submitted }

class RunnerState {
  const RunnerState({
    required this.phase,
    required this.selected,
    this.result,
  });

  final RunnerPhase phase;
  final List<int> selected;
  final AnswerResult? result;
}

RunnerState initialRunnerState(PreviousAnswer? previous) {
  if (previous != null) {
    return RunnerState(
      phase: RunnerPhase.submitted,
      selected: List<int>.from(previous.selected),
    );
  }
  return const RunnerState(phase: RunnerPhase.selecting, selected: []);
}

RunnerState toggleSelection(
  RunnerState state,
  int orderIndex,
  String questionType,
) {
  if (state.phase != RunnerPhase.selecting) return state;
  if (questionType == 'multiple_choice') {
    final has = state.selected.contains(orderIndex);
    final selected = has
        ? state.selected.where((i) => i != orderIndex).toList()
        : [...state.selected, orderIndex]..sort();
    return RunnerState(phase: state.phase, selected: selected, result: state.result);
  }
  return RunnerState(
    phase: state.phase,
    selected: [orderIndex],
    result: state.result,
  );
}

bool canSubmit(RunnerState state) =>
    state.phase == RunnerPhase.selecting && state.selected.isNotEmpty;

RunnerState markSubmitted(RunnerState state, AnswerResult result) {
  return RunnerState(
    phase: RunnerPhase.submitted,
    selected: state.selected,
    result: result,
  );
}
