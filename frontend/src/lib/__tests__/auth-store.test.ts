import { describe, it, expect, beforeEach } from "vitest";
import { useAuthStore } from "@/lib/auth-store";

beforeEach(() => {
  sessionStorage.clear();
  useAuthStore.setState({ user: null, accessToken: null, hydrated: false });
});

describe("auth store", () => {
  it("starts not hydrated", () => {
    expect(useAuthStore.getState().hydrated).toBe(false);
  });

  it("setHydrated flips the flag", () => {
    useAuthStore.getState().setHydrated(true);
    expect(useAuthStore.getState().hydrated).toBe(true);
  });

  it("hydrate() restores the access token from sessionStorage but not the hydrated flag", () => {
    // #9: only the access token is persisted; the refresh token is an httpOnly
    // cookie and never lives in JS storage.
    sessionStorage.setItem("access", "a1");
    useAuthStore.getState().hydrate();
    expect(useAuthStore.getState().accessToken).toBe("a1");
    expect(useAuthStore.getState().hydrated).toBe(false);
  });

  it("clear() removes the access token from sessionStorage and state", () => {
    sessionStorage.setItem("access", "a1");
    useAuthStore.getState().setAuth(
      { id: "1", email: "x@y.z", display_name: null, roles: [], perms: [], language_mode: "en", interface_language: "en" },
      "a1",
    );
    useAuthStore.getState().clear();
    expect(useAuthStore.getState().accessToken).toBeNull();
    expect(sessionStorage.getItem("access")).toBeNull();
  });

  it("setUser stores the user object", () => {
    const u = { id: "1", email: "x@y.z", display_name: null, roles: ["r"], perms: ["practice:read"], language_mode: "en" as const, interface_language: "en" as const };
    useAuthStore.getState().setUser(u);
    expect(useAuthStore.getState().user).toEqual(u);
  });

  it("setAuth round-trips language_mode on the user", () => {
    const u = { id: "1", email: "x@y.z", display_name: null, roles: ["r"], perms: ["practice:read"], language_mode: "zh" as const, interface_language: "en" as const };
    useAuthStore.getState().setAuth(u, "a1");
    expect(useAuthStore.getState().user?.language_mode).toBe("zh");
  });

  it("setAuth round-trips interface_language on the user", () => {
    const u = { id: "1", email: "x@y.z", display_name: null, roles: ["r"], perms: ["practice:read"], language_mode: "en" as const, interface_language: "zh" as const };
    useAuthStore.getState().setAuth(u, "a1");
    expect(useAuthStore.getState().user?.interface_language).toBe("zh");
  });
});
