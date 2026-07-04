"""Auth HTTP API."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    PasswordResetTokenStore,
    RefreshTokenStore,
    RevokedTokenStore,
    decode_access_token,
)
from app.db.session import get_session
from app.dependencies import (
    CurrentUser,
    get_current_user,
    get_lockout_store,
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
def register(body: RegisterIn, session: Session = Depends(get_session),
             refresh_store: RefreshTokenStore = Depends(get_refresh_store)):
    try:
        user, tokens = register_user(session, email=body.email, password=body.password,
                                     display_name=body.display_name, refresh_store=refresh_store)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    session.commit()
    return TokenOut(access_token=tokens.access_token, refresh_token=tokens.refresh_token,
                    user=_user_out(session, user, user.default_organization_id))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, session: Session = Depends(get_session),
          refresh_store: RefreshTokenStore = Depends(get_refresh_store),
          lockout_store: LockoutStore = Depends(get_lockout_store)):
    try:
        user, tokens = authenticate(session, email=body.email, password=body.password,
                                    refresh_store=refresh_store, lockout_store=lockout_store)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    session.commit()
    return TokenOut(access_token=tokens.access_token, refresh_token=tokens.refresh_token,
                    user=_user_out(session, user, user.default_organization_id))


@router.post("/refresh", response_model=TokenOut)
def refresh(body: RefreshIn, session: Session = Depends(get_session),
            refresh_store: RefreshTokenStore = Depends(get_refresh_store)):
    try:
        tokens = refresh_tokens(session, refresh_store, body.refresh_token)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    session.commit()
    user = session.get(User, _extract_user_id(tokens.access_token))
    return TokenOut(access_token=tokens.access_token, refresh_token=tokens.refresh_token,
                    user=_user_out(session, user, _extract_org_id(tokens.access_token)))


@router.post("/logout")
def logout_route(body: LogoutIn,
                 refresh_store: RefreshTokenStore = Depends(get_refresh_store),
                 revoked_store: RevokedTokenStore = Depends(get_revoked_store)):
    logout(refresh_store, revoked_store, body.refresh_token, body.access_token)
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
