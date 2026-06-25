"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiJson } from "../api";
import { qk } from "./keys";
import { useAuthStore } from "../auth-store";
import type { LanguageMode } from "./types";

export interface Preferences {
  language_mode: LanguageMode;
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
