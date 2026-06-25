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

// Analytics (mirrors app/schemas/analytics.py)
export interface DashboardOut {
  practiced_questions: number;
  total_answered: number;
  correct_count: number;
  accuracy: number;
  study_time_ms: number;
  streak_days: number;
  last_active_at: string | null;
}

export type MasteryLevel = "mastered" | "reviewing" | "learning" | "not_started";

export interface DomainMastery {
  domain_id: string;
  number: number;
  name: string;
  weight_pct: number;
  answered: number;
  correct: number;
  accuracy: number;
  avg_time_ms: number;
  mastery_level: MasteryLevel;
}

export interface TrendPoint {
  date: string;
  answered: number;
  correct: number;
  accuracy: number;
}

export interface TrendOut {
  window_days: number;
  points: TrendPoint[];
}

export interface WeakArea {
  domain_id: string | null;
  knowledge_point_id: string | null;
  label: string;
  answered: number;
  correct: number;
  accuracy: number;
}

export interface WeakAreasOut {
  weak_domains: WeakArea[];
  weak_knowledge_points: WeakArea[];
}

export interface ErrorTypeBreakdown {
  error_type: string | null;
  count: number;
}

export interface ErrorTypeOut {
  total_wrong_classified: number;
  distribution: ErrorTypeBreakdown[];
}

export interface ReviewRecommendation {
  focus_domain: WeakArea | null;
  wrong_to_review: string[];
  next_practice_question_ids: string[];
  rationale: string;
}

export interface PersonalReport {
  generated_at: string;
  dashboard: DashboardOut;
  domains: DomainMastery[];
  trend_30d: TrendOut;
  weak_areas: WeakAreasOut;
  error_types: ErrorTypeOut;
  recommendation: ReviewRecommendation;
}

// Question bank (mirrors app/schemas/question.py)
export type QuestionStatus =
  | "draft"
  | "pending_review"
  | "published"
  | "needs_revision"
  | "archived";
export type LicenseStatus =
  | "user_owned"
  | "third_party_licensed"
  | "public_domain"
  | "unconfirmed";
export type TextFormat = "plain" | "markdown";
export type ReviewAction = "submit" | "approve" | "request_changes" | "archive" | "restore";
export type FeedbackType =
  | "unclear_explanation"
  | "suspected_wrong_answer"
  | "ambiguous_stem"
  | "copyright_issue"
  | "other";
export type FeedbackStatus = "open" | "resolved" | "wont_fix";

export interface QuestionOption {
  id?: string;
  order_index?: number | null;
  content: string;
  content_format?: TextFormat;
  is_correct: boolean;
  explanation?: string | null;
}

export interface QuestionExplanation {
  correct_answer_rationale: string;
  key_point_summary?: string | null;
  further_reading?: string | null;
}

export interface QuestionMappings {
  domain_id: string | null;
  chapter_id: string | null;
  knowledge_point_id: string | null;
  tag_ids: string[];
}

export interface QuestionDetail {
  id: string;
  question_type: QuestionType;
  stem: string;
  stem_format: TextFormat;
  difficulty: number | null;
  language: string;
  status: QuestionStatus;
  source: string | null;
  license_status: LicenseStatus;
  version: number;
  prompt_items: unknown[] | null;
  created_at: string;
  updated_at: string;
  options: QuestionOption[];
  explanation: QuestionExplanation | null;
  mappings: QuestionMappings;
}

export interface QuestionCreateInput {
  question_type: QuestionType;
  stem: string;
  stem_format?: TextFormat;
  difficulty?: number | null;
  language?: string;
  source?: string | null;
  license_status?: LicenseStatus;
  options: QuestionOption[];
  explanation?: QuestionExplanation | null;
  mappings?: Partial<QuestionMappings>;
}

export type QuestionUpdateInput = Partial<QuestionCreateInput>;

export interface QuestionListItem {
  id: string;
  question_type: QuestionType;
  stem: string;
  status: QuestionStatus;
  difficulty: number | null;
  language: string;
  domain_id: string | null;
  created_at: string;
}

