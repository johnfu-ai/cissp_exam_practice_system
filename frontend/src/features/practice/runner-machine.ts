import type { QuestionType, PreviousAnswer, AnswerResult } from "@/lib/api/types";

export type RunnerPhase = "selecting" | "submitted";

export interface RunnerState {
  phase: RunnerPhase;
  selected: number[];
  result: AnswerResult | null;
}

export function initialRunnerState(previous?: PreviousAnswer | null): RunnerState {
  if (previous) {
    return { phase: "submitted", selected: [...previous.selected], result: null };
  }
  return { phase: "selecting", selected: [], result: null };
}

export function toggleSelection(
  state: RunnerState,
  orderIndex: number,
  questionType: QuestionType
): RunnerState {
  if (state.phase !== "selecting") return state;
  if (questionType === "multiple_choice") {
    const has = state.selected.includes(orderIndex);
    const selected = has
      ? state.selected.filter((i) => i !== orderIndex)
      : [...state.selected, orderIndex].sort((a, b) => a - b);
    return { ...state, selected };
  }
  // single_choice, true_false, and any single-answer type: replace
  return { ...state, selected: [orderIndex] };
}

export function canSubmit(state: RunnerState): boolean {
  return state.phase === "selecting" && state.selected.length > 0;
}

export function markSubmitted(state: RunnerState, result: AnswerResult): RunnerState {
  return { phase: "submitted", selected: state.selected, result };
}
