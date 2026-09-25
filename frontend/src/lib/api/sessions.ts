"use client";

// Practice/exam session API hooks shared by the paper player, report, and
// wrong-book flows (PRD v1.4). Types mirror the backend delivery schemas
// (QuestionDeliveryOut / AnswerResultOut / ExamReportOut / ReviewItemOut).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiJson } from "@/lib/api";
import { qk } from "./keys";
import type {
  AnswerResult,
  DomainBreakdown,
  ExamReport,
  ReviewItem,
  Localized,
  OptionDelivery,
  QuestionDelivery,
} from "./types";

// --- delivery ---------------------------------------------------------------

export function usePracticeQuestion(sessionId: string, position: number, enabled = true) {
  return useQuery({
    queryKey: qk.practice.question(sessionId, position),
    queryFn: () =>
      apiJson<QuestionDelivery>(
        `/api/practice/sessions/${sessionId}/questions/${position}`,
      ),
    enabled: enabled && !!sessionId && position >= 0,
    staleTime: 0,
  });
}

export function useExamQuestion(sessionId: string, position: number, enabled = true) {
  return useQuery({
    queryKey: qk.exam.question(sessionId, position),
    queryFn: () =>
      apiJson<QuestionDelivery & { time_remaining_ms: number }>(
        `/api/exam/sessions/${sessionId}/questions/${position}`,
      ),
    enabled: enabled && !!sessionId && position >= 0,
    staleTime: 0,
  });
}

// --- answering ---------------------------------------------------------------

export function useSubmitPracticeAnswer(sessionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      position: number;
      selected?: number[];
      answer_text?: string;
      started_at: string;
    }) =>
      apiJson<AnswerResult>(`/api/practice/sessions/${sessionId}/answers`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: qk.practice.question(sessionId, vars.position) });
    },
  });
}

export function usePracticeSelfAssess(sessionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { position: number; correct: boolean }) =>
      apiJson<{ session_id: string; position: number; is_correct: boolean }>(
        `/api/practice/sessions/${sessionId}/questions/${body.position}/self-assessment`,
        { method: "POST", body: JSON.stringify({ correct: body.correct }) },
      ),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: qk.practice.question(sessionId, vars.position) });
    },
  });
}

export function useSubmitExamAnswer(sessionId: string) {
  return useMutation({
    mutationFn: (body: {
      position: number;
      selected?: number[];
      answer_text?: string;
      started_at: string;
    }) =>
      apiJson<{ position: number; saved: boolean; time_remaining_ms: number; finished?: boolean }>(
        `/api/exam/sessions/${sessionId}/answers`,
        { method: "POST", body: JSON.stringify(body) },
      ),
  });
}

export function useExamSelfAssess(sessionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { position: number; correct: boolean }) =>
      apiJson<{ session_id: string; position: number; is_correct: boolean }>(
        `/api/exam/sessions/${sessionId}/answers/${body.position}/self-assessment`,
        { method: "POST", body: JSON.stringify({ correct: body.correct }) },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.exam.report(sessionId) });
      qc.invalidateQueries({ queryKey: qk.exam.review(sessionId) });
    },
  });
}

// --- finish / report / review -------------------------------------------------

export function useFinishPractice(sessionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiJson<{
        session_id: string;
        total_questions: number;
        answered_count: number;
        correct_count: number;
        accuracy: number;
        total_time_spent_ms: number;
        domains: DomainBreakdown[];
        wrong_questions: { question_id: string; stem: Localized }[];
      }>(`/api/practice/sessions/${sessionId}/finish`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["practice", "session", sessionId] });
    },
  });
}

export function useFinishExam(sessionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiJson<ExamReport>(`/api/exam/sessions/${sessionId}/finish`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.exam.report(sessionId) });
      qc.invalidateQueries({ queryKey: qk.exam.review(sessionId) });
    },
  });
}

export function useExamReport(sessionId: string, enabled = true) {
  return useQuery({
    queryKey: qk.exam.report(sessionId),
    queryFn: () => apiJson<ExamReport>(`/api/exam/sessions/${sessionId}/report`),
    enabled: enabled && !!sessionId,
  });
}

export function useExamReview(sessionId: string, enabled = true) {
  return useQuery({
    queryKey: qk.exam.review(sessionId),
    queryFn: () => apiJson<ReviewItem[]>(`/api/exam/sessions/${sessionId}/review`),
    enabled: enabled && !!sessionId,
  });
}

// --- question state (bookmark / flag / mastered) --------------------------------

export function useSetQuestionState() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      question_id: string;
      is_bookmarked?: boolean;
      is_flagged_review?: boolean;
      is_mastered?: boolean;
    }) =>
      apiJson<Record<string, unknown>>(
        `/api/practice/questions/${body.question_id}/state`,
        {
          method: "PUT",
          body: JSON.stringify({
            is_bookmarked: body.is_bookmarked,
            is_flagged_review: body.is_flagged_review,
            is_mastered: body.is_mastered,
          }),
        },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["wrong-book"] });
    },
  });
}

export type { QuestionDelivery, OptionDelivery, AnswerResult, ReviewItem };
