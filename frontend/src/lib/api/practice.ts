"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiJson } from "@/lib/api";
import { qk } from "./keys";
import type {
  SessionOut,
  SessionCreateInput,
  QuestionDelivery,
  AnswerInput,
  AnswerResult,
  SessionSummary,
  QuestionStateInput,
  QuestionState,
} from "./types";

export function useSession(id: string) {
  return useQuery({
    queryKey: qk.session(id),
    queryFn: () => apiJson<SessionOut>(`/api/practice/sessions/${id}`),
  });
}

export function useQuestion(sessionId: string, position: number) {
  return useQuery({
    queryKey: qk.question(sessionId, position),
    queryFn: () =>
      apiJson<QuestionDelivery>(`/api/practice/sessions/${sessionId}/questions/${position}`),
  });
}

export function useSessionSummary(id: string, enabled = true) {
  return useQuery({
    queryKey: qk.summary(id),
    queryFn: () => apiJson<SessionSummary>(`/api/practice/sessions/${id}/summary`),
    enabled,
  });
}

export function useCreateSession() {
  return useMutation({
    mutationFn: (body: SessionCreateInput) =>
      apiJson<SessionOut>("/api/practice/sessions", {
        method: "POST",
        body: JSON.stringify(body),
      }),
  });
}

export function useSubmitAnswer(sessionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: AnswerInput) =>
      apiJson<AnswerResult>(`/api/practice/sessions/${sessionId}/answers`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.session(sessionId) });
    },
  });
}

export function usePauseSession(sessionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiJson<SessionOut>(`/api/practice/sessions/${sessionId}/pause`, { method: "POST" }),
    onSuccess: (data) => qc.setQueryData(qk.session(sessionId), data),
  });
}

export function useResumeSession(sessionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiJson<SessionOut>(`/api/practice/sessions/${sessionId}/resume`, { method: "POST" }),
    onSuccess: (data) => qc.setQueryData(qk.session(sessionId), data),
  });
}

export function useFinishSession(sessionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiJson<SessionSummary>(`/api/practice/sessions/${sessionId}/finish`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.session(sessionId) });
      qc.invalidateQueries({ queryKey: qk.summary(sessionId) });
    },
  });
}

export function useUpdateQuestionState() {
  return useMutation({
    mutationFn: ({ questionId, body }: { questionId: string; body: QuestionStateInput }) =>
      apiJson<QuestionState>(`/api/practice/questions/${questionId}/state`, {
        method: "PUT",
        body: JSON.stringify(body),
      }),
  });
}
