"use client";

import { useQuery } from "@tanstack/react-query";
import { apiJson } from "@/lib/api";
import { qk } from "./keys";
import type { Domain, Book, Chapter, Tag } from "./types";

export function useDomains() {
  return useQuery({
    queryKey: qk.domains,
    queryFn: () => apiJson<Domain[]>("/api/domains"),
    staleTime: 5 * 60 * 1000,
  });
}

export function useBooks() {
  return useQuery({
    queryKey: qk.books,
    queryFn: () => apiJson<Book[]>("/api/books"),
    staleTime: 5 * 60 * 1000,
  });
}

export function useChapters(bookId: string | null) {
  return useQuery({
    queryKey: bookId ? qk.chapters(bookId) : ["books", "none", "chapters"],
    queryFn: () => apiJson<Chapter[]>(`/api/books/${bookId}/chapters`),
    enabled: !!bookId,
    staleTime: 5 * 60 * 1000,
  });
}

export function useTags() {
  return useQuery({
    queryKey: qk.tags,
    queryFn: () => apiJson<Tag[]>("/api/tags"),
    staleTime: 5 * 60 * 1000,
  });
}
