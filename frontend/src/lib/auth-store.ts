"use client";

import { create } from "zustand";
import type { LanguageCode, LanguageMode } from "./api/types";

export interface AuthUser {
  id: string;
  email: string;
  display_name: string | null;
  roles: string[];
  perms: string[];
  language_mode: LanguageMode;
  interface_language: LanguageCode;
}

interface AuthState {
  user: AuthUser | null;
  accessToken: string | null;
  refreshToken: string | null;
  hydrated: boolean;
  setAuth: (user: AuthUser, access: string, refresh: string) => void;
  setUser: (user: AuthUser) => void;
  setHydrated: (v: boolean) => void;
  clear: () => void;
  hydrate: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  accessToken: null,
  refreshToken: null,
  hydrated: false,
  setAuth: (user, access, refresh) => {
    sessionStorage.setItem("access", access);
    sessionStorage.setItem("refresh", refresh);
    set({ user, accessToken: access, refreshToken: refresh });
  },
  setUser: (user) => set({ user }),
  setHydrated: (v) => set({ hydrated: v }),
  clear: () => {
    sessionStorage.removeItem("access");
    sessionStorage.removeItem("refresh");
    set({ user: null, accessToken: null, refreshToken: null });
  },
  hydrate: () => {
    const access = sessionStorage.getItem("access");
    const refresh = sessionStorage.getItem("refresh");
    if (access && refresh) set({ accessToken: access, refreshToken: refresh });
  },
}));
