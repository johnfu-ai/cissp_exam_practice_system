"""Password strength policy: length, letter+digit, common-password denylist."""

from __future__ import annotations

import re

# Compact top-breaches denylist (lowercase). Seed/dev passwords that fail this
# must be bumped (see seed default Adminadmin1).
_COMMON = frozenset({
    "password", "password1", "password12", "password123", "1234567890",
    "123456789", "12345678", "qwerty123", "qwertyuiop", "adminadmin",
    "admin12345", "letmein123", "welcome123", "iloveyou12", "abc1234567",
    "monkey1234", "dragon1234", "master1234", "login12345", "princess12",
    "solo123456", "starwars12", "passw0rd12", "football12", "baseball12",
    "trustno12", "whatever12", "sunshine12", "shadow1234", "ashley1234",
    "bailey1234", "access1234", "flower1234", "michael12", "jennifer1",
    "jordan1234", "hunter1234", "computer12", "michelle12", "charlie12",
    "andrew1234", "matthew12", "jessica12", "pepper1234", "1234qwer",
    "1q2w3e4r5t", "zaq12wsx", "qazwsxedc", "pass123456", "changeme12",
    "secret1234", "test123456", "default123", "root123456", "toor123456",
    "administrator", "adminpassword", "p@ssw0rd12", "pass@word1",
    "welcome1", "welcome12", "letmein1", "letmein12", "monkey12",
    "dragon12", "master12", "login12", "abc12345", "abc123456",
    "iloveyou1", "iloveyou123", "trustno1", "sunshine1", "princess1",
    "football1", "baseball1", "shadow12", "superman1", "batman1234",
    "harley1234", "ranger1234", "buster1234", "thomas1234", "robert1234",
    "daniel1234", "hannah1234", "andrea1234", "george1234", "sexy123456",
    "freedom12", "ginger1234", "princess123", "cheese1234", "hockey1234",
    "tigger1234", "orange1234", "mercedes1", "cookie1234", "nathan1234",
    "justin1234", "batman12", "andrew12", "tinkerbell", "joshua1234",
})

_LETTER = re.compile(r"[A-Za-z]")
_DIGIT = re.compile(r"\d")


def validate_password(password: str) -> str:
    """Return password if valid; raise ValueError with a clear message otherwise."""
    if len(password) < 10:
        raise ValueError("password must be at least 10 characters")
    if len(password) > 128:
        raise ValueError("password must be at most 128 characters")
    if not _LETTER.search(password):
        raise ValueError("password must contain at least one letter")
    if not _DIGIT.search(password):
        raise ValueError("password must contain at least one digit")
    if password.lower() in _COMMON:
        raise ValueError("password is too common")
    return password
