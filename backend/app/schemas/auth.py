from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=255)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    # #9: refresh token now lives in an httpOnly cookie; the body field is a
    # backward-compat fallback for non-browser clients. The route resolves
    # cookie-first, then body.
    refresh_token: str | None = None


class LogoutIn(BaseModel):
    refresh_token: str | None = None
    # #8: the access token to revoke on logout. Optional for backward compat with
    # clients that only send the refresh token (those logouts won't kill the
    # access token early, but it still expires naturally).
    access_token: str | None = None


class ResetPasswordRequestIn(BaseModel):
    email: EmailStr


class ResetPasswordConfirmIn(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str | None
    roles: list[str]
    perms: list[str]
    language_mode: str = "en"
    interface_language: str = "en"


class PreferencesIn(BaseModel):
    language_mode: Literal["en", "zh", "bilingual"] | None = None
    interface_language: Literal["en", "zh"] | None = None


class PreferencesOut(BaseModel):
    language_mode: str
    interface_language: str


class TokenOut(BaseModel):
    access_token: str
    # #9: the refresh token is delivered via an httpOnly cookie, NOT the response
    # body, so an XSS intercepting the login/refresh response can't read it.
    # Kept (nullable) for backward-compat clients that still read the body; the
    # auth routes set it to None.
    refresh_token: str | None = None
    token_type: str = "bearer"
    user: UserOut
