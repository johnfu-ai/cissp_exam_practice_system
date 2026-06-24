// Mirrors backend Pydantic schemas. Field names are authoritative.
export type QuestionType =
  | "single_choice"
  | "multiple_choice"
  | "true_false"
  | "scenario"
  | "ordering"
  | "drag_drop"
  | "hotspot";

export type Subset = "all" | "unpracticed" | "wrong" | "bookmarked" | "needs_review";
export type OrderMode = "random" | "sequential" | "easy_to_hard";
export type ErrorType =
  | "concept_unclear"
  | "misread_stem"
  | "memory_lapse"
  | "option_confusion"
  | "time_pressure";
export type SessionStatus = "in_progress" | "completed" | "abandoned";

export interface SessionCreateInput {
  count: number;
  subset?: Subset;
  order_mode?: OrderMode;
  domain_id?: string | null;
  book_id?: string | null;
  chapter_ids?: string[];
  question_type?: string | null;
  difficulty?: number | null;
  tag_id?: string | null;
}

export interface SessionOut {
  id: string;
  status: SessionStatus;
  total_questions: number;
  correct_count: number;
  started_at: string;
  ended_at: string | null;
  paused_at: string | null;
  config: Record<string, unknown>;
}

export interface OptionDelivery {
  id: string;
  order_index: number;
  content: string;
  content_format: "plain" | "markdown";
}

export interface PreviousAnswer {
  selected: number[];
  is_correct: boolean;
}

export interface QuestionDelivery {
  session_id: string;
  position: number;
  total: number;
  question_id: string;
  stem: string;
  question_type: QuestionType;
  options: OptionDelivery[];
  elapsed_ms: number;
  previous_answer: PreviousAnswer | null;
}

export interface AnswerInput {
  position: number;
  selected: number[];
  started_at: string;
}

export interface PerOptionExplanation {
  order_index: number;
  is_correct: boolean;
  explanation: string | null;
}

export interface AnswerResult {
  is_correct: boolean;
  correct_indexes: number[];
  selected_indexes: number[];
  correct_rationale: string | null;
  key_point_summary: string | null;
  per_option: PerOptionExplanation[];
  mapping: Record<string, unknown>;
  history: Array<Record<string, unknown>>;
}

export interface DomainBreakdown {
  domain_id: string | null;
  domain_name: string | null;
  answered: number;
  correct: number;
}

export interface WrongQuestion {
  question_id: string;
  stem: string;
  selected_indexes: number[];
  correct_indexes: number[];
}

export interface SessionSummary {
  session_id: string;
  total_questions: number;
  answered_count: number;
  correct_count: number;
  accuracy: number;
  total_time_spent_ms: number;
  domains: DomainBreakdown[];
  wrong_questions: WrongQuestion[];
}

export interface QuestionStateInput {
  is_bookmarked?: boolean;
  is_flagged_review?: boolean;
  is_mastered?: boolean;
  is_questioned?: boolean;
  note?: string | null;
  error_type?: ErrorType | null;
}

export interface QuestionState {
  is_bookmarked: boolean;
  is_flagged_review: boolean;
  is_mastered: boolean;
  is_questioned: boolean;
  note: string | null;
  error_type: ErrorType | null;
}

// Taxonomy
export interface Domain {
  id: string;
  blueprint_id: string;
  number: number;
  name: string;
  weight_pct: number;
}

export interface Book {
  id: string;
  title: string;
  edition: string | null;
  author: string | null;
  publisher: string | null;
}

export interface Chapter {
  id: string;
  book_id: string;
  order_index: number;
  title: string;
}

export interface Tag {
  id: string;
  name: string;
  description: string | null;
}
