"""Optional Google/GitHub sign-in for a closed household app. Deliberately not fastapi-users'
OAuth router: that one can create accounts and match by email, and here a provider identity
may only ever be *linked* to a member who already exists, by that member, while signed in.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from httpx_oauth.clients.github import GitHubOAuth2
from httpx_oauth.clients.google import GoogleOAuth2
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.backend import current_active_user, fastapi_users
from app.auth.tokens import make_token, read_token
from app.config import get_settings
from app.db import get_session
from app.models.oauth import OAuthAccount
from app.models.user import User

router = APIRouter(prefix="/api/auth/oauth", tags=["oauth"])

OAUTH_STATE_AUD = "breidablik:oauth-state"
OAUTH_STATE_LIFETIME_SECONDS = 600
PROFILE_URL = "/profile"

optional_active_user = fastapi_users.current_user(active=True, optional=True)


def get_oauth_clients() -> dict:
    """Only the providers whose id *and* secret are configured. A dependency so tests can
    swap in fakes instead of talking to Google/GitHub.
    """
    settings = get_settings()
    clients = {}
    if settings.google_client_id and settings.google_client_secret:
        clients["google"] = GoogleOAuth2(settings.google_client_id, settings.google_client_secret)
    if settings.github_client_id and settings.github_client_secret:
        clients["github"] = GitHubOAuth2(settings.github_client_id, settings.github_client_secret)
    return clients


def _redirect_uri(request: Request, provider: str) -> str:
    base = get_settings().oauth_redirect_base.rstrip("/") or str(request.base_url).rstrip("/")
    return f"{base}/api/auth/oauth/{provider}/callback"


def _get_client(clients: dict, provider: str):
    client = clients.get(provider)
    if client is None:
        raise HTTPException(status_code=404, detail="OAUTH_PROVIDER_NOT_AVAILABLE")
    return client


async def count_signin_methods(
    session: AsyncSession, user: User, *, excluding_provider: str | None = None
) -> int:
    """How many independent ways the member has to get back in. Used so unlinking (or, later,
    removing a passkey) can't leave an account with none.
    """
    methods = 1 if user.password_login_enabled else 0
    result = await session.execute(select(OAuthAccount.provider).where(OAuthAccount.user_id == user.id))
    methods += sum(1 for provider in result.scalars() if provider != excluding_provider)
    return methods


@router.get("/providers")
async def list_providers(clients: dict = Depends(get_oauth_clients)) -> list[str]:
    return sorted(clients)


@router.get("/accounts")
async def list_linked_accounts(
    user: User = Depends(current_active_user), session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(OAuthAccount).where(OAuthAccount.user_id == user.id).order_by(OAuthAccount.provider)
    )
    return [{"provider": a.provider, "account_email": a.account_email} for a in result.scalars()]


@router.post("/{provider}/link")
async def start_link(
    provider: str,
    request: Request,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
    clients: dict = Depends(get_oauth_clients),
):
    client = _get_client(clients, provider)
    existing = await session.execute(
        select(OAuthAccount).where(OAuthAccount.user_id == user.id, OAuthAccount.provider == provider)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="ALREADY_LINKED")

    state = make_token(
        OAUTH_STATE_AUD, OAUTH_STATE_LIFETIME_SECONDS, purpose="link", provider=provider, user_id=str(user.id)
    )
    url = await client.get_authorization_url(_redirect_uri(request, provider), state=state)
    return {"authorization_url": url}


def _profile_redirect(outcome: str) -> RedirectResponse:
    return RedirectResponse(f"{PROFILE_URL}?oauth={outcome}", status_code=302)


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    request: Request,
    code: str | None = None,
    state: str | None = None,
    user: User | None = Depends(optional_active_user),
    session: AsyncSession = Depends(get_session),
    clients: dict = Depends(get_oauth_clients),
):
    client = _get_client(clients, provider)
    if not code or not state:
        return _profile_redirect("error")
    try:
        claims = read_token(state, OAUTH_STATE_AUD)
    except Exception:
        return _profile_redirect("error")
    if claims.get("provider") != provider:
        return _profile_redirect("error")

    if claims.get("purpose") == "link":
        # The state alone isn't enough: whoever completes the callback must be the very
        # member who started it, in their own session, or a crafted link could attach an
        # attacker's provider identity to someone else's account.
        if user is None or claims.get("user_id") != str(user.id):
            return _profile_redirect("error")
        try:
            token = await client.get_access_token(code, _redirect_uri(request, provider))
            account_id, account_email = await client.get_id_email(token["access_token"])
        except Exception:
            return _profile_redirect("error")

        session.add(
            OAuthAccount(
                user_id=user.id, provider=provider, account_id=str(account_id), account_email=account_email
            )
        )
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return _profile_redirect("error")
        return _profile_redirect("linked")

    return _profile_redirect("error")


@router.delete("/{provider}")
async def unlink(
    provider: str,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(OAuthAccount).where(OAuthAccount.user_id == user.id, OAuthAccount.provider == provider)
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="NOT_LINKED")

    if await count_signin_methods(session, user, excluding_provider=provider) == 0:
        raise HTTPException(status_code=400, detail="LAST_SIGNIN_METHOD")

    await session.delete(account)
    await session.commit()
    return {"ok": True}
