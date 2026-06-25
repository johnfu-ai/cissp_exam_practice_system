import type { Subset, OrderMode, SessionCreateInput, LanguageMode } from "@/lib/api/types";

export interface SessionFormState {
  count: number;
  subset: Subset;
  orderMode: OrderMode;
  domainId: string | null;
  bookId: string | null;
  chapterIds: string[];
  questionType: string | null;
  difficulty: number | null;
  tagId: string | null;
  languageMode: LanguageMode | null;
}

export const defaultSessionFormState: SessionFormState = {
  count: 10,
  subset: "all",
  orderMode: "random",
  domainId: null,
  bookId: null,
  chapterIds: [],
  questionType: null,
  difficulty: null,
  tagId: null,
  languageMode: null,
};

export function buildSessionPayload(f: SessionFormState): SessionCreateInput {
  const payload: SessionCreateInput = {
    count: f.count,
    subset: f.subset,
    order_mode: f.orderMode,
  };
  if (f.domainId) payload.domain_id = f.domainId;
  if (f.bookId) payload.book_id = f.bookId;
  if (f.chapterIds.length > 0) payload.chapter_ids = f.chapterIds;
  if (f.questionType) payload.question_type = f.questionType;
  if (f.difficulty != null) payload.difficulty = f.difficulty;
  if (f.tagId) payload.tag_id = f.tagId;
  if (f.languageMode) payload.language_mode = f.languageMode;
  return payload;
}
