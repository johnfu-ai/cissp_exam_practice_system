"""Auth HTTP API."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    RefreshTokenStore,
    decode_access_token,
    hash_password,
)
from app.db.session import get_session
from app.dependencies import CurrentUser, get_current_user, get_lockout_store, get_refresh_store
from app.models.auth import User
from app.models.enums import AuditAction
from app.schemas.auth import (
    LoginIn,
    LogoutIn,
    RefreshIn,
    RegisterIn,
    ResetPasswordIn,
    TokenOut,
    UserOut,
)
from app.services.audit import log_audit
from app.services.auth import (
    AuthError,
    LockoutStore,
    authenticate,
    load_user_perms,
    load_user_roles,
    logout,
    refresh_tokens,
    register_user,
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
                 refresh_store: RefreshTokenStore = Depends(get_refresh_store)):
    logout(refresh_store, body.refresh_token)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(current: CurrentUser = Depends(get_current_user),
       session: Session = Depends(get_session)):
    return _user_out(session, current.user, current.org_id)


@router.post("/reset-password")
def reset_password(body: ResetPasswordIn, session: Session = Depends(get_session),
                   lockout_store: LockoutStore = Depends(get_lockout_store)):
    email = body.email.lower()
    if lockout_store.is_locked(email):
        raise HTTPException(status_code=429, detail="too many attempts; try later")
    user = session.execute(select(User).filter_by(email=email)).scalar_one_or_none()
    if user is None:
        lockout_store.record_failure(email)
        raise HTTPException(status_code=404, detail="not found")
    user.password_hash = hash_password(body.new_password)
    log_audit(session, action=AuditAction.config_change, actor_id=user.id,
              organization_id=user.default_organization_id,
              entity_type="user", entity_id=str(user.id),
              details={"reset": True})
    session.commit()
    return {"ok": True}
