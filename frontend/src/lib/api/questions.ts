"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiJson } from "@/lib/api";
import { qk } from "./keys";
import type {
  QuestionDetail,
  QuestionCreateInput,
  QuestionUpdateInput,
  QuestionListResponse,
  QuestionFilters,
  ReviewAction,
  Feedback,
  FeedbackType,
  Revision,
} from "./types";

function toQuery(filters: QuestionFilters): string {
  const p = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  });
  const s = p.toString();
  return s ? `?${s}` : "";
}

export function useQuestions(filters: QuestionFilters) {
  return useQuery({
    queryKey: qk.questions.list(filters as Record<string, unknown>),
    queryFn: () => apiJson<QuestionListResponse>(`/api/questions${toQuery(filters)}`),
  });
}

export function useQuestionDetail(id: string | null) {
  return useQuery({
    queryKey: qk.questions.detail(id ?? "none"),
    queryFn: () => apiJson<QuestionDetail>(`/api/questions/${id}`),
    enabled: !!id,
  });
}

export function useCreateQuestion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: QuestionCreateInput) =>
      apiJson<QuestionDetail>("/api/questions", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["questions", "list"] }),  // #31
  });
}

export function useUpdateQuestion(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: QuestionUpdateInput) =>
      apiJson<QuestionDetail>(`/api/questions/${id}`, { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: (q) => {
      qc.setQueryData(qk.questions.detail(id), q);
      qc.invalidateQueries({ queryKey: ["questions", "list"] });  // #31: status/difficulty shown in list
    },
  });
}

export function useDeleteQuestion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiJson<{ deleted: string }>(`/api/questions/${id}`, { method: "DELETE" }),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: ["questions", "list"] });  // #31
      qc.removeQueries({ queryKey: qk.questions.detail(id) });
    },
  });
}

export function useReviewQuestion(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { action: ReviewAction; comment?: string }) =>
      apiJson<QuestionDetail>(`/api/questions/${id}/review`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: (q) => {
      qc.setQueryData(qk.questions.detail(id), q);
      qc.invalidateQueries({ queryKey: ["questions", "list"] });  // #31: status changes
    },
  });
}

export function useRevisions(id: string, enabled = true) {
  return useQuery({
    queryKey: qk.questions.revisions(id),
    queryFn: () => apiJson<Revision[]>(`/api/questions/${id}/revisions`),
    enabled,
  });
}

export function useFeedbackList(id: string, enabled = true) {
  return useQuery({
    queryKey: qk.questions.feedback(id),
    queryFn: () => apiJson<Feedback[]>(`/api/questions/${id}/feedback`),
    enabled,
  });
}

export function useCreateFeedback(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { feedback_type: FeedbackType; comment?: string }) =>
      apiJson<Feedback>(`/api/questions/${id}/feedback`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.questions.feedback(id) }),
  });
}
