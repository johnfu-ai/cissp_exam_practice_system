import { describe, it, expect, beforeEach } from "vitest";
import { useAuthStore } from "@/lib/auth-store";

beforeEach(() => {
  sessionStorage.clear();
  useAuthStore.setState({ user: null, accessToken: null, refreshToken: null, hydrated: false });
});

describe("auth store", () => {
  it("starts not hydrated", () => {
    expect(useAuthStore.getState().hydrated).toBe(false);
  });

  it("setHydrated flips the flag", () => {
    useAuthStore.getState().setHydrated(true);
    expect(useAuthStore.getState().hydrated).toBe(true);
  });

  it("hydrate() restores tokens from sessionStorage but not the hydrated flag", () => {
    sessionStorage.setItem("access", "a1");
    sessionStorage.setItem("refresh", "r1");
    useAuthStore.getState().hydrate();
    expect(useAuthStore.getState().accessToken).toBe("a1");
    expect(useAuthStore.getState().refreshToken).toBe("r1");
    expect(useAuthStore.getState().hydrated).toBe(false);
  });

  it("setUser stores the user object", () => {
    const u = { id: "1", email: "x@y.z", display_name: null, roles: ["r"], perms: ["practice:read"], language_mode: "en" as const, interface_language: "en" as const };
    useAuthStore.getState().setUser(u);
    expect(useAuthStore.getState().user).toEqual(u);
  });

  it("setAuth round-trips language_mode on the user", () => {
    const u = { id: "1", email: "x@y.z", display_name: null, roles: ["r"], perms: ["practice:read"], language_mode: "zh" as const, interface_language: "en" as const };
    useAuthStore.getState().setAuth(u, "a1", "r1");
    expect(useAuthStore.getState().user?.language_mode).toBe("zh");
  });

  it("setAuth round-trips interface_language on the user", () => {
    const u = { id: "1", email: "x@y.z", display_name: null, roles: ["r"], perms: ["practice:read"], language_mode: "en" as const, interface_language: "zh" as const };
    useAuthStore.getState().setAuth(u, "a1", "r1");
    expect(useAuthStore.getState().user?.interface_language).toBe("zh");
  });
});
