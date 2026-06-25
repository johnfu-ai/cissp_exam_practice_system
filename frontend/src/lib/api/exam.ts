"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiJson } from "@/lib/api";
import { qk } from "./keys";
import type {
  ExamCreateInput,
  ExamSession,
  ExamQuestionDelivery,
  ExamAnswerInput,
  ExamAnswerAck,
  ExamReport,
  ReviewItem,
  ExamHistoryItem,
} from "./types";

export function useCreateExam() {
  return useMutation({
    mutationFn: (body: ExamCreateInput) =>
      apiJson<ExamSession>("/api/exam/sessions", {
        method: "POST",
        body: JSON.stringify(body),
      }),
  });
}

export function useExamSession(id: string) {
  return useQuery({
    queryKey: qk.exam.session(id),
    queryFn: () => apiJson<ExamSession>(`/api/exam/sessions/${id}`),
  });
}

export function useExamQuestion(id: string, position: number, enabled = true) {
  return useQuery({
    queryKey: qk.exam.question(id, position),
    queryFn: () =>
      apiJson<ExamQuestionDelivery>(`/api/exam/sessions/${id}/questions/${position}`),
    enabled,
  });
}

// CAT-only: adaptively-selected current item.
export function useExamNext(id: string, enabled = true) {
  return useQuery({
    queryKey: qk.exam.next(id),
    queryFn: () => apiJson<ExamQuestionDelivery>(`/api/exam/sessions/${id}/next`),
    enabled,
    staleTime: 0,
    gcTime: 0,
  });
}

export function useSubmitExamAnswer(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ExamAnswerInput) =>
      apiJson<ExamAnswerAck>(`/api/exam/sessions/${id}/answers`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.exam.session(id) }),
  });
}

export function useFinishExam(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiJson<ExamReport>(`/api/exam/sessions/${id}/finish`, { method: "POST" }),
    onSuccess: (report) => {
      qc.setQueryData(qk.exam.report(id), report);
      qc.invalidateQueries({ queryKey: qk.exam.session(id) });
    },
  });
}

export function useExamReport(id: string, enabled = true) {
  return useQuery({
    queryKey: qk.exam.report(id),
    queryFn: () => apiJson<ExamReport>(`/api/exam/sessions/${id}/report`),
    enabled,
  });
}

export function useExamReview(id: string, enabled = true) {
  return useQuery({
    queryKey: qk.exam.review(id),
    queryFn: () => apiJson<ReviewItem[]>(`/api/exam/sessions/${id}/review`),
    enabled,
  });
}

export function useExamHistory() {
  return useQuery({
    queryKey: qk.exam.history,
    queryFn: () => apiJson<ExamHistoryItem[]>("/api/exam/history"),
  });
}
