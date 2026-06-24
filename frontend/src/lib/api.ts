import { useAuthStore } from "./auth-store";
import { BACKEND } from "./config";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const { accessToken, refreshToken, setAuth, clear } = useAuthStore.getState();
  const headers = new Headers(init.headers);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  const resp = await fetch(`${BACKEND}${path}`, { ...init, headers, credentials: "include" });
  if (resp.status !== 401) return resp;

  if (!refreshToken) return resp;
  const r = await fetch(`${BACKEND}/api/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
    credentials: "include",
  });
  if (!r.ok) {
    clear();
    return resp;
  }
  const data = await r.json();
  setAuth(data.user, data.access_token, data.refresh_token);
  const retryHeaders = new Headers(init.headers);
  retryHeaders.set("Authorization", `Bearer ${data.access_token}`);
  if (init.body && !retryHeaders.has("Content-Type")) retryHeaders.set("Content-Type", "application/json");
  return fetch(`${BACKEND}${path}`, { ...init, headers: retryHeaders, credentials: "include" });
}

export async function apiJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const resp = await apiFetch(path, init);
  if (!resp.ok) throw new ApiError(resp.status, await resp.text());
  return resp.json() as Promise<T>;
}
