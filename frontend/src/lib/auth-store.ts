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
  // #9: only the short-lived (60-min) access token is held in JS. The long-lived
  // refresh token lives in an httpOnly cookie set by the backend, so it is never
  // readable by JS (not in state, not in sessionStorage).
  accessToken: string | null;
  hydrated: boolean;
  setAuth: (user: AuthUser, access: string) => void;
  setUser: (user: AuthUser) => void;
  setHydrated: (v: boolean) => void;
  clear: () => void;
  hydrate: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  accessToken: null,
  hydrated: false,
  setAuth: (user, access) => {
    sessionStorage.setItem("access", access);
    set({ user, accessToken: access });
  },
  setUser: (user) => set({ user }),
  setHydrated: (v) => set({ hydrated: v }),
  clear: () => {
    sessionStorage.removeItem("access");
    set({ user: null, accessToken: null });
  },
  hydrate: () => {
    const access = sessionStorage.getItem("access");
    if (access) set({ accessToken: access });
  },
}));
