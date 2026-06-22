"use client";

import { create } from "zustand";

export interface AuthUser {
  id: string;
  email: string;
  display_name: string | null;
  roles: string[];
  perms: string[];
}

interface AuthState {
  user: AuthUser | null;
  accessToken: string | null;
  refreshToken: string | null;
  setAuth: (user: AuthUser, access: string, refresh: string) => void;
  clear: () => void;
  hydrate: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  accessToken: null,
  refreshToken: null,
  setAuth: (user, access, refresh) => {
    sessionStorage.setItem("access", access);
    sessionStorage.setItem("refresh", refresh);
    set({ user, accessToken: access, refreshToken: refresh });
  },
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
