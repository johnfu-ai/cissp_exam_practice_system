"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, apiJson } from "@/lib/api";
import { qk } from "./keys";
import type { ChapterDomainMapping, EtlDataset, EtlRun, MappingInput } from "./types";

export function useDatasets() {
  return useQuery({
    queryKey: qk.etl.datasets,
    queryFn: () => apiJson<EtlDataset[]>("/api/etl/datasets"),
  });
}

/** FR-IMP-01 / #35: upload a CSV/XLSX/JSON question file -> preview run.
 * Returns the same EtlRun shape as useCreateRun so the existing commit/rollback
 * UI reuses verbatim. Multipart body - apiFetch skips Content-Type for FormData. */
export function useUploadDataset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ file, datasetSlug }: { file: File; datasetSlug: string }) => {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("dataset_slug", datasetSlug);
      const resp = await apiFetch("/api/etl/upload", { method: "POST", body: fd });
      if (!resp.ok) throw new Error(await resp.text());
      return (await resp.json()) as EtlRun & { dataset_slug: string };
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.etl.datasets }),
  });
}

/** FR-IMP-02: paste Markdown questions → preview run (same shape as upload). */
export function usePasteMarkdown() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { markdown: string; dataset_slug?: string }) =>
      apiJson<EtlRun & { dataset_slug: string }>("/api/etl/paste", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.etl.datasets }),
  });
}

export function useCreateRun() {
  return useMutation({
    mutationFn: (datasetSlug: string) =>
      apiJson<EtlRun>("/api/etl/runs", {
        method: "POST",
        body: JSON.stringify({ dataset_slug: datasetSlug }),
      }),
  });
}

export function useRun(runId: string | null) {
  return useQuery({
    queryKey: qk.etl.run(runId ?? "none"),
    queryFn: () => apiJson<EtlRun>(`/api/etl/runs/${runId}`),
    enabled: !!runId,
  });
}

export function useCommitRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) =>
      apiJson<EtlRun>(`/api/etl/runs/${runId}/commit`, { method: "POST" }),
    onSuccess: (run) => qc.invalidateQueries({ queryKey: qk.etl.run(run.run_id) }),
  });
}

export function useRollbackRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) =>
      apiJson<EtlRun>(`/api/etl/runs/${runId}/rollback`, { method: "POST" }),
    onSuccess: (run) => qc.invalidateQueries({ queryKey: qk.etl.run(run.run_id) }),
  });
}

// --- Chapter→domain mappings (FR-ETL-15) ---

function invalidateMappings(qc: ReturnType<typeof useQueryClient>) {
  return () => qc.invalidateQueries({ queryKey: ["etl", "mappings"] });
}

export function useMappings(datasetSlug?: string | null) {
  const qs =
    datasetSlug && datasetSlug.trim()
      ? `?dataset_slug=${encodeURIComponent(datasetSlug.trim())}`
      : "";
  return useQuery({
    queryKey: qk.etl.mappings(datasetSlug?.trim() || null),
    queryFn: () => apiJson<ChapterDomainMapping[]>(`/api/etl/mappings${qs}`),
  });
}

export function useCreateMapping() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: MappingInput) =>
      apiJson<Pick<ChapterDomainMapping, "id" | "dataset_slug" | "chapter_number">>(
        "/api/etl/mappings",
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: invalidateMappings(qc),
  });
}

export function useUpdateMapping() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: MappingInput }) =>
      apiJson<{ id: string }>(`/api/etl/mappings/${id}`, {
        method: "PUT",
        body: JSON.stringify(body),
      }),
    onSuccess: invalidateMappings(qc),
  });
}

export function useDeleteMapping() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiJson<{ deleted: string }>(`/api/etl/mappings/${id}`, { method: "DELETE" }),
    onSuccess: invalidateMappings(qc),
  });
}
