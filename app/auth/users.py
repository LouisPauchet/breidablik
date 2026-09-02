import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends
from fastapi_users import BaseUserManager, UUIDIDMixin
from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyAccessTokenDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models.user import AccessToken, User


async def get_user_db(
    session: AsyncSession = Depends(get_session),
) -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    yield SQLAlchemyUserDatabase(session, User)


async def get_access_token_db(
    session: AsyncSession = Depends(get_session),
) -> AsyncGenerator[SQLAlchemyAccessTokenDatabase, None]:
    yield SQLAlchemyAccessTokenDatabase(session, AccessToken)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    def __init__(self, user_db: SQLAlchemyUserDatabase):
        settings = get_settings()
        self.reset_password_token_secret = settings.secret_key
        self.verification_token_secret = settings.secret_key
        super().__init__(user_db)

    async def on_after_update(self, user: User, update_dict: dict, request=None) -> None:
        # A leaked/stolen session cookie shouldn't survive the user changing their password —
        # and neither should a trusted device's PIN shortcut, since it was established under
        # the old credentials. The request making this very change keeps its own session
        # (mirrors the existing "this device stays logged in" behavior for device trust) —
        # only every *other* AccessToken for this user is revoked.
        if "password" in update_dict:
            from app.auth.backend import auth_backend
            from app.auth.device_trust import revoke_all_device_trusts
            from app.auth.sessions import revoke_all_access_tokens

            await revoke_all_device_trusts(self.user_db.session, user.id)
            current_token = request.cookies.get(auth_backend.transport.cookie_name) if request else None
            await revoke_all_access_tokens(self.user_db.session, user.id, except_token=current_token)

    async def on_after_reset_password(self, user: User, request=None) -> None:
        from app.auth.backend import auth_backend
        from app.auth.device_trust import revoke_all_device_trusts
        from app.auth.sessions import revoke_all_access_tokens

        await revoke_all_device_trusts(self.user_db.session, user.id)
        current_token = request.cookies.get(auth_backend.transport.cookie_name) if request else None
        await revoke_all_access_tokens(self.user_db.session, user.id, except_token=current_token)


async def get_user_manager(
    user_db: SQLAlchemyUserDatabase = Depends(get_user_db),
) -> AsyncGenerator[UserManager, None]:
    yield UserManager(user_db)
