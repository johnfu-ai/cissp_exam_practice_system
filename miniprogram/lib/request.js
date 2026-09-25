// API client for the CISSP backend (FR-CLIENT-04/07).
//
// - promise wrapper around wx.request with Authorization injection
// - 401 -> single-flight refresh via body refresh_token (mini programs have
//   no cookie jar; the refresh token is parsed from the login/refresh
//   Set-Cookie header and stored locally)
// - errors normalize to { status, detail }

const { getApiBase } = require("./config");
const storage = require("./storage");

let refreshing = null; // single-flight promise (audit P1 #29 pattern)

function rawRequest(options) {
  return new Promise((resolve, reject) => {
    global.wx.request({
      ...options,
      success: resolve,
      fail: reject,
    });
  });
}

/** Pull the refresh_token value out of a Set-Cookie header (array or string). */
function extractRefreshToken(setCookie) {
  if (!setCookie) return null;
  const parts = Array.isArray(setCookie) ? setCookie : [setCookie];
  for (const raw of parts) {
    const m = /(?:^|;\s*)refresh_token=([^;]+)/.exec(String(raw));
    if (m) return m[1];
  }
  return null;
}

function saveSession(body, setCookie) {
  if (body && body.access_token) {
    storage.setItem(storage.KEYS.ACCESS, body.access_token);
  }
  const refresh = extractRefreshToken(setCookie);
  if (refresh) storage.setItem(storage.KEYS.REFRESH, refresh);
}

function clearSession() {
  storage.removeItem(storage.KEYS.ACCESS);
  storage.removeItem(storage.KEYS.REFRESH);
  storage.removeItem(storage.KEYS.USER);
}

async function refreshTokens() {
  const refreshToken = storage.getItem(storage.KEYS.REFRESH);
  if (!refreshToken) throw new Error("no refresh token");
  const res = await rawRequest({
    url: `${getApiBase()}/api/auth/refresh`,
    method: "POST",
    header: { "Content-Type": "application/json" },
    data: { refresh_token: refreshToken },
  });
  if (res.statusCode >= 400) throw new Error("refresh failed");
  saveSession(res.data, res.header && (res.header["Set-Cookie"] || res.header["set-cookie"]));
  return res.data.access_token;
}

/**
 * Authenticated JSON request.
 * @returns {Promise<{status:number, data:object, header:object}>}
 */
async function request(method, path, data, extraHeader) {
  const token = storage.getItem(storage.KEYS.ACCESS);
  const header = { "Content-Type": "application/json", ...(extraHeader || {}) };
  if (token) header.Authorization = `Bearer ${token}`;

  const res = await rawRequest({
    url: `${getApiBase()}${path}`,
    method,
    header,
    data,
  });

  if (res.statusCode === 401) {
    try {
      if (!refreshing) refreshing = refreshTokens().finally(() => {
        refreshing = null;
      });
      await refreshing;
    } catch (e) {
      clearSession();
      throw { status: 401, detail: "session expired" };
    }
    return request(method, path, data, extraHeader);
  }
  if (res.statusCode >= 400) {
    throw { status: res.statusCode, detail: res.data };
  }
  return { status: res.statusCode, data: res.data, header: res.header || {} };
}

async function login(email, password) {
  const res = await rawRequest({
    url: `${getApiBase()}/api/auth/login`,
    method: "POST",
    header: { "Content-Type": "application/json" },
    data: { email, password },
  });
  if (res.statusCode >= 400) {
    throw { status: res.statusCode, detail: res.data };
  }
  saveSession(res.data, res.header && (res.header["Set-Cookie"] || res.header["set-cookie"]));
  if (res.data && res.data.user) {
    storage.setItem(storage.KEYS.USER, res.data.user);
  }
  return res.data;
}

module.exports = {
  request,
  login,
  clearSession,
  extractRefreshToken,
  isLoggedIn: () => !!storage.getItem(storage.KEYS.ACCESS),
  getAccessToken: () => storage.getItem(storage.KEYS.ACCESS),
  getRefreshToken: () => storage.getItem(storage.KEYS.REFRESH),
};
