from datetime import date, datetime

from app.config import get_settings


def today() -> date:
    """'Today' in the household's configured timezone, not the host server's system
    timezone (typically UTC) — otherwise duty rollover and reminders silently shift by a
    day depending on where the app happens to be deployed.
    """
    return datetime.now(get_settings().zone_info).date()
