from datetime import date
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, EmailStr, Field

from app.core.password_policy import validate_password

StrongPassword = Annotated[str, AfterValidator(validate_password)]


class RegisterIn(BaseModel):
    email: EmailStr
    password: StrongPassword = Field(max_length=128)
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
    new_password: StrongPassword = Field(max_length=128)


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: StrongPassword = Field(max_length=128)


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str | None
    roles: list[str]
    perms: list[str]
    language_mode: str = "en"
    interface_language: str = "en"
    exam_target_date: date | None = None
    daily_goal_answers: int | None = None


class PreferencesIn(BaseModel):
    language_mode: Literal["en", "zh", "bilingual"] | None = None
    interface_language: Literal["en", "zh"] | None = None
    # FR-USER-06 learner goals. A field explicitly sent as null CLEARS the
    # goal; an absent field leaves it unchanged (see model_fields_set use in
    # the route).
    exam_target_date: date | None = None
    daily_goal_answers: int | None = Field(default=None, ge=1, le=500)


class PreferencesOut(BaseModel):
    language_mode: str
    interface_language: str
    exam_target_date: date | None = None
    daily_goal_answers: int | None = None


class TokenOut(BaseModel):
    access_token: str
    # #9: the refresh token is delivered via an httpOnly cookie, NOT the response
    # body, so an XSS intercepting the login/refresh response can't read it.
    # Kept (nullable) for backward-compat clients that still read the body; the
    # auth routes set it to None.
    refresh_token: str | None = None
    token_type: str = "bearer"
    user: UserOut
