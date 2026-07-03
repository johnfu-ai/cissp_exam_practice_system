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
    refresh_token: str


class LogoutIn(BaseModel):
    refresh_token: str


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
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut
