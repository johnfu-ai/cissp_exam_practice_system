"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiJson } from "@/lib/api";
import { qk } from "./keys";
import type {
  Blueprint,
  BlueprintInput,
  Domain,
  DomainInput,
  Book,
  BookInput,
  Chapter,
  ChapterInput,
  KnowledgePoint,
  KnowledgePointInput,
  Tag,
  TagInput,
} from "./types";

function invalidator(qc: ReturnType<typeof useQueryClient>, keys: readonly (readonly unknown[])[]) {
  return () => keys.forEach((k) => qc.invalidateQueries({ queryKey: k }));
}

// --- Blueprints + domains ---
export function useBlueprints() {
  return useQuery({
    queryKey: qk.blueprints,
    queryFn: () => apiJson<Blueprint[]>("/api/admin/blueprints"),
  });
}

export function useCreateBlueprint() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: BlueprintInput) =>
      apiJson<Blueprint>("/api/admin/blueprints", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: invalidator(qc, [qk.blueprints, qk.domains]),
  });
}

export function useUpdateBlueprint() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<BlueprintInput> }) =>
      apiJson<Blueprint>(`/api/admin/blueprints/${id}`, { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: invalidator(qc, [qk.blueprints]),
  });
}

export function useSetCurrentBlueprint() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiJson<Blueprint>(`/api/admin/blueprints/${id}/set-current`, { method: "POST" }),
    onSuccess: invalidator(qc, [qk.blueprints, qk.domains]),
  });
}

export function useDeleteBlueprint() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiJson(`/api/admin/blueprints/${id}`, { method: "DELETE" }),
    onSuccess: invalidator(qc, [qk.blueprints]),
  });
}

export function useCreateDomain() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ blueprintId, body }: { blueprintId: string; body: DomainInput }) =>
      apiJson<Domain>(`/api/admin/blueprints/${blueprintId}/domains`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: invalidator(qc, [qk.blueprints, qk.domains]),
  });
}

export function useUpdateDomain() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ blueprintId, domainId, body }: { blueprintId: string; domainId: string; body: DomainInput }) =>
      apiJson<Domain>(`/api/admin/blueprints/${blueprintId}/domains/${domainId}`, {
        method: "PUT",
        body: JSON.stringify(body),
      }),
    onSuccess: invalidator(qc, [qk.blueprints, qk.domains]),
  });
}

export function useDeleteDomain() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ blueprintId, domainId }: { blueprintId: string; domainId: string }) =>
      apiJson(`/api/admin/blueprints/${blueprintId}/domains/${domainId}`, { method: "DELETE" }),
    onSuccess: invalidator(qc, [qk.blueprints, qk.domains]),
  });
}

// --- Books + chapters ---
export function useCreateBook() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: BookInput) => apiJson<Book>("/api/books", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: invalidator(qc, [qk.books]),
  });
}

export function useUpdateBook() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: BookInput }) =>
      apiJson<Book>(`/api/books/${id}`, { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: invalidator(qc, [qk.books]),
  });
}

export function useDeleteBook() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiJson(`/api/books/${id}`, { method: "DELETE" }),
    onSuccess: invalidator(qc, [qk.books]),
  });
}

export function useCreateChapter() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ bookId, body }: { bookId: string; body: ChapterInput }) =>
      apiJson<Chapter>(`/api/books/${bookId}/chapters`, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: (_d, v) => qc.invalidateQueries({ queryKey: qk.chapters(v.bookId) }),
  });
}

export function useUpdateChapter() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ bookId, chapterId, body }: { bookId: string; chapterId: string; body: ChapterInput }) =>
      apiJson<Chapter>(`/api/books/${bookId}/chapters/${chapterId}`, { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: (_d, v) => qc.invalidateQueries({ queryKey: qk.chapters(v.bookId) }),
  });
}

export function useDeleteChapter() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ bookId, chapterId }: { bookId: string; chapterId: string }) =>
      apiJson(`/api/books/${bookId}/chapters/${chapterId}`, { method: "DELETE" }),
    onSuccess: (_d, v) => qc.invalidateQueries({ queryKey: qk.chapters(v.bookId) }),
  });
}

// --- Knowledge points ---
export function useKnowledgePoints() {
  return useQuery({
    queryKey: qk.knowledgePoints,
    queryFn: () => apiJson<KnowledgePoint[]>("/api/knowledge-points"),
  });
}

export function useCreateKnowledgePoint() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: KnowledgePointInput) =>
      apiJson<KnowledgePoint>("/api/knowledge-points", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: invalidator(qc, [qk.knowledgePoints]),
  });
}

export function useUpdateKnowledgePoint() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: KnowledgePointInput }) =>
      apiJson<KnowledgePoint>(`/api/knowledge-points/${id}`, { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: invalidator(qc, [qk.knowledgePoints]),
  });
}

export function useDeleteKnowledgePoint() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiJson(`/api/knowledge-points/${id}`, { method: "DELETE" }),
    onSuccess: invalidator(qc, [qk.knowledgePoints]),
  });
}

// --- Tags ---
export function useCreateTag() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: TagInput) => apiJson<Tag>("/api/tags", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: invalidator(qc, [qk.tags]),
  });
}

export function useUpdateTag() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: TagInput }) =>
      apiJson<Tag>(`/api/tags/${id}`, { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: invalidator(qc, [qk.tags]),
  });
}

export function useDeleteTag() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiJson(`/api/tags/${id}`, { method: "DELETE" }),
    onSuccess: invalidator(qc, [qk.tags]),
  });
}
