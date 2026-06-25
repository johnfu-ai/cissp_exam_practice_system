import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { apiJson, ApiError } from "@/lib/api";
import { useAuthStore } from "@/lib/auth-store";

const user = { id: "u1", email: "a@b.c", display_name: null, roles: [], perms: [], language_mode: "en" as const };

beforeEach(() => {
  useAuthStore.setState({ user, accessToken: "stale", refreshToken: "r1" });
});
afterEach(() => {
  vi.restoreAllMocks();
  useAuthStore.setState({ user: null, accessToken: null, refreshToken: null });
});

describe("apiJson silent refresh", () => {
  it("on 401 refreshes once then retries with the new token", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response("nope", { status: 401 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ user, access_token: "fresh", refresh_token: "r2" }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      );

    const data = await apiJson<{ ok: boolean }>("/api/practice/sessions/x");

    expect(data).toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    // second call is the refresh
    expect(String(fetchMock.mock.calls[1][0])).toContain("/api/auth/refresh");
    // third (retry) carries the fresh token
    const retryHeaders = new Headers((fetchMock.mock.calls[2][1] as RequestInit).headers);
    expect(retryHeaders.get("Authorization")).toBe("Bearer fresh");
    expect(useAuthStore.getState().accessToken).toBe("fresh");
  });

  it("throws ApiError with status when a non-401 error response is returned", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      async () => new Response("bad scope", { status: 422 })
    );
    await expect(apiJson("/api/practice/sessions")).rejects.toMatchObject({
      status: 422,
    });
    await expect(apiJson("/api/practice/sessions")).rejects.toBeInstanceOf(ApiError);
  });
});
