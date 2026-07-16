import { useAuthStore } from "./auth-store";
import { BACKEND } from "./config";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// Singleton refresh promise: concurrent 401s (e.g. several React Query hooks
// firing on page load) share ONE refresh instead of each firing /api/auth/refresh
// and logging the user out (audit P1 #29 H2). #9: the refresh token is in an
// httpOnly cookie, so this call sends no token in the body - the browser
// attaches the cookie automatically via credentials:"include".
let refreshPromise: Promise<string | null> | null = null;

function refreshOnce(): Promise<string | null> {
  if (refreshPromise) return refreshPromise;
  refreshPromise = (async () => {
    try {
      const r = await fetch(`${BACKEND}/api/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
        credentials: "include",
      });
      if (!r.ok) return null;
      const data = await r.json();
      useAuthStore.getState().setAuth(data.user, data.access_token);
      return data.access_token as string;
    } finally {
      refreshPromise = null;
    }
  })();
  return refreshPromise;
}

function redirectToLogin(): void {
  if (typeof window === "undefined") return;
  // Don't bounce if already on an auth page (avoids a redirect loop).
  const p = window.location.pathname || "";
  if (!p.startsWith("/login") && !p.startsWith("/register") && !p.startsWith("/forgot-password")) {
    window.location.href = "/login";
  }
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const { accessToken, clear } = useAuthStore.getState();
  const headers = new Headers(init.headers);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  const resp = await fetch(`${BACKEND}${path}`, { ...init, headers, credentials: "include" });
  if (resp.status !== 401) return resp;

  // #9: refresh via httpOnly cookie. No refresh token lives in JS state.
  const newAccess = await refreshOnce();
  if (!newAccess) {
    // refresh failed (no cookie / expired / revoked) - clear + send to login so
    // the user isn't stranded on a protected page with every fetch 401-ing
    // (audit P1 #29).
    clear();
    redirectToLogin();
    return resp;
  }
  const retryHeaders = new Headers(init.headers);
  retryHeaders.set("Authorization", `Bearer ${newAccess}`);
  if (init.body && !retryHeaders.has("Content-Type")) retryHeaders.set("Content-Type", "application/json");
  return fetch(`${BACKEND}${path}`, { ...init, headers: retryHeaders, credentials: "include" });
}

export async function apiJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const resp = await apiFetch(path, init);
  if (!resp.ok) throw new ApiError(resp.status, await resp.text());
  return resp.json() as Promise<T>;
}
