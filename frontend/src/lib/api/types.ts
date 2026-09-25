// Hand-written frontend type surface for the backend API.
//
// #32: the GENERATED source of truth lives in `./schema.ts` (produced by
// `npm run gen:api` from `openapi.json`). Prefer importing generated shapes
// from `./schema` for new code; this module keeps stable human-readable
// aliases used across features. When the backend schema changes, regenerate
// (`npm run gen:api`) and update mirrors here.
import type { components } from "./schema";

/** Generated schema namespace (for progressive migration off hand mirrors). */
export type Schemas = components["schemas"];

export type QuestionType =
  | "single_choice"
  | "multiple_choice"
  | "true_false"
  | "essay"
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
  shuffle_options?: boolean;
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
  selected: number[] | null;
  is_correct: boolean | null;
  text?: string | null;
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
  time_remaining_ms?: number;
  previous_answer: PreviousAnswer | null;
  note: string | null;
}

export interface RelatedQuestion {
  question_id: string;
  stem: Localized;
  knowledge_point_id: string | null;
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
  is_correct: boolean | null;
  correct_indexes: number[];
  selected_indexes: number[];
  correct_rationale: Localized;
  key_point_summary: Localized;
  reference_answer?: Localized | null;
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

/** Chapter→domain mapping used by ETL (FR-ETL-15). Not a book Chapter row. */
export interface ChapterDomainMapping {
  id: string;
  dataset_slug: string;
  chapter_number: number;
  chapter_title: string;
  domain_id: string | null;
}

export interface MappingInput {
  dataset_slug: string;
  chapter_number: number;
  chapter_title: string;
  domain_id?: string | null;
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
  duplicates?: number;
  conflicts?: { external_id: string; reason: string }[];
  near_duplicates?: {
    external_id: string;
    similar_to_question_id: string;
    similarity: number;
    stem_excerpt: string;
  }[];
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
  reference_answer?: Localized | null;
  your_answer: { selected: number[] | null; text?: string | null; is_correct?: boolean | null } | null;
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

export interface ClassReportMember {
  user_id: string;
  email: string;
  display_name: string | null;
  answered: number;
  correct: number;
  accuracy: number;
  study_time_ms: number;
  exam_sessions: number;
  last_active_at: string | null;
}

export interface ClassReport {
  class_id: string;
  class_name: string;
  window_days: number;
  members: ClassReportMember[];
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

// --- PRD v1.4: papers / paper sessions / wrong book --------------------------

export type QuestionTypeV14 = QuestionType | "essay";
export type PaperStatus = "draft" | "published" | "archived";

export interface PaperListItem {
  id: string;
  name: string;
  description: string | null;
  duration_minutes: number | null;
  total_score: number;
  question_count: number;
  status: PaperStatus;
  domain_number: number | null;
  created_at: string | null;
  attempts: number;
  best_score: number | null;
  max_score: number;
}

export interface PapersResponse {
  items: PaperListItem[];
  total: number;
}

export interface PaperQuestionMeta {
  position: number;
  question_id: string;
  question_type: string;
  score: number;
}

export interface PaperDetail extends PaperListItem {
  type_counts: Record<string, number>;
  questions: PaperQuestionMeta[];
}

export interface PaperSessionSummary {
  id: string;
  kind: "practice" | "exam";
  status: string;
  total_questions: number;
  correct_count: number;
  started_at: string | null;
  ended_at: string | null;
  // PRD v1.6 FR-PAPER-14: attempt-history stats (score/pass only for exams)
  answered: number;
  score: number | null;
  max_score: number | null;
  passed: boolean | null;
  duration_seconds: number | null;
}

export interface PaperSessionsResponse {
  items: PaperSessionSummary[];
}

// PRD v1.5 FR-PAPER-10..12

/** Free-practice bank — a dataset carrying published questions (e.g. OSG v10). */
export interface Bank {
  dataset_slug: string;
  name: string;
  question_count: number;
  languages: string[];
  has_papers: boolean;
}

export interface BanksResponse {
  items: Bank[];
}

/** Resume bundle for the paper player (`GET /api/papers/sessions/{id}/state`). */
export interface PaperSessionState {
  session_id: string;
  kind: "practice" | "exam";
  status: string;
  paper_id: string | null;
  paper_name: string | null;
  total: number;
  answered_positions: number[];
  wrong_positions: number[];
  elapsed_seconds: number | null;
  deadline_at: string | null;
}

/** Resumable entry (`GET /api/papers/sessions/in-progress`). */
export interface InProgressSession {
  session_id: string;
  kind: "practice" | "exam";
  source: "paper" | "bank";
  paper_id: string | null;
  paper_name: string | null;
  dataset_slug: string | null;
  dataset_name: string | null;
  total: number;
  answered: number;
  started_at: string | null;
}

export interface InProgressSessionsResponse {
  items: InProgressSession[];
}

/** `POST /api/papers/sessions/{id}/switch-mode` result. */
export interface SwitchModeResult {
  session_id: string;
  kind: "practice" | "exam";
  paper_id: string | null;
}









export interface ExamReportWrongQuestion {
  question_id: string;
  stem: Localized;
  selected_indexes: number[];
  correct_indexes: number[];
}


export interface ExamReviewOption {
  order_index: number;
  content: Localized;
  is_correct: boolean;
  explanation: Localized;
}


// --- wrong book -------------------------------------------------------------------

export interface WrongBookItem {
  question_id: string;
  question_type: string;
  stem: Localized;
  options: { order_index: number; content: Localized; explanation: Localized }[];
  correct_indexes: number[];
  rationale: Localized;
  reference_answer?: Localized | null;
  wrong_count: number;
  last_wrong_at: string | null;
  is_mastered: boolean;
  is_bookmarked: boolean;
  is_flagged_review: boolean;
  mastery_level: string;
  papers: string[];
}

export interface WrongBookResponse {
  items: WrongBookItem[];
  total: number;
}
