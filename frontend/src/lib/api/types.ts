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

export type LanguageCode = "en" | "zh";
export type LanguageMode = "en" | "zh" | "bilingual";

export interface Localized {
  en: string | null;
  zh: string | null;
}

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
  language_mode?: LanguageMode | null;
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
  content: Localized;
  content_format: Localized;
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
  question_type: QuestionType;
  available_languages: LanguageCode[];
  language_mode: LanguageMode;
  stem: Localized;
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
  explanation: Localized;
}

export interface AnswerResult {
  is_correct: boolean;
  correct_indexes: number[];
  selected_indexes: number[];
  correct_rationale: Localized;
  key_point_summary: Localized;
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
  stem: Localized;
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

export interface TranslationOption {
  order_index: number;
  content: string;
  content_format?: TextFormat;
  explanation?: string | null;
}
export interface Translation {
  language: LanguageCode;
  stem: string;
  stem_format?: TextFormat;
  correct_answer_rationale: string;
  key_point_summary?: string | null;
  further_reading?: string | null;
  options: TranslationOption[];
}
export interface CanonicalOption {
  id?: string;
  order_index?: number | null;
  is_correct: boolean;
}

export interface QuestionDetail {
  id: string;
  question_type: QuestionType;
  difficulty: number | null;
  available_languages: LanguageCode[];
  status: QuestionStatus;
  source: string | null;
  license_status: LicenseStatus;
  version: number;
  prompt_items: unknown[] | null;
  created_at: string;
  updated_at: string;
  options: CanonicalOption[];
  translations: Translation[];
  mappings: QuestionMappings;
}

export interface QuestionCreateInput {
  question_type: QuestionType;
  difficulty?: number | null;
  source?: string | null;
  license_status?: LicenseStatus;
  prompt_items?: unknown[] | null;
  options: CanonicalOption[];
  translations: Translation[];
  mappings?: Partial<QuestionMappings>;
}

export type QuestionUpdateInput = Partial<QuestionCreateInput>;

export interface QuestionListItem {
  id: string;
  question_type: QuestionType;
  status: QuestionStatus;
  difficulty: number | null;
  available_languages: LanguageCode[];
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
  missing_language?: LanguageCode;
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
  language_mode?: LanguageMode | null;
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
  question_type: QuestionType;
  available_languages: LanguageCode[];
  language_mode: LanguageMode;
  stem: Localized;
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
  content: Localized;
  is_correct: boolean;
  explanation: Localized;
}

export interface ReviewItem {
  position: number;
  question_id: string;
  question_type: string;
  available_languages: LanguageCode[];
  stem: Localized;
  options: ReviewOption[];
  correct_rationale: Localized;
  key_point_summary: Localized;
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

// Admin backoffice (mirrors app/schemas/admin.py)
export type UserStatus = "active" | "disabled";
export type RoleName =
  | "individual_learner"
  | "instructor"
  | "content_editor"
  | "org_admin"
  | "system_admin";

export interface AdminUser {
  id: string;
  email: string;
  display_name: string | null;
  status: string;
  default_organization_id: string | null;
  roles: string[];
}

export interface AdminClass {
  id: string;
  name: string;
  description: string | null;
  instructor_id: string | null;
  organization_id: string;
  member_count: number;
}

export interface ClassMember {
  user_id: string;
  email: string;
  display_name: string | null;
}

export interface CatParamsVersion {
  id: string;
  version_label: string;
  effective_date: string;
  is_current: boolean;
  params: Record<string, number | boolean>;
}

export interface CatParamsInput {
  version_label: string;
  effective_date: string;
  params: { k0: number; decay: number; base_se: number; early_stop_enabled: boolean };
  set_current: boolean;
}

export interface QualityDashboard {
  open_feedback_count: number;
  low_accuracy_question_count: number;
  missing_explanation_count: number;
  disputed_question_count: number;
}

export interface AdminFeedback {
  id: string;
  question_id: string;
  reporter_id: string | null;
  feedback_type: string;
  comment: string | null;
  status: string;
  created_at: string;
}

export interface LowAccuracyQuestion {
  question_id: string;
  stem: string;
  answered: number;
  correct: number;
  accuracy: number;
}

export interface AuditLog {
  id: string;
  occurred_at: string;
  action: string;
  actor_id: string | null;
  organization_id: string | null;
  entity_type: string | null;
  entity_id: string | null;
  details: Record<string, unknown> | null;
  ip_address: string | null;
}

export interface PaginatedAudit {
  items: AuditLog[];
  total: number;
  limit: number;
  offset: number;
}

export interface ReportSummary {
  scope: string;
  window_days: number;
  active_users: number;
  practice_session_count: number;
  exam_session_count: number;
  total_answers: number;
  correct_answers: number;
  accuracy: number;
  published_question_count: number;
  used_question_count: number;
  question_bank_usage_pct: number;
  top_error_questions: LowAccuracyQuestion[];
}

export interface Blueprint {
  id: string;
  version_label: string;
  effective_date: string;
  min_items: number;
  max_items: number;
  duration_minutes: number;
  passing_score: number;
  max_score: number;
  is_current: boolean;
  domains: Domain[];
}

export interface BlueprintInput {
  version_label: string;
  effective_date: string;
  min_items: number;
  max_items: number;
  duration_minutes: number;
  passing_score: number;
  max_score: number;
}

export interface DomainInput {
  number: number;
  name: string;
  weight_pct: number;
}

export interface BookInput {
  title: string;
  edition?: string | null;
  author?: string | null;
  publisher?: string | null;
  source_url?: string | null;
}

export interface ChapterInput {
  order_index: number;
  title: string;
}

export interface KnowledgePoint {
  id: string;
  name: string;
  description: string | null;
  parent_id: string | null;
}

export interface KnowledgePointInput {
  name: string;
  description?: string | null;
  parent_id?: string | null;
}

export interface TagInput {
  name: string;
  description?: string | null;
}
