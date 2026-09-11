"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, apiJson, ApiError } from "@/lib/api";
import { qk } from "./keys";
import type {
  AdminUser,
  AdminClass,
  ClassMember,
  ClassReport,
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

/** FR-ANA-08: per-student cohort report (30/90-day window). */
export function useClassReport(id: string, windowDays: 30 | 90, enabled = true) {
  return useQuery({
    queryKey: qk.admin.classReport(id, windowDays),
    queryFn: () =>
      apiJson<ClassReport>(
        `/api/admin/classes/${id}/report?window_days=${windowDays}`,
      ),
    enabled,
  });
}

async function expectNoContent(path: string, init: RequestInit): Promise<void> {
  const resp = await apiFetch(path, init);
  if (!resp.ok) throw new ApiError(resp.status, await resp.text());
}

export function useAddClassMember() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ classId, userId }: { classId: string; userId: string }) =>
      expectNoContent(`/api/admin/classes/${classId}/members`, {
        method: "POST",
        body: JSON.stringify({ user_id: userId }),
      }),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: qk.admin.classMembers(vars.classId) });
      qc.invalidateQueries({ queryKey: qk.admin.classes });
    },
  });
}

export function useRemoveClassMember() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ classId, userId }: { classId: string; userId: string }) =>
      expectNoContent(`/api/admin/classes/${classId}/members/${userId}`, {
        method: "DELETE",
      }),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: qk.admin.classMembers(vars.classId) });
      qc.invalidateQueries({ queryKey: qk.admin.classes });
    },
  });
}

export function useAdminResetPassword() {
  return useMutation({
    mutationFn: ({ id, newPassword }: { id: string; newPassword?: string }) =>
      apiJson<{ ok: boolean; password?: string }>(`/api/admin/users/${id}/reset-password`, {
        method: "POST",
        body: JSON.stringify(newPassword ? { new_password: newPassword } : {}),
      }),
  });
}

export interface LanguageCoverage {
  total: number;
  en_only: number;
  zh_only: number;
  both: number;
  neither: number;
}

export function useLanguageCoverage(enabled = true) {
  return useQuery({
    queryKey: qk.admin.languageCoverage,
    queryFn: () => apiJson<LanguageCoverage>("/api/admin/questions/language-coverage"),
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
