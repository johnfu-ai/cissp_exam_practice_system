"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, apiJson } from "@/lib/api";
import { qk } from "./keys";
import type { EtlDataset, EtlRun } from "./types";

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
