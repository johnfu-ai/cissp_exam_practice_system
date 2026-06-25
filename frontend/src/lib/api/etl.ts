"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiJson } from "@/lib/api";
import { qk } from "./keys";
import type { EtlDataset, EtlRun } from "./types";

export function useDatasets() {
  return useQuery({
    queryKey: qk.etl.datasets,
    queryFn: () => apiJson<EtlDataset[]>("/api/etl/datasets"),
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
