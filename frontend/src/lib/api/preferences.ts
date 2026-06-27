"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiJson } from "../api";
import { qk } from "./keys";
import { useAuthStore } from "../auth-store";
import { writeUiLangCookie } from "@/lib/i18n/cookie";
import type { LanguageCode, LanguageMode } from "./types";

export interface Preferences {
  language_mode: LanguageMode;
  interface_language: LanguageCode;
}

export function usePreferences() {
  return useQuery({
    queryKey: qk.preferences(),
    queryFn: () => apiJson<Preferences>("/api/users/me/preferences"),
  });
}

export function useUpdatePreferences() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (language_mode: LanguageMode) =>
      apiJson<Preferences>("/api/users/me/preferences", {
        method: "PUT",
        body: JSON.stringify({ language_mode }),
      }),
    onSuccess: (data) => {
      qc.setQueryData(qk.preferences(), data);
      qc.invalidateQueries({ queryKey: qk.me() });
      // Sync the auth store so sidebar/UI reflects the new mode instantly.
      const { user, setUser } = useAuthStore.getState();
      if (user) {
        setUser({ ...user, language_mode: data.language_mode });
      }
    },
  });
}

/**
 * Update the UI interface language (en/zh). On success: refresh the
 * preferences + /me cache, sync the auth store, and write the `ui_lang`
 * cookie so the next SSR render is correct. The caller (Settings page) is
 * responsible for calling `setLocale` on the i18n context to switch the
 * active render locale immediately.
 */
export function useUpdateInterfaceLanguage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (interface_language: LanguageCode) =>
      apiJson<Preferences>("/api/users/me/preferences", {
        method: "PUT",
        body: JSON.stringify({ interface_language }),
      }),
    onSuccess: (data) => {
      qc.setQueryData(qk.preferences(), data);
      qc.invalidateQueries({ queryKey: qk.me() });
      const { user, setUser } = useAuthStore.getState();
      if (user) {
        setUser({ ...user, interface_language: data.interface_language });
      }
      writeUiLangCookie(data.interface_language);
    },
  });
}
