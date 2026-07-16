# Move refresh token to httpOnly cookie (#9)

**Date:** 2026-07-16
**Audit item:** Frontend P1 #9 (the remaining half - singleton refresh race already done in #29).
**Branch:** `fix/p1-httponly-cookie`

## Problem

Both access (60-min TTL) and refresh (14-day TTL) tokens live in `sessionStorage` (`auth-store.ts:34-35`), so a single stored XSS exfiltrates the long-lived refresh token. The concurrent-401 refresh race is already fixed (#29 singleton); the remaining work is moving the refresh token out of JS-reachable storage.

## Design

### Backend (`app/api/auth.py`, `app/schemas/auth.py`)

- Set an **httpOnly** `refresh_token` cookie on `/login`, `/register`, `/refresh`; clear it on `/logout`.
  - `httponly=True` (JS can't read it), `samesite="lax"` (localhost:3000→8000 and same-eTLD prod are same-site, so Lax is sent on fetch), `secure=` True only in non-dev (HTTPS), `path="/api/auth"` (only sent to auth endpoints), `max_age=refresh_token_expire_days*86400`.
- `/refresh` and `/logout` resolve the refresh token **cookie-first, body-fallback** (backward compat for non-browser clients + tests). `RefreshIn.refresh_token` and `LogoutIn.refresh_token` become `str | None = None`.
- `TokenOut.refresh_token` becomes `str | None = None`; login/register/refresh return `refresh_token=None` in the body (the token is in the cookie, NOT the body - so an XSS intercepting the login response can't read it).
- CORS already has `allow_credentials=True`.

### Frontend (`lib/auth-store.ts`, `lib/api.ts`, login/register pages)

- `auth-store`: drop `refreshToken` from state + `setAuth` signature (`setAuth(user, access)`); drop sessionStorage for refresh. **Access token stays in memory + sessionStorage** (60-min TTL - acceptable SPA tradeoff; the long-lived credential is the one that had to move). `clear()` stops touching refresh sessionStorage.
- `api.ts`: `refreshOnce()` posts `/api/auth/refresh` with `credentials:"include"` and empty body (cookie sent automatically); no longer reads a refresh token from the store. `apiFetch` 401 path calls `refreshOnce()` with no arg.
- login/register: `setAuth(data.user, data.access_token)` (drop `data.refresh_token`); keep `credentials:"include"` so the cookie lands.

### Tests

- Backend: new tests - login sets an httpOnly `refresh_token` cookie; body `refresh_token` is None; `/refresh` works via cookie alone; `/refresh` body-fallback still works when cookie absent; `/logout` clears the cookie. Update the 3 existing body-`refresh_token` assertions in `test_auth_api.py` to use the TestClient cookie jar (and clear cookies when asserting a specific old token is rejected).
- Frontend: `auth-store` no longer persists/reads refresh; `api.refreshOnce` posts with credentials + empty body (no refresh token read from store).

## Out of scope

- Moving the access token to memory-only with a reload-refresh flow (short-TTL sessionStorage is an acceptable tradeoff; the 14-day refresh token was the XSS prize).
- SameSite=None/Secure for truly cross-site (different-eTLD) deployments - Lax covers localhost dev + same-eTLD prod.
