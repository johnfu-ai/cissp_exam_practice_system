"""Auth HTTP API."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.core.config import settings, _DEV_ENVS
from app.core.security import (
    PasswordResetTokenStore,
    RateLimiter,
    RefreshTokenStore,
    RevokedTokenStore,
    decode_access_token,
)
from app.db.session import get_session
from app.dependencies import (
    CurrentUser,
    get_current_user,
    get_lockout_store,
    get_rate_limiter,
    get_refresh_store,
    get_reset_token_store,
    get_revoked_store,
)
from app.models.auth import User
from app.schemas.auth import (
    LoginIn,
    LogoutIn,
    PasswordChangeIn,
    RefreshIn,
    RegisterIn,
    ResetPasswordConfirmIn,
    ResetPasswordRequestIn,
    TokenOut,
    UserOut,
)
from app.services.auth import (
    AuthError,
    LockoutStore,
    authenticate,
    change_password,
    confirm_password_reset,
    load_user_perms,
    load_user_roles,
    logout,
    refresh_tokens,
    register_user,
    request_password_reset,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "refresh_token"


def _refresh_cookie_params() -> dict:
    """#9: httpOnly refresh-token cookie params.

    - ``httponly`` so JS can't read it (the whole point).
    - ``samesite="lax"``: localhost:3000->8000 and same-eTLD prod are same-site,
      so Lax is sent on fetch/XHR to /api/auth/*; Lax also blocks CSRF on
      cross-site subrequests. Truly cross-site (different eTLD) deployments would
      need SameSite=None; Secure (HTTPS) - out of scope, documented.
    - ``secure`` only in non-dev (HTTPS); dev runs on http://localhost.
    - ``path="/api/auth"`` so the cookie is sent only to auth endpoints.
    - ``max_age`` matches the refresh-token lifetime so it survives restarts.
    """
    return {
        "key": REFRESH_COOKIE_NAME,
        "httponly": True,
        "samesite": "lax",
        "secure": settings.app_env.lower() not in _DEV_ENVS,
        "path": "/api/auth",
        "max_age": settings.refresh_token_expire_days * 86400,
    }


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(value=refresh_token, **_refresh_cookie_params())


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME, path="/api/auth", samesite="lax",
        secure=settings.app_env.lower() not in _DEV_ENVS,
    )


def _resolve_refresh_token(request: Request, body_token: str | None) -> str | None:
    """#9: cookie-first, body-fallback. Returns None when neither is present."""
    cookie_token = request.cookies.get(REFRESH_COOKIE_NAME)
    return cookie_token or body_token


def auth_rate_limit(scope: str):
    """#10: per-IP fixed-window rate limit on unauthenticated auth endpoints.
    Caps credential-stuffing from a single IP (per-email lockout alone never
    trips for password-spray against many accounts)."""
    def _dep(request: Request,
             rate_limiter: RateLimiter = Depends(get_rate_limiter)) -> bool:
        ip = request.client.host if request.client else "unknown"
        if not rate_limiter.allow(
            f"{scope}:{ip}",
            limit=settings.login_rate_limit,
            window_seconds=settings.login_rate_window_seconds,
        ):
            raise HTTPException(status_code=429, detail="too many requests from this IP")
        return True
    return _dep


def _user_out(session, user, org_id) -> UserOut:
    return UserOut(
        id=str(user.id), email=user.email, display_name=user.display_name,
        roles=load_user_roles(session, user.id, org_id),
        perms=load_user_perms(session, user.id, org_id),
        language_mode=getattr(user, "language_mode", "en") or "en",
        interface_language=getattr(user, "interface_language", "en") or "en",
    )


def _extract_user_id(access_token: str) -> uuid.UUID:
    return uuid.UUID(decode_access_token(access_token)["sub"])


def _extract_org_id(access_token: str) -> uuid.UUID:
    return uuid.UUID(decode_access_token(access_token)["org_id"])


@router.post("/register", response_model=TokenOut)
def register(body: RegisterIn, request: Request, response: Response,
             session: Session = Depends(get_session),
             refresh_store: RefreshTokenStore = Depends(get_refresh_store),
             _: bool = Depends(auth_rate_limit("register"))):
    try:
        user, tokens = register_user(session, email=body.email, password=body.password,
                                     display_name=body.display_name, refresh_store=refresh_store)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    session.commit()
    _set_refresh_cookie(response, tokens.refresh_token)  # #9: httpOnly cookie
    return TokenOut(access_token=tokens.access_token, refresh_token=None,
                    user=_user_out(session, user, user.default_organization_id))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, response: Response,
          session: Session = Depends(get_session),
          refresh_store: RefreshTokenStore = Depends(get_refresh_store),
          lockout_store: LockoutStore = Depends(get_lockout_store),
          _: bool = Depends(auth_rate_limit("login"))):
    try:
        user, tokens = authenticate(session, email=body.email, password=body.password,
                                    refresh_store=refresh_store, lockout_store=lockout_store)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    session.commit()
    _set_refresh_cookie(response, tokens.refresh_token)  # #9: httpOnly cookie
    return TokenOut(access_token=tokens.access_token, refresh_token=None,
                    user=_user_out(session, user, user.default_organization_id))


@router.post("/refresh", response_model=TokenOut)
def refresh(body: RefreshIn, request: Request, response: Response,
            session: Session = Depends(get_session),
            refresh_store: RefreshTokenStore = Depends(get_refresh_store)):
    refresh_token = _resolve_refresh_token(request, body.refresh_token)
    if not refresh_token:
        raise HTTPException(status_code=401, detail="missing refresh token")
    try:
        tokens = refresh_tokens(session, refresh_store, refresh_token)
    except AuthError as e:
        # bad/expired/reused refresh: clear the cookie so the client stops retrying
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=e.status_code, detail=str(e))
    session.commit()
    _set_refresh_cookie(response, tokens.refresh_token)  # rotate the cookie
    user = session.get(User, _extract_user_id(tokens.access_token))
    return TokenOut(access_token=tokens.access_token, refresh_token=None,
                    user=_user_out(session, user, _extract_org_id(tokens.access_token)))


@router.post("/logout")
def logout_route(body: LogoutIn, request: Request, response: Response,
                 refresh_store: RefreshTokenStore = Depends(get_refresh_store),
                 revoked_store: RevokedTokenStore = Depends(get_revoked_store)):
    refresh_token = _resolve_refresh_token(request, body.refresh_token)
    logout(refresh_store, revoked_store, refresh_token, body.access_token)
    _clear_refresh_cookie(response)  # #9: drop the cookie
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(current: CurrentUser = Depends(get_current_user),
       session: Session = Depends(get_session)):
    return _user_out(session, current.user, current.org_id)


@router.put("/password")
def change_password_route(
    body: PasswordChangeIn,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    try:
        change_password(
            session, user=current.user,
            current_password=body.current_password,
            new_password=body.new_password,
        )
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    session.commit()
    return {"ok": True}


@router.post("/reset-password/request")
def reset_password_request(
    body: ResetPasswordRequestIn,
    session: Session = Depends(get_session),
    reset_store: PasswordResetTokenStore = Depends(get_reset_token_store),
    lockout_store: LockoutStore = Depends(get_lockout_store),
    _: bool = Depends(auth_rate_limit("reset")),
):
    try:
        token = request_password_reset(
            session, email=body.email,
            reset_store=reset_store, lockout_store=lockout_store,
        )
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    session.commit()
    # Always 200 (no email enumeration). The token is returned ONLY in a
    # development/dev/test environment so the flow is testable end-to-end
    # without email infra; a real deployment emails the link (future work).
    resp = {"ok": True}
    if token is not None and settings.app_env.lower() in {"development", "dev", "test"}:
        resp["token"] = token
    return resp


@router.post("/reset-password/confirm")
def reset_password_confirm(
    body: ResetPasswordConfirmIn,
    session: Session = Depends(get_session),
    reset_store: PasswordResetTokenStore = Depends(get_reset_token_store),
):
    try:
        confirm_password_reset(
            session, token=body.token,
            new_password=body.new_password, reset_store=reset_store,
        )
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    session.commit()
    return {"ok": True}
