from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://breidablik:breidablik@localhost:5432/breidablik"
    secret_key: str = "change-me-to-a-long-random-string"
    timezone: str = "Europe/Paris"

    # False only for plain-http local dev — browsers refuse to set a Secure cookie over http.
    cookie_secure: bool = True

    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_claim_email: str = "mailto:admin@example.com"

    cron_secret: str = "change-me-too"
    enable_internal_scheduler: bool = False

    passenger_force_wsgi: bool = False

    frontend_dist_dir: str = "frontend/.output/public"

    # Deliberately outside the deployed code tree by convention (see README) so a Passenger
    # code update never touches uploaded photos — the updater script only overlays code.
    avatar_storage_dir: str = "var/avatars"
    avatar_max_upload_bytes: int = 5 * 1024 * 1024

    # Social sign-in is opt-in: a provider is only offered once both its id and secret are set.
    # It only ever links to an existing member (see app/auth/oauth.py) — never creates one.
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    # Public origin used to build the provider callback URL (e.g. https://home.example.org).
    # Empty means "whatever origin the request came in on", which is wrong behind some proxies.
    oauth_redirect_base: str = ""

    @property
    def zone_info(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


@lru_cache
def get_settings() -> Settings:
    return Settings()
