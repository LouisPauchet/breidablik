"""Revoking the actual login-session cookie's backing row. Distinct from DeviceTrust (the
PIN quick-login shortcut, revoked separately by app/auth/device_trust.py) — this is the
`AccessToken` row the session cookie itself points at, backing the real password+2FA login.
"""

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import AccessToken


async def revoke_all_access_tokens(
    session: AsyncSession, user_id, except_token: str | None = None
) -> None:
    query = delete(AccessToken).where(AccessToken.user_id == user_id)
    if except_token is not None:
        query = query.where(AccessToken.token != except_token)
    await session.execute(query)
    await session.commit()