export interface QuestionListResponse {
  items: QuestionListItem[];
  total: number;
  page: number;
  size: number;
}

export interface QuestionFilters {
  page?: number;
  size?: number;
  status?: QuestionStatus;
  question_type?: QuestionType;
  language?: string;
  difficulty?: number;
  search?: string;
  domain_id?: string;
}

export interface Feedback {
  id: string;
  question_id: string;
  reporter_id: string | null;
  feedback_type: FeedbackType;
  comment: string | null;
  status: FeedbackStatus;
  created_at: string;
}

export interface Revision {
  revision_number: number;
  edited_by_id: string | null;
  edited_at: string;
  change_summary: string | null;
  snapshot: Record<string, unknown>;
}

// ETL / import (mirrors app/api/etl.py)
export interface EtlDataset {
  id: string;
  slug: string;
  name: string;
  source_path: string;
  total_questions: number;
  languages: string[];
}

export type EtlRunPhase = "preview" | "committed" | "rolled_back";

export interface EtlPreviewError {
  external_id: string | null;
  language: string | null;
  reason: string;
}

export interface EtlPreviewSummary {
  would_create: number;
  would_update: number;
  unchanged: number;
  by_type: Record<string, number>;
  by_language: Record<string, number>;
  errors: EtlPreviewError[];
  content_hash: string;
}

export interface EtlRun {
  run_id: string;
  phase: EtlRunPhase;
  preview_summary: EtlPreviewSummary | null;
  committed_at?: string | null;
}

// Exam (mirrors app/schemas/exam.py)
export type ExamKind = "fixed" | "cat";

export interface ExamCreateInput {
  kind: ExamKind;
  count?: number | null;
}

export interface ExamSession {
  id: string;
  status: string;
  session_kind: ExamKind;
  total_questions: number;
  correct_count: number;
  started_at: string;
  ended_at: string | null;
  time_remaining_ms: number | null;
  config: Record<string, unknown>;
}

export interface ExamQuestionDelivery {
  session_id: string;
  position: number;
  total: number;
  question_id: string;
  stem: string;
  question_type: QuestionType;
  options: OptionDelivery[];
  elapsed_ms: number;
  time_remaining_ms: number;
  previous_answer: { selected: number[] } | null;
}

export interface ExamAnswerInput {
  position: number;
  selected: number[];
  started_at: string;
}

export interface ExamAnswerAck {
  position: number;
  saved: boolean;
  time_remaining_ms: number;
  finished: boolean;
}

export interface DomainPerformance {
  domain_id: string | null;
  domain_name: string | null;
  weight_pct: number | null;
  answered: number;
  correct: number;
  accuracy: number;
}

export interface ExamReport {
  session_id: string;
  status: string;
  total_questions: number;
  answered_count: number;
  correct_count: number;
  scaled_score: number;
  max_score: number;
  passing_score: number;
  passed: boolean;
  accuracy: number;
  total_time_ms: number;
  avg_time_ms: number;
  domains: DomainPerformance[];
  wrong_questions: WrongQuestion[];
  // CAT-only (null for fixed exams):
  ability_estimate: number | null;
  ability_ci_lower: number | null;
  ability_ci_upper: number | null;
  sem: number | null;
  readiness_level: string | null;
  disclaimer: string | null;
}

export interface ReviewOption {
  order_index: number;
  content: string;
  is_correct: boolean;
  explanation: string | null;
}

export interface ReviewItem {
  position: number;
  question_id: string;
  stem: string;
  question_type: QuestionType;
  options: ReviewOption[];
  correct_rationale: string | null;
  key_point_summary: string | null;
  your_answer: { selected: number[] } | null;
  time_spent_ms: number | null;
}

export interface ExamHistoryItem {
  id: string;
  started_at: string;
  ended_at: string | null;
  status: string;
  total_questions: number;
  correct_count: number;
  scaled_score: number;
  max_score: number;
  passed: boolean;
  accuracy: number;
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
