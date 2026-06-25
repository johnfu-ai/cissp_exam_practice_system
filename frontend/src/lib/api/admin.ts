"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiJson } from "@/lib/api";
import { qk } from "./keys";
import type {
  AdminUser,
  AdminClass,
  ClassMember,
  CatParamsVersion,
  CatParamsInput,
  QualityDashboard,
  AdminFeedback,
  LowAccuracyQuestion,
  PaginatedAudit,
  ReportSummary,
  UserStatus,
  RoleName,
} from "./types";

// --- Users ---
export function useAdminUsers(search: string, offset = 0) {
  const q = { search, offset };
  return useQuery({
    queryKey: qk.admin.users(q),
    queryFn: () =>
      apiJson<{ items: AdminUser[]; total: number }>(
        `/api/admin/users?${new URLSearchParams({ ...(search ? { search } : {}), offset: String(offset) })}`
      ),
  });
}

export function useSetUserStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: UserStatus }) =>
      apiJson<AdminUser>(`/api/admin/users/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "users"] }),
  });
}

export function useSetUserRoles() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, roleNames }: { id: string; roleNames: RoleName[] }) =>
      apiJson<AdminUser>(`/api/admin/users/${id}/roles`, { method: "PUT", body: JSON.stringify({ role_names: roleNames }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "users"] }),
  });
}

// --- Classes ---
export function useClasses() {
  return useQuery({
    queryKey: qk.admin.classes,
    queryFn: () => apiJson<{ items: AdminClass[]; total: number } | AdminClass[]>("/api/admin/classes"),
  });
}

export function useCreateClass() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; description?: string | null }) =>
      apiJson<AdminClass>("/api/admin/classes", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.admin.classes }),
  });
}

export function useDeleteClass() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiJson(`/api/admin/classes/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.admin.classes }),
  });
}

export function useClassMembers(id: string, enabled = true) {
  return useQuery({
    queryKey: qk.admin.classMembers(id),
    queryFn: () => apiJson<ClassMember[]>(`/api/admin/classes/${id}/members`),
    enabled,
  });
}

// --- CAT params ---
export function useCatParams() {
  return useQuery({
    queryKey: qk.admin.catParams,
    queryFn: () => apiJson<CatParamsVersion[]>("/api/admin/cat-params"),
  });
}

export function useCreateCatParams() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CatParamsInput) =>
      apiJson<CatParamsVersion>("/api/admin/cat-params", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.admin.catParams }),
  });
}

export function useSetCurrentCatParams() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiJson<CatParamsVersion>(`/api/admin/cat-params/${id}/current`, { method: "PUT" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.admin.catParams }),
  });
}

// --- Quality ---
export function useQualityDashboard() {
  return useQuery({
    queryKey: qk.admin.qualityDashboard,
    queryFn: () => apiJson<QualityDashboard>("/api/admin/quality/dashboard"),
  });
}

export function useQualityFeedback(offset = 0) {
  return useQuery({
    queryKey: qk.admin.feedback({ offset }),
    queryFn: () =>
      apiJson<{ items: AdminFeedback[]; total: number }>(`/api/admin/quality/feedback?offset=${offset}`),
  });
}

export function useResolveFeedback() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status, comment }: { id: string; status: "resolved" | "wont_fix"; comment?: string }) =>
      apiJson<AdminFeedback>(`/api/admin/quality/feedback/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ status, comment }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "quality"] });
    },
  });
}

export function useLowAccuracy() {
  return useQuery({
    queryKey: qk.admin.lowAccuracy,
    queryFn: () => apiJson<LowAccuracyQuestion[]>("/api/admin/quality/low-accuracy"),
  });
}

// --- Audit ---
export function useAuditLogs(action: string | null, offset = 0) {
  const q = { action: action ?? "", offset };
  return useQuery({
    queryKey: qk.admin.audit(q),
    queryFn: () =>
      apiJson<PaginatedAudit>(
        `/api/admin/audit-logs?${new URLSearchParams({ ...(action ? { action } : {}), offset: String(offset) })}`
      ),
  });
}

// --- Reports ---
export function useReportSummary(windowDays: 30 | 90) {
  return useQuery({
    queryKey: qk.admin.report(windowDays),
    queryFn: () => apiJson<ReportSummary>(`/api/admin/reports/summary?window_days=${windowDays}`),
  });
}
