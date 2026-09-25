"use client";

// Paper (试卷/题库) API hooks — PRD v1.4 FR-PAPER.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiJson } from "@/lib/api";
import { qk } from "./keys";
import type { LanguageMode, PaperDetail, PaperListItem, PapersResponse, PaperSessionsResponse } from "./types";

export type PaperSessionMode = "practice" | "exam";

export interface PaperSessionCreated {
  id: string;
  kind: "practice" | "exam";
  status: string;
  total_questions: number;
  correct_count: number;
  config: Record<string, unknown>;
}

export function usePapers(includeUnpublished = false) {
  return useQuery({
    queryKey: qk.papers.list(includeUnpublished),
    queryFn: () =>
      apiJson<PapersResponse>(
        `/api/papers${includeUnpublished ? "?include_unpublished=true" : ""}`,
      ),
  });
}

export function usePaperDetail(id: string | null) {
  return useQuery({
    queryKey: qk.papers.detail(id ?? "none"),
    queryFn: () => apiJson<PaperDetail>(`/api/papers/${id}`),
    enabled: !!id,
  });
}

export function usePaperSessions(id: string | null) {
  return useQuery({
    queryKey: qk.papers.sessions(id ?? "none"),
    queryFn: () => apiJson<PaperSessionsResponse>(`/api/papers/${id}/sessions`),
    enabled: !!id,
  });
}

export function useCreatePaperSession(paperId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { mode: PaperSessionMode; language_mode?: LanguageMode }) =>
      apiJson<PaperSessionCreated>(`/api/papers/${paperId}/sessions`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["papers"] });
    },
  });
}

export type { PaperListItem, PaperDetail };
