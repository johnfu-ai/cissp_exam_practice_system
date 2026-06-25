"use client";

import { useQuery } from "@tanstack/react-query";
import { apiJson } from "@/lib/api";
import { qk } from "./keys";
import type {
  DashboardOut,
  DomainMastery,
  TrendOut,
  WeakAreasOut,
  ErrorTypeOut,
  ReviewRecommendation,
  PersonalReport,
} from "./types";

export function useDashboard() {
  return useQuery({
    queryKey: qk.analytics.dashboard,
    queryFn: () => apiJson<DashboardOut>("/api/analytics/dashboard"),
  });
}

export function useDomainMastery() {
  return useQuery({
    queryKey: qk.analytics.domains,
    queryFn: () => apiJson<DomainMastery[]>("/api/analytics/domains"),
  });
}

export function useTrend(windowDays: 30 | 90) {
  return useQuery({
    queryKey: qk.analytics.trend(windowDays),
    queryFn: () => apiJson<TrendOut>(`/api/analytics/trend?window_days=${windowDays}`),
  });
}

export function useWeakAreas() {
  return useQuery({
    queryKey: qk.analytics.weakAreas,
    queryFn: () => apiJson<WeakAreasOut>("/api/analytics/weak-areas"),
  });
}

export function useErrorTypes() {
  return useQuery({
    queryKey: qk.analytics.errorTypes,
    queryFn: () => apiJson<ErrorTypeOut>("/api/analytics/error-types"),
  });
}

export function useRecommendation() {
  return useQuery({
    queryKey: qk.analytics.recommendation,
    queryFn: () => apiJson<ReviewRecommendation>("/api/analytics/recommendation"),
  });
}

export function usePersonalReport() {
  return useQuery({
    queryKey: qk.analytics.report,
    queryFn: () => apiJson<PersonalReport>("/api/analytics/report"),
  });
}
