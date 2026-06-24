"use client";

import { useEffect } from "react";
import { useAuthStore, type AuthUser } from "./auth-store";
import { apiJson } from "./api";

/**
 * Restores auth state on first mount: rehydrates tokens from sessionStorage,
 * and when a token exists but the user object was lost (e.g. page reload),
 * refetches GET /api/auth/me. Flips `hydrated` true once resolved so route
 * guards can render instead of flashing /login.
 */
export function useHydratedAuth() {
  const hydrated = useAuthStore((s) => s.hydrated);

  useEffect(() => {
    if (hydrated) return;
    let cancelled = false;
    const init = async () => {
      const store = useAuthStore.getState();
      store.hydrate();
      const { accessToken, user } = useAuthStore.getState();
      if (accessToken && !user) {
        try {
          const me = await apiJson<AuthUser>("/api/auth/me");
          if (!cancelled) useAuthStore.getState().setUser(me);
        } catch {
          if (!cancelled) useAuthStore.getState().clear();
        }
      }
      if (!cancelled) useAuthStore.getState().setHydrated(true);
    };
    void init();
    return () => {
      cancelled = true;
    };
  }, [hydrated]);

  return useAuthStore();
}
