import uuid

from fastapi import Depends
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import AuthenticationBackend, CookieTransport
from fastapi_users.authentication.strategy.db import AccessTokenDatabase, DatabaseStrategy

from app.auth.users import get_access_token_db, get_user_manager
from app.config import get_settings
from app.models.user import AccessToken, User

SESSION_LIFETIME_SECONDS = 60 * 60 * 24 * 30  # 30 days

settings = get_settings()

cookie_transport = CookieTransport(
    cookie_name="breidablik_session",
    cookie_max_age=SESSION_LIFETIME_SECONDS,
    cookie_secure=settings.cookie_secure,
    cookie_samesite="lax",
)


def get_database_strategy(
    access_token_db: AccessTokenDatabase[AccessToken] = Depends(get_access_token_db),
) -> DatabaseStrategy:
    return DatabaseStrategy(access_token_db, lifetime_seconds=SESSION_LIFETIME_SECONDS)


auth_backend = AuthenticationBackend(
    name="cookie",
    transport=cookie_transport,
    get_strategy=get_database_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

current_active_user = fastapi_users.current_user(active=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)
