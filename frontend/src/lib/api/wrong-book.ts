"use client";

// Wrong-book (错题集) API hooks — PRD v1.4 FR-WRONG.

import { useMutation, useQuery } from "@tanstack/react-query";
import { apiJson } from "@/lib/api";
import { qk } from "./keys";
import type { LanguageMode, Localized, WrongBookItem, WrongBookResponse } from "./types";

export type WrongBookTab = "wrong" | "bookmarked" | "flagged";

export function useWrongBook(tab: WrongBookTab, paperId: string | null) {
  return useQuery({
    queryKey: qk.wrongBook.list(tab, paperId ?? "all"),
    queryFn: () =>
      apiJson<WrongBookResponse>(
        `/api/wrong-book?tab=${tab}${paperId ? `&paper_id=${paperId}` : ""}`,
      ),
  });
}

export function useWrongBookPractice() {
  return useMutation({
    mutationFn: (body: { paper_id?: string; count?: number; language_mode?: LanguageMode }) =>
      apiJson<{ id: string; total_questions: number; config: Record<string, unknown> }>(
        "/api/wrong-book/practice",
        { method: "POST", body: JSON.stringify(body) },
      ),
  });
}

export type { WrongBookItem, Localized };
