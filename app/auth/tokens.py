"""Short-lived signed tokens for the multi-step login/enrollment flows (pending-2FA, pending
TOTP enrollment). Reuses fastapi-users' own JWT helper rather than adding a new dependency
(e.g. itsdangerous) for what is the same kind of short-lived, purpose-scoped token fastapi-users
already uses internally for password-reset/verification links.
"""

from fastapi_users.jwt import decode_jwt, generate_jwt

from app.config import get_settings


def make_token(audience: str, lifetime_seconds: int, **claims: str) -> str:
    settings = get_settings()
    data = {**claims, "aud": [audience]}
    return generate_jwt(data, settings.secret_key, lifetime_seconds)


def read_token(token: str, audience: str) -> dict:
    settings = get_settings()
    return decode_jwt(token, settings.secret_key, audience=[audience])
