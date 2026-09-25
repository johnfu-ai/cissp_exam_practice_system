import { beforeEach, describe, expect, it } from "vitest";
import { installWxMock } from "./wx-mock";

let wx;
let api;

beforeEach(() => {
  wx = installWxMock();
  // re-require so module state (refreshing single-flight) resets per test
  for (const key of Object.keys(require.cache)) {
    if (key.includes("/miniprogram/lib/")) delete require.cache[key];
  }
  api = require("../lib/request.js");
});

describe("extractRefreshToken", () => {
  it("parses single and multiple Set-Cookie forms", () => {
    const { extractRefreshToken } = api;
    expect(extractRefreshToken("refresh_token=abc; Path=/api/auth; HttpOnly")).toBe("abc");
    expect(
      extractRefreshToken(["other=1; Path=/", "refresh_token=xyz; Secure"]),
    ).toBe("xyz");
    expect(extractRefreshToken(null)).toBe(null);
    expect(extractRefreshToken("access_token=1")).toBe(null);
  });
});

describe("login", () => {
  it("stores the access token and the cookie-sourced refresh token", async () => {
    wx.__respond({
      statusCode: 200,
      data: { access_token: "A1", user: { email: "e@x" } },
      header: {
        "Set-Cookie": "refresh_token=R1; Path=/api/auth; HttpOnly; SameSite=lax",
      },
    });
    await api.login("e@x", "pw");
    expect(api.getAccessToken()).toBe("A1");
    expect(api.getRefreshToken()).toBe("R1");
    expect(wx.__store.get("cissp_user")).toEqual({ email: "e@x" });
  });
});

describe("request auth + refresh", () => {
  it("sends the bearer token and passes 2xx through", async () => {
    wx.__store.set("cissp_access", "T1");
    wx.__respond({ statusCode: 200, data: { ok: 1 }, header: {} });
    const res = await api.request("GET", "/api/papers");
    expect(res.data).toEqual({ ok: 1 });
    expect(wx.__calls.request[0].header.Authorization).toBe("Bearer T1");
  });

  it("on 401 refreshes once (single-flight, body refresh_token) and retries", async () => {
    wx.__store.set("cissp_access", "STALE");
    wx.__store.set("cissp_refresh", "R9");
    wx.__respond([
      { statusCode: 401, data: { detail: "expired" }, header: {} },
      {
        statusCode: 200,
        data: { access_token: "NEW" },
        header: { "Set-Cookie": "refresh_token=R10; Path=/api/auth" },
      },
      { statusCode: 200, data: { total: 8 }, header: {} },
    ]);
    const res = await api.request("GET", "/api/wrong-book?tab=wrong");
    expect(res.data).toEqual({ total: 8 });
    expect(api.getAccessToken()).toBe("NEW");
    expect(api.getRefreshToken()).toBe("R10");
    // the refresh call carried the refresh token in the BODY
    expect(wx.__calls.request[1].data).toEqual({ refresh_token: "R9" });
  });

  it("clears the session when refresh is impossible", async () => {
    wx.__store.set("cissp_access", "STALE");
    // no refresh token stored -> 401 -> clear + throw
    wx.__respond({ statusCode: 401, data: {}, header: {} });
    await expect(api.request("GET", "/api/papers")).rejects.toMatchObject({
      status: 401,
    });
    expect(api.isLoggedIn()).toBe(false);
  });

  it("normalizes API errors to {status, detail}", async () => {
    wx.__respond({ statusCode: 422, data: { detail: "bad" }, header: {} });
    await expect(api.request("POST", "/api/x", {})).rejects.toMatchObject({
      status: 422,
      detail: { detail: "bad" },
    });
  });
});
